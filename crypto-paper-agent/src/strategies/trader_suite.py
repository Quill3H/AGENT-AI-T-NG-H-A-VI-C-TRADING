"""
src/strategies/trader_suite.py
==============================
Round-11 rules from the public methods of three traders the owner named
(docs/research/2026-10-18-round11-traders.md):

- IncomeSharks: two daily Supertrends (ATR 10 x3 and x2) and On-Balance Volume (OBV)
  confirming the trend.
- Nebraskangooner: horizontal resistance breakouts confirmed by volume, reward at least
  twice the risk.
- Big Cheds: in a clear uptrend buy pullbacks to the 8 EMA; scale out on the way up.

Only the parts that can be written as fixed rules on price and volume are here. Every rule
reads closed bars only; fills happen at the next execution-bar open. Every entry carries a
stop. Scale-outs use `rules.partial_exits` (handled by the RuleStrategy base class and the
paper broker, which moves the stop to break-even after a partial).
"""
from src.strategies.indicator_suite import LONG, RuleStrategy, atr, completed_daily, ema, supertrend
from src.strategies.style_suite import SwingEmaPullback

VOLUME_X, BREAKOUT_BARS, REWARD_R = 1.5, 30, 2.0


def obv(frame):
    """On-Balance Volume: running sum of volume signed by the close-to-close direction."""
    step = frame["close"].diff()
    signed = frame["volume"].where(step > 0, -frame["volume"].where(step < 0, 0.0))
    return signed.fillna(0.0).cumsum()


def obv_rising(frame):
    """OBV above its 20-bar EMA (volume is flowing in)."""
    line = obv(frame)
    return bool(line.iloc[-1] > ema(line, 20).iloc[-1])


def daily_supertrends_up(frame):
    """Both daily Supertrends (10, 3) and (10, 2) point up on the last completed UTC day."""
    days = completed_daily(frame)
    if len(days) < 30:
        return False
    return bool(supertrend(days, 10, 3.0)[1][-1] > 0 and supertrend(days, 10, 2.0)[1][-1] > 0)


class SwingEmaSharks(SwingEmaPullback):
    """S1 (4h): C1 (swing EMA pullback, long) taken only when both daily Supertrends are up
    and OBV is above its 20-bar EMA (IncomeSharks' confirmation)."""

    name = "SWING_EMA_SHARKS"
    window = 400  # about 66 days of 4h bars for the daily Supertrends
    columns = ("open", "high", "low", "close", "volume")

    def entry(self, frame):
        signal = super().entry(frame.iloc[-SwingEmaPullback.window:])  # C1 sees exactly its own window
        if signal is None or signal[0] != LONG:
            return None
        return signal if daily_supertrends_up(frame) and obv_rising(frame) else None

    def should_exit(self, frame, direction):
        return super().should_exit(frame.iloc[-SwingEmaPullback.window:], direction)


class SupertrendObv(RuleStrategy):
    """S2 (4h, long): Supertrend(10, 2) turns up on this bar while Supertrend(10, 3) is up
    and OBV is above its 20-bar EMA -> long; stop at the Supertrend(10, 3) line. Exit when
    Supertrend(10, 2) turns down."""

    name = "SUPERTREND_OBV"
    window = 200
    columns = ("open", "high", "low", "close", "volume")

    def entry(self, frame):
        fast_line, fast = supertrend(frame, 10, 2.0)
        slow_line, slow = supertrend(frame, 10, 3.0)
        if fast[-2] < 0 and fast[-1] > 0 and slow[-1] > 0 and obv_rising(frame):
            return LONG, float(slow_line[-1])
        return None

    def should_exit(self, frame, direction):
        return bool(supertrend(frame, 10, 2.0)[1][-1] < 0)


class GoonerBreakout(RuleStrategy):
    """G1 (4h, long): EMA50 above EMA200; the previous close was at or under the highest
    high of the 30 bars before it and this bar closes above that level on volume over 1.5x
    the previous 20-bar mean -> long. Stop: lowest low of 5 bars minus 0.5 ATR(14). Take
    profit at 2R. Exit early if the close falls back under EMA50."""

    name = "GOONER_BREAKOUT"
    window = 260
    columns = ("open", "high", "low", "close", "volume")

    def entry(self, frame):
        close = frame["close"]
        if not ema(close, 50).iloc[-1] > ema(close, 200).iloc[-1]:
            return None
        level = float(frame["high"].iloc[-1 - BREAKOUT_BARS:-1].max())
        last, prev = float(close.iloc[-1]), float(close.iloc[-2])
        loud = frame["volume"].iloc[-1] > VOLUME_X * frame["volume"].iloc[-21:-1].mean()
        if prev <= level < last and loud:
            stop = float(frame["low"].iloc[-5:].min()) - 0.5 * float(atr(frame, 14).iloc[-1])
            return LONG, stop, last + REWARD_R * (last - stop)
        return None

    def should_exit(self, frame, direction):
        return float(frame["close"].iloc[-1]) < float(ema(frame["close"], 50).iloc[-1])


class ChedsEmaPullback(RuleStrategy):
    """K1 (4h, long): clear uptrend = last completed day closed above its EMA21 with daily
    EMA8 > EMA21, and on 4h EMA8 > EMA21; the previous bar dipped to EMA8 and this bar closes
    back above EMA8 as an up candle -> long. Stop: lowest low of 5 bars minus 0.5 ATR(14).
    Exit when the close falls under EMA21."""

    name = "CHEDS_EMA_PULLBACK"
    window = 400

    def entry(self, frame):
        days = completed_daily(frame)
        if len(days) < 30:
            return None
        d8, d21 = ema(days["close"], 8).iloc[-1], ema(days["close"], 21).iloc[-1]
        if not (days["close"].iloc[-1] > d21 and d8 > d21):
            return None
        close = frame["close"]
        e8, e21 = ema(close, 8), ema(close, 21)
        bar, prev = frame.iloc[-1], frame.iloc[-2]
        if e8.iloc[-1] > e21.iloc[-1] and prev["low"] <= e8.iloc[-2] and bar["close"] > e8.iloc[-1] \
                and bar["close"] > bar["open"]:
            return LONG, float(frame["low"].iloc[-5:].min()) - 0.5 * float(atr(frame, 14).iloc[-1])
        return None

    def should_exit(self, frame, direction):
        return float(frame["close"].iloc[-1]) < float(ema(frame["close"], 21).iloc[-1])
