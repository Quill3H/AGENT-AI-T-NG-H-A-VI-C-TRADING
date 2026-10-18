#!/usr/bin/env python3
"""Round 6 of the futures research: docs/research/2026-10-18-candlesticks.md (paper only).

  python scripts/reproduce_candles.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_candles.py --data-dir <dir> --stage final --candidate K1-rr2 --output final.json

Finished runs are written to --output at once; rerunning with the same --output resumes.
"""
import argparse
import json
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_portfolio  # noqa: E402
from scripts.reproduce_indicator_search import pick  # noqa: E402
from scripts.reproduce_trading_styles import CORE, DEV, FINAL_B, RISKS  # noqa: E402

FINAL_A = ("2021-01-01", "2026-09-30")
FRESH = ("XLMUSDT", "BCHUSDT", "UNIUSDT", "AAVEUSDT")
EXITS = PROJECT_ROOT / "config" / "research" / "candles_2026_10_18"
ENTRIES = {"K1": "candle_pullback", "K2": "candle_reversal", "K3": "candle_continuation", "K4": "candle_pullback_1h"}
MODES = ("base", "rr1", "rr2", "sr", "pct", "trail", "indicator")
CANDIDATES = {f"{k}-{m}": (s, m) for k, s in ENTRIES.items() for m in MODES}


def jobs_for(stage, candidate=None):
    """(label, strategy, exit mode, window, symbols, risk, cost)."""
    if stage == "dev":
        return [(f"{key} risk 2%", s, m, DEV, CORE, "2%", 1.0) for key, (s, m) in CANDIDATES.items()]
    s, m = CANDIDATES[candidate]
    if stage == "dev-risk":
        return [(f"{candidate} risk {r}", s, m, DEV, CORE, r, 1.0) for r in ("1%", "10%")]
    jobs = [(f"A: XLM/BCH/UNI/AAVE 2021-01..2026-09, risk {r}", s, m, FINAL_A, FRESH, r, 1.0) for r in RISKS]
    jobs.append(("A, risk 2%, costs x2", s, m, FINAL_A, FRESH, "2%", 2.0))
    jobs += [(f"B: BTC/ETH/SOL 2024-01..2026-09, risk {r}", s, m, FINAL_B, CORE, r, 1.0) for r in RISKS]
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--stage", choices=["dev", "dev-risk", "final"], required=True)
    parser.add_argument("--candidate", choices=sorted(CANDIDATES))
    parser.add_argument("--extra-config", action="append", default=[], help="what-if YAML merged after the risk file")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.stage != "dev" and not args.candidate:
        parser.error("--candidate is required for this stage")
    output = Path(args.output)
    out = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    out.pop("selection", None)
    lock = threading.Lock()

    def save():
        output.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    with ProcessPoolExecutor(4) as pool:
        def one(job):
            label, strategy, mode, window, symbols, risk, cost = job
            files = [str(EXITS / f"exit_{mode}.yaml")] + RISKS[risk] + list(args.extra_config)
            summary = run_vision_portfolio.run(args.data_dir, strategy, *window, files, cost, symbols=symbols, pool=pool)
            with lock:
                out[label] = summary
                save()

        with ThreadPoolExecutor(6) as threads:
            for future in [threads.submit(one, j) for j in jobs_for(args.stage, args.candidate) if j[0] not in out]:
                future.result()
    if args.stage == "dev":
        chosen, clean = pick({key: out[f"{key} risk 2%"] for key in CANDIDATES})
        out["selection"] = {"chosen": chosen, "met_rule": clean}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
