#!/usr/bin/env python3
"""Back-to-back spot/perpetual funding baskets on the verified Binance Vision archive (paper only).

Example:
  python scripts/run_vision_carry.py --data-dir <dir> --start 2021-01-01 --end 2023-12-31
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_layer.vision_dataset import basket_frame  # noqa: E402
from src.report.performance_summary import curve_summary  # noqa: E402
from src.research.carry import simulate_carry_sequence  # noqa: E402
from scripts.run_vision_backtest import deep_merge  # noqa: E402


def load_config(overrides):
    config = yaml.safe_load((PROJECT_ROOT / "config" / "default_config.yaml").read_text(encoding="utf-8"))
    config = deep_merge(config, yaml.safe_load((PROJECT_ROOT / "config" / "strategies" / "funding_arbitrage.yaml").read_text(encoding="utf-8")))
    for path in overrides:
        config = deep_merge(config, yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    config.setdefault("news_filter", {})["enabled"] = False
    return config


def run(data_dir, start, end, overrides=(), cost_multiplier=1.0, initial_capital=None, symbol="BTCUSDT"):
    config = load_config(overrides)
    config.setdefault("data", {})["futures_symbol"] = symbol
    for fee in ("taker_pct", "maker_pct", "slippage_pct"):
        config["fees"][fee] = float(config["fees"][fee]) * cost_multiplier
    start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    frame = basket_frame(data_dir, symbol=symbol)
    frame = frame.loc[(frame.index >= start) & (frame.index < end)]
    capital = float(initial_capital or config["account"]["initial_equity_usd"])
    curve, baskets = simulate_carry_sequence(frame, config, capital)
    pnl = [b["net_pnl"] for b in baskets]
    return curve, curve_summary(curve, capital, start, end, pnl)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--config", action="append", default=[])
    parser.add_argument("--cost-multiplier", type=float, default=1.0)
    parser.add_argument("--output")
    args = parser.parse_args()
    _, summary = run(args.data_dir, args.start, args.end, args.config, args.cost_multiplier)
    text = json.dumps(summary, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
