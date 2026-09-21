"""Atomic, fully funded spot-long/perpetual-short basket (ADR 0011)."""

from dataclasses import dataclass, field, asdict
from copy import deepcopy
import math
import pandas as pd
import numpy as np

from src.risk.circuit_breakers import CircuitBreakerState
from src.risk.invariant_checks import check_all_invariants, get_mmr_tier
from src.features.news_calendar import NewsCalendarFilter
from src.logging.trade_logger import snapshot_run_config
from src.research.validation import number, positive_int, time_index, source_time


@dataclass
class FundingArbitrageResult:
    entered: bool = False
    exited: bool = False
    entry_time: object = None
    exit_time: object = None
    quantity: float = 0.0
    spot_notional: float = 0.0
    perp_notional: float = 0.0
    fees_paid: float = 0.0
    funding_cashflow: float = 0.0
    spot_pnl: float = 0.0
    perp_pnl: float = 0.0
    net_pnl: float = 0.0
    max_abs_delta_usd: float = 0.0
    exit_reason: object = None
    cash: float = 0.0
    spot_inventory: float = 0.0
    spot_value: float = 0.0
    perp_collateral: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    equity: float = 0.0
    ledger: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)
    rejections: list = field(default_factory=list)
    accounting_invariants_verified: bool = True

    def to_dict(self):
        return asdict(self)

    def metrics(self):
        return {
            "total_net_pnl": self.net_pnl,
            "final_equity": self.equity,
            "total_trades": int(self.exited),
            "total_fees": self.fees_paid,
            "total_funding_trades": self.funding_cashflow,
            "accounting_invariants_verified": self.accounting_invariants_verified,
        }


