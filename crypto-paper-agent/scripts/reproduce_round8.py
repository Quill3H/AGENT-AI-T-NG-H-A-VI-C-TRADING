#!/usr/bin/env python3
"""Round 8 of the futures research: docs/research/2026-10-18-round8-plan.md (paper only).

  python scripts/reproduce_round8.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_round8.py --data-dir <dir> --stage final --candidate C1 --risk 5% --frozen-commit <sha> --output final.json
  python scripts/reproduce_round8.py --data-dir <dir> --stage forward --candidate C1 --risk 5% --frozen-commit <sha> --end <day> --output fwd.json

Finished runs are written to --output at once (rerunning resumes) and appended to the
research ledger (src/research/ledger.py).
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

from scripts import run_vision_portfolio  # noqa: E402
from scripts.reproduce_futures_search import score  # noqa: E402
from scripts.reproduce_trading_styles import CORE, DEV, FINAL_B, RISKS as BASE_RISKS  # noqa: E402
from src.report.performance_summary import curve_summary  # noqa: E402
from src.research import ledger  # noqa: E402

ROUND = 8
CONFIGS = PROJECT_ROOT / "config" / "research"
RISKS = {"2%": BASE_RISKS["2%"], "5%": [str(CONFIGS / "futures_search_2026_10_16" / "whatif_risk_5pct.yaml")],
         "10%": BASE_RISKS["10%"]}
LEVERAGE_WHATIF = str(CONFIGS / "candles_2026_10_18" / "whatif_leverage_x20.yaml")
RR2 = str(CONFIGS / "candles_2026_10_18" / "exit_rr2.yaml")
FINAL = ("2026-10-01", "2026-10-17")  # Binance Vision daily archives; no earlier final used them
MAX_DD = 35.0
STEPS = (50.0, 30.0, 20.0, 10.0)
# key: (legs, source); a leg is (strategy, extra config files). Several legs share the capital equally.
CANDIDATES = {
    "C1": ([("swing_ema_pullback_long", [])], "W1 long only (round-8 loss analysis: shorts ~0R after costs)"),
    "C2": ([("blowoff_fade", [])], "GCR-style contrarian short after a blow-off"),
    "C3": ([("flush_buy", [])], "Machi Big Brother / James Wynn-style buy after a flush"),
    "C4": ([("swing_ema_pullback_long", []), ("candle_continuation", [RR2]), ("volatility_breakout", [])],
           "equal-weight C1 + K3-rr2 + T2"),
    "W1": ([("swing_ema_pullback", [])], "reference: round-5 W1, both sides"),
    "K3": ([("candle_continuation", [RR2])], "reference: round-6 K3-rr2"),
    "T2": ([("volatility_breakout", [])], "reference: round-7 Williams volatility breakout"),
}
SELECTABLE = ("C1", "C2", "C3", "C4")


def run_legs(data_dir, legs, start, end, files, cost=1.0, capital=10000.0, symbols=CORE, pool=None):
    """One portfolio of len(legs) x len(symbols) sleeves with equal capital."""
    if len(legs) == 1:
        strategy, extra = legs[0]
        return run_vision_portfolio.run(data_dir, strategy, start, end, files + extra, cost, capital, symbols, pool)
    share = capital / (len(legs) * len(symbols))
    args = [(data_dir, strategy, start, end, files + extra, cost, share, s) for strategy, extra in legs for s in symbols]
    results = list(pool.map(run_vision_portfolio.sleeve, *zip(*args))) if pool else [run_vision_portfolio.sleeve(*a) for a in args]
    begin, stop = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    total = run_vision_portfolio.combine_curves([c for c, _ in results], [share] * len(args))
    summary = curve_summary(total, capital, begin, stop, [p for _, pnl in results for p in pnl])
    summary["legs"] = {}
    for (strategy, _), i in zip(legs, range(0, len(args), len(symbols))):
        part = run_vision_portfolio.combine_curves([c for c, _ in results[i:i + len(symbols)]], [share] * len(symbols))
        legs_pnl = [p for _, pnl in results[i:i + len(symbols)] for p in pnl]
        leg = curve_summary(part, share * len(symbols), begin, stop, legs_pnl)
        leg.pop("monthly", None)
        summary["legs"][strategy] = leg
    return summary


def average_month(summary):
    return (summary.get("monthly") or {}).get("average_month_pct", -100.0)


def step_reached(summary):
    return next((s for s in STEPS if average_month(summary) >= s), 0.0)


def pick(results):
    """Protocol rule (plan, 'Step targets and selection'). Returns (label, rule met)."""
    capped = {k: v for k, v in results.items() if v["max_drawdown_pct"] <= MAX_DD}
    clean = {k: v for k, v in capped.items() if min(v["yearly_return_pct"].values()) > 0}
    if clean or capped:
        pool = clean or capped
        return max(pool, key=lambda k: average_month(pool[k])), "full" if clean else "drawdown only"
    return max(results, key=lambda k: score(results[k])), "none"


def jobs_for(stage, candidate=None, risk=None, end=None):
    """(label, ledger stage, key, window, risk, cost, extra files)."""
    if stage == "dev":
        jobs = [(f"{k} risk {r}", "dev", k, DEV, r, 1.0, []) for k in CANDIDATES for r in RISKS]
        jobs += [(f"C1 x20 BTC/ETH what-if, risk {r}", "dev-whatif", "C1", DEV, r, 1.0, [LEVERAGE_WHATIF]) for r in ("5%", "10%")]
        return jobs
    if stage == "final":
        jobs = [(f"B: BTC/ETH/SOL 2024-01..2026-09 (seen), risk {risk}", "validation", candidate, FINAL_B, risk, 1.0, []),
                (f"Final: BTC/ETH/SOL 2026-10-01..10-17, risk {risk}", "final", candidate, FINAL, risk, 1.0, []),
                ("Final, costs x2", "final", candidate, FINAL, risk, 2.0, [])]
        return jobs + [(f"Final, reference {k}, risk 2%", "final", k, FINAL, "2%", 1.0, []) for k in ("W1", "K3", "T2")]
    window = (FINAL[0], end)
    return [(f"Forward {window[0]}..{end}: {candidate} risk {risk}", "forward", candidate, window, risk, 1.0, [])] + \
           [(f"Forward {window[0]}..{end}: {k} risk 2%", "forward", k, window, "2%", 1.0, []) for k in ("W1", "K3", "T2")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--stage", choices=["dev", "final", "forward"], required=True)
    parser.add_argument("--candidate", choices=SELECTABLE)
    parser.add_argument("--risk", choices=sorted(RISKS))
    parser.add_argument("--frozen-commit")
    parser.add_argument("--end", help="last day of the forward window (forward stage)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    if args.stage != "dev" and not (args.candidate and args.risk and args.frozen_commit):
        parser.error("--candidate, --risk and --frozen-commit are required after the dev stage")
    if args.stage == "forward" and not args.end:
        parser.error("--end is required for the forward stage")
    output = Path(args.output)
    out = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    out.pop("selection", None)
    jobs = [j for j in jobs_for(args.stage, args.candidate, args.risk, args.end) if j[0] not in out]
    if args.stage == "final" and any(j[1] == "final" for j in jobs):
        ledger.check_untouched(CORE, *FINAL, ledger.load())
    lock = threading.Lock()

    def save():
        output.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    with ProcessPoolExecutor(4) as pool:
        def one(job):
            label, stage, key, window, risk, cost, extra = job
            legs, source = CANDIDATES[key]
            files = RISKS[risk] + extra
            summary = run_legs(args.data_dir, legs, *window, files, cost, pool=pool)
            summary["step_reached_pct"] = step_reached(summary)
            with lock:
                out[label] = summary
                save()
                if not args.no_ledger:
                    strategy = "+".join(s for s, _ in legs)
                    ledger.record(ROUND, stage, key, strategy, label, *window, CORE, risk, summary,
                                  source=source, config_files=files, frozen_commit=args.frozen_commit)

        with ThreadPoolExecutor(8) as threads:
            for future in [threads.submit(one, job) for job in jobs]:
                future.result()
    if args.stage == "dev":
        pool = {f"{k} risk {r}": out[f"{k} risk {r}"] for k in SELECTABLE for r in RISKS}
        chosen, rule = pick(pool)
        out["selection"] = {"chosen": chosen, "rule_met": rule, "step_reached_pct": step_reached(out[chosen])}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
