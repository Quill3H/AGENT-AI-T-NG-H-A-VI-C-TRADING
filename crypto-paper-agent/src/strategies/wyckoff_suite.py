"""
src/strategies/wyckoff_suite.py
===============================
Round-10 Wyckoff rules (docs/research/2026-10-18-wyckoff-ichimoku.md). A trading range is
the 40 bars before the signal: height <= 8 ATR(14) and ADX(14) < 25, as in round 5's W3.
Every rule reads only closed bars; fills happen at the next execution-bar open. Numbers are
fixed before any run, not fitted.
"""
from src.strategies.indicator_suite import LONG, SHORT, RuleStrategy, adx, atr, ema

RANGE_BARS, MAX_HEIGHT_ATR, MAX_ADX, VOLUME_X = 40, 8.0, 25.0, 1.5
LPS_BARS = 10    # bars after the sign of strength in which the pullback must come
MAX_BARS = 60


def trading_range(frame, end):
    """(low, high) of the 40 bars before position `end` (negative index) if they form a
    quiet range, else None."""
    part = frame.iloc[end - RANGE_BARS:end]
    low, high = float(part["low"].min()), float(part["high"].max())
    upto = frame.iloc[:end]
    band = float(atr(upto, 14).iloc[-1])
    if high - low > MAX_HEIGHT_ATR * band or float(adx(upto, 14).iloc[-1]) >= MAX_ADX:
        return None
    return low, high


def loud(frame, i):
    """Volume of the bar at position i above 1.5x the mean of the 20 bars before it."""
    return frame["volume"].iloc[i] > VOLUME_X * float(frame["volume"].iloc[i - 20:i].mean())


class WyckoffTrendExit(RuleStrategy):
    """Shared exit: let the move run until the close crosses EMA(50), or 60 bars."""

    columns = ("open", "high", "low", "close", "volume")

    def should_exit(self, frame, direction):
        last, e50 = float(frame["close"].iloc[-1]), float(ema(frame["close"], 50).iloc[-1])
        crossed = (direction == LONG and last < e50) or (direction == SHORT and last > e50)
        return crossed or self.held_bars >= MAX_BARS


class WyckoffSpringRun(WyckoffTrendExit):
    """WY1: round-5 spring/upthrust entry (a high-volume bar trades below the range low and
    closes back inside -> long, stop 0.25 ATR under its low) without the fixed target at the
    range high; the trade runs until the EMA(50) exit."""

    name = "WYCKOFF_SPRING_RUN"
    window = 120

    def entry(self, frame):
        span = trading_range(frame, -1)
        if span is None or not loud(frame, len(frame) - 1):
            return None
        low, high = span
        bar, band = frame.iloc[-1], float(atr(frame, 14).iloc[-1])
        if bar["low"] < low and low < bar["close"] < high:
            return LONG, float(bar["low"]) - 0.25 * band
        if bar["high"] > high and low < bar["close"] < high:
            return SHORT, float(bar["high"]) + 0.25 * band
        return None


class WyckoffSosLps(WyckoffTrendExit):
    """WY2: sign of strength then last point of support. Within the last 10 bars a
    high-volume bar closed above a quiet range (SOS); no close since fell back below the
    range high; this bar's low comes back within 0.5 ATR of the range high and it closes
    above it (LPS) -> long, stop 0.25 ATR under this bar's low. Mirror: sign of weakness and
    last point of supply -> short."""

    name = "WYCKOFF_SOS_LPS"
    window = 140

    def entry(self, frame):
        n, bar = len(frame), frame.iloc[-1]
        band = float(atr(frame, 14).iloc[-1])
        for back in range(2, LPS_BARS + 2):
            i = n - back
            span = trading_range(frame, i - n)
            if span is None or not loud(frame, i):
                continue
            low, high = span
            after = frame["close"].iloc[i:]
            sos = frame["close"].iloc[i] > high
            sow = frame["close"].iloc[i] < low
            if sos and (after > high).all() and bar["low"] <= high + 0.5 * band:
                return LONG, float(bar["low"]) - 0.25 * band
            if sow and (after < low).all() and bar["high"] >= low - 0.5 * band:
                return SHORT, float(bar["high"]) + 0.25 * band
        return None
