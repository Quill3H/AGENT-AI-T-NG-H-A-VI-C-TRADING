#!/usr/bin/env python3
"""
run_backtest.py - Entrypoint thực thi Backtest Giai đoạn 5
===========================================================
Chạy backtest chiến lược Trend Following end-to-end trên khung 4h/15m.
Tuân thủ nghiêm ngặt ANTIGRAVITY_STAGE_05_TASK.md:
- Hỗ trợ đầy đủ --config, --strategy, --start, --end, --no-fetch.
- Path độc lập với Current Working Directory (CWD).
- Fail rõ ràng nếu strategy chưa hỗ trợ hoặc cache thiếu khi dùng --no-fetch.
- KHÔNG kết nối API key thật, KHÔNG đặt lệnh thật.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict

from loguru import logger
import numpy as np
import pandas as pd
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Thêm thư mục gốc vào sys.path để đảm bảo import đúng khi gọi từ bất kỳ đâu
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import BacktestEngine
from src.data_layer.cache_manager import (
    has_complete_cache,
    load_from_cache,
)
from src.data_layer.fetcher import fetch_all, merge_ohlcv_with_oi_and_funding
from src.strategies.trend_following import TrendFollowingStrategy


def _load_yaml(file_path: Path) -> Dict[str, Any]:
    """Đọc file YAML an toàn."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Config file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def _deep_merge_dict(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Merge lồng nhau hai dictionary."""
    result = dict(base)
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge_dict(result[k], v)
        else:
            result[k] = v
    return result


