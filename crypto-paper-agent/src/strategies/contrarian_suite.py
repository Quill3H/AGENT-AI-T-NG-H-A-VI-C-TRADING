"""
src/strategies/contrarian_suite.py
==================================
Round-8 contrarian rules (docs/research/2026-10-18-round8-plan.md), the price-only part of
what well-known crypto traders describe in public: GCR shorting euphoric blow-offs, and
Machi Big Brother / James Wynn buying sharp liquidation flushes. Their news, macro and
on-chain judgement is not codable from OHLCV and is left out.

Every rule reads only closed signal bars; fills happen at the next execution-bar open.
Numbers are fixed before any run, not fitted.
"""
from src.strategies.indicator_suite import LONG, SHORT, RuleStrategy, atr, ema, rsi

STRETCH_ATR = 3.0   # how far the last bar closed from EMA(20), in ATR(14)
RSI_HIGH, RSI_LOW = 80.0, 20.0
MAX_BARS = 12       # two days on 4h bars


class ExtremeFade(RuleStrategy):
    """C2/C3 (4h): the previous bar closed more than 3 ATR(14) above EMA(20) with RSI(14) > 80,
    and this bar closes red -> short (blow-off fade). Stop: highest high of the last 3 bars
    plus 0.25 ATR. Exit when the close is back at EMA(20) or after 12 bars. Mirror long after
    a flush below EMA(20) - 3 ATR with RSI < 20 and a green bar. `rules.allow_long` and
    `rules.allow_short` pick the side."""

    name = "EXTREME_FADE"
    window = 60

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.allow_long = bool(self.rules.get("allow_long", True))

    def entry(self, frame):
        close = frame["close"]
        e20, band, strength = ema(close, 20), atr(frame, 14), rsi(close, 14)
        bar, prev = frame.iloc[-1], frame.iloc[-2]
        gap = 0.25 * float(band.iloc[-1])
        stretched_up = prev["close"] > e20.iloc[-2] + STRETCH_ATR * band.iloc[-2] and strength.iloc[-2] > RSI_HIGH
        stretched_down = prev["close"] < e20.iloc[-2] - STRETCH_ATR * band.iloc[-2] and strength.iloc[-2] < RSI_LOW
        if stretched_up and bar["close"] < bar["open"]:
            return SHORT, float(frame["high"].iloc[-3:].max()) + gap
        if stretched_down and bar["close"] > bar["open"] and self.allow_long:
            return LONG, float(frame["low"].iloc[-3:].min()) - gap
        return None

    def should_exit(self, frame, direction):
        last, e20 = float(frame["close"].iloc[-1]), float(ema(frame["close"], 20).iloc[-1])
        back = (direction == LONG and last >= e20) or (direction == SHORT and last <= e20)
        return back or self.held_bars >= MAX_BARS
