#!/usr/bin/env python3
"""Round 16 of the futures research: funding carry at the bank-rate threshold and a three-sleeve
portfolio (carry + trend + pairs), docs/research/2026-10-20-round16-carry-portfolio.md (paper only).

  python scripts/reproduce_round16.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_round16.py --data-dir <binance-vision-usdm dir> --stage check --candidate M2 --risk 5% --frozen-commit <sha> --output check.json

Spot klines exist for BTC/ETH/SOL only and end 2026-09-30, so the carry sleeves run on those three
coins and there is no October check. Finished runs are written to --output at once (rerunning
resumes) and appended to the research ledger.
"""
import argparse
import json
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_carry, run_vision_portfolio  # noqa: E402
from scripts.reproduce_round8 import RISKS as ALL_RISKS, average_month, pick, step_reached  # noqa: E402
from scripts.reproduce_sessions import TOP10  # noqa: E402
from scripts.reproduce_trading_styles import CORE, DEV, FINAL_B  # noqa: E402
from src.report.performance_summary import curve_summary  # noqa: E402
from src.research import ledger  # noqa: E402

ROUND = 16
RISKS = {r: ALL_RISKS[r] for r in ("2%", "5%")}
CARRY = PROJECT_ROOT / "config" / "research" / "round16_2026_10_20"
CARRY_6, CARRY_10 = [str(CARRY / "carry_min_apr_6pct.yaml")], [str(CARRY / "carry_min_apr_10pct.yaml")]
# sleeve: (kind, strategy or carry config, symbols, weight)
CANDIDATES = {
    "K1": ([("carry", CARRY_6, CORE, 1.0)], "spot/perp funding baskets when funding >= 6% a year (bank rate), BTC/ETH/SOL"),
    "K2": ([("carry", CARRY_10, CORE, 1.0)], "spot/perp funding baskets when funding >= 10% a year, BTC/ETH/SOL"),
    "M2": ([("carry", CARRY_6, CORE, 1 / 3), ("rule", "swing_ema_pullback_long", TOP10, 1 / 3),
            ("rule", "pairs_ggr_12m", TOP10, 1 / 3)], "one third each: K1 carry, C1 trend (top-10), P1 pairs (top-10)"),
}
SELECTABLE = tuple(CANDIDATES)
NO_RISK = ("K1", "K2")  # carry baskets are sized by notional, not by risk per trade


def carry_sleeve(data_dir, start, end, files, cost, capital, symbol):
    curve, summary = run_vision_carry.run(data_dir, start, end, files, cost, initial_capital=capital, symbol=symbol)
    return curve, [], summary["completed_trades"]


def rule_sleeve(data_dir, strategy, start, end, files, cost, capital, symbol):
    curve, pnl = run_vision_portfolio.sleeve(data_dir, strategy, start, end, files, cost, capital, symbol)
    return curve, pnl, len(pnl)


def run_mix(data_dir, key, start, end, risk, cost, pool, capital=10000.0):
    jobs = []
    for kind, what, symbols, weight in CANDIDATES[key][0]:
        share = capital * weight / len(symbols)
        for symbol in symbols:
            if kind == "carry":
                jobs.append(pool.submit(carry_sleeve, data_dir, start, end, what, cost, share, symbol))
            else:
                jobs.append(pool.submit(rule_sleeve, data_dir, what, start, end, RISKS[risk], cost, share, symbol))
            jobs[-1].share = share
    curves, shares, pnl, trades = [], [], [], 0
    for job in jobs:
        curve, sleeve_pnl, count = job.result()
        curves.append(curve)
        shares.append(job.share)
        pnl += sleeve_pnl
        trades += count
    begin, stop = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    summary = curve_summary(run_vision_portfolio.combine_curves(curves, shares), capital, begin, stop, pnl)
    summary["completed_trades"] = trades
    summary["note"] = "win rate and trade P&L cover the rule sleeves only; carry baskets count in completed_trades"
    return summary


def jobs_for(stage, candidate=None, risk=None):
    """(label, ledger stage, key, window, risk, cost)."""
    if stage == "dev":
        return [(f"{k}" if k in NO_RISK else f"{k} risk {r}", "dev", k, DEV, None if k in NO_RISK else r, 1.0)
                for k in CANDIDATES for r in (["5%"] if k in NO_RISK else list(RISKS))]
    label = candidate if candidate in NO_RISK else f"{candidate} risk {risk}"
    return [(f"B: 2024-01..2026-09 (seen), {label}", "validation", candidate, FINAL_B, risk, 1.0),
            ("B, costs x2", "validation", candidate, FINAL_B, risk, 2.0)]


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
    if args.stage == "check" and not (args.candidate and args.frozen_commit):
        parser.error("--candidate and --frozen-commit are required for the check stage")
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
            summary = run_mix(args.data_dir, key, *window, risk or "5%", cost, pool)
            summary["step_reached_pct"] = step_reached(summary)
            sleeves = CANDIDATES[key][0]
            with lock:
                out[label] = summary
                save()
                if not args.no_ledger:
                    ledger.record(ROUND, stage, key, "+".join(s if isinstance(s, str) else "carry" for _, s, _, _ in sleeves), label,
                                  *window, sorted({c for _, _, syms, _ in sleeves for c in syms}), risk or "n/a", summary,
                                  source=CANDIDATES[key][1], config_files=RISKS.get(risk or "", []),
                                  frozen_commit=args.frozen_commit)

        with ThreadPoolExecutor(3) as threads:
            for future in [threads.submit(one, job) for job in jobs]:
                future.result()
    if args.stage == "dev":
        chosen, rule = pick({k: v for k, v in out.items() if k != "selection"})
        out["selection"] = {"chosen": chosen, "rule_met": rule, "step_reached_pct": step_reached(out[chosen])}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
