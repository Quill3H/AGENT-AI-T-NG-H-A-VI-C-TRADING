"""
src/strategies/style_suite.py
=============================
Round-5 trading-style strategies (docs/research/2026-10-17-trading-styles.md).

Swing (4h/1d), day trading (1h/15m, flat before the UTC day ends), scalping (5m),
Wyckoff spring/upthrust with volume, and support/resistance with Japanese candle
patterns (Nison).  Every rule reads only closed signal bars; fills happen at the
next execution open.  Every entry carries a stop-loss.  Parameters are fixed in the
research log before any run, not fitted to our data.
"""
import numpy as np
import pandas as pd

from src.strategies.indicator_suite import LONG, SHORT, RuleStrategy, adx, atr, ema, rsi


# ------------------------------------------------------------ candle patterns
def _parts(bar):
    body = abs(bar["close"] - bar["open"])
    upper = bar["high"] - max(bar["open"], bar["close"])
    lower = min(bar["open"], bar["close"]) - bar["low"]
    return body, upper, lower, bar["high"] - bar["low"]


def bullish_engulfing(prev, bar):
    """Down candle followed by an up candle whose body covers the previous body."""
    return (prev["close"] < prev["open"] and bar["close"] > bar["open"]
            and bar["close"] >= prev["open"] and bar["open"] <= prev["close"])


def bearish_engulfing(prev, bar):
    return (prev["close"] > prev["open"] and bar["close"] < bar["open"]
            and bar["close"] <= prev["open"] and bar["open"] >= prev["close"])


def hammer(bar):
    """Small body near the top; lower shadow at least twice the body, little upper shadow."""
    body, upper, lower, span = _parts(bar)
    return span > 0 and lower >= 2.0 * body and upper <= 0.25 * span and body > 0


def shooting_star(bar):
    body, upper, lower, span = _parts(bar)
    return span > 0 and upper >= 2.0 * body and lower <= 0.25 * span and body > 0


def session_vwap(frame):
    """Volume-weighted average price restarted at each UTC day, using closed bars only."""
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    day = frame.index.normalize()
    weighted = (typical * frame["volume"]).groupby(day).cumsum()
    volume = frame["volume"].groupby(day).cumsum()
    return weighted / volume.replace(0.0, np.nan)


def _bar_close(frame, bars_per_hour):
    """UTC close time of the last bar as fractional hours since midnight."""
    last = frame.index[-1]
    return last.hour + last.minute / 60.0 + 1.0 / bars_per_hour


# ------------------------------------------------------------------- swing
class SwingEmaPullback(RuleStrategy):
    """W1 (4h): EMA50 above EMA200 and close above EMA200; the previous bar dipped to EMA20 and
    this bar closes back above EMA20 as an up candle -> long. Stop: lowest low of 5 bars minus
    0.5 ATR(14). Exit when close falls below EMA50. Mirror for shorts."""

    name = "SWING_EMA_PULLBACK"
    window = 260

    def entry(self, frame):
        close = frame["close"]
        e20, e50, e200 = ema(close, 20), ema(close, 50), ema(close, 200)
        bar, prev = frame.iloc[-1], frame.iloc[-2]
        gap = 0.5 * float(atr(frame, 14).iloc[-1])
        if e50.iloc[-1] > e200.iloc[-1] and bar["close"] > e200.iloc[-1]:
            if prev["low"] <= e20.iloc[-2] and bar["close"] > e20.iloc[-1] and bar["close"] > bar["open"]:
                return LONG, float(frame["low"].iloc[-5:].min()) - gap
        if e50.iloc[-1] < e200.iloc[-1] and bar["close"] < e200.iloc[-1]:
            if prev["high"] >= e20.iloc[-2] and bar["close"] < e20.iloc[-1] and bar["close"] < bar["open"]:
                return SHORT, float(frame["high"].iloc[-5:].max()) + gap
        return None

    def should_exit(self, frame, direction):
        last, e50 = float(frame["close"].iloc[-1]), float(ema(frame["close"], 50).iloc[-1])
        return (direction == LONG and last < e50) or (direction == SHORT and last > e50)


