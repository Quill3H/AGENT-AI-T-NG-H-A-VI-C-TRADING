"""
src/strategies/candles.py
=========================
Japanese candlestick patterns after Steve Nison (the owner's file 13.Nen-Nhat, chapters
4-8), for round 6 (docs/research/2026-10-18-candlesticks.md).

Every function looks only at the closed bars it is given; the last row is the newest
closed bar. Crypto trades around the clock, so the next bar opens at the previous
close and the book's gap conditions (piercing line opening below the prior low, star
gaps) cannot occur. Here they are relaxed to "opens at or beyond the prior close".
A "long" body is at least 0.6 x ATR(14), the size scale of the market at that time.
"""
import pandas as pd

from src.strategies.indicator_suite import atr

LONG_BODY = 0.6


def _body(bar):
    return abs(bar["close"] - bar["open"])


def _range(bar):
    return bar["high"] - bar["low"]


def _white(bar):
    return bar["close"] > bar["open"]


def _black(bar):
    return bar["close"] < bar["open"]


def _mid(bar):
    return (bar["open"] + bar["close"]) / 2.0


def doji(bar):
    """Open and close (almost) equal: body at most 10% of the range."""
    span = _range(bar)
    return span > 0 and _body(bar) <= 0.1 * span


def hammer_shape(bar):
    """Body in the upper part, lower shadow >= 2x body, little or no upper shadow (book ch. 4)."""
    body, span = _body(bar), _range(bar)
    upper = bar["high"] - max(bar["open"], bar["close"])
    lower = min(bar["open"], bar["close"]) - bar["low"]
    return span > 0 and body > 0 and lower >= 2.0 * body and upper <= 0.1 * span


def star_shape(bar):
    """Shooting star / inverted hammer: the hammer shape upside down."""
    body, span = _body(bar), _range(bar)
    upper = bar["high"] - max(bar["open"], bar["close"])
    lower = min(bar["open"], bar["close"]) - bar["low"]
    return span > 0 and body > 0 and upper >= 2.0 * body and lower <= 0.1 * span


def engulfing(prev, bar, bullish):
    if bullish:
        return _black(prev) and _white(bar) and bar["close"] >= prev["open"] and bar["open"] <= prev["close"]
    return _white(prev) and _black(bar) and bar["close"] <= prev["open"] and bar["open"] >= prev["close"]


def harami(prev, bar, unit, bullish):
    """Long body followed by a small body inside it, opposite colour (doji allowed)."""
    if _body(prev) < LONG_BODY * unit or _body(bar) > 0.5 * _body(prev):
        return False
    top, bottom = max(prev["open"], prev["close"]), min(prev["open"], prev["close"])
    inside = bottom <= min(bar["open"], bar["close"]) and max(bar["open"], bar["close"]) <= top
    colour = (_black(prev) and not _black(bar)) if bullish else (_white(prev) and not _white(bar))
    return inside and colour


def piercing(prev, bar, unit, bullish):
    """Piercing line (bullish) / dark cloud cover (bearish): long body, then a close past its midpoint."""
    if _body(prev) < LONG_BODY * unit:
        return False
    if bullish:
        return _black(prev) and _white(bar) and bar["open"] <= prev["close"] and _mid(prev) < bar["close"] < prev["open"]
    return _white(prev) and _black(bar) and bar["open"] >= prev["close"] and prev["open"] < bar["close"] < _mid(prev)


def star(first, middle, last, unit, bullish):
    """Morning star (bullish) / evening star (bearish); a doji middle makes it a doji star."""
    if _body(first) < LONG_BODY * unit or _body(middle) > 0.3 * _body(first):
        return False
    if bullish:
        return _black(first) and _white(last) and last["close"] > _mid(first)
    return _white(first) and _black(last) and last["close"] < _mid(first)


def three_soldiers(bars, unit, bullish):
    """Three white soldiers / three black crows: three long bodies in a row, each closing near its extreme."""
    if len(bars) < 3:
        return False
    a, b, c = bars.iloc[-3], bars.iloc[-2], bars.iloc[-1]
    for bar in (a, b, c):
        if _body(bar) < LONG_BODY * unit or (bullish and not _white(bar)) or (not bullish and not _black(bar)):
            return False
        shadow = bar["high"] - bar["close"] if bullish else bar["close"] - bar["low"]
        if shadow > 0.3 * _body(bar):
            return False
    if bullish:
        return a["close"] < b["close"] < c["close"] and a["open"] <= b["open"] <= a["close"] and b["open"] <= c["open"] <= b["close"]
    return a["close"] > b["close"] > c["close"] and a["close"] <= b["open"] <= a["open"] and b["close"] <= c["open"] <= b["open"]


def three_methods(bars, unit, bullish):
    """Rising / falling three methods: long body, three small bars inside its range, then a long body beyond its close."""
    if len(bars) < 5:
        return False
    first, small, last = bars.iloc[-5], bars.iloc[-4:-1], bars.iloc[-1]
    if _body(first) < LONG_BODY * unit or _body(last) < LONG_BODY * unit:
        return False
    if (small["high"] > first["high"]).any() or (small["low"] < first["low"]).any():
        return False
    if (abs(small["close"] - small["open"]) > 0.5 * _body(first)).any():
        return False
    if bullish:
        return _white(first) and _white(last) and last["close"] > first["close"]
    return _black(first) and _black(last) and last["close"] < first["close"]


def reversal_signal(frame, bullish):
    """Name of the bullish (or bearish) reversal pattern completed by the last bar, and the bars it spans."""
    unit = float(atr(frame, 14).iloc[-1])
    a, b, c = frame.iloc[-3], frame.iloc[-2], frame.iloc[-1]
    if star(a, b, c, unit, bullish):
        return ("doji star" if doji(b) else ("morning star" if bullish else "evening star")), 3
    if engulfing(b, c, bullish):
        return "engulfing", 2
    if piercing(b, c, unit, bullish):
        return ("piercing line" if bullish else "dark cloud cover"), 2
    if harami(b, c, unit, bullish):
        return "harami", 2
    if bullish and hammer_shape(c):
        return "hammer", 1
    if not bullish and hammer_shape(c):
        return "hanging man", 1
    if not bullish and star_shape(c):
        return "shooting star", 1
    if bullish and star_shape(c):
        return "inverted hammer", 1
    return None, 0


def continuation_signal(frame, bullish):
    unit = float(atr(frame, 14).iloc[-1])
    if three_soldiers(frame, unit, bullish):
        return ("three white soldiers" if bullish else "three black crows"), 3
    if three_methods(frame, unit, bullish):
        return ("rising three methods" if bullish else "falling three methods"), 5
    return None, 0


def prior_move(frame, span, bullish, bars=5):
    """Nison: a reversal pattern needs something to reverse. Close before the pattern vs `bars` earlier."""
    before = frame["close"].iloc[-span - 1]
    earlier = frame["close"].iloc[-span - 1 - bars]
    return before < earlier if bullish else before > earlier


def pattern_bars(frame, span) -> pd.DataFrame:
    return frame.iloc[-span:]
