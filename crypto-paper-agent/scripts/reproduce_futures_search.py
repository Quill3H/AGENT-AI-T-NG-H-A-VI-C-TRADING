#!/usr/bin/env python3
"""Re-run the 3-coin futures search in docs/research/2026-10-16-futures-search.md (paper only).

  python scripts/reproduce_futures_search.py --data-dir <binance-vision-usdm dir> --stage dev
  python scripts/reproduce_futures_search.py --data-dir <dir> --stage final --candidate F3

The dev stage scores every candidate on 2021-2023.  The final stage scores one
frozen candidate on 2024-2025, on 2021-2025, with costs x2, and the risk what-ifs.
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_portfolio  # noqa: E402

BTC_VARIANTS = PROJECT_ROOT / "config" / "research" / "method_search_2026_10_16"
VARIANTS = PROJECT_ROOT / "config" / "research" / "futures_search_2026_10_16"
DEV = ("2021-01-01", "2023-12-31")
FINAL = ("2024-01-01", "2025-12-31")
FULL = ("2021-01-01", "2025-12-31")
CANDIDATES = {
    "F1": ("trend_following", []),
    "F2": ("breakout_retest", []),
    "F3": ("donchian_trend", [BTC_VARIANTS / "donchian_s1_long_short.yaml"]),
    "F4": ("donchian_trend", [BTC_VARIANTS / "donchian_s2_long_short.yaml"]),
    "F5": ("donchian_trend", [VARIANTS / "donchian_4h_20_10.yaml"]),
    "F6": ("donchian_trend", [VARIANTS / "donchian_4h_55_20.yaml"]),
}
WHAT_IFS = {"risk 5%": VARIANTS / "whatif_risk_5pct.yaml", "risk 10%": VARIANTS / "whatif_risk_10pct.yaml"}


def score(summary):
    return summary["total_return_pct"] / max(summary["max_drawdown_pct"], 0.01)


def pick(dev_results):
    """Selection rule fixed in the protocol: best return/drawdown among candidates with no losing dev year."""
    clean = {k: v for k, v in dev_results.items() if min(v["yearly_return_pct"].values()) > 0}
    pool = clean or dev_results
    best = max(pool, key=lambda k: score(pool[k]))
    return best, bool(clean)


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
            for key, (strategy, files) in CANDIDATES.items():
                out[f"dev | {key} {strategy} {' '.join(f.stem for f in files)}".strip()] = run_vision_portfolio.run(
                    args.data_dir, strategy, *DEV, [str(f) for f in files], pool=pool)
            chosen, clean = pick({k.split()[2]: v for k, v in out.items()})
            out["selection"] = {"chosen": chosen, "met_no_losing_year_rule": clean}
        else:
            if not args.candidate:
                parser.error("--candidate is required for the final stage")
            strategy, files = CANDIDATES[args.candidate]
            files = [str(f) for f in files]
            out["final 2024-2025"] = run_vision_portfolio.run(args.data_dir, strategy, *FINAL, files, pool=pool)
            out["full 2021-2025"] = run_vision_portfolio.run(args.data_dir, strategy, *FULL, files, pool=pool)
            out["full 2021-2025 cost x2"] = run_vision_portfolio.run(args.data_dir, strategy, *FULL, files, 2.0, pool=pool)
            for name, path in WHAT_IFS.items():
                out[f"WHAT-IF {name} | full 2021-2025"] = run_vision_portfolio.run(
                    args.data_dir, strategy, *FULL, files + [str(path)], pool=pool)
    text = json.dumps(out, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
