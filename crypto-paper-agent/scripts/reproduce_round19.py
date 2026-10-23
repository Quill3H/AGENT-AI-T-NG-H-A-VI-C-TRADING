#!/usr/bin/env python3
"""Round 19 of the futures research: the owner's r/Daytrading ICT liquidity post (Asia/London
sweep, displacement, HTF FVG, 15m ORB + FVG or a 30m FVG retracement) on BTC/ETH/SOL 5m
perpetuals, docs/research/2026-10-23-round19-ict-sweep-fvg.md (paper only).

  python scripts/reproduce_round19.py --data-dir <forward dir> --pilot-dir <dir with 1m> --stage dev --output dev.json
  python scripts/reproduce_round19.py --data-dir <forward dir> --stage check --candidate L1 --risk 2% --frozen-commit <sha> --output check.json
  python scripts/reproduce_round19.py --data-dir <forward dir> --stage forward --candidate L1 --risk 2% --frozen-commit <sha> --start 2026-10-18 --end <day> --output fwd.json

Every BTC/ETH/SOL bar up to 2026-10-17 has been used by an earlier round: the check stage is
`validation` on seen data (the script asserts check_untouched refuses those windows), and only
the forward stage, which check_untouched must accept, can give new evidence. Finished runs are
written to --output at once (rerunning resumes) and appended to the research ledger.
"""
import argparse
import json
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_backtest, run_vision_portfolio  # noqa: E402
from scripts.reproduce_round8 import FINAL as OCTOBER, RISKS as ALL_RISKS, average_month, pick  # noqa: E402
from scripts.reproduce_trading_styles import CORE, DEV, FINAL_B  # noqa: E402
from src.report.lifecycles import completed_lifecycles  # noqa: E402
from src.report.performance_summary import curve_summary, equity_series  # noqa: E402
from src.research import ledger  # noqa: E402

ROUND = 19
RISKS = {r: ALL_RISKS[r] for r in ("2%", "5%")}
PILOT = ("2023-01-01", "2023-03-31")  # the only months with 1m bars for BTC/ETH/SOL
CANDIDATES = {
    "C1": ("swing_ema_pullback_long", "reference: round-8 swing EMA pullback, long only, on the same BTC/ETH/SOL"),
    "L1": ("ict_orb_fvg", "ICT post trade 1: Asia+London lows swept, displacement, HTF FVG, 15m ORB + 5m FVG, target Asia high"),
    "L2": ("ict_irl_erl", "ICT post trade 2: same context, first retracement into a 30m FVG, fixed 2R"),
    "L3": ("ict_both", "ICT post: L1 and L2, at most one each a day"),
    "P1": ("ict_orb_fvg_1m", "pilot: L1 with 1m entry bars (the post's 1-minute FVG), 2023-01..03 only"),
}
SELECTABLE = ("L1", "L2", "L3")
VARIANTS_TRIED = 7  # L1-L3 x 2%/5% risk + the 1m pilot; costs x2 and C1 are stresses/references
# Forward gate (pre-registered): every line must hold for the pick to join the forward check-in.
GATE_MIN_MONTH = 0.48    # dev average month >= the 5.9%/yr bank deposit
GATE_MAX_DD = 35.0
GATE_MIN_TRADES = 30


def sleeve(data_dir, strategy, start, end, files, cost, capital, symbol):
    """run_vision_portfolio.sleeve plus each trade's net R (net P&L / initial risk in USD)."""
    broker = run_vision_backtest.run(data_dir, strategy, start, end, files, cost, initial_capital=capital,
                                     summarize=False, symbol=symbol)
    stop = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    curve = equity_series(broker.account_snapshots)
    curve = curve[curve.index < stop]
    if len(curve):
        curve.iloc[-1] = float(broker.equity)
    pnl = [float(t["net_pnl"] if isinstance(t, dict) else t.net_pnl) for t in completed_lifecycles(broker.trade_history)]
    r = [t.net_pnl / (abs(t.entry_price - t.initial_stop_loss_price) * t.quantity)
         for t in broker.trade_history if abs(t.entry_price - t.initial_stop_loss_price) * t.quantity > 0]
    return curve, pnl, r


def run_portfolio(data_dir, strategy, start, end, files, cost, pool, capital=10000.0, symbols=CORE):
    share = capital / len(symbols)
    args = [(data_dir, strategy, start, end, list(files), cost, share, s) for s in symbols]
    results = list(pool.map(sleeve, *zip(*args)))
    begin, stop = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    total = run_vision_portfolio.combine_curves([c for c, _, _ in results], [share] * len(symbols))
    summary = curve_summary(total, capital, begin, stop, [p for _, pnl, _ in results for p in pnl])
    rs = [x for _, _, r in results for x in r]
    summary["mean_net_r"] = round(float(np.mean(rs)), 3) if rs else None
    summary["sleeves"] = {}
    for symbol, (curve, pnl, r) in zip(symbols, results):
        part = curve_summary(curve, share, begin, stop, pnl)
        part.pop("monthly", None)
        part["mean_net_r"] = round(float(np.mean(r)), 3) if r else None
        summary["sleeves"][symbol] = part
    return summary