def _get_git_commit_sha() -> str:
    """Lấy commit SHA hiện tại qua git CLI."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_GIT_COMMIT"


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Futures Paper-Trading Research Agent (Backtest Runner - Stage 5)"
    )
    parser.add_argument(
        "--config",
        default="config/default_config.yaml",
        help="Path to YAML config file (default: config/default_config.yaml)",
    )
    parser.add_argument(
        "--strategy",
        default="trend_following",
        choices=["trend_following", "breakout_retest", "smc_liquidity_sweep", "funding_arbitrage", "all"],
        help="Strategy to backtest (default: trend_following)",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Override start date (YYYY-MM-DD or ISO8601 UTC)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Override end date (YYYY-MM-DD or ISO8601 UTC)",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Chỉ dùng cache local, không fetch dữ liệu mới từ network",
    )
    parser.add_argument(
        "--force-close",
        action="store_true",
        default=True,
        help="Force close all open positions on finalize (default: True)",
    )
    args = parser.parse_args()

    # 1. Kiểm tra chiến lược được hỗ trợ (Test 13: fail rõ ràng nếu chưa hỗ trợ)
    if args.strategy != "trend_following":
        sys.stderr.write(
            f"ERROR: Strategy '{args.strategy}' is not implemented in Stage 5. "
            f"Only 'trend_following' is supported. Out of scope strategies fail-closed.\n"
        )
        sys.exit(1)

    # 2. Xử lý đường dẫn độc lập CWD
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (PROJECT_ROOT / config_path).resolve()

    if not config_path.is_file():
        sys.stderr.write(f"ERROR: Config file not found at: {config_path}\n")
        sys.exit(1)

    # 3. Tải và hợp nhất cấu hình
    base_config = _load_yaml(config_path)

    # Đọc thêm config riêng của chiến lược nếu có
    strat_cfg_path = PROJECT_ROOT / "config" / "strategies" / f"{args.strategy}.yaml"
    if strat_cfg_path.is_file():
        strat_cfg = _load_yaml(strat_cfg_path)
        config = _deep_merge_dict(base_config, strat_cfg)
    else:
        config = base_config

    # Điều chỉnh raw_data_dir thành đường dẫn tuyệt đối
    raw_rel = config.get("data", {}).get("raw_data_dir", "data/raw")
    raw_dir = (PROJECT_ROOT / raw_rel).resolve()
    config["data"]["raw_data_dir"] = str(raw_dir)

    # 4. Xác định khoảng thời gian start và end
    start_str = args.start or config.get("data", {}).get("start_date", "2021-01-01")
    end_str = args.end or config.get("data", {}).get("end_date", "2023-12-31")

    try:
        start_dt = pd.Timestamp(start_str, tz="UTC")
        if len(start_str) == 10:  # Format YYYY-MM-DD
            start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except Exception as e:
        sys.stderr.write(f"ERROR: Invalid start date format '{start_str}': {e}\n")
        sys.exit(1)

    try:
        end_dt = pd.Timestamp(end_str, tz="UTC")
        if len(end_str) == 10:  # Format YYYY-MM-DD -> inclusive to end of day
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    except Exception as e:
        sys.stderr.write(f"ERROR: Invalid end date format '{end_str}': {e}\n")
        sys.exit(1)

    if end_dt <= start_dt:
        sys.stderr.write(f"ERROR: end_date ({end_dt}) must be greater than start_date ({start_dt})\n")
        sys.exit(1)

    symbol = config.get("data", {}).get("futures_symbol", "BTCUSDT")
    exchange = config.get("data", {}).get("exchange", "binance")
    timeframes = ["4h", "15m"]

    print("=" * 70)
    print(" CRYPTO FUTURES PAPER-TRADING RESEARCH AGENT - STAGE 5 BACKTEST")
    print(" OUT OF SCOPE: No real API keys, no live orders, pure simulation")
    print("=" * 70)
    print(f"Git Commit SHA : {_get_git_commit_sha()}")
    print(f"Config File    : {config_path}")
    print(f"Strategy       : {args.strategy}")
    print(f"Symbol         : {symbol}")
    print(f"Time Range UTC : {start_dt.isoformat()} -> {end_dt.isoformat()}")
    print(f"Cache Directory: {raw_dir}")
    print(f"Fetch Mode     : {'LOCAL CACHE ONLY (--no-fetch)' if args.no_fetch else 'AUTO FETCH/CACHE'}")
    print("=" * 70)

    # 5. Tải / Kiểm tra dữ liệu
    data: Dict[str, pd.DataFrame] = {}

    if args.no_fetch:
        print("\n[Data] Checking local parquet cache integrity...")
        for tf in timeframes:
            complete = has_complete_cache(
                base_dir=str(raw_dir),
                exchange=exchange,
                symbol=symbol,
                timeframe=tf,
                data_type="ohlcv",
                since=start_dt,
                until=end_dt,
            )
            if not complete:
                sys.stderr.write(
                    f"\nERROR: Incomplete local cache for {symbol} {tf} between {start_dt} and {end_dt}.\n"
                    f"Flag --no-fetch is active; network fetch is prohibited.\n"
                    f"Please download data or remove --no-fetch.\n"
                )
                sys.exit(1)

            # Load from cache
            ohlcv_df = load_from_cache(str(raw_dir), exchange, symbol, tf, "ohlcv", start_dt, end_dt)
            if ohlcv_df is None or ohlcv_df.empty:
                sys.stderr.write(f"\nERROR: Failed to load OHLCV data from cache for {tf}.\n")
                sys.exit(1)

            oi_df = load_from_cache(str(raw_dir), exchange, symbol, tf, "open_interest", start_dt, end_dt)
            if oi_df is None:
                oi_df = pd.DataFrame()

            funding_df = load_from_cache(str(raw_dir), exchange, symbol, "8h", "funding_rate", start_dt, end_dt)
            if funding_df is None or funding_df.empty:
                funding_df = load_from_cache(str(raw_dir), exchange, symbol, tf, "funding_rate", start_dt, end_dt)
            if funding_df is None:
                funding_df = pd.DataFrame()

            merged = merge_ohlcv_with_oi_and_funding(
                ohlcv_df=ohlcv_df,
                oi_df=oi_df,
                funding_df=funding_df,
                timeframe=tf,
                config=config,
            )
            filtered = merged.loc[start_dt:end_dt]
            if filtered.empty:
                sys.stderr.write(f"\nERROR: Filtered data for {tf} is empty in range {start_dt} to {end_dt}.\n")
                sys.exit(1)
            data[tf] = filtered
            print(f"  - Loaded {tf:4s}: {len(filtered):6d} bars ({filtered.index[0]} to {filtered.index[-1]})")
    else:
        print("\n[Data] Fetching / Loading data from cache and network...")
        try:
            fetched_data = fetch_all(
                symbol=config.get("data", {}).get("symbol", "BTC/USDT"),
                timeframes=timeframes,
                since=start_dt,
                until=end_dt,
                config=config,
                force_refresh=False,
            )
            for tf in timeframes:
                df_tf = fetched_data.get(tf, pd.DataFrame())
                filtered = df_tf.loc[start_dt:end_dt]
                if filtered.empty:
                    sys.stderr.write(f"\nERROR: Fetched data for {tf} is empty in range {start_dt} to {end_dt}.\n")
                    sys.exit(1)
                data[tf] = filtered
                print(f"  - Ready {tf:4s}: {len(filtered):6d} bars ({filtered.index[0]} to {filtered.index[-1]})")
        except Exception as e:
            sys.stderr.write(f"\nERROR: Failed to fetch/prepare data: {e}\n")
            sys.exit(1)

    # 6. Khởi tạo Strategy và BacktestEngine
    print("\n[Engine] Initializing TrendFollowingStrategy and BacktestEngine...")
    strategy = TrendFollowingStrategy(config=config, symbol=symbol)
    engine = BacktestEngine(
        config=config,
        data_4h=data["4h"],
        data_15m=data["15m"],
        strategy=strategy,
        symbol=symbol,
    )

    # 7. Chạy Backtest
    print("\n[Engine] Running causal multi-timeframe backtest loop...")
    metrics = engine.run(force_close=args.force_close)

    # 8. Xuất báo cáo kết quả chi tiết
    print("\n" + "=" * 70)
    print("                   BACKTEST EXECUTION REPORT")
    print("=" * 70)
    print(f"Time Range 15m       : {metrics['start_time']} -> {metrics['end_time']}")
    print(f"Bars Processed       : 15m={metrics['bars_15m_count']}, 4h={metrics['bars_4h_count']}")
    print("-" * 70)
    print(f"Initial Balance      : {metrics['start_equity']:,.2f} USDT")
    print(f"Final Equity         : {metrics['final_equity']:,.2f} USDT")
    print(f"Total Return         : {metrics['total_return_pct']:+.2f}%")
    print(f"Max Drawdown         : -{metrics['max_drawdown_usd']:,.2f} USDT (-{metrics['max_drawdown_pct']:.2f}%)")
    print("-" * 70)
    print(f"Total Orders Sent    : {metrics['submitted_orders_count']}")
    print(f"Orders Filled        : {metrics['orders_filled_count']}")
    print(f"Orders Rejected      : {metrics['orders_rejected_count']}")
    print(f"Orders Cancelled     : {metrics['orders_cancelled_count']}")
    if metrics['rejection_reasons']:
        print("Rejection Breakdown  :")
        for r_name, r_cnt in metrics['rejection_reasons'].items():
            print(f"  - {r_name}: {r_cnt}")
    print("-" * 70)
    print(f"Total Closed Trades  : {metrics['total_trades']}")
    print(f"  - LONG Trades      : {metrics['long_trades_count']}")
    print(f"  - SHORT Trades     : {metrics['short_trades_count']}")
    print(f"Trade Outcomes       : {metrics['win_trades_count']} Win / {metrics['loss_trades_count']} Loss / {metrics['breakeven_trades_count']} Breakeven")
    print(f"Win Rate (Overall)   : {metrics['win_rate']:.2f}% (Benchmark: 35-45%)")
    print(f"Win Rate (LONG)      : {metrics['win_rate_long']:.2f}%")
    print(f"Win Rate (SHORT)     : {metrics['win_rate_short']:.2f}%")
    print("-" * 70)
    print(f"Gross Price PnL      : {metrics['total_gross_pnl']:+,.2f} USDT")
    print(f"Trading Fees Paid    : -{metrics['total_fees']:,.2f} USDT")
    print(f"Funding Cashflow     : {metrics['total_funding_trades']:+,.2f} USDT")
    print(f"Net Realized PnL     : {metrics['total_net_pnl']:+,.2f} USDT")
    print(f"Exit Reasons         : {metrics['exit_reasons']}")
    print("-" * 70)
    print(f"Accounting Audit     : {'PASSED (wallet_balance matches ledger)' if metrics['accounting_invariants_verified'] else 'FAILED'}")
    print(f"Finalize Mode        : force_close={metrics['force_close_on_finalize']}")
    print("=" * 70)

    print("\nBacktest completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
