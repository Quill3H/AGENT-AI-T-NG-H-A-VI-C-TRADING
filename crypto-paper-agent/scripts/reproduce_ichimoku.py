#!/usr/bin/env python3
"""Round 9 of the futures research: Ichimoku cloud, docs/research/2026-10-19-ichimoku.md (paper only).

  python scripts/reproduce_ichimoku.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_ichimoku.py --data-dir <forward dir> --stage final --candidate I1-4h --risk 2% --frozen-commit <sha> --output final.json

Finished runs are written to --output at once (rerunning resumes) and appended to the
research ledger (src/research/ledger.py).
"""
import argparse
import json
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.reproduce_round8 import FINAL as OCTOBER, RISKS as ALL_RISKS, pick, run_legs, step_reached  # noqa: E402
from scripts.reproduce_sessions import TOP10  # noqa: E402
from scripts.reproduce_trading_styles import CORE, DEV, FINAL_B  # noqa: E402
from src.research import ledger  # noqa: E402

ROUND = 9
RISKS = {r: ALL_RISKS[r] for r in ("2%", "5%")}
SEEN_ALL = ("2021-01-01", "2026-09-30")
# the 7 top-10 coins whose 2026-10-01..17 bars no final has used (round 8 spent BTC/ETH/SOL)
FRESH = tuple(s for s in TOP10 if s not in CORE)
CANDIDATES = {
    "I1-4h": ("ichimoku_tk_4h", "Tenkan/Kijun cross with cloud and Chikou filter, 4h"),
    "I2-4h": ("ichimoku_kumo_4h", "cloud breakout, 4h"),
    "I1-1h": ("ichimoku_tk_1h", "Tenkan/Kijun cross, 1h"),
    "I2-1h": ("ichimoku_kumo_1h", "cloud breakout, 1h"),
    "I1-15m": ("ichimoku_tk_15m", "Tenkan/Kijun cross, 15m"),
    "I2-15m": ("ichimoku_kumo_15m", "cloud breakout, 15m"),
    "I1-4h-long": ("ichimoku_tk_4h_long", "I1-4h long only (round-8 lesson: longs carried W1)"),
    "I2-4h-long": ("ichimoku_kumo_4h_long", "I2-4h long only"),
}


def jobs_for(stage, candidate=None, risk=None):
    """(label, ledger stage, key, window, symbols, risk, cost)."""
    if stage == "dev":
        return [(f"{k} risk {r}", "dev", k, DEV, CORE, r, 1.0) for k in CANDIDATES for r in RISKS]
    name = "/".join(s.replace("USDT", "") for s in FRESH)
    return [(f"Final: {name} 2026-10-01..10-17, risk {risk}", "final", candidate, OCTOBER, FRESH, risk, 1.0),
            ("Final, costs x2", "final", candidate, OCTOBER, FRESH, risk, 2.0),
            (f"BTC/ETH/SOL 2026-10-01..10-17 (seen in round 8), risk {risk}", "validation", candidate, OCTOBER, CORE, risk, 1.0),
            (f"B: BTC/ETH/SOL 2024-01..2026-09 (seen), risk {risk}", "validation", candidate, FINAL_B, CORE, risk, 1.0),
            (f"Top-10 2021-01..2026-09 (seen), risk {risk}", "validation", candidate, SEEN_ALL, TOP10, risk, 1.0)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--stage", choices=["dev", "final"], required=True)
    parser.add_argument("--candidate", choices=sorted(CANDIDATES))
    parser.add_argument("--risk", choices=sorted(RISKS))
    parser.add_argument("--frozen-commit")
    parser.add_argument("--output", required=True)
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    if args.stage == "final" and not (args.candidate and args.risk and args.frozen_commit):
        parser.error("--candidate, --risk and --frozen-commit are required for the final stage")
    output = Path(args.output)
    out = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    out.pop("selection", None)
    jobs = [j for j in jobs_for(args.stage, args.candidate, args.risk) if j[0] not in out]
    if any(j[1] == "final" for j in jobs):
        ledger.check_untouched(FRESH, *OCTOBER, ledger.load())
    lock = threading.Lock()

    def save():
        output.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    with ProcessPoolExecutor(4) as pool:
        def one(job):
            label, stage, key, window, symbols, risk, cost = job
            strategy, source = CANDIDATES[key]
            summary = run_legs(args.data_dir, [(strategy, [])], *window, RISKS[risk], cost, symbols=symbols, pool=pool)
            summary["step_reached_pct"] = step_reached(summary)
            with lock:
                out[label] = summary
                save()
                if not args.no_ledger:
                    ledger.record(ROUND, stage, key, strategy, label, *window, symbols, risk, summary,
                                  source=source, config_files=RISKS[risk], frozen_commit=args.frozen_commit)

        with ThreadPoolExecutor(6) as threads:
            for future in [threads.submit(one, job) for job in jobs]:
                future.result()
    if args.stage == "dev":
        chosen, rule = pick({k: v for k, v in out.items() if k != "selection"})
        out["selection"] = {"chosen": chosen, "rule_met": rule, "step_reached_pct": step_reached(out[chosen])}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
