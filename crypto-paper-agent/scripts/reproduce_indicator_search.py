#!/usr/bin/env python3
"""Round 3 of the futures research: docs/research/2026-10-16-indicator-search.md (paper only, no funding strategy).

  python scripts/reproduce_indicator_search.py --data-dir <binance-vision-usdm dir> --stage dev
  python scripts/reproduce_indicator_search.py --data-dir <dir> --stage final --candidate I4
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_portfolio  # noqa: E402
from scripts.reproduce_futures_search import BTC_VARIANTS, VARIANTS, score  # noqa: E402

DEV = ("2021-01-01", "2023-12-31")
VALIDATION = ("2024-01-01", "2026-09-30")
HOLDOUT = ("2021-01-01", "2026-09-30")
CORE = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
HOLDOUT_COINS = ("BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT")
RISK = [str(VARIANTS / "owner_risk_10pct.yaml")]
MIN_TRADES = 30
CANDIDATES = {
    "I1": ("tsmom", []),
    "I2": ("rsi2_reversion", []),
    "I3": ("squeeze_breakout", []),
    "I4": ("mtf_trend", []),
    "I5": ("adx_donchian", []),
    "I6": ("supertrend", []),
}
REFERENCE = {"F3 (reference, not selectable)": ("donchian_trend", [str(BTC_VARIANTS / "donchian_s1_long_short.yaml")])}


def pick(results):
    """Protocol rule: best return/DD among candidates with no losing dev year and >= 30 trades."""
    clean = {k: v for k, v in results.items()
             if min(v["yearly_return_pct"].values()) > 0 and v["completed_trades"] >= MIN_TRADES}
    pool = clean or results
    return max(pool, key=lambda k: score(pool[k])), bool(clean)


def run(data_dir, strategy, files, window, symbols, pool):
    return run_vision_portfolio.run(data_dir, strategy, *window, files + RISK, symbols=symbols, pool=pool)


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
            for key, (strategy, files) in {**CANDIDATES, **REFERENCE}.items():
                out[key] = run(args.data_dir, strategy, files, DEV, CORE, pool)
            chosen, clean = pick({k: v for k, v in out.items() if k in CANDIDATES})
            out["selection"] = {"chosen": chosen, "met_rule": clean}
        else:
            if not args.candidate:
                parser.error("--candidate is required for the final stage")
            strategy, files = CANDIDATES[args.candidate]
            out["validation BTC/ETH/SOL 2024-01..2026-09"] = run(args.data_dir, strategy, files, VALIDATION, CORE, pool)
            out["holdout BNB/XRP/DOGE/ADA 2021-01..2026-09"] = run(args.data_dir, strategy, files, HOLDOUT, HOLDOUT_COINS, pool)
            out["holdout cost x2"] = run_vision_portfolio.run(
                args.data_dir, strategy, *HOLDOUT, files + RISK, 2.0, symbols=HOLDOUT_COINS, pool=pool)
    text = json.dumps(out, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
