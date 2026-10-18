#!/usr/bin/env python3
"""Round 10 of the futures research: Wyckoff and Ichimoku on BTC/ETH/SOL only,
docs/research/2026-10-18-wyckoff-ichimoku.md (paper only).

  python scripts/reproduce_round10.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_round10.py --data-dir <forward dir> --stage check --candidate WY2-4h --risk 2% --frozen-commit <sha> --output check.json

Every BTC/ETH/SOL bar up to 2026-10-17 has been used by an earlier final test, so after the
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

from scripts.reproduce_round8 import FINAL as OCTOBER, RISKS as ALL_RISKS, pick, run_legs, step_reached  # noqa: E402
from scripts.reproduce_trading_styles import CORE, DEV, FINAL_B  # noqa: E402
from src.research import ledger  # noqa: E402

ROUND = 10
RISKS = {r: ALL_RISKS[r] for r in ("2%", "5%")}
CANDIDATES = {
    "WY1-4h": ([("wyckoff_spring_run_4h", [])], "Wyckoff spring/upthrust, EMA50 exit, 4h"),
    "WY2-4h": ([("wyckoff_sos_lps_4h", [])], "Wyckoff sign of strength + last point of support, 4h"),
    "WY1-1h": ([("wyckoff_spring_run_1h", [])], "Wyckoff spring/upthrust, EMA50 exit, 1h"),
    "WY2-1h": ([("wyckoff_sos_lps_1h", [])], "Wyckoff SOS + LPS, 1h"),
    "I3-4h": ([("ichimoku_tk_4h_daily", [])], "Ichimoku TK cross with daily cloud filter, 4h"),
    "I4-4h": ([("ichimoku_tk_4h_trail", [])], "Ichimoku TK cross with Kijun trailing stop, 4h"),
    "M1": ([("swing_ema_pullback_long", []), ("ichimoku_tk_4h", []), ("wyckoff_sos_lps_4h", [])],
           "equal-weight round-8 C1 + round-9 I1-4h + WY2-4h"),
    "I1-4h": ([("ichimoku_tk_4h", [])], "reference: round-9 pick"),
    "W3": ([("wyckoff_spring", [])], "reference: round-5 Wyckoff spring with fixed target"),
}
SELECTABLE = ("WY1-4h", "WY2-4h", "WY1-1h", "WY2-1h", "I3-4h", "I4-4h", "M1")


def jobs_for(stage, candidate=None, risk=None):
    """(label, ledger stage, key, window, risk, cost)."""
    if stage == "dev":
        return [(f"{k} risk {r}", "dev", k, DEV, r, 1.0) for k in CANDIDATES for r in RISKS]
    return [(f"B: BTC/ETH/SOL 2024-01..2026-09 (seen), risk {risk}", "validation", candidate, FINAL_B, risk, 1.0),
            ("B, costs x2", "validation", candidate, FINAL_B, risk, 2.0),
            (f"BTC/ETH/SOL 2026-10-01..10-17 (seen), risk {risk}", "validation", candidate, OCTOBER, risk, 1.0)]


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
            label, stage, key, window, risk, cost = job
            legs, source = CANDIDATES[key]
            summary = run_legs(args.data_dir, legs, *window, RISKS[risk], cost, pool=pool)
            summary["step_reached_pct"] = step_reached(summary)
            with lock:
                out[label] = summary
                save()
                if not args.no_ledger:
                    ledger.record(ROUND, stage, key, "+".join(s for s, _ in legs), label, *window, CORE, risk, summary,
                                  source=source, config_files=RISKS[risk], frozen_commit=args.frozen_commit)

        with ThreadPoolExecutor(6) as threads:
            for future in [threads.submit(one, job) for job in jobs]:
                future.result()
    if args.stage == "dev":
        chosen, rule = pick({f"{k} risk {r}": out[f"{k} risk {r}"] for k in SELECTABLE for r in RISKS})
        out["selection"] = {"chosen": chosen, "rule_met": rule, "step_reached_pct": step_reached(out[chosen])}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
