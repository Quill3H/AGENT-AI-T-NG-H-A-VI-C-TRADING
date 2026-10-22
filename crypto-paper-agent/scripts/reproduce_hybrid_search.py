#!/usr/bin/env python3
"""Round 2 of docs/research/2026-10-16-futures-search.md: trend + carry on BTC, ETH, SOL (paper only).

  python scripts/reproduce_hybrid_search.py --data-dir <binance-vision-usdm dir> --stage dev
  python scripts/reproduce_hybrid_search.py --data-dir <dir> --stage final --candidate H2
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_carry, run_vision_portfolio  # noqa: E402
from scripts.reproduce_futures_search import BTC_VARIANTS, VARIANTS, pick  # noqa: E402
from src.report.performance_summary import curve_summary  # noqa: E402

DEV = ("2021-01-01", "2025-12-31")
FINAL = ("2026-01-01", "2026-09-30")
SYMBOLS = run_vision_portfolio.SYMBOLS
TREND = ("donchian_trend", [str(BTC_VARIANTS / "donchian_s1_long_short.yaml"), str(VARIANTS / "owner_risk_10pct.yaml")])
CANDIDATES = {"H1": {"carry": 1.0}, "H2": {"carry": 0.5, "trend": 0.5}, "H3": {"trend": 1.0}}


def carry_sleeve(data_dir, start, end, capital, symbol):
    curve, summary = run_vision_carry.run(data_dir, start, end, initial_capital=capital, symbol=symbol)
    return curve, summary["completed_trades"]


def run(data_dir, mix, start, end, pool, capital=10000.0):
    jobs = []
    for kind, weight in mix.items():
        share = capital * weight / len(SYMBOLS)
        for symbol in SYMBOLS:
            if kind == "carry":
                jobs.append((kind, symbol, share, pool.submit(carry_sleeve, data_dir, start, end, share, symbol)))
            else:
                jobs.append((kind, symbol, share, pool.submit(
                    run_vision_portfolio.sleeve, data_dir, TREND[0], start, end, TREND[1], 1.0, share, symbol)))
    curves, shares, pnl, trades, sleeves = [], [], [], 0, {}
    begin, stop = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    for kind, symbol, share, job in jobs:
        curve, extra = job.result()
        curves.append(curve)
        shares.append(share)
        sleeve_pnl = extra if kind == "trend" else []
        pnl += sleeve_pnl
        trades += len(extra) if kind == "trend" else extra
        part = curve_summary(curve, share, begin, stop, sleeve_pnl)
        part.pop("monthly", None)
        sleeves[f"{kind} {symbol}"] = part
    summary = curve_summary(run_vision_portfolio.combine_curves(curves, shares), capital, begin, stop, pnl)
    summary["completed_trades"] = trades
    summary["note"] = "trade statistics cover the trend sleeves only; carry baskets are counted in completed_trades"
    summary["sleeves"] = sleeves
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--stage", choices=["dev", "final"], required=True)
    parser.add_argument("--candidate", choices=sorted(CANDIDATES))
    parser.add_argument("--output")
    args = parser.parse_args()
    out = {}
    with ProcessPoolExecutor(4) as pool:
        if args.stage == "dev":
            for key, mix in CANDIDATES.items():
                out[key] = run(args.data_dir, mix, *DEV, pool)
            chosen, clean = pick(out)
            out["selection"] = {"chosen": chosen, "met_no_losing_year_rule": clean}
        else:
            if not args.candidate:
                parser.error("--candidate is required for the final stage")
            out[f"final 2026-01..09 | {args.candidate}"] = run(args.data_dir, CANDIDATES[args.candidate], *FINAL, pool)
    text = json.dumps(out, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
