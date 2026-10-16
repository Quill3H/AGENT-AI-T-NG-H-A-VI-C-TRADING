#!/usr/bin/env python3
"""Round 4 of the futures research: docs/research/2026-10-16-new-directions.md (paper only).

  python scripts/reproduce_new_directions.py --data-dir <binance-vision-usdm dir> --work-dir <scratch> --stage dev
  python scripts/reproduce_new_directions.py --data-dir <dir> --work-dir <scratch> --stage final --candidate N3

Signal tables are written to --work-dir; each value only uses data up to its day.
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_portfolio  # noqa: E402
from scripts.reproduce_indicator_search import RISK, pick  # noqa: E402
from src.data_layer.vision_dataset import load_bars  # noqa: E402
from src.research import signals  # noqa: E402

DEV = ("2021-01-01", "2023-12-31")
FINAL_A = ("2021-01-01", "2026-09-30")
FINAL_B = ("2024-01-01", "2026-09-30")
CORE = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
KNOWN7 = CORE + ("BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT")
FRESH = ("LINKUSDT", "AVAXUSDT", "LTCUSDT", "DOTUSDT")
CANDIDATES = ("N1", "N2", "N3", "N4")


def metrics(data_dir, symbol):
    path = Path(data_dir) / f"{symbol}_metrics_daily.parquet"
    return pd.read_parquet(path) if path.is_file() else None


def signal_table(data_dir, candidate, symbols):
    bars = {s: load_bars(data_dir, "1d", symbol=s) for s in symbols}
    if candidate == "N1":
        closes = pd.DataFrame({s: b["close"] for s, b in bars.items()})
        return signals.cross_sectional_positions(closes)
    use_metrics = candidate == "N4"
    features = signals.PRICE_FEATURES + (signals.METRIC_FEATURES if use_metrics else [])
    panel = {s: signals.daily_features(b, metrics(data_dir, s) if use_metrics else None) for s, b in bars.items()}
    probs = signals.walk_forward_probabilities(panel, {s: b["close"] for s, b in bars.items()}, features)
    return signals.probability_positions(probs)


def run(data_dir, work_dir, candidate, window, symbols, pool, signal_universe=None, cost=1.0):
    if candidate == "N2":
        return run_vision_portfolio.run(data_dir, "regime_switch", *window, RISK, cost, symbols=symbols, pool=pool)
    table = signal_table(data_dir, candidate, signal_universe or symbols)
    tag = f"{candidate}_{'_'.join(s[:3] for s in (signal_universe or symbols))}"
    table_path = Path(work_dir) / f"signals_{tag}.parquet"
    table.to_parquet(table_path)
    override = Path(work_dir) / f"signals_{tag}.yaml"
    override.write_text(yaml.safe_dump({"rules": {"signal_path": str(table_path), "allow_short": True}}), encoding="utf-8")
    summary = run_vision_portfolio.run(data_dir, "signal_series", *window, [str(override)] + RISK, cost, symbols=symbols, pool=pool)
    summary["signal_days_long_short_flat"] = {
        "long": int((table.loc[window[0]:window[1]] > 0).sum().sum()),
        "short": int((table.loc[window[0]:window[1]] < 0).sum().sum()),
        "flat": int((table.loc[window[0]:window[1]] == 0).sum().sum()),
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--stage", choices=["dev", "final"], required=True)
    parser.add_argument("--candidate", choices=CANDIDATES)
    parser.add_argument("--output")
    args = parser.parse_args()
    Path(args.work_dir).mkdir(parents=True, exist_ok=True)
    out = {}
    with ProcessPoolExecutor(4) as pool:
        if args.stage == "dev":
            out["N1"] = run(args.data_dir, args.work_dir, "N1", DEV, KNOWN7, pool)
            for key in ("N2", "N3", "N4"):
                out[key] = run(args.data_dir, args.work_dir, key, DEV, CORE, pool)
            chosen, clean = pick(out)
            out["selection"] = {"chosen": chosen, "met_rule": clean}
        else:
            if not args.candidate:
                parser.error("--candidate is required for the final stage")
            c = args.candidate
            out["final A: LINK/AVAX/LTC/DOT 2021-01..2026-09"] = run(args.data_dir, args.work_dir, c, FINAL_A, FRESH, pool)
            out["final A, costs x2"] = run(args.data_dir, args.work_dir, c, FINAL_A, FRESH, pool, cost=2.0)
            out["final B: BTC/ETH/SOL 2024-01..2026-09"] = run(args.data_dir, args.work_dir, c, FINAL_B, CORE, pool)
    text = json.dumps(out, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
