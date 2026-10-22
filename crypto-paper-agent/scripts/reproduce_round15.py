#!/usr/bin/env python3
"""Round 15 of the futures research: funding-rate (crowding) rules on the top-10
perpetuals, docs/research/2026-10-19-round15-funding.md (paper only).

  python scripts/reproduce_round12.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_round12.py --data-dir <forward dir> --stage check --candidate F2 --risk 5% --frozen-commit <sha> --output check.json

Every top-10 bar up to 2026-10-17 has been used by an earlier final test, so after the
freeze this round can only run `validation` checks on seen data; new evidence comes from
the forward stage of scripts/reproduce_round8.py style runs. Finished runs are written to
--output at once (rerunning resumes) and appended to the research ledger.
"""
import argparse
import json
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.reproduce_round8 import FINAL as OCTOBER, RISKS as ALL_RISKS, average_month, pick, run_legs, step_reached  # noqa: E402
from scripts.reproduce_sessions import TOP10  # noqa: E402
from scripts.reproduce_trading_styles import DEV, FINAL_B  # noqa: E402
from src.research import ledger  # noqa: E402

ROUND = 15
RISKS = {r: ALL_RISKS[r] for r in ("2%", "5%")}
CANDIDATES = {
    "C1": ([("swing_ema_pullback_long", [])], "reference: round-8 swing EMA pullback, long only, on the same top-10"),
    "F1": ([("c1_funding_filter", [])], "C1, no new long while 7-day funding > its 180-day 90th percentile (BIS: high carry predicts crashes)"),
    "F2": ([("funding_carry_ls", [])], "weekly: long the 3 lowest, short the 3 highest 7-day mean funding"),
    "F3": ([("funding_crowded_short", [])], "weekly: short the 3 highest 7-day mean funding when positive"),
}
SELECTABLE = tuple(k for k in CANDIDATES if k != "C1")


def jobs_for(stage, candidate=None, risk=None):
    """(label, ledger stage, key, window, risk, cost[, symbols])."""
    if stage == "dev":
        return [(f"{k} risk {r}", "dev", k, DEV, r, 1.0) for k in CANDIDATES for r in RISKS]
    return [(f"B: top-10 2024-01..2026-09 (seen), risk {risk}", "validation", candidate, FINAL_B, risk, 1.0),
            ("B, costs x2", "validation", candidate, FINAL_B, risk, 2.0),
            (f"Top-10 2026-10-01..10-17 (seen), risk {risk}", "validation", candidate, OCTOBER, risk, 1.0),
            (f"Reference C1 B: top-10 2024-01..2026-09 (seen), risk {risk}", "validation", "C1", FINAL_B, risk, 1.0)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--stage", choices=["dev", "check"], required=True)
    parser.add_argument("--candidate", choices=SELECTABLE)
    parser.add_argument("--risk", choices=sorted(RISKS))
    parser.add_argument("--frozen-commit")
    parser.add_argument("--output", required=True)
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    if args.stage == "check" and not (args.candidate and args.risk and args.frozen_commit):
        parser.error("--candidate, --risk and --frozen-commit are required for the check stage")
    output = Path(args.output)
    out = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    out.pop("selection", None)
    jobs = [j for j in jobs_for(args.stage, args.candidate, args.risk) if j[0] not in out]
    lock = threading.Lock()

    def save():
        output.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    with ProcessPoolExecutor(4) as pool:
        def one(job):
            label, stage, key, window, risk, cost = job[:6]
            symbols = job[6] if len(job) > 6 else TOP10
            legs, source = CANDIDATES[key]
            summary = run_legs(args.data_dir, legs, *window, RISKS[risk], cost, symbols=symbols, pool=pool)
            summary["step_reached_pct"] = step_reached(summary)
            with lock:
                out[label] = summary
                save()
                if not args.no_ledger:
                    ledger.record(ROUND, stage, key, "+".join(s for s, _ in legs), label, *window, symbols, risk, summary,
                                  source=source, config_files=RISKS[risk], frozen_commit=args.frozen_commit)

        with ThreadPoolExecutor(6) as threads:
            for future in [threads.submit(one, job) for job in jobs]:
                future.result()
    if args.stage == "dev":
        chosen, rule = pick({f"{k} risk {r}": out[f"{k} risk {r}"] for k in SELECTABLE for r in RISKS})
        out["selection"] = {"chosen": chosen, "rule_met": rule, "step_reached_pct": step_reached(out[chosen]),
                            "beats_c1_same_risk": average_month(out[chosen]) > average_month(out[f"C1 risk {chosen.split()[-1]}"])}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
