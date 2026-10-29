"""
src/strategies/session_suite.py
===============================
Round-7 strategies taken from the owner's video (docs/research/2026-10-18-video-sessions.md):
"Beginners Guide To Start Day Trading In 2026". The video trades CME futures on US Eastern
time; here the same clock rules run on crypto 5m bars, converted with daylight saving.

Every rule reads only closed 5m bars; fills happen at the next 5m open. Every entry has a
stop. Rule numbers come from the video and are fixed before any run, not fitted.
"""
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.strategies.indicator_suite import LONG, SHORT, RuleStrategy, adx, atr, ema

NEW_YORK = ZoneInfo("America/New_York")
FIVE_MINUTES = pd.Timedelta(minutes=5)


def eastern_close(frame):
    """US Eastern wall-clock time at which the last 5m bar closed."""
    return (frame.index[-1] + FIVE_MINUTES).tz_convert(NEW_YORK)


def eastern_hours(moment):
    return moment.hour + moment.minute / 60.0


def eastern_at(day, hour, minute=0):
    """UTC timestamp of a US Eastern wall-clock time on the given date."""
    return pd.Timestamp(dt.datetime(day.year, day.month, day.day, hour, minute), tz=NEW_YORK).tz_convert("UTC")


def heikin_ashi(frame):
    """Heikin-Ashi open/high/low/close. HA open is the running average seeded on the first bar."""
    close = (frame["open"] + frame["high"] + frame["low"] + frame["close"]) / 4.0
    seed = (frame["open"].iloc[0] + frame["close"].iloc[0]) / 2.0
    lagged = pd.Series(np.r_[seed, close.to_numpy()[:-1]], index=frame.index)
    open_ = lagged.ewm(alpha=0.5, adjust=False).mean()
    high = np.maximum(frame["high"], np.maximum(open_, close))
    low = np.minimum(frame["low"], np.minimum(open_, close))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def last_swing(values, k, high):
    """Most recent confirmed swing (k bars each side) in a 1-d array, or None."""
    for i in range(len(values) - k - 1, k - 1, -1):
        window = values[i - k:i + k + 1]
        if (high and values[i] == window.max() and (window < values[i]).sum() == 2 * k) or \
                (not high and values[i] == window.min() and (window > values[i]).sum() == 2 * k):
            return float(values[i])
    return None


class EasternSessionStrategy(RuleStrategy):
    """Shared clock: at most `per_day` entries per US Eastern day, flat by the 16:00 close."""

    per_day = 1

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.day = None
        self.entries_today = 0

    def budget_left(self, day):
        if day != self.day:
            self.day, self.entries_today = day, 0
        return self.entries_today < self.per_day

    def spend(self, signal):
        self.entries_today += 1
        return signal

    def should_exit(self, frame, direction):
        return eastern_hours(eastern_close(frame)) >= 16.0 or self.held_bars >= 96


class LondonBreakout(EasternSessionStrategy):
    """V1: range = the London bars from 03:00 to 08:00 ET. From 08:00 to 11:00 ET the first
    5m close outside the range enters in that direction (a wick does not count; only the
    first break of the day). Stop beyond the trigger bar, take profit 2R."""

    name = "LONDON_BREAKOUT"
    window = 160
    trend_span = None

    def entry(self, frame):
        now = eastern_close(frame)
        day = now.date()
        if not 8.0 < eastern_hours(now) <= 11.0 or not self.budget_left(day):
            return None
        start, end = eastern_at(day, 3), eastern_at(day, 8)
        session = frame.loc[start:end - FIVE_MINUTES]
        if len(session) != 60:
            return None
        top, bottom = float(session["high"].max()), float(session["low"].min())
        closes = frame.loc[end:, "close"]
        outside = (closes > top) | (closes < bottom)
        if outside.iloc[:-1].any() or not outside.iloc[-1]:
            return None
        self.entries_today = self.per_day  # the first break uses up the day, traded or not
        bar, last = frame.iloc[-1], float(closes.iloc[-1])
        trend = None if self.trend_span is None else float(ema(frame["close"], self.trend_span).iloc[-1])
        if last > top and (trend is None or last > trend):
            stop = float(bar["low"])
            return LONG, stop, last + 2.0 * (last - stop)
        if last < bottom and (trend is None or last < trend):
            stop = float(bar["high"])
            return SHORT, stop, last - 2.0 * (stop - last)
        return None


class LondonBreakoutTrend(LondonBreakout):
    """V2: V1 only in the direction of the video's EMA(100) trend filter on 1h, computed as
    EMA(1200) of 5m closes."""

    name = "LONDON_BREAKOUT_TREND"
    window = 1400
    trend_span = 1200


