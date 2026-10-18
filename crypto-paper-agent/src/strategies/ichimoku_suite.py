"""
src/strategies/ichimoku_suite.py
================================
Round-9 Ichimoku Kinko Hyo rules (docs/research/2026-10-19-ichimoku.md), with Goichi
Hosoda's standard settings 9 / 26 / 52 and a 26-bar displacement.

Look-ahead: the cloud drawn at bar t comes from spans computed at bar t-26, and the
lagging line (Chikou) is checked as close[t] vs close[t-26], so every value is known when
bar t closes. Fills happen at the next execution-bar open. Every entry has a stop.
"""
from src.strategies.indicator_suite import LONG, SHORT, RuleStrategy, atr

TENKAN, KIJUN, SENKOU_B, SHIFT = 9, 26, 52, 26


def _midpoint(frame, bars):
    return (frame["high"].rolling(bars).max() + frame["low"].rolling(bars).min()) / 2.0


def ichimoku(frame):
    """Tenkan, Kijun, the cloud under the current bar (span A/B from 26 bars ago) and the
    cloud being projected now (spans computed on this bar). All causal."""
    tenkan, kijun = _midpoint(frame, TENKAN), _midpoint(frame, KIJUN)
    span_a, span_b = (tenkan + kijun) / 2.0, _midpoint(frame, SENKOU_B)
    return {"tenkan": tenkan, "kijun": kijun, "cloud_a": span_a.shift(SHIFT), "cloud_b": span_b.shift(SHIFT),
            "future_a": span_a, "future_b": span_b}


class IchimokuStrategy(RuleStrategy):
    """Shared exit: close back across the Kijun line. `rules.allow_short` picks the sides."""

    window = 140

    def should_exit(self, frame, direction):
        last, kijun = float(frame["close"].iloc[-1]), float(_midpoint(frame, KIJUN).iloc[-1])
        return (direction == LONG and last < kijun) or (direction == SHORT and last > kijun)

    def _stop(self, frame, direction, level):
        gap = 0.5 * float(atr(frame, 14).iloc[-1])
        return level - gap if direction == LONG else level + gap


class IchimokuTkCross(IchimokuStrategy):
    """I1: Tenkan crosses above Kijun on this bar, the close is above the cloud and the
    Chikou is above the close 26 bars ago -> long; stop 0.5 ATR(14) under the Kijun. Mirror
    for shorts."""

    name = "ICHIMOKU_TK_CROSS"

    def entry(self, frame):
        ich = ichimoku(frame)
        close = frame["close"]
        t, k = ich["tenkan"], ich["kijun"]
        top = max(ich["cloud_a"].iloc[-1], ich["cloud_b"].iloc[-1])
        bottom = min(ich["cloud_a"].iloc[-1], ich["cloud_b"].iloc[-1])
        last, lagged = float(close.iloc[-1]), float(close.iloc[-1 - SHIFT])
        if t.iloc[-2] <= k.iloc[-2] and t.iloc[-1] > k.iloc[-1] and last > top and last > lagged:
            return LONG, self._stop(frame, LONG, float(k.iloc[-1]))
        if t.iloc[-2] >= k.iloc[-2] and t.iloc[-1] < k.iloc[-1] and last < bottom and last < lagged:
            return SHORT, self._stop(frame, SHORT, float(k.iloc[-1]))
        return None


class IchimokuKumoBreakout(IchimokuStrategy):
    """I2: the previous close was at or below the cloud top and this close is above it, the
    projected cloud is bullish (span A > span B), Tenkan > Kijun and the Chikou is above the
    close 26 bars ago -> long; stop 0.5 ATR(14) under the cloud bottom. Mirror for shorts."""

    name = "ICHIMOKU_KUMO_BREAKOUT"

    def entry(self, frame):
        ich = ichimoku(frame)
        close = frame["close"]
        a, b = ich["cloud_a"], ich["cloud_b"]
        top_now, top_prev = max(a.iloc[-1], b.iloc[-1]), max(a.iloc[-2], b.iloc[-2])
        bottom_now, bottom_prev = min(a.iloc[-1], b.iloc[-1]), min(a.iloc[-2], b.iloc[-2])
        last, prev, lagged = float(close.iloc[-1]), float(close.iloc[-2]), float(close.iloc[-1 - SHIFT])
        bullish = ich["future_a"].iloc[-1] > ich["future_b"].iloc[-1]
        tk_up = ich["tenkan"].iloc[-1] > ich["kijun"].iloc[-1]
        if prev <= top_prev and last > top_now and bullish and tk_up and last > lagged:
            return LONG, self._stop(frame, LONG, float(bottom_now))
        if prev >= bottom_prev and last < bottom_now and not bullish and not tk_up and last < lagged:
            return SHORT, self._stop(frame, SHORT, float(top_now))
        return None
