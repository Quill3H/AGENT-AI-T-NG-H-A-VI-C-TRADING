"""
src/strategies/oi_reclaim.py
============================
btc_oi_contraction_reclaim_v1 (owner spec 2026-10-22, docs/research/2026-10-22-btc-oi-reclaim-v1.md):
buy BTCUSDT perpetual after a large 1h drop that comes with a fall in open interest (contracts),
once price reclaims part of the drop; target the pre-drop close. Paper only, long or flat, one
position, 1x, one account.

A dedicated event simulator (like the carry basket simulator) because the rules need exact
timing the bar engine does not model: OI availability lag, cancel on a 15m low below the event
low, fill strictly after the signal is available, re-check at the fill open, a cost gate on
rounded sizes, a 24h time stop and a funding account that drops every positive cashflow.

Per 15m bar with open time b while a position is open (fill bar excluded for steps 1-3):
  1. gap through stop or target at the open -> exit at open (price exits precede funding)
  2. funding event at b -> cashflow -qty * open * rate (no_positive drops cashflows > 0)
  3. b >= fill + 24h -> exit at open (TIME_STOP)
  4. low <= stop -> exit at stop; else high >= target -> exit at target (stop first if both).
     Known only when the bar closes, so the exit is stamped b + 15m (intrabar_estimated).
Every fill and exit pays taker fee and adverse slippage. Funding is never a signal or gate.

Risk and accounting (Codex review 2026-10-22, F1-F4): every cashflow (entry cost, funding,
exit) goes to a ledger at its event time and to the project CircuitBreakerState (rolling 24h
loss, 3-loss streak halves risk, 3 wins restore it); a lock closes the open position at the next
open (CIRCUIT_BREAKER_LOCK, not counted in the streak, as in PaperBroker). Entries pass the
project invariants (check_all_invariants). The equity curve is rebuilt from the ledger at every
15m close. A missing 15m bar or a missing/non-finite scheduled funding event in the window
raises DataQualityError instead of producing a result.
"""
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.features.news_calendar import NewsCalendarFilter
from src.risk.circuit_breakers import CircuitBreakerState
from src.risk.invariant_checks import calculate_estimated_liquidation_price, check_all_invariants

HOUR = pd.Timedelta("1h")
QUARTER = pd.Timedelta("15min")

DEFAULTS = {
    "shock_atr": 2.0, "atr_bars": 14, "oi_change_max": -0.01, "oi_lag_minutes": 15, "confirm_bars": 2,
    "reclaim": 0.25, "stop_atr": 0.25, "min_rr": 1.5, "cost_gate": 2.0, "cooldown_hours": 24,
    "time_stop_hours": 24, "risk_pct": 0.005, "max_notional_x_equity": 1.0, "taker_pct": 0.0005,
    "slippage_pct": 0.0003, "lot_step": 0.001, "tick": 0.1, "min_notional": 100.0,
    "daily_loss_pct": 0.05, "lock_hours": 24, "entry_delay_bars": 0, "use_oi": True,
    "funding_mode": "actual", "initial_equity": 10000.0, "funding_hours": (0, 8, 16),
}
PROJECT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "default_config.yaml"


class DataQualityError(ValueError):
    """The data a run needs is incomplete; the run has no scoreable result."""

    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(f"{k}: {v['count']}" for k, v in issues.items()))


def funding_rates(funding):
    if funding is None or "funding_rate" not in funding:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC"))
    return funding["funding_rate"]


