#!/usr/bin/env python3
"""Round 5 of the futures research: docs/research/2026-10-17-trading-styles.md (paper only).

  python scripts/reproduce_trading_styles.py --data-dir <binance-vision-usdm dir> --stage dev --output dev.json
  python scripts/reproduce_trading_styles.py --data-dir <dir> --stage final --candidate W1 --output final.json

Each finished run is written to --output straight away, so a long run can be followed.
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
from scripts.reproduce_indicator_search import RISK as RISK_10, pick  # noqa: E402

DEV = ("2021-01-01", "2023-12-31")
FINAL_A = ("2021-01-01", "2026-09-30")
FINAL_B = ("2024-01-01", "2026-09-30")
CORE = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
FRESH = ("ETCUSDT", "ATOMUSDT", "NEARUSDT", "FILUSDT")
VARIANTS = PROJECT_ROOT / "config" / "research" / "trading_styles_2026_10_17"
RISKS = {"1%": [str(VARIANTS / "risk_1pct.yaml")], "2%": [str(VARIANTS / "risk_2pct.yaml")], "10%": RISK_10}
CANDIDATES = {
    "W1": "swing_ema_pullback",
    "W2": "sr_candles",
    "W3": "wyckoff_spring",
    "D1": "day_orb",
    "D2": "day_vwap",
    "C1": "scalp_ema",
    "C2": "scalp_bb",
    # amendment 2026-10-17 (owner: scalp on 15m and 1h), registered before these ran
    "C3": "scalp_bb_15m",
    "C4": "scalp_rsi_15m",
    "C5": "scalp_bb_1h",
    "C6": "scalp_rsi_1h",
}
SCALPING = ("C1", "C2", "C3", "C4", "C5", "C6")
PILOT = ("2023-01-01", "2023-03-31")  # 1m data is only downloaded for this dev quarter
PILOT_CANDIDATES = {"P1": "scalp_ema_1m", "P2": "scalp_bb_1m"}


def jobs_for(stage, candidate=None):
    """(label, strategy, window, symbols, risk, cost) for every run of a stage."""
    jobs = []
    if stage == "pilot":
        for key, strategy in PILOT_CANDIDATES.items():
            for risk in RISKS:
                jobs.append((f"{key} risk {risk}", strategy, PILOT, CORE, risk, 1.0))
            jobs.append((f"{key} risk 2%, costs x2", strategy, PILOT, CORE, "2%", 2.0))
    elif stage == "dev":
        for key, strategy in CANDIDATES.items():
            for risk in RISKS:
                jobs.append((f"{key} risk {risk}", strategy, DEV, CORE, risk, 1.0))
            if key in SCALPING:
                jobs.append((f"{key} risk 2%, costs x2", strategy, DEV, CORE, "2%", 2.0))
    else:
        strategy = CANDIDATES[candidate]
        for risk in RISKS:
            jobs.append((f"A: ETC/ATOM/NEAR/FIL 2021-01..2026-09, risk {risk}", strategy, FINAL_A, FRESH, risk, 1.0))
        jobs.append(("A, risk 2%, costs x2", strategy, FINAL_A, FRESH, "2%", 2.0))
        for risk in RISKS:
            jobs.append((f"B: BTC/ETH/SOL 2024-01..2026-09, risk {risk}", strategy, FINAL_B, CORE, risk, 1.0))
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--stage", choices=["dev", "pilot", "final"], required=True)
    parser.add_argument("--candidate", choices=sorted(CANDIDATES))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.stage == "final" and not args.candidate:
        parser.error("--candidate is required for the final stage")
    output = Path(args.output)
    out = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}  # resume a stopped run
    out.pop("selection", None)
    lock = threading.Lock()

    def save():
        Path(args.output).write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    with ProcessPoolExecutor(4) as pool:
        def one(job):
            label, strategy, window, symbols, risk, cost = job
            summary = run_vision_portfolio.run(args.data_dir, strategy, *window, RISKS[risk], cost, symbols=symbols, pool=pool)
            with lock:
                out[label] = summary
                save()

        with ThreadPoolExecutor(6) as threads:
            for future in [threads.submit(one, job) for job in jobs_for(args.stage, args.candidate) if job[0] not in out]:
                future.result()
    if args.stage == "dev":
        at_2pct = {key: out[f"{key} risk 2%"] for key in CANDIDATES}
        chosen, clean = pick(at_2pct)
        out["selection"] = {"chosen": chosen, "met_rule": clean}
    save()
    print(json.dumps(out.get("selection", {}), default=str))


if __name__ == "__main__":
    main()
