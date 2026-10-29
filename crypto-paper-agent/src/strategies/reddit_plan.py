"""
src/strategies/reddit_plan.py
=============================
Round-17 rules from the r/Daytrading post the owner pasted on 2026-10-20, "The Simple Futures
Trading Plan I Wish I Had When I Started" (docs/research/2026-10-20-round17-reddit-plan.md).
The post trades CME index futures on US Eastern time; here the same clock rules run on crypto
perpetual 5m bars, converted with daylight saving:

- trade only around the US open, at most two setups a day, then stop;
- place the stop where the idea is invalidated, then check that the reward is worth it;
- setup 1: the pre-market range breakout between 07:00 and 07:30 ET;
- setup 2: the reversal of the 09:30 opening move, a hammer / shooting star / engulfing candle
  on 5m after 09:45 (the post then times the entry on 1m; here it fills at the next 5m open).

Every rule reads only closed 5m bars and every entry has a stop. Targets are 2R and positions
are flat by 16:00 ET.
"""
from src.strategies.indicator_suite import LONG, SHORT
from src.strategies.session_suite import FIVE_MINUTES, EasternSessionStrategy, eastern_at, eastern_close, eastern_hours

MIN_RISK = 0.003  # skip a trade whose stop is closer than 0.3% (about twice the round-trip cost)


def reversal(prev, bar, bullish):
    """Hammer / bullish engulfing (bullish=True) or shooting star / bearish engulfing."""
    body = abs(bar["close"] - bar["open"])
    upper = bar["high"] - max(bar["open"], bar["close"])
    lower = min(bar["open"], bar["close"]) - bar["low"]
    span = bar["high"] - bar["low"]
    if span <= 0:
        return False
    if bullish:
        hammer = lower >= 2 * body and upper <= body and lower >= 0.6 * span
        engulf = prev["close"] < prev["open"] and bar["close"] > bar["open"] and \
            bar["close"] >= prev["open"] and bar["open"] <= prev["close"]
        return bool(hammer or engulf)
    star = upper >= 2 * body and lower <= body and upper >= 0.6 * span
    engulf = prev["close"] > prev["open"] and bar["close"] < bar["open"] and \
        bar["close"] <= prev["open"] and bar["open"] >= prev["close"]
    return bool(star or engulf)


def with_target(direction, entry, stop):
    risk = abs(entry - stop)
    if risk < MIN_RISK * entry:
        return None  # the reward is not worth the costs
    return (direction, stop, entry + 2 * risk) if direction == LONG else (direction, stop, entry - 2 * risk)


class RedditPlan(EasternSessionStrategy):
    """R1 (`rules.setups: [premarket]`), R2 (`[open_reversal]`) or R3 (both, the post's plan):
    each setup at most once per US Eastern day."""

    name = "REDDIT_PLAN"
    window = 160
    per_day = 2

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.setups = tuple(self.rules.get("setups", ["premarket", "open_reversal"]))
        self.used = set()

    def entry(self, frame):
        now = eastern_close(frame)
        day = now.date()
        if day != self.day:
            self.used = set()
        if not self.budget_left(day):
            return None
        hours = eastern_hours(now)
        for setup, rule, start, end in (("premarket", self.premarket, 7.0, 7.5), ("open_reversal", self.open_reversal, 9.75, 11.0)):
            if setup in self.setups and setup not in self.used and start < hours <= end:
                signal = rule(frame, day)
                if signal is not None:
                    self.used.add(setup)
                    return self.spend(signal)
        return None

    @staticmethod
    def premarket(frame, day):
        """Range = 06:00-07:00 ET; the first 5m close outside it from 07:00 to 07:30 enters that
        way; the stop is the far side of the range (a break back through it voids the idea)."""
        start, end = eastern_at(day, 6), eastern_at(day, 7)
        session = frame.loc[start:end - FIVE_MINUTES]
        if len(session) != 12:
            return None
        top, bottom = float(session["high"].max()), float(session["low"].min())
        closes = frame.loc[end:, "close"]
        outside = (closes > top) | (closes < bottom)
        if outside.iloc[:-1].any() or not outside.iloc[-1]:
            return None
        last = float(closes.iloc[-1])
        return with_target(LONG, last, bottom) if last > top else with_target(SHORT, last, top)

    @staticmethod
    def open_reversal(frame, day):
        """Opening move = 09:30 open to the 09:45 close. From 09:45 to 11:00 ET a 5m reversal
        candle against that move enters against it; the stop is beyond the candle."""
        start = eastern_at(day, 9, 30)
        opening = frame.loc[start:start + 2 * FIVE_MINUTES]
        if len(opening) != 3 or len(frame.loc[start:]) < 4:
            return None
        move_up = float(opening["close"].iloc[-1]) > float(opening["open"].iloc[0])
        prev, bar = frame.iloc[-2], frame.iloc[-1]
        if not reversal(prev, bar, bullish=not move_up):
            return None
        last = float(bar["close"])
        return with_target(SHORT, last, float(bar["high"])) if move_up else with_target(LONG, last, float(bar["low"]))