class FundingArbitrageSimulator:
    """Each row is an available synchronized quote, not an intrabar fill claim.

    Decision uses observed funding; next quote opens both legs. Settlement uses
    its own rate/readiness/source time. Only one basket per run is admitted.
    All input is validated before creating financial state.
    """

    def __init__(self, config, circuit_breaker=None, news_filter=None):
        self.config = deepcopy(config)
        cfg = config.get("funding_arbitrage", {})
        self.min_apr = number(cfg.get("min_apr", 0.15), "min_apr")
        self.period = positive_int(
            cfg.get("funding_period_hours", 8), "funding_period_hours"
        )
        if 24 % self.period:
            raise ValueError("funding period must divide 24 hours")
        self.negative_cycles = positive_int(
            cfg.get("negative_cycles_to_exit", 2), "negative_cycles_to_exit"
        )
        self.stop_pct = number(
            cfg.get("stop_pct", 0.02), "stop_pct", maximum=1, positive=True
        )
        self.risk_pct = number(
            cfg.get("base_risk_percent", 0.02),
            "base_risk_percent",
            maximum=1,
            positive=True,
        )
        fees = config.get("fees", {})
        self.fee = number(fees.get("taker_pct", 0.0005), "taker_pct", maximum=1)
        self.slip = number(fees.get("slippage_pct", 0.0003), "slippage_pct", maximum=1)
        self.cb = circuit_breaker or CircuitBreakerState.from_config(config)
        self.news = (
            deepcopy(news_filter)
            if news_filter is not None
            else NewsCalendarFilter(config)
        )
        self.persisted_config = snapshot_run_config(config, self.news)
        self.symbol = config.get("data", {}).get("futures_symbol", "BTCUSDT")

    def _validate(self, frame):
        time_index(frame)
        required = {
            "spot_close",
            "perp_close",
            "observed_funding_rate",
            "observed_funding_time",
            "funding_rate",
            "funding_time",
            "funding_readiness",
        }
        if required.difference(frame.columns):
            raise ValueError(
                f"Funding arbitrage requires explicit columns: {sorted(required.difference(frame.columns))}"
            )
        for ts, row in frame.iterrows():
            number(row.spot_close, "spot_close", positive=True)
            number(row.perp_close, "perp_close", positive=True)
            number(
                row.observed_funding_rate,
                "observed_funding_rate",
                minimum=-1,
                maximum=1,
            )
            source_time(row.observed_funding_time, ts, "observed_funding_time")
            if self._settlement(ts):
                if (
                    not isinstance(row.funding_readiness, (bool, np.bool_))
                    or not row.funding_readiness
                ):
                    raise ValueError("funding_readiness must be True at settlement")
                number(row.funding_rate, "funding_rate", minimum=-1, maximum=1)
                source_time(row.funding_time, ts, "funding_time")
        if not frame.empty:
            required_times = pd.date_range(
                frame.index[0].normalize(), frame.index[-1], freq=f"{self.period}h"
            )
            required_times = required_times[required_times >= frame.index[0]]
            if not required_times.isin(frame.index).all():
                raise ValueError("dataset omits settlement schedule boundary")

    def _settlement(self, ts):
        return (
            ts.hour % self.period == 0
            and ts.minute == ts.second == ts.microsecond == ts.nanosecond == 0
        )

    def simulate(self, frame, initial_capital, notional_usd=None, force_close=True):
        capital = number(initial_capital, "initial_capital", positive=True)
        requested = (
            None
            if notional_usd is None
            else number(notional_usd, "notional_usd", positive=True)
        )
        if type(force_close) is not bool:
            raise TypeError("force_close must be boolean")
        self._validate(frame)
        r = FundingArbitrageResult(cash=capital, equity=capital)
        pending = None
        entry_spot = entry_perp = 0.0
        negative = 0
        settled = set()

        def mark(ts, spot, perp):
            if r.spot_inventory:
                r.spot_value = r.quantity * spot
                r.spot_pnl = r.quantity * (spot - entry_spot)
                r.perp_pnl = r.quantity * (entry_perp - perp)
                r.unrealized_pnl = r.spot_pnl + r.perp_pnl
                r.max_abs_delta_usd = max(
                    r.max_abs_delta_usd, abs(r.quantity * (spot - perp))
                )
            else:
                r.spot_value = 0.0
                r.unrealized_pnl = 0.0
            r.equity = (
                r.cash
                + r.spot_value
                + r.perp_collateral
                + (r.perp_pnl if r.spot_inventory else 0.0)
            )
            r.realized_pnl = (
                (r.spot_pnl + r.perp_pnl if r.exited else 0.0)
                + r.funding_cashflow
                - r.fees_paid
            )
            r.net_pnl = r.realized_pnl + r.unrealized_pnl
            if not all(
                math.isfinite(v)
                for v in (r.equity, r.net_pnl, r.cash, r.perp_collateral)
            ):
                raise AssertionError("non-finite basket ledger")
            if abs(capital + r.net_pnl - r.equity) > 1e-7:
                raise AssertionError("basket equity reconciliation failed")
            expected_cash = capital + sum(e["cash_delta"] for e in r.ledger)
            if abs(expected_cash - r.cash) > 1e-7:
                raise AssertionError("basket cash ledger mismatch")

        def unwind(ts, spot, perp, reason):
            exit_spot, exit_perp = spot * (1 - self.slip), perp * (1 + self.slip)
            r.spot_pnl = r.quantity * (exit_spot - entry_spot)
            r.perp_pnl = r.quantity * (entry_perp - exit_perp)
            fee = r.quantity * (exit_spot + exit_perp) * self.fee
            delta = r.quantity * exit_spot + r.perp_collateral + r.perp_pnl - fee
            r.cash += delta
            r.fees_paid += fee
            r.spot_inventory = r.spot_value = r.perp_collateral = 0.0
            r.exited = True
            r.exit_time = ts
            r.exit_reason = reason
            r.ledger.append(
                {
                    "time": ts,
                    "kind": "UNWIND",
                    "cash_delta": delta,
                    "fee": fee,
                    "spot_realized": r.spot_pnl,
                    "perp_realized": r.perp_pnl,
                }
            )
            mark(ts, spot, perp)
            self.cb.record_cashflow(
                r.spot_pnl + r.perp_pnl - fee, ts, max(0.0, r.equity)
            )
            if reason != "CIRCUIT_BREAKER_LOCK":
                self.cb.record_trade_outcome(r.net_pnl, ts)

        for ts, row in frame.iterrows():
            spot, perp = float(row.spot_close), float(row.perp_close)
            self.cb.advance_time(ts)
            mark(ts, spot, perp)
            if r.spot_inventory:
                mmr, cum = get_mmr_tier(
                    r.quantity * perp, self.symbol, self.config.get("leverage_brackets")
                )
                reason = None
                if r.perp_collateral + r.perp_pnl <= r.quantity * perp * mmr - cum:
                    reason = "LIQUIDATION"
                elif spot <= entry_spot * (1 - self.stop_pct) or perp >= entry_perp * (
                    1 + self.stop_pct
                ):
                    reason = "EMERGENCY_STOP"
                elif self.cb.is_locked or self.cb.is_halted:
                    reason = "CIRCUIT_BREAKER_LOCK"
                if reason:
                    unwind(ts, spot, perp, reason)
                elif self._settlement(ts):
                    if ts in settled:
                        raise ValueError("duplicate settlement identity")
                    settled.add(ts)
                    cashflow = r.quantity * perp * float(row.funding_rate)
                    r.perp_collateral += cashflow
                    r.funding_cashflow += cashflow
                    r.ledger.append(
                        {
                            "time": ts,
                            "kind": "FUNDING",
                            "cash_delta": 0.0,
                            "funding": cashflow,
                            "source_time": row.funding_time,
                            "rate": float(row.funding_rate),
                        }
                    )
                    negative = negative + 1 if row.funding_rate < 0 else 0
                    mark(ts, spot, perp)
                    self.cb.record_cashflow(cashflow, ts, max(0.0, r.equity))
                    if self.cb.is_locked or self.cb.is_halted:
                        unwind(ts, spot, perp, "CIRCUIT_BREAKER_LOCK")
                    elif (
                        r.perp_collateral + r.perp_pnl <= r.quantity * perp * mmr - cum
                    ):
                        unwind(ts, spot, perp, "LIQUIDATION")
                    elif negative >= self.negative_cycles:
                        unwind(ts, spot, perp, "NEGATIVE_FUNDING_TWO_CYCLES")
            elif not r.entered and pending is not None:
                es, ep = spot * (1 + self.slip), perp * (1 - self.slip)
                budget = r.equity * self.risk_pct * self.cb.risk_multiplier
                max_q = min(
                    r.cash / ((es + ep) * (1 + self.fee)),
                    budget / ((es + ep) * self.stop_pct),
                )
                q = max_q if requested is None else requested / es
                cost = q * (es + ep) * (1 + self.fee)
                reasons = []
                if cost > r.cash + 1e-8:
                    reasons.append("INSUFFICIENT_BASKET_CAPITAL")
                if q * (es + ep) * self.stop_pct > budget + 1e-8:
                    reasons.append("BASKET_STOP_RISK_EXCEEDED")
                order = {
                    "symbol": self.symbol,
                    "direction": "SHORT",
                    "entry_price": ep,
                    "stop_loss_price": ep * (1 + self.stop_pct),
                    "leverage": 1.0,
                    "base_risk_percent": self.risk_pct,
                    "risk_percent": self.risk_pct * self.cb.risk_multiplier,
                    "conviction_tier": "normal",
                    "position_size_usd": q * ep,
                    "timestamp": pending,
                }
                account = {
                    "equity": r.equity,
                    "available_margin": max(0.0, r.cash - q * es * (1 + self.fee)),
                    "current_time": ts,
                    "circuit_breaker_state": self.cb,
                    "news_filter": self.news,
                }
                ok, gate_reasons = check_all_invariants(order, account, self.config)
                reasons.extend(gate_reasons)
                if not reasons and ok:
                    r.entered = True
                    r.entry_time = ts
                    r.quantity = q
                    entry_spot, entry_perp = es, ep
                    r.spot_notional = q * es
                    r.perp_notional = q * ep
                    r.spot_inventory = q
                    r.perp_collateral = q * ep
                    fee = q * (es + ep) * self.fee
                    r.fees_paid = fee
                    r.cash -= cost
                    r.ledger.append(
                        {
                            "time": ts,
                            "kind": "ENTRY",
                            "cash_delta": -cost,
                            "fee": fee,
                            "spot_purchase": q * es,
                            "perp_collateral": q * ep,
                            "signal_time": pending,
                        }
                    )
                    mark(ts, spot, perp)
                    self.cb.record_cashflow(-fee, ts, max(0.0, r.equity))
                    if self.cb.is_locked:
                        unwind(ts, spot, perp, "CIRCUIT_BREAKER_LOCK")
                else:
                    r.rejections.append({"time": ts, "reasons": reasons})
                pending = None
            if (
                not r.entered
                and float(row.observed_funding_rate) * 365 * 24 / self.period
                >= self.min_apr
            ):
                pending = ts
            mark(ts, spot, perp)
            r.snapshots.append(
                {
                    "timestamp": ts,
                    "cash": r.cash,
                    "spot_value": r.spot_value,
                    "perp_collateral": r.perp_collateral,
                    "unrealized_pnl": r.unrealized_pnl,
                    "equity": r.equity,
                }
            )
        if force_close and r.spot_inventory:
            unwind(frame.index[-1], spot, perp, "FORCE_CLOSE_END_OF_DATA")
            r.snapshots[-1].update(
                cash=r.cash,
                spot_value=0.0,
                perp_collateral=0.0,
                unrealized_pnl=0.0,
                equity=r.equity,
            )
        return r