def gate(dev, dev_costs2, seen):
    """Pre-registered forward gate; returns {line: passed}."""
    return {"dev average month >= 0.48%": average_month(dev) >= GATE_MIN_MONTH,
            "dev max DD <= 35%": dev["max_drawdown_pct"] <= GATE_MAX_DD,
            "dev trades >= 30": dev["completed_trades"] >= GATE_MIN_TRADES,
            "dev costs x2 return > 0": dev_costs2["total_return_pct"] > 0,
            "seen 2024-01..2026-09 return > 0": seen["total_return_pct"] > 0}


def jobs_for(stage, candidate=None, risk=None, start=None, end=None):
    """(label, ledger stage, key, window, risk, cost, data dir key)."""
    if stage == "dev":
        jobs = [(f"{k} risk {r}", "dev", k, DEV, r, 1.0, "data") for k in ("C1",) + SELECTABLE for r in RISKS]
        jobs += [(f"{k} risk {r}, costs x2", "dev-costs", k, DEV, r, 2.0, "data") for k in SELECTABLE for r in RISKS]
        jobs += [("P1 pilot 1m, risk 2%", "dev-pilot", "P1", PILOT, "2%", 1.0, "pilot"),
                 ("L1 pilot window 5m, risk 2%", "dev-pilot", "L1", PILOT, "2%", 1.0, "pilot")]
        return jobs
    if stage == "check":
        return [(f"B: BTC/ETH/SOL 2024-01..2026-09 (seen), risk {risk}", "validation", candidate, FINAL_B, risk, 1.0, "data"),
                ("B, costs x2", "validation", candidate, FINAL_B, risk, 2.0, "data"),
                (f"BTC/ETH/SOL 2026-10-01..10-17 (seen), risk {risk}", "validation", candidate, OCTOBER, risk, 1.0, "data"),
                (f"Reference C1 B: BTC/ETH/SOL 2024-01..2026-09 (seen), risk {risk}", "validation", "C1", FINAL_B, risk, 1.0, "data")]
    return [(f"Forward {start}..{end}: {candidate} risk {risk}", "forward", candidate, (start, end), risk, 1.0, "data")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--pilot-dir", help="directory with BTC/ETH/SOL 1m and 5m bars (dev pilot)")
    parser.add_argument("--stage", choices=["dev", "check", "forward"], required=True)
    parser.add_argument("--candidate", choices=SELECTABLE)
    parser.add_argument("--risk", choices=sorted(RISKS))
    parser.add_argument("--frozen-commit")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--output", required=True)
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    if args.stage != "dev" and not (args.candidate and args.risk and args.frozen_commit):
        parser.error("--candidate, --risk and --frozen-commit are required after the dev stage")
    if args.stage == "dev" and not args.pilot_dir:
        parser.error("--pilot-dir is required for the dev stage")
    if args.stage == "forward" and not (args.start and args.end):
        parser.error("--start and --end are required for the forward stage")
    records = ledger.load()
    if args.stage == "check":
        for window in (FINAL_B, OCTOBER):  # seen data: must never be relabelled as a final test
            try:
                ledger.check_untouched(CORE, *window, records)
            except ValueError:
                continue
            raise SystemExit(f"{window} is not spent; this round's protocol expects it to be seen data")
    if args.stage == "forward":
        ledger.check_untouched(CORE, args.start, args.end, records)
    output = Path(args.output)
    out = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    out.pop("selection", None)
    dirs = {"data": args.data_dir, "pilot": args.pilot_dir}
    jobs = [j for j in jobs_for(args.stage, args.candidate, args.risk, args.start, args.end) if j[0] not in out]
    lock = threading.Lock()

    def save():
        output.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    with ProcessPoolExecutor(4) as pool:
        def one(job):
            label, stage, key, window, risk, cost, where = job
            strategy, source = CANDIDATES[key]
            summary = run_portfolio(dirs[where], strategy, *window, RISKS[risk], cost, pool)
            with lock:
                out[label] = summary
                save()
                if not args.no_ledger:
                    ledger.record(ROUND, stage, key, strategy, label, *window, CORE, risk, summary, source=source,
                                  config_files=RISKS[risk], frozen_commit=args.frozen_commit,
                                  variants_tried=VARIANTS_TRIED)

        with ThreadPoolExecutor(6) as threads:
            for future in [threads.submit(one, job) for job in jobs]:
                future.result()
    if args.stage == "dev":
        chosen, rule = pick({f"{k} risk {r}": out[f"{k} risk {r}"] for k in SELECTABLE for r in RISKS})
        out["selection"] = {"chosen": chosen, "rule_met": rule,
                            "beats_c1_same_risk": average_month(out[chosen]) > average_month(out[f"C1 risk {chosen.split()[-1]}"])}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