def data_issues(bars, funding, start, end, funding_hours=(0, 8, 16)):
    """Problems in the 15m bars and funding a run over [start, end) needs. Empty dict = usable.
    Every 15m open in the window must exist with finite positive OHLC (a missing bar can hide a
    stop), and every scheduled funding time must carry a finite rate (missing is not zero)."""
    issues = {}

    def add(name, times):
        times = list(times)
        if times:
            issues[name] = {"count": len(times), "first": [str(t) for t in times[:5]]}

    grid = pd.date_range(start, end, freq="15min", inclusive="left")
    w = bars[(bars.index >= start) & (bars.index < end)]
    add("missing_15m_bars", grid.difference(w.index))
    px = w[["open", "high", "low", "close"]].to_numpy(dtype=float)
    bad = ~np.isfinite(px).all(axis=1) | (px <= 0).any(axis=1)
    add("bad_ohlc", w.index[bad])
    rates = funding_rates(funding)
    rates = rates[(rates.index >= start) & (rates.index < end)]
    due = grid[np.isin(grid.hour, list(funding_hours)) & (grid.minute == 0)]
    add("missing_funding_events", due.difference(rates.index))
    add("non_finite_funding", rates.index[~np.isfinite(rates.to_numpy(dtype=float))])
    return issues


def hourly_bars(bars15):
    """1h bars from exactly four closed 15m bars (:00 :15 :30 :45); incomplete hours are dropped
    and counted. Index = hour open."""
    hours = bars15.index.floor("h")
    groups = bars15.groupby(hours)
    count = groups["open"].count()
    h1 = pd.DataFrame({"open": groups["open"].first(), "high": groups["high"].max(),
                       "low": groups["low"].min(), "close": groups["close"].last()})
    full = count == 4
    return h1[full], int((~full).sum())


def true_range(h1):
    prev = h1["close"].shift(1)
    return pd.concat([h1["high"] - h1["low"], (h1["high"] - prev).abs(), (h1["low"] - prev).abs()], axis=1).max(axis=1)


def floor_to(x, step):
    return math.floor(x / step + 1e-9) * step


@dataclass
class Trade:
    event_id: str
    fill_time: pd.Timestamp
    entry_open: float
    entry_price: float
    quantity: float
    stop: float
    target: float
    exit_time: pd.Timestamp = None
    exit_price: float = None
    exit_reason: str = None
    price_pnl: float = 0.0
    fees: float = 0.0
    slippage_cost: float = 0.0
    funding: float = 0.0
    funding_skipped_positive: float = 0.0
    net_pnl: float = 0.0
    equity_before: float = 0.0
    risk_budget: float = 0.0
    risk_multiplier: float = 1.0
    liquidation_price: float = None
    exit_bar_open: pd.Timestamp = None
    intrabar_estimated: bool = False
    gate: dict = field(default_factory=dict)


def detect(h1, oi, cfg, start, end):
    """Every complete 1h bar s closing in [start, end] -> shock / OI layers. Returns a DataFrame,
    one row per price shock, with the frozen event levels and OI snapshots."""
    n = cfg["atr_bars"]
    tr = true_range(h1)
    hours = h1.index
    consecutive = hours.to_series().diff().eq(HOUR)
    rows = []
    for i in range(n + 1, len(h1)):
        s_open = hours[i]
        t = s_open + HOUR
        if t < start or t > end:
            continue
        window = consecutive.iloc[i - n:i + 1]
        if not window.all():  # 14 TR bars, the bar before s and s itself must be consecutive hours
            continue
        a = float(tr.iloc[i - n:i].mean())
        c_prev = float(h1["close"].iloc[i - 1])
        close_s, low_s = float(h1["close"].iloc[i]), float(h1["low"].iloc[i])
        if not (math.isfinite(a) and a > 0) or c_prev - close_s < cfg["shock_atr"] * a:
            continue
        oi_now = oi.get(t) if oi is not None else None
        oi_prev = oi.get(t - HOUR) if oi is not None else None
        change = oi_now / oi_prev - 1 if oi_now is not None and oi_prev is not None else None
        rows.append({"event_id": f"BTC-{t:%Y%m%d%H}", "s_open": s_open, "t": t, "c_prev": c_prev,
                     "close_s": close_s, "low_s": low_s, "atr": a, "oi_t": oi_now, "oi_t_1h": oi_prev,
                     "oi_change": change, "i": i})
    return pd.DataFrame(rows)


