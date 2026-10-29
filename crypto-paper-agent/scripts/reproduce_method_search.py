#!/usr/bin/env python3
"""Re-run every attempt in docs/research/2026-10-16-method-search.md and print one JSON document.

Paper simulation only. Development window 2021-2023 for all attempts; the frozen
candidate is then scored on 2024-2025 and on the owner's full 2021-2025 window.

  python scripts/reproduce_method_search.py --data-dir <binance-vision-btcusdt dir> --output results.json
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_backtest, run_vision_carry  # noqa: E402
from src.report.performance_summary import curve_summary, equity_series  # noqa: E402

VARIANTS = PROJECT_ROOT / "config" / "research" / "method_search_2026_10_16"
DEV = ("2021-01-01", "2023-12-31")
FINAL = ("2024-01-01", "2025-12-31")
FULL = ("2021-01-01", "2025-12-31")
DIRECTIONAL = [
    ("1 trend_following", "trend_following", []),
    ("2 breakout_retest", "breakout_retest", []),
    ("3 donchian 20/10 long+short", "donchian_trend", ["donchian_s1_long_short.yaml"]),
    ("4 donchian 20/10 long only", "donchian_trend", ["donchian_s1_long_only.yaml"]),
    ("5 donchian 55/20 long+short", "donchian_trend", ["donchian_s2_long_short.yaml"]),
    ("6 donchian 55/20 long only", "donchian_trend", ["donchian_s2_long_only.yaml"]),
]
CARRY = [("7 carry min_apr 0.15 (frozen)", []), ("8 carry min_apr 0.10", ["carry_min_apr_10.yaml"])]


def directional(data_dir, strategy, files, window):
    return run_vision_backtest.run(data_dir, strategy, *window, [str(VARIANTS / f) for f in files])


def carry(data_dir, files, window, cost=1.0):
    return run_vision_carry.run(data_dir, *window, [str(VARIANTS / f) for f in files], cost)[1]


def half_and_half(data_dir):
    """Attempt 9: 5,000 USDT in attempt 3 and 5,000 USDT in attempt 7, summed hour by hour."""
    trend_files = [str(VARIANTS / "donchian_s1_long_short.yaml")]
    broker = run_vision_backtest.run(data_dir, "donchian_trend", *DEV, trend_files, initial_capital=5000.0, summarize=False)
    trend = equity_series(broker.account_snapshots)
    carry_curve, _ = run_vision_carry.run(data_dir, *DEV, initial_capital=5000.0)
    index = trend.index.union(carry_curve.index)
    total = trend.reindex(index).ffill().fillna(5000.0) + carry_curve.reindex(index).ffill().fillna(5000.0)
    start, end = pd.Timestamp(DEV[0], tz="UTC"), pd.Timestamp(DEV[1], tz="UTC") + pd.Timedelta(days=1)
    return curve_summary(total, 10000.0, start, end, [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    d = args.data_dir
    jobs = {}
    with ProcessPoolExecutor() as pool:
        for name, strategy, files in DIRECTIONAL:
            jobs[f"dev | {name}"] = pool.submit(directional, d, strategy, files, DEV)
        for name, files in CARRY:
            jobs[f"dev | {name}"] = pool.submit(carry, d, files, DEV)
        for cost in (2.0, 3.0):
            jobs[f"dev | 7 carry cost x{cost:g}"] = pool.submit(carry, d, [], DEV, cost)
        jobs["dev | 9 half donchian 20/10 + half carry"] = pool.submit(half_and_half, d)
        jobs["final 2024-2025 | 7 carry"] = pool.submit(carry, d, [], FINAL)
        jobs["full 2021-2025 | 7 carry"] = pool.submit(carry, d, [], FULL)
        jobs["full 2021-2025 | 7 carry cost x2"] = pool.submit(carry, d, [], FULL, 2.0)
        results = {key: job.result() for key, job in jobs.items()}
    text = json.dumps(results, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
