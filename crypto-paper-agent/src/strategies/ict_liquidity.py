"""
src/strategies/ict_liquidity.py
===============================
Round-19 rules from the r/Daytrading post the owner pasted on 2026-10-23 (two NQ/MNQ
"liquidity" trades: Asia/London lows swept, bullish displacement, a higher-timeframe fair value
gap, then either a 15-minute opening range breakout with a small FVG or a retracement into a
30-minute FVG; the Asia high is the draw on liquidity). Protocol and every number:
docs/research/2026-10-23-round19-ict-sweep-fvg.md.

Translation to crypto perpetuals (disclosed): Asia = 00:00-06:00 UTC and London = 07:00-12:00
UTC of the US Eastern trading day; the New York open is 09:30 ET with daylight saving, so it
falls at 13:30 or 14:30 UTC. Shorts mirror longs. Every rule reads closed bars only, every
entry has a stop, fills are at the next bar open, positions are flat by 16:00 ET, and only
Monday-Friday New York days trade.

A fair value gap (FVG) is three bars where bar 3's low is above bar 1's high (bullish; the gap
is [high1, low3]) or bar 3's high is below bar 1's low (bearish; [high3, low1]).
"""
import datetime as dt

import pandas as pd

from src.strategies.indicator_suite import LONG, SHORT, atr
from src.strategies.session_suite import NEW_YORK, EasternSessionStrategy, eastern_at, eastern_hours

MIN_RISK = 0.003     # skip a stop closer than 0.3% of price (about twice the round-trip cost), as round 17
MIN_GAP = 0.0005     # an FVG must span at least 0.05% of price
HTF_DAYS = 10        # 1h and 4h FVGs formed in the 10 days before the trading day
DISPLACEMENT_ATR = 1.0
ORB_MIN_RR = 1.5     # ORB setup: the Asia-high target must be at least 1.5R away
IRL_RR = 2.0         # IRL -> ERL setup: fixed 2R target


def utc_at(day, hour):
    return pd.Timestamp(dt.datetime(day.year, day.month, day.day, hour), tz="UTC")


def fvgs(bars, bullish):
    """[(bar-1 time, bar-3 time, bottom, top, bar-1 low/high)] of every FVG in `bars`."""
    out = []
    h, l = bars["high"].to_numpy(), bars["low"].to_numpy()
    for i in range(2, len(bars)):
        if bullish and l[i] > h[i - 2]:
            out.append((bars.index[i - 2], bars.index[i], h[i - 2], l[i], l[i - 2]))
        elif not bullish and h[i] < l[i - 2]:
            out.append((bars.index[i - 2], bars.index[i], h[i], l[i - 2], h[i - 2]))
    return [g for g in out if g[3] - g[2] >= MIN_GAP * g[3]]


def closed_resample(bars, rule, until):
    """OHLC bars of `rule` (UTC-aligned) whose whole bucket ends at or before `until`."""
    out = bars.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return out[out.index + pd.Timedelta(rule) <= until]


def live_htf_zones(history, day_start, bullish):
    """1h and 4h FVGs formed in the HTF_DAYS before `day_start` that no later HTF close has
    gone through (below the bottom for bullish, above the top for bearish) by `day_start`."""
    recent = history.loc[day_start - pd.Timedelta(days=HTF_DAYS + 1):day_start - pd.Timedelta(microseconds=1)]
    zones = []
    for rule in ("1h", "4h"):
        bars = closed_resample(recent, rule, day_start)
        bars = bars[bars.index >= day_start - pd.Timedelta(days=HTF_DAYS)]
        for _, third, bottom, top, _ in fvgs(bars, bullish):
            later = bars.loc[bars.index > third, "close"]
            if bullish and (later < bottom).any() or not bullish and (later > top).any():
                continue
            zones.append((bottom, top))
    return zones