class HeikinAshiScalp(RuleStrategy):
    """V3: with the close above EMA(100), two clean red Heikin-Ashi bars (no upper wick) then
    an HA doji (body <= 30% of range, both wicks >= 20%) larger than one of the two before
    -> long at the close. Stop at the doji's low, take profit 1R measured from the doji's
    high. Mirror for shorts. Exit after 24 bars (2 hours)."""

    name = "HEIKIN_ASHI_SCALP"
    window = 300

    def entry(self, frame):
        ha = heikin_ashi(frame)
        o, h, l, c = (ha[k].to_numpy()[-3:] for k in ("open", "high", "low", "close"))
        span = h - l
        if span[-1] <= 0:
            return None
        body = abs(c[-1] - o[-1])
        upper = h[-1] - max(o[-1], c[-1])
        lower = min(o[-1], c[-1]) - l[-1]
        doji = body <= 0.3 * span[-1] and upper >= 0.2 * span[-1] and lower >= 0.2 * span[-1]
        if not doji or span[-1] <= min(span[0], span[1]):
            return None
        last = float(frame["close"].iloc[-1])
        trend = float(ema(frame["close"], 100).iloc[-1])
        red = all(c[i] < o[i] and o[i] >= h[i] for i in (0, 1))
        green = all(c[i] > o[i] and o[i] <= l[i] for i in (0, 1))
        if red and last > trend:
            stop, tip = float(l[-1]), float(h[-1])
            return LONG, stop, tip + (tip - stop)
        if green and last < trend:
            stop, tip = float(h[-1]), float(l[-1])
            return SHORT, stop, tip - (stop - tip)
        return None

    def should_exit(self, frame, direction):
        return self.held_bars >= 24