class Simulator:
    def __init__(self, bars15, funding, oi, config=None, project_config=None):
        self.cfg = {**DEFAULTS, **(config or {})}
        if self.cfg["funding_mode"] not in ("actual", "no_positive"):
            raise ValueError("funding_mode must be actual or no_positive")
        if self.cfg["lock_hours"] != 24:
            raise ValueError("lock_hours is fixed at 24 by the project circuit breaker")
        self.b = bars15
        self.h1, self.incomplete_hours = hourly_bars(bars15)
        self.funding_table = funding
        self.funding = funding_rates(funding)
        self.oi = oi
        project = project_config if project_config is not None else yaml.safe_load(PROJECT_CONFIG.read_text(encoding="utf-8"))
        breaker = dict(project.get("circuit_breakers", {}))
        breaker["daily_loss_limit_pct"] = self.cfg["daily_loss_pct"]
        self.project = {**project, "circuit_breakers": breaker}
        self.news = NewsCalendarFilter(self.project)

    # ------------------------------------------------------------------ ledger
    def _book(self, time, kind, amount, event_id, curve_time):
        """One cashflow. curve_time = the first 15m close at which it is known."""
        self.cash += amount
        self.ledger.append({"time": time, "curve_time": curve_time, "kind": kind, "event_id": event_id,
                            "amount": amount, "cash_after": self.cash})

    # ------------------------------------------------------------------
    def run(self, start, end):
        cfg = self.cfg
        start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
        bars = self.b[(self.b.index >= start) & (self.b.index < end)]
        if not len(bars):
            raise ValueError("no 15m bars in window")
        issues = data_issues(self.b, self.funding_table, start, end, cfg["funding_hours"])
        if issues:
            raise DataQualityError(issues)
        last_close_time = bars.index[-1] + QUARTER
        shocks = detect(self.h1, self.oi, cfg, start, last_close_time)
        lag = pd.Timedelta(minutes=cfg["oi_lag_minutes"])
        self.cash, self.ledger = cfg["initial_equity"], []
        self.cb = CircuitBreakerState.from_config(self.project)
        trades, audit = [], []
        layers = {"complete_1h_bars": int(((self.h1.index + HOUR >= start) & (self.h1.index + HOUR <= last_close_time)).sum()),
                  "incomplete_1h_bars": self.incomplete_hours, "price_shocks": len(shocks), "oi_missing": 0,
                  "oi_not_contracting": 0, "events": 0, "skipped_cooldown": 0, "skipped_position_open": 0,
                  "accepted": 0, "cancelled_low_break": 0, "expired": 0, "window_end": 0, "signals": 0}
        rejects = {}
        missing_oi = []
        cooldown_until = None
        busy_until = None

        for ev in shocks.to_dict("records"):
            row = dict(ev)
            if cfg["use_oi"]:
                if ev["oi_change"] is None or (isinstance(ev["oi_change"], float) and math.isnan(ev["oi_change"])):
                    layers["oi_missing"] += 1
                    missing_oi.append(str(ev["t"]))
                    row["outcome"] = "OI_MISSING"
                    audit.append(row)
                    continue
                if ev["oi_change"] > cfg["oi_change_max"]:
                    layers["oi_not_contracting"] += 1
                    continue
            layers["events"] += 1
            t = ev["t"]
            if busy_until is not None and t < busy_until:
                layers["skipped_position_open"] += 1
                row["outcome"] = "SKIPPED_POSITION_OPEN"
                audit.append(row)
                continue
            if cooldown_until is not None and t <= cooldown_until:
                layers["skipped_cooldown"] += 1
                row["outcome"] = "SKIPPED_COOLDOWN"
                audit.append(row)
                continue
            layers["accepted"] += 1
            cooldown_until = t + pd.Timedelta(hours=cfg["cooldown_hours"])
            available = t + (lag if cfg["use_oi"] else pd.Timedelta(0))
            outcome, info = self._confirm(ev, available, last_close_time)
            row.update(info)
            if outcome != "SIGNAL":
                layers[{"CANCELLED": "cancelled_low_break", "EXPIRED": "expired", "WINDOW_END": "window_end"}[outcome]] += 1
                row["outcome"] = outcome
                audit.append(row)
                continue
            layers["signals"] += 1
            fill_time = info["fill_time"]
            if not self.cb.is_trading_allowed(fill_time):
                rejects["BREAKER_LOCK"] = rejects.get("BREAKER_LOCK", 0) + 1
                row["outcome"] = "REJECT_BREAKER_LOCK"
                audit.append(row)
                continue
            trade, reason = self._enter(ev, fill_time)
            if trade is None:
                rejects[reason] = rejects.get(reason, 0) + 1
                row["outcome"] = "REJECT_" + reason
                audit.append(row)
                continue
            self._hold(trade, end, last_close_time)
            booked = sum(e["amount"] for e in self.ledger if e["event_id"] == trade.event_id)
            if abs(booked - trade.net_pnl) > 1e-6:
                raise AssertionError(f"{trade.event_id}: ledger {booked} != trade net {trade.net_pnl}")
            busy_until = trade.exit_time
            trades.append(trade)
            row["outcome"] = "TRADE_" + trade.exit_reason
            audit.append(row)

        if abs(cfg["initial_equity"] + sum(e["amount"] for e in self.ledger) - self.cash) > 1e-6:
            raise AssertionError("cash does not reconcile with the ledger")
        curve = self._equity_curve(bars, trades)
        return {"trades": trades, "audit": audit, "layers": layers, "rejects": rejects,
                "missing_oi_event_times": missing_oi, "curve": curve, "final_cash": self.cash,
                "ledger": list(self.ledger), "breaker": {"locks": self.cb.lock_count,
                                                         "final_risk_multiplier": self.cb.risk_multiplier},
                "start": start, "end": end}
    # ------------------------------------------------------------------
    def _confirm(self, ev, available, last_close_time):
        cfg, h1, b = self.cfg, self.h1, self.b
        t, low_s = ev["t"], ev["low_s"]
        level = ev["close_s"] + cfg["reclaim"] * (ev["c_prev"] - ev["close_s"])
        info = {"reclaim_level": level, "available": available}
        for k in range(1, cfg["confirm_bars"] + 1):
            close_k = t + k * HOUR
            if close_k > last_close_time:
                return "WINDOW_END", info
            seen = b[(b.index >= t) & (b.index < close_k)]
            if (seen["low"] < low_s).any():
                info["cancel_time"] = seen.index[(seen["low"] < low_s).argmax()]
                return "CANCELLED", info
            if available > close_k:
                continue  # OI not known when this bar closed; never used retroactively
            start_k = close_k - HOUR
            if start_k not in h1.index:
                continue
            bar = h1.loc[start_k]
            if bar["close"] > bar["open"] and bar["close"] >= level:
                signal_at = max(close_k, available)
                after = b.index[b.index > signal_at]
                pos = cfg["entry_delay_bars"]
                if len(after) <= pos or after[pos] + QUARTER > last_close_time:
                    return "WINDOW_END", info
                fill_time = after[pos]
                between = b[(b.index >= close_k) & (b.index < fill_time)]
                if (between["low"] < low_s).any():
                    info["cancel_time"] = between.index[(between["low"] < low_s).argmax()]
                    return "CANCELLED", info
                info.update({"signal_bar_close": close_k, "signal_at": signal_at, "fill_time": fill_time})
                return "SIGNAL", info
        return "EXPIRED", info

    def _enter(self, ev, fill_time):
        cfg = self.cfg
        cash = self.cash
        fee, slip = cfg["taker_pct"], cfg["slippage_pct"]
        o = float(self.b.at[fill_time, "open"])
        level = ev["close_s"] + cfg["reclaim"] * (ev["c_prev"] - ev["close_s"])
        if o < level:
            return None, "BELOW_RECLAIM_AT_OPEN"
        if o <= ev["low_s"]:
            return None, "AT_OR_BELOW_EVENT_LOW"
        stop = floor_to(ev["low_s"] - cfg["stop_atr"] * ev["atr"], cfg["tick"])
        target = floor_to(ev["c_prev"], cfg["tick"])
        entry = o * (1 + slip)
        if not (stop < entry < target):
            return None, "PRICE_ORDER"
        if target - entry < cfg["min_rr"] * (entry - stop):
            return None, "RR"
        multiplier = self.cb.risk_multiplier
        budget = cfg["risk_pct"] * multiplier * cash
        stop_fill = stop * (1 - slip)
        per_unit = (entry - stop_fill) + entry * fee + stop_fill * fee
        qty = budget / per_unit
        qty = min(qty, cfg["max_notional_x_equity"] * cash / entry, cash / (entry * (1 + fee)))
        qty = floor_to(qty, cfg["lot_step"])
        if qty <= 0:
            return None, "LOT"
        if qty * entry < cfg["min_notional"]:
            return None, "MIN_NOTIONAL"
        gross = qty * (target - o)
        cost = qty * (o * slip + entry * fee + target * slip + target * (1 - slip) * fee)
        gate = {"formula": "qty*(T-O) > 2*qty*(O*slip + E*fee + T*slip + T*(1-slip)*fee)",
                "O": o, "E": entry, "S": stop, "T": target, "qty": qty, "gross_to_target": gross,
                "round_trip_cost": cost, "risk_at_stop": qty * per_unit, "budget": budget}
        if gross <= cfg["cost_gate"] * cost:
            return None, "COST_GATE"
        # project hard invariants (risk tier, leverage, notional, margin, liquidation vs stop, breaker)
        order = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": entry, "stop_loss_price": stop,
                 "leverage": 1.0, "base_risk_percent": cfg["risk_pct"], "risk_percent": cfg["risk_pct"] * multiplier,
                 "conviction_tier": "low", "position_size_usd": qty * entry, "timestamp": fill_time}
        account = {"equity": cash, "available_margin": cash, "current_time": fill_time,
                   "circuit_breaker_state": self.cb, "news_filter": self.news}
        ok, reasons = check_all_invariants(order, account, self.project)
        if not ok:
            gate["invariant_reasons"] = reasons
            return None, "INVARIANT"
        trade = Trade(ev["event_id"], fill_time, o, entry, qty, stop, target, equity_before=cash,
                      risk_budget=budget, risk_multiplier=multiplier, gate=gate)
        trade.liquidation_price = calculate_estimated_liquidation_price(
            "LONG", entry, qty * entry, 1.0, "BTCUSDT", self.project.get("leverage_brackets"))
        trade.fees = qty * entry * fee
        trade.slippage_cost = qty * o * slip
        entry_cost = -(trade.fees + trade.slippage_cost)
        self._book(fill_time, "ENTRY", entry_cost, trade.event_id, fill_time + QUARTER)
        self.cb.record_cashflow(entry_cost, fill_time, max(0.0, self.cash), param_name="entry_cost")
        return trade, None

    def _hold(self, tr, end, last_close_time):
        cfg = self.cfg
        fee, slip = cfg["taker_pct"], cfg["slippage_pct"]
        b = self.b
        later = b[(b.index >= tr.fill_time) & (b.index < end)]
        steps = later.index.to_series().diff().dropna()
        if (steps != QUARTER).any():
            raise DataQualityError({"missing_15m_bars": {"count": int((steps != QUARTER).sum()),
                                                         "first": [str(t) for t in steps.index[steps != QUARTER][:5]]}})
        deadline = tr.fill_time + pd.Timedelta(hours=cfg["time_stop_hours"])
        exit_raw = None
        intrabar = False
        for when, bar in later.iterrows():
            o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
            if when == tr.fill_time:
                if self.cb.is_locked or self.cb.is_halted:  # the entry cost itself tripped the breaker
                    exit_raw, reason, at = o, "CIRCUIT_BREAKER_LOCK", when
                    break
            else:
                if o <= tr.liquidation_price:
                    exit_raw, reason, at = tr.liquidation_price, "LIQUIDATION", when
                    break
                if o <= tr.stop:
                    exit_raw, reason, at = o, "STOP_GAP", when
                    break
                if o >= tr.target:
                    exit_raw, reason, at = o, "TARGET_GAP", when
                    break
                if when in self.funding.index:
                    rate = float(self.funding.at[when])
                    if not math.isfinite(rate):
                        raise DataQualityError({"non_finite_funding": {"count": 1, "first": [str(when)]}})
                    flow = -tr.quantity * o * rate
                    if cfg["funding_mode"] == "no_positive" and flow > 0:
                        tr.funding_skipped_positive += flow
                    else:
                        tr.funding += flow
                        self._book(when, "FUNDING", flow, tr.event_id, when + QUARTER)
                        mark = self.cash + tr.quantity * (o - tr.entry_open)
                        self.cb.record_cashflow(flow, when, max(0.0, mark), param_name="funding")
                        if self.cb.is_locked or self.cb.is_halted:
                            exit_raw, reason, at = o, "CIRCUIT_BREAKER_LOCK", when
                            break
                elif when.minute == 0 and when.hour in cfg["funding_hours"]:
                    raise DataQualityError({"missing_funding_events": {"count": 1, "first": [str(when)]}})
                if when >= deadline:
                    exit_raw, reason, at = o, "TIME_STOP", when
                    break
            if l <= tr.stop:
                exit_raw, reason, at, intrabar = tr.stop, "STOP", when + QUARTER, True
                break
            if h >= tr.target:
                exit_raw, reason, at, intrabar = tr.target, "TARGET", when + QUARTER, True
                break
        if exit_raw is None:
            when = later.index[-1]
            exit_raw, reason, at = float(later.iloc[-1]["close"]), "END_OF_WINDOW", when + QUARTER
        exit_px = exit_raw * (1 - slip)
        tr.exit_time, tr.exit_price, tr.exit_reason = at, exit_px, reason
        tr.exit_bar_open, tr.intrabar_estimated = when, intrabar
        tr.price_pnl = tr.quantity * (exit_raw - tr.entry_open)
        exit_slip, exit_fee = tr.quantity * exit_raw * slip, tr.quantity * exit_px * fee
        tr.slippage_cost += exit_slip
        tr.fees += exit_fee
        tr.net_pnl = tr.price_pnl - tr.slippage_cost - tr.fees + tr.funding
        exit_cash = tr.price_pnl - exit_slip - exit_fee
        # stamped at the open for gap / time / breaker exits (known then), at the close otherwise
        self._book(at, "EXIT", exit_cash, tr.event_id, at if at > when else at + QUARTER)
        if reason == "CIRCUIT_BREAKER_LOCK":  # forced close: cashflow only, no streak (PaperBroker rule)
            self.cb.record_cashflow(exit_cash, at, max(0.0, self.cash), param_name="exit_cashflow")
        else:
            self.cb.record_trade_result(pnl=tr.net_pnl, timestamp=at, equity=max(0.0, self.cash), cashflow=exit_cash)

    def _equity_curve(self, bars, trades):
        """Equity at every 15m close: initial equity + every ledger cashflow known by that close
        + the open position marked at the close (no exit costs)."""
        closes = bars.index + QUARTER
        flows = pd.Series([e["amount"] for e in self.ledger], index=pd.DatetimeIndex([e["curve_time"] for e in self.ledger]),
                          dtype=float) if self.ledger else pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC"))
        booked = flows.groupby(level=0).sum().cumsum().reindex(closes, method="ffill").fillna(0.0)
        equity = self.cfg["initial_equity"] + booked
        close_px = pd.Series(bars["close"].to_numpy(dtype=float), index=closes)
        for tr in trades:
            exit_known = next(e["curve_time"] for e in self.ledger if e["event_id"] == tr.event_id and e["kind"] == "EXIT")
            inside = (closes > tr.fill_time) & (closes < exit_known)
            equity[inside] += tr.quantity * (close_px[inside] - tr.entry_open)
        return equity


def trade_rows(trades):
    rows = []
    for tr in trades:
        d = asdict(tr)
        d.pop("gate")
        d.update({f"gate_{k}": v for k, v in tr.gate.items() if k != "formula"})
        rows.append(d)
    return rows