class IctLiquidity(EasternSessionStrategy):
    """L1 (`rules.setups: [orb_fvg]`), L2 (`[irl_erl]`) or L3 (both): each setup at most once per
    US Eastern day, after the same pre-New-York context (both lows swept, displacement back
    above them, an HTF FVG tapped and held, the Asia high not yet taken) or its mirror."""

    name = "ICT_LIQUIDITY"
    window = 240

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.setups = tuple(self.rules.get("setups", ["orb_fvg", "irl_erl"]))
        self.per_day = len(self.setups)
        self.bar = pd.Timedelta(minutes=int(self.rules.get("bar_minutes", 5)))
        self.window = int(self.rules.get("window_bars", self.window))
        self.used = set()
        self.history = None
        self.context_day, self.context = None, None

    def on_candle_close(self, candle_4h, history_4h, broker_state):
        self.history = history_4h  # full closed history; the HTF zones are cut from it once a day
        flat = not (getattr(broker_state, "positions", {}) or {}).get(self.symbol)
        now = pd.Timestamp(candle_4h.get("close_time") or history_4h.index[-1] + self.bar).tz_convert(NEW_YORK)
        if flat and (now.weekday() >= 5 or not 9.5 < eastern_hours(now) <= 12.0):
            self.held_bars = 0
            return None  # outside every entry window: skip the window copy (entry would return None)
        return super().on_candle_close(candle_4h, history_4h, broker_state)

    def close_time(self, frame):
        return frame.index[-1] + self.bar

    def should_exit(self, frame, direction):
        return eastern_hours(self.close_time(frame).tz_convert(NEW_YORK)) >= 16.0

    # ------------------------------------------------------------------ context
    def day_context(self, frame, day):
        """{LONG: ctx or None, SHORT: ctx or None}, fixed from bars before the New York open."""
        if self.context_day == day:
            return self.context
        nyopen = eastern_at(day, 9, 30)
        asia = frame.loc[utc_at(day, 0):utc_at(day, 6) - self.bar]
        london = frame.loc[utc_at(day, 7):utc_at(day, 12) - self.bar]
        pre = frame.loc[utc_at(day, 7):nyopen - self.bar]
        late = frame.loc[utc_at(day, 12):nyopen - self.bar]
        expected = pd.Timedelta(hours=6) // self.bar, pd.Timedelta(hours=5) // self.bar
        context = {LONG: None, SHORT: None}
        if len(asia) == expected[0] and len(london) == expected[1] and len(late) and len(pre):
            source = self.history if self.history is not None else frame
            for direction, bullish in ((LONG, True), (SHORT, False)):
                context[direction] = self._side(frame, source, asia, london, pre, late, day, bullish)
        self.context_day, self.context = day, context
        return context

    def _side(self, frame, source, asia, london, pre, late, day, bullish):
        if bullish:
            levels = float(asia["low"].min()), float(london["low"].min())
            extreme_at, extreme = pre["low"].idxmin(), float(pre["low"].min())
            swept = extreme < levels[0] and float(late["low"].min()) < levels[1]
            holds = lambda b, t: extreme <= t and float(pre["close"].min()) >= b  # noqa: E731
        else:
            levels = float(asia["high"].max()), float(london["high"].max())
            extreme_at, extreme = pre["high"].idxmax(), float(pre["high"].max())
            swept = extreme > levels[0] and float(late["high"].max()) > levels[1]
            holds = lambda b, t: extreme >= b and float(pre["close"].max()) <= t  # noqa: E731
        if not swept:
            return None
        zones = live_htf_zones(source, utc_at(day, 0), bullish)
        if not any(holds(b, t) for b, t in zones):
            return None
        target = float(asia["high"].max()) if bullish else float(asia["low"].min())
        return {"bullish": bullish, "levels": levels, "extreme_at": extreme_at, "extreme": extreme, "target": target}

    def displaced(self, frame, ctx):
        """A bar after the sweep extreme with a body >= 1 ATR(14) in the trade direction that
        closes beyond both swept levels."""
        after = frame.loc[ctx["extreme_at"] + self.bar:]
        if not len(after):
            return False
        ranges = atr(frame, 14).shift(1).reindex(after.index)
        body = after["close"] - after["open"]
        if ctx["bullish"]:
            hit = (body >= DISPLACEMENT_ATR * ranges) & (after["close"] > max(ctx["levels"]))
        else:
            hit = (-body >= DISPLACEMENT_ATR * ranges) & (after["close"] < min(ctx["levels"]))
        return bool(hit.any())

    def target_untaken(self, frame, ctx, day):
        since = frame.loc[utc_at(day, 6):]
        return float(since["high"].max()) < ctx["target"] if ctx["bullish"] else float(since["low"].min()) > ctx["target"]

    # ------------------------------------------------------------------ entries
    def entry(self, frame):
        now = self.close_time(frame).tz_convert(NEW_YORK)
        day = now.date()
        if now.weekday() >= 5:
            return None  # the post's market has no Saturday/Sunday New York open
        if day != self.day:
            self.used = set()
        if not self.budget_left(day):
            return None
        hours = eastern_hours(now)
        for setup, rule, start, end in (("orb_fvg", self.orb_fvg, 9.75, 11.0), ("irl_erl", self.irl_erl, 9.5, 12.0)):
            if setup in self.setups and setup not in self.used and start < hours <= end:
                for direction, ctx in self.day_context(frame, day).items():
                    if ctx is None or not self.target_untaken(frame, ctx, day) or not self.displaced(frame, ctx):
                        continue
                    signal = rule(frame, day, direction, ctx)
                    if signal is not None:
                        self.used.add(setup)
                        return self.spend(signal)
        return None

    def orb_fvg(self, frame, day, direction, ctx):
        """15-minute opening range 09:30-09:45 ET; the bar that just closed completes an FVG in
        the trade direction and closes beyond the range. Stop beyond FVG bar 1; target the Asia
        extreme, at least 1.5R away."""
        start = eastern_at(day, 9, 30)
        opening = frame.loc[start:start + pd.Timedelta(minutes=15) - self.bar]
        if len(opening) != pd.Timedelta(minutes=15) // self.bar or len(frame) < 3:
            return None
        gaps = fvgs(frame.iloc[-3:], ctx["bullish"])
        if not gaps:
            return None
        last = float(frame["close"].iloc[-1])
        stop = float(gaps[-1][4])
        if ctx["bullish"] and last <= float(opening["high"].max()) or \
                not ctx["bullish"] and last >= float(opening["low"].min()):
            return None
        risk = abs(last - stop)
        if risk < MIN_RISK * last or abs(ctx["target"] - last) < ORB_MIN_RR * risk:
            return None
        return direction, stop, ctx["target"]

    def irl_erl(self, frame, day, direction, ctx):
        """The latest 30m FVG in the trade direction formed after the sweep (its bar 1 may hold
        the sweep); the bar that just closed is the first to trade back into it and closes inside
        or beyond it. Stop beyond 30m bar 1; target fixed 2R."""
        now = self.close_time(frame)
        bucket = ctx["extreme_at"].floor("30min")
        bars = closed_resample(frame.loc[bucket:], "30min", now)
        gaps = fvgs(bars, ctx["bullish"])
        if not gaps:
            return None
        _, third, bottom, top, outer = gaps[-1]
        after = frame.loc[third + pd.Timedelta(minutes=30):]
        if not len(after):
            return None
        bar, before = after.iloc[-1], after.iloc[:-1]
        if ctx["bullish"]:
            touched = float(bar["low"]) <= top and float(bar["close"]) >= bottom and (before["low"] > top).all()
        else:
            touched = float(bar["high"]) >= bottom and float(bar["close"]) <= top and (before["high"] < bottom).all()
        if not touched:
            return None
        last, stop = float(bar["close"]), float(outer)
        risk = abs(last - stop)
        if risk < MIN_RISK * last or (ctx["bullish"] and stop >= last) or (not ctx["bullish"] and stop <= last):
            return None
        return (direction, stop, last + IRL_RR * risk) if ctx["bullish"] else (direction, stop, last - IRL_RR * risk)
