#!/usr/bin/env python3
"""Run one directional strategy on BTC, ETH and SOL perpetuals as one paper portfolio.

Paper simulation only. The starting capital is split equally into one sleeve per
coin; each sleeve runs through its own paper broker and risk gate, and the
portfolio equity is the hour-by-hour sum of the sleeves.  Because each sleeve
has its own daily-loss breaker, the portfolio-level daily loss can reach the
breaker limit on every sleeve at once; the report shows the combined drawdown.

  python scripts/run_vision_portfolio.py --data-dir <binance-vision-usdm dir> \
      --strategy donchian_trend --start 2021-01-01 --end 2023-12-31
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_backtest  # noqa: E402
from src.report.lifecycles import completed_lifecycles  # noqa: E402
from src.report.performance_summary import curve_summary, equity_series  # noqa: E402

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def combine_curves(curves, starting_capital):
    """Sum sleeve equity curves on their joint timestamps; a sleeve counts its start capital until it has data."""
    index = curves[0].index
    for curve in curves[1:]:
        index = index.union(curve.index)
    total = pd.Series(0.0, index=index)
    for curve, capital in zip(curves, starting_capital):
        total = total + curve.reindex(index).ffill().fillna(capital)
    return total


def sleeve(data_dir, strategy, start, end, overrides, cost_multiplier, capital, symbol):
    broker = run_vision_backtest.run(data_dir, strategy, start, end, overrides, cost_multiplier,
                                     initial_capital=capital, summarize=False, symbol=symbol)
    stop = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    curve = equity_series(broker.account_snapshots)
    curve = curve[curve.index < stop]
    if len(curve):
        curve.iloc[-1] = float(broker.equity)
    trades = completed_lifecycles(broker.trade_history)
    pnl = [float(t["net_pnl"] if isinstance(t, dict) else t.net_pnl) for t in trades]
    return curve, pnl


def run(data_dir, strategy, start, end, overrides=(), cost_multiplier=1.0, capital=10000.0, symbols=SYMBOLS, pool=None):
    share = float(capital) / len(symbols)
    args = [(data_dir, strategy, start, end, list(overrides), cost_multiplier, share, s) for s in symbols]
    results = list(pool.map(sleeve, *zip(*args))) if pool else [sleeve(*a) for a in args]
    begin, stop = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    total = combine_curves([curve for curve, _ in results], [share] * len(symbols))
    summary = curve_summary(total, float(capital), begin, stop, [p for _, pnl in results for p in pnl])
    summary["sleeves"] = {}
    for symbol, (curve, pnl) in zip(symbols, results):
        part = curve_summary(curve, share, begin, stop, pnl)
        part.pop("monthly", None)
        summary["sleeves"][symbol] = part
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--config", action="append", default=[])
    parser.add_argument("--cost-multiplier", type=float, default=1.0)
    parser.add_argument("--output")
    args = parser.parse_args()
    summary = run(args.data_dir, args.strategy, args.start, args.end, args.config, args.cost_multiplier)
    text = json.dumps(summary, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
