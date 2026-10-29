"""
src/strategies/cross_section.py
===============================
Round-13 cross-sectional momentum (docs/research/2026-10-19-round13-cross-section.md),
after Liu, Tsyvinski and Wu, "Common Risk Factors in Cryptocurrency" (NBER w25882): each
week rank the coins by their past 1- or 3-week return, buy the strongest and sell the
weakest, and hold for a week.

Each symbol runs in its own paper sleeve. The rule reads the other coins' 4h closes from
`config["runtime"]["data_dir"]` and only uses bars that have closed by the decision time,
so the ranking never sees a later price. Every entry carries a stop of 2 daily ATR(14).
"""
from pathlib import Path

import pandas as pd

from src.strategies.indicator_suite import LONG, SHORT, RuleStrategy, atr, completed_daily

BARS_PER_WEEK = 42  # 4h bars


def is_rebalance_bar(open_time):
    """The 4h bar that opens Sunday 20:00 UTC closes at the start of the UTC week."""
    return open_time.weekday() == 6 and open_time.hour == 20


def rank_scores(closes, open_time, lookback_bars):
    """Past return of every coin whose bars at `open_time` and `lookback_bars` earlier exist."""
    then = open_time - pd.Timedelta(hours=4 * lookback_bars)
    if open_time not in closes.index or then not in closes.index:
        return pd.Series(dtype=float)
    return (closes.loc[open_time] / closes.loc[then] - 1.0).dropna()


class CrossSectionMomentum(RuleStrategy):
    """X (4h, weekly): at the bar that closes the UTC week, rank the universe by past return
    over `rules.lookback_weeks`. In the top `rules.top_n` -> long; in the bottom `top_n` ->
    short (if `allow_short`). With `rules.absolute`, a long also needs its own return > 0 and
    a short < 0. Exit at a later weekly bar once the coin leaves its group. Stop: 2 daily
    ATR(14) from the close."""

    name = "CROSS_SECTION_MOMENTUM"
    window = 120

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.lookback = int(self.rules.get("lookback_weeks", 3)) * BARS_PER_WEEK
        self.top_n = int(self.rules.get("top_n", 3))
        self.min_coins = int(self.rules.get("min_coins", 6))
        self.absolute = bool(self.rules.get("absolute", False))
        self.universe = list(self.rules.get("universe", [symbol]))
        data_dir = (config.get("runtime") or {}).get("data_dir")
        self.closes = self._load(data_dir) if data_dir else None

    def _load(self, data_dir):
        columns = {}
        for coin in self.universe:
            path = Path(data_dir) / f"{coin}_perp_4h.parquet"
            if path.is_file():
                columns[coin] = pd.read_parquet(path, columns=["close"])["close"]
        return pd.DataFrame(columns)

    def group(self, frame):
        """'long', 'short' or None for this symbol at the bar that just closed."""
        if self.closes is None:
            return None
        scores = rank_scores(self.closes, frame.index[-1], self.lookback)
        if len(scores) < self.min_coins or self.symbol not in scores:
            return None
        ordered = scores.sort_values(ascending=False)
        own = float(scores[self.symbol])
        if self.symbol in ordered.index[:self.top_n] and (not self.absolute or own > 0):
            return "long"
        if self.symbol in ordered.index[-self.top_n:] and (not self.absolute or own < 0):
            return "short"
        return None

    def entry(self, frame):
        if not is_rebalance_bar(frame.index[-1]):
            return None
        side = self.group(frame)
        days = completed_daily(frame)
        if side is None or len(days) < 15:
            return None
        gap = 2.0 * float(atr(days, 14).iloc[-1])
        close = float(frame["close"].iloc[-1])
        return (LONG, close - gap) if side == "long" else (SHORT, close + gap)

    def should_exit(self, frame, direction):
        if not is_rebalance_bar(frame.index[-1]):
            return False
        side = self.group(frame)
        return side != ("long" if direction == LONG else "short")
