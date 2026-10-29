#!/usr/bin/env python3
"""Round 11 of the futures research: raise the win rate of the swing EMA method with rules
from IncomeSharks, Nebraskangooner and Big Cheds, docs/research/2026-10-18-round11-traders.md
(paper only).

  python scripts/reproduce_round11.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_round11.py --data-dir <forward dir> --stage check --candidate P1 --risk 5% --frozen-commit <sha> --output check.json

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

from scripts.reproduce_round8 import FINAL as OCTOBER, MAX_DD, RISKS as ALL_RISKS, average_month, pick, run_legs, step_reached  # noqa: E402
from scripts.reproduce_sessions import TOP10  # noqa: E402
from scripts.reproduce_trading_styles import CORE, DEV, FINAL_B  # noqa: E402
from src.research import ledger  # noqa: E402

ROUND = 11
RISKS = {r: ALL_RISKS[r] for r in ("2%", "5%")}
SEEN_ALL = ("2021-01-01", "2026-09-30")
CANDIDATES = {
    "C1": ([("swing_ema_pullback_long", [])], "reference: round-8 swing EMA pullback, long only"),
    "P1": ([("swing_ema_long_half_1r", [])], "C1, half taken at 1R then stop to break-even"),
    "P2": ([("swing_ema_long_thirds", [])], "C1 scaled out in thirds at 1R and 2R (Big Cheds)"),
    "S1": ([("swing_ema_sharks", [])], "C1 with IncomeSharks daily Supertrend (10,3)+(10,2) and OBV filter"),
    "X1": ([("swing_ema_sharks_half_1r", [])], "S1, half taken at 1R"),
    "S2": ([("supertrend_obv", [])], "IncomeSharks dual Supertrend + OBV, 4h long"),
    "G1": ([("gooner_breakout", [])], "Nebraskangooner 30-bar high breakout on 1.5x volume, 2R target"),
    "K1": ([("cheds_ema_pullback", [])], "Big Cheds 8 EMA pullback in a daily uptrend"),
    "K2": ([("cheds_ema_pullback_thirds", [])], "K1 scaled out in thirds at 1R and 2R"),
}
SELECTABLE = tuple(CANDIDATES)


def win_pick(results):
    """Plan rule: no losing development year, max drawdown <= 35% and an average month at
    least C1's at the same risk; among those the highest win rate (then average month).
    Returns (label, rule met)."""
    eligible = {}
    for r in RISKS:
        floor = average_month(results[f"C1 risk {r}"])
        for k in SELECTABLE:
            v = results[f"{k} risk {r}"]
            if v["max_drawdown_pct"] <= MAX_DD and min(v["yearly_return_pct"].values()) > 0 and average_month(v) >= floor:
                eligible[f"{k} risk {r}"] = v
    if not eligible:
        chosen, rule = pick(results)
        return chosen, "fallback " + rule
    return max(eligible, key=lambda k: (eligible[k]["win_rate_pct"], average_month(eligible[k]))), "full"


def jobs_for(stage, candidate=None, risk=None):
    """(label, ledger stage, key, window, risk, cost[, symbols])."""
    if stage == "dev":
        return [(f"{k} risk {r}", "dev", k, DEV, r, 1.0) for k in CANDIDATES for r in RISKS]
    return [(f"B: BTC/ETH/SOL 2024-01..2026-09 (seen), risk {risk}", "validation", candidate, FINAL_B, risk, 1.0),
            ("B, costs x2", "validation", candidate, FINAL_B, risk, 2.0),
            (f"BTC/ETH/SOL 2026-10-01..10-17 (seen), risk {risk}", "validation", candidate, OCTOBER, risk, 1.0),
            (f"Top-10 2021-01..2026-09 (seen), risk {risk}", "validation", candidate, SEEN_ALL, risk, 1.0, TOP10),
            ("Reference C1 B: BTC/ETH/SOL 2024-01..2026-09 (seen), risk 5%", "validation", "C1", FINAL_B, "5%", 1.0)]


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
            symbols = job[6] if len(job) > 6 else CORE
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
        chosen, rule = win_pick({f"{k} risk {r}": out[f"{k} risk {r}"] for k in SELECTABLE for r in RISKS})
        out["selection"] = {"chosen": chosen, "rule_met": rule, "step_reached_pct": step_reached(out[chosen]),
                            "round8_rule_pick": pick({f"{k} risk {r}": out[f"{k} risk {r}"] for k in SELECTABLE for r in RISKS})}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