class ZoneSwingBreak(EasternSessionStrategy):
    """V4: support/resistance zones on 1h bars, entry on a 5m swing break in the New York
    morning.
    - Zone: a 1h pivot high (3 bars each side); zone = top of its body to its high. It counts
      if price fell at least 1 ATR(14, 1h) below the zone within the next 6 hours. Mirror
      for support (low to the bottom of the body). Pivots from the last 10 days.
    - Long: within the last 12 5m bars price touched a support zone without closing below
      it, and this close breaks above the last confirmed 5m swing high (2 bars each side).
      Stop 0.1 ATR(14, 5m) below the last 5m swing low, take profit 2.5R. Mirror for shorts.
    - Entries from 09:30 to 12:00 ET, at most 2 per day."""

    name = "ZONE_SWING_BREAK"
    window = 2900
    per_day = 2

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.zone_hour = None
        self.zones = ([], [])  # (supports, resistances) as (bottom, top)

    def refresh_zones(self, frame):
        hour = (frame.index[-1] + FIVE_MINUTES).floor("1h")
        if hour == self.zone_hour:
            return
        self.zone_hour = hour
        bars = frame.loc[:hour - FIVE_MINUTES].resample("1h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        bars = bars.iloc[:-1] if len(bars) and bars.index[-1] + pd.Timedelta(hours=1) > hour else bars
        if len(bars) < 30:
            self.zones = ([], [])
            return
        span = atr(bars, 14).to_numpy()
        hi, lo = bars["high"].to_numpy(), bars["low"].to_numpy()
        body_top = np.maximum(bars["open"], bars["close"]).to_numpy()
        body_low = np.minimum(bars["open"], bars["close"]).to_numpy()
        supports, resistances = [], []
        for i in range(3, len(bars) - 3):
            if not np.isfinite(span[i]):
                continue
            later = slice(i + 1, min(i + 7, len(bars)))
            if hi[i] > hi[i - 3:i].max() and hi[i] > hi[i + 1:i + 4].max() and lo[later].min() <= body_top[i] - span[i]:
                resistances.append((body_top[i], hi[i]))
            if lo[i] < lo[i - 3:i].min() and lo[i] < lo[i + 1:i + 4].min() and hi[later].max() >= body_low[i] + span[i]:
                supports.append((lo[i], body_low[i]))
        self.zones = (supports, resistances)

    def entry(self, frame):
        now = eastern_close(frame)
        if not 9.5 < eastern_hours(now) <= 12.0 or not self.budget_left(now.date()):
            return None
        self.refresh_zones(frame)
        supports, resistances = self.zones
        recent = frame.iloc[-12:]
        tail = frame.iloc[-60:]
        highs, lows, closes = tail["high"].to_numpy(), tail["low"].to_numpy(), tail["close"].to_numpy()
        last, previous = float(closes[-1]), float(closes[-2])
        buffer = 0.1 * float(atr(tail, 14).iloc[-1])
        swing_high, swing_low = last_swing(highs[:-1], 2, True), last_swing(lows[:-1], 2, False)
        if swing_high is None or swing_low is None:
            return None
        touched_support = any(recent["low"].min() <= top and recent["close"].min() >= bottom for bottom, top in supports)
        touched_resistance = any(recent["high"].max() >= bottom and recent["close"].max() <= top for bottom, top in resistances)
        if touched_support and previous <= swing_high < last:
            stop = swing_low - buffer
            if stop < last:
                return self.spend((LONG, stop, last + 2.5 * (last - stop)))
        if touched_resistance and previous >= swing_low > last:
            stop = swing_high + buffer
            if stop > last:
                return self.spend((SHORT, stop, last - 2.5 * (stop - last)))
        return None


# ------------------------------------------------- published methods of known traders
class HolyGrail(RuleStrategy):
    """T1, Linda Raschke's "Holy Grail" (Street Smarts, 1995), on 1h bars: with ADX(14) above
    30 and EMA(20) rising over 5 bars, the low touches EMA(20) on a pullback and this close
    rises above the previous high -> long. Stop at the lowest low of the last 5 bars, take
    profit at the 20-bar high (skipped when there is no room). Mirror for shorts. Exit after
    24 bars."""

    name = "HOLY_GRAIL"
    window = 120

    def entry(self, frame):
        if float(adx(frame, 14).iloc[-1]) <= 30:
            return None
        line = ema(frame["close"], 20)
        last, bar, previous = float(frame["close"].iloc[-1]), frame.iloc[-1], frame.iloc[-2]
        rising = line.iloc[-1] > line.iloc[-6]
        touched_low = frame["low"].iloc[-3:].min() <= line.iloc[-1]
        touched_high = frame["high"].iloc[-3:].max() >= line.iloc[-1]
        if rising and touched_low and last > previous["high"] and float(bar["close"]) > line.iloc[-1]:
            stop, target = float(frame["low"].iloc[-5:].min()), float(frame["high"].iloc[-21:-1].max())
            return (LONG, stop, target) if target > last > stop else None
        if not rising and touched_high and last < previous["low"] and float(bar["close"]) < line.iloc[-1]:
            stop, target = float(frame["high"].iloc[-5:].max()), float(frame["low"].iloc[-21:-1].min())
            return (SHORT, stop, target) if target < last < stop else None
        return None

    def should_exit(self, frame, direction):
        return self.held_bars >= 24


class VolatilityBreakout(RuleStrategy):
    """T2, Larry Williams' volatility breakout (Long-Term Secrets to Short-Term Trading, 1999),
    on 5m bars: the first close of the UTC day above open + 0.6 x yesterday's range -> long;
    below open - 0.6 x range -> short. Stop 0.5 x yesterday's range from the entry; exit on
    the bar that ends the UTC day. One entry per day."""

    name = "VOLATILITY_BREAKOUT"
    window = 576  # yesterday plus a whole day

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.last_day = None

    def entry(self, frame):
        day = frame.index[-1].normalize()
        if day == self.last_day:
            return None
        today, yesterday = frame.loc[day:], frame.loc[day - pd.Timedelta(days=1):day - FIVE_MINUTES]
        if len(yesterday) != 288 or len(today) < 2:
            return None
        spread = float(yesterday["high"].max() - yesterday["low"].min())
        start = float(today["open"].iloc[0])
        closes = today["close"]
        up, down = closes > start + 0.6 * spread, closes < start - 0.6 * spread
        if (up | down).iloc[:-1].any():
            self.last_day = day
            return None
        last = float(closes.iloc[-1])
        if up.iloc[-1]:
            self.last_day = day
            return LONG, last - 0.5 * spread
        if down.iloc[-1]:
            self.last_day = day
            return SHORT, last + 0.5 * spread
        return None

    def should_exit(self, frame, direction):
        return (frame.index[-1] + FIVE_MINUTES).normalize() != frame.index[-1].normalize()


class NarrowRangeBreakout(RuleStrategy):
    """T3, Toby Crabel's NR7 (Day Trading with Short Term Price Patterns, 1990), on 4h bars:
    when the previous bar had the smallest range of the last 7, a close above its high ->
    long, below its low -> short. Stop at the other end of that bar, take profit 2R. Exit
    after 6 bars (one day)."""

    name = "NR7_BREAKOUT"
    window = 30

    def entry(self, frame):
        spans = (frame["high"] - frame["low"]).to_numpy()
        if spans[-2] > spans[-8:-1].min() or spans[-2] <= 0:
            return None
        inside, last = frame.iloc[-2], float(frame["close"].iloc[-1])
        top, bottom = float(inside["high"]), float(inside["low"])
        if last > top:
            return LONG, bottom, last + 2.0 * (last - bottom)
        if last < bottom:
            return SHORT, top, last - 2.0 * (top - last)
        return None

    def should_exit(self, frame, direction):
        return self.held_bars >= 6
