"""
src/strategies/pairs.py
=======================
Round-14 pairs trading (docs/research/2026-10-19-round14-pairs.md), after the distance method
of Gatev, Goetzmann and Rouwenhorst, "Pairs Trading: Performance of a Relative-Value
Arbitrage Rule" (Review of Financial Studies, 2006):

- formation: normalise each coin's closes to 1 at the start of the window and pick the
  `top_pairs` pairs with the smallest sum of squared differences between normalised prices;
- trading: renormalise at the start of the trading window; when a pair's spread moves more
  than `entry_sigma` formation standard deviations, short the leg that is high and buy the
  leg that is low; close at the next crossing or at the end of the window; a pair may reopen.

Each coin runs in its own paper sleeve, so a coin's side is the sign of the sum of its legs
over the open pairs. The whole path is computed once from the 4h closes in
`config["runtime"]["data_dir"]`; the side at a bar uses only closes up to that bar.
Every entry carries a stop of `stop_atr` daily ATR(14) from the close.
"""
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from src.strategies.indicator_suite import LONG, SHORT, RuleStrategy, atr, completed_daily


def window_starts(first, last, months, anchor="2020-09-01"):
    """Start of every trading window from `anchor`, one every `months` months."""
    starts = pd.date_range(pd.Timestamp(anchor, tz="UTC"), last, freq=f"{months}MS")
    return [s for s in starts if s > first]


def select_pairs(formation, top_pairs):
    """[(a, b, sigma)] for the `top_pairs` pairs with the smallest sum of squared differences."""
    full = formation.dropna(axis=1, how="any")
    if len(full) < 2 or full.shape[1] < 2:
        return []
    normal = full / full.iloc[0]
    ranked = []
    for a, b in combinations(sorted(normal.columns), 2):
        gap = normal[a] - normal[b]
        ranked.append((float((gap ** 2).sum()), a, b, float(gap.std())))
    ranked.sort()
    return [(a, b, sigma) for _, a, b, sigma in ranked[:top_pairs] if sigma > 0]


def pair_path(trading, base_a, base_b, sigma, entry_sigma):
    """+1 (short a, long b), -1 (long a, short b) or 0 for every bar of the trading window."""
    gap = (trading.iloc[:, 0] / base_a - trading.iloc[:, 1] / base_b).to_numpy()
    state, out = 0, np.zeros(len(gap))
    for i, value in enumerate(gap):
        if np.isnan(value):
            state = 0
        elif state == 0 and abs(value) > entry_sigma * sigma:
            state = 1 if value > 0 else -1
        elif state != 0 and value * state <= 0:  # crossed back
            state = 0
        out[i] = state
    return out


def coin_sides(closes, formation_months, trading_months, top_pairs, entry_sigma):
    """DataFrame of -1/0/+1 per coin and 4h bar: the sign of the coin's net leg."""
    net = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    starts = window_starts(closes.index[0], closes.index[-1], trading_months)
    for start in starts:
        end = start + pd.DateOffset(months=trading_months)
        formation = closes[(closes.index >= start - pd.DateOffset(months=formation_months)) & (closes.index < start)]
        if formation.empty or formation.index[0] > start - pd.DateOffset(months=formation_months) + pd.Timedelta(days=1):
            continue  # the window is not fully covered by data
        trading = closes[(closes.index >= start) & (closes.index < end)]
        for a, b, sigma in select_pairs(formation, top_pairs):
            base = formation.iloc[-1]
            path = pair_path(trading[[a, b]], base[a], base[b], sigma, entry_sigma)
            net.loc[trading.index, a] -= path
            net.loc[trading.index, b] += path
    return np.sign(net)


class PairsDistance(RuleStrategy):
    """P (4h): Gatev-Goetzmann-Rouwenhorst distance pairs on the `rules.universe` coins.
    Enter when this coin's net side changes to long or short; exit when it changes away."""

    name = "PAIRS_DISTANCE"
    window = 120

    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        self.stop_atr = float(self.rules.get("stop_atr", 3.0))
        data_dir = (config.get("runtime") or {}).get("data_dir")
        self.sides = None
        if data_dir:
            closes = self._load(data_dir, list(self.rules.get("universe", [symbol])))
            if symbol in closes:
                self.sides = coin_sides(closes, int(self.rules.get("formation_months", 12)),
                                        int(self.rules.get("trading_months", 6)), int(self.rules.get("top_pairs", 5)),
                                        float(self.rules.get("entry_sigma", 2.0)))[symbol]

    @staticmethod
    def _load(data_dir, universe):
        columns = {}
        for coin in universe:
            path = Path(data_dir) / f"{coin}_perp_4h.parquet"
            if path.is_file():
                columns[coin] = pd.read_parquet(path, columns=["close"])["close"]
        return pd.DataFrame(columns)

    def side(self, when):
        if self.sides is None or when not in self.sides.index:
            return 0
        return int(self.sides.loc[when])

    def entry(self, frame):
        now, before = self.side(frame.index[-1]), self.side(frame.index[-2])
        days = completed_daily(frame)
        if now == 0 or now == before or len(days) < 15:
            return None
        gap = self.stop_atr * float(atr(days, 14).iloc[-1])
        close = float(frame["close"].iloc[-1])
        return (LONG, close - gap) if now > 0 else (SHORT, close + gap)

    def should_exit(self, frame, direction):
        return self.side(frame.index[-1]) != (1 if direction == LONG else -1)
