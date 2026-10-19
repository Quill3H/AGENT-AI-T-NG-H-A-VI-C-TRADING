"""
src/strategies/adaptive_suite.py
================================
Round-12 rules that adapt to the market state (docs/research/2026-10-19-round12-adaptive.md):
an adaptive moving average (Kaufman), exits and stops that follow trend strength or
volatility, an order-flow filter from taker buy volume, a volatility-expansion filter and a
regime switch between the swing EMA pullback and a Bollinger reversion in quiet markets.

Every rule reads closed bars only; fills happen at the next execution-bar open. Every entry
carries a stop. Settings are the published defaults, fixed before any run.
"""
import numpy as np
import pandas as pd

from src.strategies.indicator_suite import LONG, RuleStrategy, adx, atr, completed_daily, ema
from src.strategies.style_suite import SwingEmaPullback

C1_WINDOW = SwingEmaPullback.window


def efficiency_ratio(close, bars=10):
    """Kaufman's efficiency ratio: net move / sum of absolute moves over `bars`."""
    change = (close - close.shift(bars)).abs()
    path = close.diff().abs().rolling(bars).sum()
    return (change / path.replace(0.0, np.nan)).fillna(0.0)


def kama(close, bars=10, fast=2, slow=30):
    """Kaufman adaptive moving average (10, 2, 30)."""
    fast_sc, slow_sc = 2.0 / (fast + 1), 2.0 / (slow + 1)
    sc = ((efficiency_ratio(close, bars) * (fast_sc - slow_sc) + slow_sc) ** 2).to_numpy()
    values = close.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) > bars:
        out[bars] = values[bars]
        for i in range(bars + 1, len(values)):
            out[i] = out[i - 1] + sc[i] * (values[i] - out[i - 1])
    return pd.Series(out, index=close.index)


class KamaTrend(RuleStrategy):
    """A1 (4h, long): the close crosses above KAMA(10,2,30), KAMA is higher than 3 bars ago
    and the efficiency ratio is above 0.3 -> long. Stop: lowest low of 5 bars minus 0.5
    ATR(14). Exit when the close falls under KAMA."""

    name = "KAMA_TREND"
    window = 200

    def entry(self, frame):
        close = frame["close"]
        line = kama(close)
        if close.iloc[-2] <= line.iloc[-2] and close.iloc[-1] > line.iloc[-1] \
                and line.iloc[-1] > line.iloc[-4] and efficiency_ratio(close).iloc[-1] > 0.3:
            return LONG, float(frame["low"].iloc[-5:].min()) - 0.5 * float(atr(frame, 14).iloc[-1])
        return None

    def should_exit(self, frame, direction):
        return float(frame["close"].iloc[-1]) < float(kama(frame["close"]).iloc[-1])


class _C1Based(SwingEmaPullback):
    """C1 entries computed on exactly C1's own window, long only."""

    window = C1_WINDOW

    def c1_entry(self, frame):
        signal = SwingEmaPullback.entry(self, frame.iloc[-C1_WINDOW:])
        return signal if signal is not None and signal[0] == LONG else None

    def entry(self, frame):
        return self.c1_entry(frame)


class SwingEmaAdaptiveExit(_C1Based):
    """A2 (4h): C1, but while ADX(14) <= 25 (weak trend) the exit moves up to a close under
    EMA20; in a strong trend it stays at EMA50."""

    name = "SWING_EMA_ADAPTIVE_EXIT"

    def should_exit(self, frame, direction):
        close = frame["close"]
        line = ema(close, 50) if float(adx(frame, 14).iloc[-1]) > 25.0 else ema(close, 20)
        return float(close.iloc[-1]) < float(line.iloc[-1])


class SwingEmaChandelier(_C1Based):
    """A3 (4h): C1 with a Chandelier trailing stop, highest high of 22 bars minus 3 ATR(22)
    (the broker only lets a stop tighten); the EMA50 exit stays."""

    name = "SWING_EMA_CHANDELIER"

    def trail(self, frame, direction):
        return float(frame["high"].iloc[-22:].max()) - 3.0 * float(atr(frame, 22).iloc[-1])


class SwingEmaOrderFlow(_C1Based):
    """A4 (4h): C1 only when aggressive buyers led over the last 20 bars: taker buy volume
    minus taker sell volume, summed, is above zero."""

    name = "SWING_EMA_ORDER_FLOW"
    columns = ("open", "high", "low", "close", "volume", "taker_buy_base_volume")

    def entry(self, frame):
        signal = self.c1_entry(frame)
        if signal is None:
            return None
        delta = (2.0 * frame["taker_buy_base_volume"] - frame["volume"]).iloc[-20:].sum()
        return signal if delta > 0 else None


class SwingEmaVolExpansion(_C1Based):
    """A6 (4h): C1 only when volatility is expanding: ATR(14) / close above its median of
    the previous 100 bars."""

    name = "SWING_EMA_VOL_EXPANSION"

    def entry(self, frame):
        signal = self.c1_entry(frame)
        if signal is None:
            return None
        ratio = atr(frame, 14) / frame["close"]
        return signal if ratio.iloc[-1] > ratio.iloc[-101:-1].median() else None


class RegimeSwingBands(_C1Based):
    """A5 (4h): daily ADX(14) on the last completed day picks the mode. ADX >= 20: C1 trend
    entries and exits. ADX < 20 (quiet range): the previous close was under the lower
    Bollinger band (20, 2) and this close is back above it -> long, stop 1 ATR(14) under the
    3-bar low, target the middle band, time exit after 12 bars."""

    name = "REGIME_SWING_BANDS"
    window = 400

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.mode = None

    def entry(self, frame):
        days = completed_daily(frame)
        if len(days) < 40:
            return None
        trending = float(adx(days, 14).iloc[-1]) >= 20.0
        if trending:
            signal = self.c1_entry(frame)
            self.mode = "trend" if signal is not None else self.mode
            return signal
        close = frame["close"]
        middle, spread = close.rolling(20).mean(), 2.0 * close.rolling(20).std(ddof=0)
        lower = middle - spread
        if close.iloc[-2] < lower.iloc[-2] and close.iloc[-1] > lower.iloc[-1] and middle.iloc[-1] > close.iloc[-1]:
            self.mode = "range"
            stop = float(frame["low"].iloc[-3:].min()) - float(atr(frame, 14).iloc[-1])
            return LONG, stop, float(middle.iloc[-1])
        return None

    def should_exit(self, frame, direction):
        if self.mode == "range":
            return self.held_bars >= 12
        return SwingEmaPullback.should_exit(self, frame.iloc[-C1_WINDOW:], direction)