class SupportResistanceCandles(RuleStrategy):
    """W2 (1d): support/resistance = lowest low / highest high of the previous 30 days.
    Bullish engulfing or hammer with its low within 0.5 ATR(14) of support -> long, stop
    0.5 ATR below the candle low, take profit at resistance; skipped unless reward >= 1.5x risk.
    Mirror with bearish engulfing / shooting star at resistance. Time exit after 20 bars."""

    name = "SR_CANDLES"
    window = 60

    def entry(self, frame):
        bar, prev = frame.iloc[-1], frame.iloc[-2]
        previous = frame.iloc[-31:-1]
        support, resistance = float(previous["low"].min()), float(previous["high"].max())
        gap = 0.5 * float(atr(frame, 14).iloc[-1])
        last = float(bar["close"])
        if (bullish_engulfing(prev, bar) or hammer(bar)) and bar["low"] <= support + gap:
            stop = float(bar["low"]) - gap
            if resistance - last >= 1.5 * (last - stop):
                return LONG, stop, resistance
        if (bearish_engulfing(prev, bar) or shooting_star(bar)) and bar["high"] >= resistance - gap:
            stop = float(bar["high"]) + gap
            if last - support >= 1.5 * (stop - last):
                return SHORT, stop, support
        return None

    def should_exit(self, frame, direction):
        return self.held_bars >= 20


class WyckoffSpring(RuleStrategy):
    """W3 (4h): a trading range = previous 40 bars, height <= 8 ATR(14) and ADX(14) < 25.
    Spring: the bar trades below the range low, closes back inside, on volume > 1.5x the
    20-bar mean -> long, stop 0.25 ATR below the bar low, take profit at the range high.
    Upthrust is the mirror short. Time exit after 30 bars."""

    name = "WYCKOFF_SPRING"
    window = 80
    columns = ("open", "high", "low", "close", "volume")

    def entry(self, frame):
        bar = frame.iloc[-1]
        previous = frame.iloc[-41:-1]
        low, high = float(previous["low"].min()), float(previous["high"].max())
        band = float(atr(frame, 14).iloc[-1])
        if high - low > 8.0 * band or float(adx(frame, 14).iloc[-1]) >= 25:
            return None
        if bar["volume"] <= 1.5 * float(frame["volume"].iloc[-21:-1].mean()):
            return None
        if bar["low"] < low and low < bar["close"] < high:
            return LONG, float(bar["low"]) - 0.25 * band, high
        if bar["high"] > high and low < bar["close"] < high:
            return SHORT, float(bar["high"]) + 0.25 * band, low
        return None

    def should_exit(self, frame, direction):
        return self.held_bars >= 30


# -------------------------------------------------------------- day trading
class DayOpeningRange(RuleStrategy):
    """D1 (1h): opening range = the first 4 hours of the UTC day. From the 04:00 close until
    the 20:00 close, a close beyond the range in the direction of EMA(200) -> entry, stop at
    the other side of the range (skipped when the range is wider than 3 ATR(14)), take profit
    2x risk. One entry per day. Every position is closed by the bar that ends the UTC day."""

    name = "DAY_ORB"
    window = 260

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.last_entry_day = None

    def entry(self, frame):
        hour = _bar_close(frame, 1)
        day = frame.index[-1].normalize()
        if not 4 <= hour <= 20 or day == self.last_entry_day:
            return None
        today = frame.loc[frame.index >= day]
        opening = today.iloc[:4]
        if len(opening) < 4:
            return None
        top, bottom = float(opening["high"].max()), float(opening["low"].min())
        if top - bottom > 3.0 * float(atr(frame, 14).iloc[-1]):
            return None
        last, trend = float(frame["close"].iloc[-1]), float(ema(frame["close"], 200).iloc[-1])
        if last > top and last > trend:
            self.last_entry_day = day
            return LONG, bottom, last + 2.0 * (last - bottom)
        if last < bottom and last < trend:
            self.last_entry_day = day
            return SHORT, top, last - 2.0 * (top - last)
        return None

    def should_exit(self, frame, direction):
        return _bar_close(frame, 1) >= 24


