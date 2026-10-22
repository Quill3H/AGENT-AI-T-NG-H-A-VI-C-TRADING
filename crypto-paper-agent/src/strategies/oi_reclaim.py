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
  4. low <= stop -> exit at stop; else high >= target -> exit at target (stop first if both)
Every fill and exit pays taker fee and adverse slippage. Funding is never a signal or gate.
"""
import math
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

HOUR = pd.Timedelta("1h")
QUARTER = pd.Timedelta("15min")

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
    def __init__(self, bars15, funding, oi, config=None):
        self.cfg = {**DEFAULTS, **(config or {})}
        if self.cfg["funding_mode"] not in ("actual", "no_positive"):
            raise ValueError("funding_mode must be actual or no_positive")
        self.b = bars15
        self.h1, self.incomplete_hours = hourly_bars(bars15)
        self.funding = funding["funding_rate"] if funding is not None else pd.Series(dtype=float)
        self.oi = oi

    # ------------------------------------------------------------------
    def run(self, start, end):
        cfg = self.cfg
        start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
        bars = self.b[(self.b.index >= start) & (self.b.index < end)]
        if not len(bars):
            raise ValueError("no 15m bars in window")
        last_close_time = bars.index[-1] + QUARTER
        shocks = detect(self.h1, self.oi, cfg, start, last_close_time)
        lag = pd.Timedelta(minutes=cfg["oi_lag_minutes"])
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
        lock_until = None
        day_key, day_start_equity, day_realized = None, cash, 0.0

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
            if lock_until is not None and fill_time < lock_until:
                rejects["BREAKER_LOCK"] = rejects.get("BREAKER_LOCK", 0) + 1
                row["outcome"] = "REJECT_BREAKER_LOCK"
                audit.append(row)
                continue
            trade, reason = self._enter(ev, fill_time, cash)
            if trade is None:
                rejects[reason] = rejects.get(reason, 0) + 1
                row["outcome"] = "REJECT_" + reason
                audit.append(row)
                continue
            self._hold(trade, end, last_close_time)
            cash += trade.net_pnl
            busy_until = trade.exit_time
            trades.append(trade)
            row["outcome"] = "TRADE_" + trade.exit_reason
            audit.append(row)
            # daily-loss breaker on realized P&L (UTC day of the exit)
            key = trade.exit_time.normalize()
            if key != day_key:
                day_key, day_start_equity, day_realized = key, cash - trade.net_pnl, 0.0
            day_realized += trade.net_pnl
            if day_realized <= -cfg["daily_loss_pct"] * day_start_equity:
                lock_until = trade.exit_time + pd.Timedelta(hours=cfg["lock_hours"])

        curve = self._equity_curve(bars, trades)
        return {"trades": trades, "audit": audit, "layers": layers, "rejects": rejects,
                "missing_oi_event_times": missing_oi, "curve": curve, "final_cash": cash,
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

    def _enter(self, ev, fill_time, cash):
        cfg = self.cfg
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
        budget = cfg["risk_pct"] * cash
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
        trade = Trade(ev["event_id"], fill_time, o, entry, qty, stop, target, equity_before=cash,
                      risk_budget=budget, gate=gate)
        trade.fees = qty * entry * fee
        trade.slippage_cost = qty * o * slip
        return trade, None

    def _hold(self, tr, end, last_close_time):
        cfg = self.cfg
        fee, slip = cfg["taker_pct"], cfg["slippage_pct"]
        b = self.b
        later = b[(b.index >= tr.fill_time) & (b.index < end)]
        deadline = tr.fill_time + pd.Timedelta(hours=cfg["time_stop_hours"])
        exit_raw = exit_px = None
        for when, bar in later.iterrows():
            o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
            if when != tr.fill_time:
                if o <= tr.stop:
                    exit_raw, reason, at = o, "STOP_GAP", when
                    break
                if o >= tr.target:
                    exit_raw, reason, at = o, "TARGET_GAP", when
                    break
                if when in self.funding.index:
                    rate = float(self.funding.at[when])
                    flow = -tr.quantity * o * rate
                    if cfg["funding_mode"] == "no_positive" and flow > 0:
                        tr.funding_skipped_positive += flow
                    else:
                        tr.funding += flow
                if when >= deadline:
                    exit_raw, reason, at = o, "TIME_STOP", when
                    break
            if l <= tr.stop:
                exit_raw, reason, at = tr.stop, "STOP", when
                break
            if h >= tr.target:
                exit_raw, reason, at = tr.target, "TARGET", when
                break
        if exit_raw is None:
            last = later.iloc[-1]
            exit_raw, reason, at = float(last["close"]), "END_OF_WINDOW", later.index[-1] + QUARTER
        exit_px = exit_raw * (1 - slip)
        tr.exit_time, tr.exit_price, tr.exit_reason = at, exit_px, reason
        tr.price_pnl = tr.quantity * (exit_raw - tr.entry_open)
        tr.slippage_cost += tr.quantity * exit_raw * slip
        tr.fees += tr.quantity * exit_px * fee
        tr.net_pnl = tr.price_pnl - tr.slippage_cost - tr.fees + tr.funding

    def _equity_curve(self, bars, trades):
        """Cash plus open-position mark (close, no exit costs) at every 15m close."""
        equity = pd.Series(self.cfg["initial_equity"], index=bars.index + QUARTER, dtype=float)
        cash = self.cfg["initial_equity"]
        for tr in trades:
            inside = (equity.index > tr.fill_time) & (equity.index < tr.exit_time)
            marks = bars["close"].reindex(equity.index[inside] - QUARTER).to_numpy()
            entry_cost = tr.quantity * tr.entry_open * self.cfg["slippage_pct"] + tr.quantity * tr.entry_price * self.cfg["taker_pct"]
            equity[inside] = cash - entry_cost + tr.quantity * (marks - tr.entry_open)
            cash += tr.net_pnl
            equity[equity.index >= tr.exit_time] = cash
        return equity


def trade_rows(trades):
    rows = []
    for tr in trades:
        d = asdict(tr)
        d.pop("gate")
        d.update({f"gate_{k}": v for k, v in tr.gate.items() if k != "formula"})
        rows.append(d)
    return rows
