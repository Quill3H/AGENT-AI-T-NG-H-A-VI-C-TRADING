"""
src/strategies/funding_signals.py
=================================
Round-15 funding-rate rules (docs/research/2026-10-19-round15-funding.md). Perpetual funding
measures how crowded one side is. Schmeling, Schrimpf and Todorov, "Crypto carry" (BIS
working paper 1087), find that a high futures-spot carry predicts price crashes.

Funding events are read from `{coin}_perp_funding.parquet` in `config["runtime"]["data_dir"]`.
A decision at a 4h close uses only events settled at or before that close.
"""
from pathlib import Path

import pandas as pd

from src.strategies.adaptive_suite import _C1Based
from src.strategies.cross_section import is_rebalance_bar
from src.strategies.indicator_suite import LONG, SHORT, RuleStrategy, atr, completed_daily

BAR = pd.Timedelta(hours=4)


def load_funding(data_dir, coins):
    out = {}
    for coin in coins:
        path = Path(data_dir) / f"{coin}_perp_funding.parquet"
        if path.is_file():
            out[coin] = pd.read_parquet(path, columns=["funding_rate"])["funding_rate"].sort_index()
    return out


def mean_funding(series, until, days):
    """Mean rate of the events in (until - days, until]."""
    window = series[(series.index > until - pd.Timedelta(days=days)) & (series.index <= until)]
    return float(window.mean()) if len(window) else float("nan")


def crowded(series, until, days=7, history_days=180, quantile=0.9):
    """True when the `days` mean is above the `quantile` of its own daily values over the past
    `history_days` (needs at least half of that history)."""
    past = series[(series.index > until - pd.Timedelta(days=history_days)) & (series.index <= until)]
    if past.index.size == 0 or past.index[0] > until - pd.Timedelta(days=history_days / 2):
        return False
    rolling = past.rolling(pd.Timedelta(days=days)).mean().resample("1D").last().dropna()
    return mean_funding(series, until, days) > float(rolling.quantile(quantile))


class C1FundingFilter(_C1Based):
    """F1 (4h): C1, but no new long while this coin's 7-day mean funding is above the 90th
    percentile of its own 7-day means over the past 180 days (a crowded long)."""

    name = "C1_FUNDING_FILTER"

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        data_dir = (config.get("runtime") or {}).get("data_dir")
        self.funding = load_funding(data_dir, [symbol]).get(symbol) if data_dir else None

    def entry(self, frame):
        signal = self.c1_entry(frame)
        if signal is None or self.funding is None:
            return signal
        return None if crowded(self.funding, frame.index[-1] + BAR) else signal


class FundingCarry(RuleStrategy):
    """F (4h, weekly): at the bar that closes the UTC week, rank `rules.universe` by 7-day mean
    funding. Long the `top_n` lowest (longs there are paid or pay least), short the `top_n`
    highest (crowded longs). `rules.side`: 'both', or 'short' for the crowded side only, which
    also needs a positive mean. Exit at a later weekly bar once the coin leaves its group.
    Stop: 2 daily ATR(14) from the close."""

    name = "FUNDING_CARRY"
    window = 120

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.days = int(self.rules.get("lookback_days", 7))
        self.top_n = int(self.rules.get("top_n", 3))
        self.min_coins = int(self.rules.get("min_coins", 6))
        self.side = str(self.rules.get("side", "both"))
        data_dir = (config.get("runtime") or {}).get("data_dir")
        self.funding = load_funding(data_dir, list(self.rules.get("universe", [symbol]))) if data_dir else {}

    def group(self, frame):
        until = frame.index[-1] + BAR
        scores = pd.Series({c: mean_funding(s, until, self.days) for c, s in self.funding.items()}).dropna()
        if len(scores) < self.min_coins or self.symbol not in scores:
            return None
        ordered = scores.sort_values()
        if self.side == "both" and self.symbol in ordered.index[:self.top_n]:
            return "long"
        if self.symbol in ordered.index[-self.top_n:] and (self.side == "both" or scores[self.symbol] > 0):
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
        return self.group(frame) != ("long" if direction == LONG else "short")
