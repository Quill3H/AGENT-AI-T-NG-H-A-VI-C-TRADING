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
  2. funding event at b -> cashflow -qty * open * rate (no_positive drops cashflows > 0);
     a breaker lock from that cashflow closes the position at the same open
  3. b >= fill + 24h -> exit at open (TIME_STOP)
  4. low <= stop -> exit at stop; else high >= target -> exit at target (stop first if both);
     an intrabar exit is known only at the bar close, so it is stamped b + 15m
Every fill and exit pays taker fee and adverse slippage. Funding is never a signal or gate.

Risk (Codex review 2026-10-22, F1): the project CircuitBreakerState and check_all_invariants,
as in the broker and the carry simulator. Entry costs, each funding payment and the exit are
booked as cashflows at their own time (rolling 24h loss, 5% -> 24h lock that closes an open
position at once); only the closed trade's net P&L moves the loss/win streak (3 losses -> risk
x0.5, 3 wins in a row -> x1). Every cashflow also goes to a ledger, and the 15m equity curve is
built from that ledger plus the open position's mark (F3); the run fails if the ledger, the
trades and the final cash disagree (F4). A missing 15m bar or funding settlement fails the run
with DataQualityError before anything is simulated (F2); nothing is filled or assumed zero.
"""
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.risk.circuit_breakers import CircuitBreakerState
from src.risk.invariant_checks import calculate_estimated_liquidation_price, check_all_invariants

HOUR = pd.Timedelta("1h")
QUARTER = pd.Timedelta("15min")
PROJECT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "default_config.yaml"
# BTCUSDT settles funding every 8h in both windows (data_check: no event off this schedule).
# Extra events off the schedule are used as they come; a missing scheduled one fails the run.
FUNDING_SETTLEMENT_HOURS = (0, 8, 16)
BREAKER_LOCK = "CIRCUIT_BREAKER_LOCK"


class DataQualityError(ValueError):
    """A 15m bar or a funding settlement the run needs is missing or unusable."""

DEFAULTS = {
    "shock_atr": 2.0, "atr_bars": 14, "oi_change_max": -0.01, "oi_lag_minutes": 15, "confirm_bars": 2,
    "reclaim": 0.25, "stop_atr": 0.25, "min_rr": 1.5, "cost_gate": 2.0, "cooldown_hours": 24,
    "time_stop_hours": 24, "risk_pct": 0.005, "max_notional_x_equity": 1.0, "taker_pct": 0.0005,
    "slippage_pct": 0.0003, "lot_step": 0.001, "tick": 0.1, "min_notional": 100.0,
    "daily_loss_pct": 0.05, "lock_hours": 24, "entry_delay_bars": 0, "use_oi": True,
    "funding_mode": "actual", "initial_equity": 10000.0,
}


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
    exit_time: pd.Timestamp = None  # when the exit is known: the bar open, or its close if intrabar
    exit_bar: pd.Timestamp = None   # open time of the 15m bar the exit happens in
    exit_price: float = None
    exit_reason: str = None
    price_pnl: float = 0.0
    fees: float = 0.0
    slippage_cost: float = 0.0
    funding: float = 0.0
    funding_skipped_positive: float = 0.0
    net_pnl: float = 0.0
    equity_before: float = 0.0
    risk_multiplier: float = 1.0
    risk_budget: float = 0.0
    liquidation_price: float = None
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
            raise ValueError("lock_hours must be 24: the project circuit breaker locks for 24h")
        if project_config is None:
            project_config = yaml.safe_load(PROJECT_CONFIG.read_text(encoding="utf-8"))
        risk = dict(project_config.get("risk", {}))
        # the stricter of the project cap and v1's 1x notional cap
        risk["max_notional_pct_of_equity"] = min(float(risk.get("max_notional_pct_of_equity", math.inf)),
                                                 float(self.cfg["max_notional_x_equity"]))
        breakers = {**project_config.get("circuit_breakers", {}), "daily_loss_limit_pct": self.cfg["daily_loss_pct"]}
        self.project = {**project_config, "risk": risk, "circuit_breakers": breakers,
                        "fees": {"taker_pct": self.cfg["taker_pct"]}}
        self.b = bars15
        self.h1, self.incomplete_hours = hourly_bars(bars15)
        self.funding_table = funding
        self.funding = funding["funding_rate"] if funding is not None else pd.Series(dtype=float)
        self.oi = oi

    # ------------------------------------------------------------------
    def preflight(self, start, end):
        """Every 15m bar from the first ATR input to the window end, and every scheduled funding
        settlement in the window, must be present and finite. Raises DataQualityError."""
        cfg, problems = self.cfg, []
        first = start - (cfg["atr_bars"] + 2) * HOUR  # 14 TR bars, the bar before them and s
        idx = self.b.index
        if idx.has_duplicates:
            problems.append("duplicate 15m bar times")
        grid = pd.date_range(first, end, freq=QUARTER, inclusive="left")
        missing = grid.difference(idx)
        if len(missing):
            problems.append(f"{len(missing)} of {len(grid)} 15m bars missing in [{first}, {end}), first at {missing[0]}")
        w = self.b[(idx >= first) & (idx < end)]
        off = w.index.difference(grid)
        if len(off):
            problems.append(f"{len(off)} 15m bars off the 15m grid, first at {off[0]}")
        px = w[["open", "high", "low", "close"]].astype(float)
        bad = (~np.isfinite(px).all(axis=1) | (px <= 0).any(axis=1)
               | (px["high"] < px[["open", "close"]].max(axis=1)) | (px["low"] > px[["open", "close"]].min(axis=1)))
        if bad.any():
            problems.append(f"{int(bad.sum())} 15m bars with non-finite or inconsistent OHLC, first at {w.index[bad.to_numpy()][0]}")
        if self.funding_table is None:
            problems.append("no funding table: missing funding is never taken as zero")
        else:
            f = self.funding[(self.funding.index >= start) & (self.funding.index < end)]
            if f.index.has_duplicates:
                problems.append("duplicate funding settlement times")
            rates = pd.to_numeric(f, errors="coerce").astype(float)
            if (~np.isfinite(rates)).any():
                problems.append(f"{int((~np.isfinite(rates)).sum())} non-finite funding rates, first at {f.index[~np.isfinite(rates.to_numpy())][0]}")
            hours = pd.date_range(start.floor("D"), end, freq="h", inclusive="left")
            due = hours[hours.hour.isin(FUNDING_SETTLEMENT_HOURS) & (hours >= start)]
            absent = due.difference(f.index)
            if len(absent):
                problems.append(f"{len(absent)} of {len(due)} funding settlements missing, first at {absent[0]}")
        if problems:
            raise DataQualityError("; ".join(problems))

    def run(self, start, end):
        cfg = self.cfg
        start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
        self.preflight(start, end)
        bars = self.b[(self.b.index >= start) & (self.b.index < end)]
        last_close_time = bars.index[-1] + QUARTER
        shocks = detect(self.h1, self.oi, cfg, start, last_close_time)
        lag = pd.Timedelta(minutes=cfg["oi_lag_minutes"])
        breaker = CircuitBreakerState.from_config(self.project)
        self.ledger = []
        cash = cfg["initial_equity"]
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
            if not breaker.is_trading_allowed(fill_time):
                rejects["BREAKER_LOCK"] = rejects.get("BREAKER_LOCK", 0) + 1
                row["outcome"] = "REJECT_BREAKER_LOCK"
                row["breaker_locked_until"] = breaker.locked_until
                audit.append(row)
                continue
            trade, reason = self._enter(ev, info, cash, breaker)
            if trade is None:
                rejects[reason] = rejects.get(reason, 0) + 1
                row["outcome"] = "REJECT_" + reason
                if reason == "INVARIANT":
                    row["invariant_reasons"] = self._last_invariant_reasons
                audit.append(row)
                continue
            cash = self._hold(trade, breaker, cash, end)
            busy_until = trade.exit_time
            trades.append(trade)
            row["outcome"] = "TRADE_" + trade.exit_reason
            audit.append(row)

        curve_detail = self._equity_curve(bars, trades)
        curve = curve_detail["equity"]
        booked = sum(e["amount"] for e in self.ledger)
        net = sum(tr.net_pnl for tr in trades)
        tolerance = 1e-6 * max(1.0, cfg["initial_equity"])
        if (abs(booked - net) > tolerance or abs(cfg["initial_equity"] + booked - cash) > tolerance
                or abs(float(curve.iloc[-1]) - cash) > tolerance):
            raise AssertionError(f"cashflow ledger does not reconcile: ledger {booked}, trades {net}, "
                                 f"cash {cash}, final equity {float(curve.iloc[-1])}")
        return {"trades": trades, "audit": audit, "layers": layers, "rejects": rejects,
                "missing_oi_event_times": missing_oi, "curve": curve, "curve_detail": curve_detail,
                "cashflows": list(self.ledger), "final_cash": cash, "start": start, "end": end,
                "breaker": {"locks": breaker.lock_count, "risk_multiplier_at_end": breaker.risk_multiplier,
                            "consecutive_losses_at_end": breaker.consecutive_losses}}

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

    def _enter(self, ev, info, cash, breaker):
        cfg = self.cfg
        fill_time = info["fill_time"]
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
        multiplier = breaker.risk_multiplier
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
        order = {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": entry, "stop_loss_price": stop,
                 "leverage": 1.0, "base_risk_percent": cfg["risk_pct"], "risk_percent": cfg["risk_pct"] * multiplier,
                 "conviction_tier": "normal", "position_size_usd": qty * entry, "timestamp": info["signal_at"]}
        account = {"equity": cash, "available_margin": cash, "current_time": fill_time,
                   "circuit_breaker_state": breaker}
        ok, reasons = check_all_invariants(order, account, self.project)
        if not ok:
            self._last_invariant_reasons = reasons
            return None, "INVARIANT"
        trade = Trade(ev["event_id"], fill_time, o, entry, qty, stop, target, equity_before=cash,
                      risk_multiplier=multiplier, risk_budget=budget, gate=gate,
                      liquidation_price=calculate_estimated_liquidation_price("LONG", entry, qty * entry, 1.0, "BTCUSDT",
                                                                              self.project.get("leverage_brackets")))
        return trade, None

    def _book(self, breaker, tr, kind, bar, when, amount, cash, mark, **extra):
        """One cashflow: ledger row, then the breaker's rolling 24h ledger at the time it happens."""
        cash += amount
        self.ledger.append({"time": when, "bar": bar, "event_id": tr.event_id, "kind": kind, "amount": amount,
                            "cash_after": cash, **extra})
        breaker.record_cashflow(amount, when, max(0.0, cash + mark), param_name=kind.lower())
        return cash

    def _hold(self, tr, breaker, cash, end):
        """Hold one trade from its fill to its exit, booking every cashflow; returns the cash after the exit."""
        cfg = self.cfg
        fee, slip = cfg["taker_pct"], cfg["slippage_pct"]
        b = self.b
        later = b[(b.index >= tr.fill_time) & (b.index < end)]
        deadline = tr.fill_time + pd.Timedelta(hours=cfg["time_stop_hours"])
        tr.fees = tr.quantity * tr.entry_price * fee
        tr.slippage_cost = tr.quantity * tr.entry_open * slip
        cash = self._book(breaker, tr, "ENTRY", tr.fill_time, tr.fill_time, -(tr.fees + tr.slippage_cost), cash, 0.0)
        exit_raw = None
        if breaker.is_locked or breaker.is_halted:
            exit_raw, reason, bar_at, at = tr.entry_open, BREAKER_LOCK, tr.fill_time, tr.fill_time
        previous = None
        for when, bar in later.iterrows():
            if exit_raw is not None:
                break
            if previous is not None and when - previous != QUARTER:
                raise DataQualityError(f"15m bar missing after {previous} while a position is open")
            previous = when
            o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])
            if when != tr.fill_time:
                if o <= tr.stop:
                    exit_raw, reason, bar_at, at = o, "STOP_GAP", when, when
                    break
                if o >= tr.target:
                    exit_raw, reason, bar_at, at = o, "TARGET_GAP", when, when
                    break
                if when in self.funding.index:
                    rate = float(self.funding.at[when])
                    flow = -tr.quantity * o * rate
                    mark = tr.quantity * (o - tr.entry_open)
                    if cfg["funding_mode"] == "no_positive" and flow > 0:
                        tr.funding_skipped_positive += flow
                        self.ledger.append({"time": when, "bar": when, "event_id": tr.event_id, "kind": "FUNDING_DROPPED",
                                            "amount": 0.0, "cash_after": cash, "rate": rate, "dropped": flow})
                    else:
                        tr.funding += flow
                        cash = self._book(breaker, tr, "FUNDING", when, when, flow, cash, mark, rate=rate)
                        if breaker.is_locked or breaker.is_halted:
                            exit_raw, reason, bar_at, at = o, BREAKER_LOCK, when, when
                            break
                if when >= deadline:
                    exit_raw, reason, bar_at, at = o, "TIME_STOP", when, when
                    break
            if l <= tr.stop:
                exit_raw, reason, bar_at, at = tr.stop, "STOP", when, when + QUARTER
                break
            if h >= tr.target:
                exit_raw, reason, bar_at, at = tr.target, "TARGET", when, when + QUARTER
                break
        if exit_raw is None:
            last = later.iloc[-1]
            exit_raw, reason, bar_at, at = float(last["close"]), "END_OF_WINDOW", later.index[-1], later.index[-1] + QUARTER
        exit_px = exit_raw * (1 - slip)
        tr.exit_time, tr.exit_bar, tr.exit_price, tr.exit_reason = at, bar_at, exit_px, reason
        tr.price_pnl = tr.quantity * (exit_raw - tr.entry_open)
        exit_slip, exit_fee = tr.quantity * exit_raw * slip, tr.quantity * exit_px * fee
        tr.slippage_cost += exit_slip
        tr.fees += exit_fee
        tr.net_pnl = tr.price_pnl - tr.slippage_cost - tr.fees + tr.funding
        exit_flow = tr.price_pnl - exit_slip - exit_fee
        cash += exit_flow
        self.ledger.append({"time": at, "bar": bar_at, "event_id": tr.event_id, "kind": "EXIT_" + reason,
                            "amount": exit_flow, "cash_after": cash})
        # a forced close by the breaker books its cashflow but is not a strategy win or loss (as in the broker)
        if reason == BREAKER_LOCK:
            breaker.record_cashflow(exit_flow, at, max(0.0, cash), param_name="exit_cashflow")
        else:
            breaker.record_trade_result(tr.net_pnl, at, max(0.0, cash), cashflow=exit_flow)
        return cash

    def _equity_curve(self, bars, trades):
        """Equity at every 15m close: initial equity plus every ledger cashflow booked in that bar or
        earlier, plus the open position marked at the close (no exit costs). Index = bar close."""
        flows = pd.Series(0.0, index=bars.index)
        for e in self.ledger:
            flows[e["bar"]] += e["amount"]
        cash = self.cfg["initial_equity"] + flows.cumsum()
        unrealized = pd.Series(0.0, index=bars.index)
        position = pd.Series(0.0, index=bars.index)
        for tr in trades:
            inside = (bars.index >= tr.fill_time) & (bars.index < tr.exit_bar)
            unrealized[inside] = tr.quantity * (bars["close"][inside] - tr.entry_open)
            position[inside] = tr.quantity
        frame = pd.DataFrame({"bar_open": bars.index, "position_qty": position.to_numpy(), "cash": cash.to_numpy(),
                              "unrealized": unrealized.to_numpy()}, index=pd.DatetimeIndex(bars.index + QUARTER, name="close_time"))
        frame["equity"] = frame["cash"] + frame["unrealized"]
        return frame


def trade_rows(trades):
    rows = []
    for tr in trades:
        d = asdict(tr)
        d.pop("gate")
        d.update({f"gate_{k}": v for k, v in tr.gate.items() if k != "formula"})
        rows.append(d)
    return rows