class DayVwapReclaim(RuleStrategy):
    """D2 (15m): with close above EMA(200), the previous close below the session VWAP and
    this close back above it -> long; mirror for shorts. Stop 1.5 ATR(14), take profit 2x
    risk. Entries only between the 01:00 and 20:00 closes; flat by the bar ending the day."""

    name = "DAY_VWAP"
    window = 260
    columns = ("open", "high", "low", "close", "volume")

    def entry(self, frame):
        hour = _bar_close(frame, 4)
        if not 1 <= hour <= 20:
            return None
        vwap = session_vwap(frame)
        close = frame["close"]
        last, previous = float(close.iloc[-1]), float(close.iloc[-2])
        if frame.index[-2].normalize() != frame.index[-1].normalize():
            return None
        trend = float(ema(close, 200).iloc[-1])
        gap = 1.5 * float(atr(frame, 14).iloc[-1])
        if last > trend and previous < vwap.iloc[-2] and last > vwap.iloc[-1]:
            return LONG, last - gap, last + 2.0 * gap
        if last < trend and previous > vwap.iloc[-2] and last < vwap.iloc[-1]:
            return SHORT, last + gap, last - 2.0 * gap
        return None

    def should_exit(self, frame, direction):
        return _bar_close(frame, 4) >= 24


# ----------------------------------------------------------------- scalping
class ScalpEmaCross(RuleStrategy):
    """C1 (5m): EMA9 crosses EMA21 in the direction of EMA(200), RSI(14) between 50 and 70
    (30 and 50 for shorts). Stop 1 ATR(14), take profit 1.5 ATR. Exit after 24 bars (2 hours)."""

    name = "SCALP_EMA"
    window = 260

    def entry(self, frame):
        close = frame["close"]
        fast, slow, trend = ema(close, 9), ema(close, 21), float(ema(close, 200).iloc[-1])
        last, value = float(close.iloc[-1]), float(rsi(close, 14).iloc[-1])
        gap = float(atr(frame, 14).iloc[-1])
        up = fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
        down = fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]
        if up and last > trend and 50 < value < 70:
            return LONG, last - gap, last + 1.5 * gap
        if down and last < trend and 30 < value < 50:
            return SHORT, last + gap, last - 1.5 * gap
        return None

    def should_exit(self, frame, direction):
        return self.held_bars >= 24


class ScalpBollingerRevert(RuleStrategy):
    """C2 (5m): ADX(14) < 20; close below the lower Bollinger band (20, 2) with RSI(7) < 20 ->
    long, take profit at the middle band, stop 1.5 ATR(14). Mirror above the upper band with
    RSI(7) > 80. Exit after 24 bars."""

    name = "SCALP_BB"
    window = 120

    def entry(self, frame):
        close = frame["close"]
        middle, spread = close.rolling(20).mean(), close.rolling(20).std()
        last = float(close.iloc[-1])
        if float(adx(frame, 14).iloc[-1]) >= 20:
            return None
        value = float(rsi(close, 7).iloc[-1])
        gap = 1.5 * float(atr(frame, 14).iloc[-1])
        centre = float(middle.iloc[-1])
        if last < centre - 2.0 * float(spread.iloc[-1]) and value < 20:
            return LONG, last - gap, centre
        if last > centre + 2.0 * float(spread.iloc[-1]) and value > 80:
            return SHORT, last + gap, centre
        return None

    def should_exit(self, frame, direction):
        return self.held_bars >= 24


class ScalpRsiPullback(RuleStrategy):
    """C4/C6 (15m or 1h, owner 2026-10-17 "scalp bằng nến 15m và 1h" for a higher win rate):
    with close above EMA(200), RSI(2) < 10 -> long; mirror with RSI(2) > 90 below EMA(200).
    Quick take profit 1 ATR(14), wider stop 1.5 ATR(14), exit after 8 bars."""

    name = "SCALP_RSI_PULLBACK"
    window = 260

    def entry(self, frame):
        close = frame["close"]
        last, trend = float(close.iloc[-1]), float(ema(close, 200).iloc[-1])
        value = float(rsi(close, 2).iloc[-1])
        gap = float(atr(frame, 14).iloc[-1])
        if last > trend and value < 10:
            return LONG, last - 1.5 * gap, last + gap
        if last < trend and value > 90:
            return SHORT, last + 1.5 * gap, last - gap
        return None

    def should_exit(self, frame, direction):
        return self.held_bars >= 8
