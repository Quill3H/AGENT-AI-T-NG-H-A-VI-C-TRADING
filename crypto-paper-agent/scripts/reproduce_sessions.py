#!/usr/bin/env python3
"""Round 7 of the futures research: docs/research/2026-10-18-video-sessions.md (paper only).

  python scripts/reproduce_sessions.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_sessions.py --data-dir <dir> --stage final --candidate V1 --frozen-commit <sha> --output final.json

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

from scripts import run_vision_portfolio  # noqa: E402
from scripts.reproduce_futures_search import score  # noqa: E402
from scripts.reproduce_trading_styles import CORE, DEV, FINAL_B, RISKS  # noqa: E402
from src.research import ledger  # noqa: E402

ROUND = 7
FINAL_A = ("2021-01-01", "2026-09-30")
FRESH = ("TRXUSDT", "ALGOUSDT", "VETUSDT", "SANDUSDT")
LEVERAGE_WHATIF = str(PROJECT_ROOT / "config" / "research" / "candles_2026_10_18" / "whatif_leverage_x20.yaml")
MIN_PER_WEEK = 5.0  # owner 2026-10-18: "1 tuần khoảng 5-10 lệnh"
CANDIDATES = {
    "V1": ("london_breakout", "video 3:47-4:02, London breakout 5m"),
    "V2": ("london_breakout_trend", "video 3:47-4:02 + EMA(100) filter 2:23"),
    "V3": ("heikin_ashi_scalp", "video 3:10-3:26, Heikin-Ashi scalp"),
    "V4": ("zone_swing_break", "video 2:53-3:01, zone tap + swing break"),
    "V5": ("swing_ema_pullback_1h", "round-5 W1 rules on 1h bars, more trades"),
    "T1": ("holy_grail", "Linda Raschke, Street Smarts (1995)"),
    "T2": ("volatility_breakout", "Larry Williams, Long-Term Secrets to Short-Term Trading (1999)"),
    "T3": ("nr7_breakout", "Toby Crabel, Day Trading with Short Term Price Patterns (1990)"),
}


def pick(results):
    """Protocol rule: best return/DD among candidates with >= 5 trades/week and no losing dev
    year; else the best with >= 5 trades/week; else the best overall. Returns (key, rule met)."""
    weekly = {k: v for k, v in results.items() if ledger.trades_per_week(v, *DEV) >= MIN_PER_WEEK}
    clean = {k: v for k, v in weekly.items() if min(v["yearly_return_pct"].values()) > 0}
    pool = clean or weekly or results
    return max(pool, key=lambda k: score(pool[k])), "full" if clean else ("frequency only" if weekly else "none")


def jobs_for(stage, candidate=None):
    """(label, ledger stage, key, window, symbols, risk, cost, extra files)."""
    if stage == "dev":
        return [(f"{k} risk {r}", "dev", k, DEV, CORE, r, 1.0, []) for k in CANDIDATES for r in ("1%", "2%")]
    jobs = [(f"A: TRX/ALGO/VET/SAND 2021-01..2026-09, risk {r}", "final", candidate, FINAL_A, FRESH, r, 1.0, [])
            for r in RISKS]
    jobs.append(("A, risk 1%, costs x2", "final", candidate, FINAL_A, FRESH, "1%", 2.0, []))
    jobs += [(f"B: BTC/ETH/SOL 2024-01..2026-09 (seen), risk {r}", "validation", candidate, FINAL_B, CORE, r, 1.0, [])
             for r in RISKS]
    jobs += [(f"x20/x5 {part}, risk {r}", "final-whatif", candidate, window, symbols, r, 1.0, [LEVERAGE_WHATIF])
             for part, window, symbols in (("A", FINAL_A, FRESH), ("B", FINAL_B, CORE)) for r in ("2%", "10%")]
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--stage", choices=["dev", "final"], required=True)
    parser.add_argument("--candidate", choices=sorted(CANDIDATES))
    parser.add_argument("--frozen-commit")
    parser.add_argument("--output", required=True)
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    if args.stage == "final" and not (args.candidate and args.frozen_commit):
        parser.error("--candidate and --frozen-commit are required for the final stage")
    output = Path(args.output)
    out = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    out.pop("selection", None)
    jobs = [j for j in jobs_for(args.stage, args.candidate) if j[0] not in out]
    if args.stage == "final":
        ledger.check_untouched(FRESH, *FINAL_A, ledger.load())
    lock = threading.Lock()

    def save():
        output.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    with ProcessPoolExecutor(4) as pool:
        def one(job):
            label, stage, key, window, symbols, risk, cost, extra = job
            strategy, source = CANDIDATES[key]
            files = RISKS[risk] + extra
            summary = run_vision_portfolio.run(args.data_dir, strategy, *window, files, cost, symbols=symbols, pool=pool)
            with lock:
                out[label] = summary
                save()
                if not args.no_ledger:
                    ledger.record(ROUND, stage, key, strategy, label, *window, symbols, risk, summary,
                                  source=source, config_files=files, frozen_commit=args.frozen_commit)

        with ThreadPoolExecutor(6) as threads:
            for future in [threads.submit(one, job) for job in jobs]:
                future.result()
    if args.stage == "dev":
        chosen, rule = pick({key: out[f"{key} risk 1%"] for key in CANDIDATES})
        out["selection"] = {"chosen": chosen, "rule_met": rule}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
