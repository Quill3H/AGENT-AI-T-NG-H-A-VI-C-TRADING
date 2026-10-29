#!/usr/bin/env python3
"""Paper-trade journal (owner rule 2026-10-21): rerun one strategy per coin and write every
trade's entry, stop, target, exit and exit reason to a CSV (paper only).

  python scripts/trade_journal.py --data-dir <forward dir> --strategy swing_ema_pullback_long \\
      --symbols BTCUSDT ETHUSDT SOLUSDT --start 2026-10-18 --end 2026-10-24 --config <risk yaml> --output week.csv
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_backtest  # noqa: E402
from src.report.trade_journal import journal_rows, write_journal  # noqa: E402


def journal(data_dir, strategy, symbols, start, end, overrides=(), capital=10000.0):
    share = float(capital) / len(symbols)
    rows = []
    for symbol in symbols:
        broker = run_vision_backtest.run(data_dir, strategy, start, end, list(overrides), 1.0,
                                         initial_capital=share, summarize=False, symbol=symbol)
        rows += journal_rows(broker.trade_history, strategy)
    return sorted(rows, key=lambda r: (r["entry_time"], r["symbol"], r["exit_time"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--config", action="append", default=[], help="extra YAML merged over the strategy config")
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = journal(args.data_dir, args.strategy, args.symbols, args.start, args.end, args.config, args.capital)
    write_journal(rows, args.output)
    print(f"{len(rows)} journal lines -> {args.output}")


if __name__ == "__main__":
    main()
