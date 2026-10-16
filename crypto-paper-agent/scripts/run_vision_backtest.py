#!/usr/bin/env python3
"""Run a directional strategy through the paper broker on the verified Binance Vision archive.

Paper simulation only. Every decision uses closed 4h bars; fills happen at the next 15m open.

Example:
  python scripts/run_vision_backtest.py --data-dir <dir> --strategy trend_following \
      --start 2021-01-01 --end 2025-12-31 --output result.json
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import BacktestEngine  # noqa: E402
from src.data_layer.vision_dataset import attach_funding, load_bars, load_funding  # noqa: E402
from src.execution.paper_broker import PaperBroker  # noqa: E402
from src.report.performance_summary import summarize_run  # noqa: E402
from src.strategies.registry import directional_strategy  # noqa: E402

WARMUP = pd.Timedelta(days=120)


def deep_merge(base, update):
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(strategy, overrides):
    config = yaml.safe_load((PROJECT_ROOT / "config" / "default_config.yaml").read_text(encoding="utf-8"))
    strategy_file = PROJECT_ROOT / "config" / "strategies" / f"{strategy}.yaml"
    if strategy_file.is_file():
        config = deep_merge(config, yaml.safe_load(strategy_file.read_text(encoding="utf-8")))
    for path in overrides:
        config = deep_merge(config, yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    config.setdefault("strategy", {})["name"] = strategy.upper()
    config.setdefault("news_filter", {})["enabled"] = False
    return config


def run(data_dir, strategy, start, end, overrides=(), cost_multiplier=1.0, initial_capital=None, summarize=True):
    """Return the owner-facing summary, or the finished broker when summarize=False."""
    config = load_config(strategy, overrides)
    if initial_capital is not None:
        config["account"]["initial_equity_usd"] = float(initial_capital)
    for fee in ("taker_pct", "maker_pct", "slippage_pct"):
        config["fees"][fee] = float(config["fees"][fee]) * cost_multiplier
    start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    signal_tf = config["strategy"].get("timeframe_signal", "4h")
    exec_tf = config["strategy"].get("timeframe_execution", "15m")
    signal = load_bars(data_dir, signal_tf)
    signal = signal.loc[(signal.index >= start - WARMUP) & (signal.index < end)]
    execution = load_bars(data_dir, exec_tf)
    execution = execution.loc[(execution.index >= start) & (execution.index < end)]
    execution = attach_funding(execution, load_funding(data_dir))
    engine = BacktestEngine(
        config=config,
        data_4h=signal,
        data_15m=execution,
        strategy=directional_strategy(strategy, config),
        broker=PaperBroker(config=config),
    )
    metrics = engine.run(force_close=True)
    return summarize_run(engine.broker, metrics, start, end) if summarize else engine.broker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--config", action="append", default=[], help="extra YAML merged over the strategy config")
    parser.add_argument("--cost-multiplier", type=float, default=1.0)
    parser.add_argument("--output")
    args = parser.parse_args()
    summary = run(args.data_dir, args.strategy, args.start, args.end, args.config, args.cost_multiplier)
    text = json.dumps(summary, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
