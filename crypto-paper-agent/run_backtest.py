#!/usr/bin/env python3
"""
run_backtest.py - Entrypoint chính
===================================
Chạy backtest end-to-end theo config.
KHÔNG kết nối API key thật, KHÔNG đặt lệnh thật.

Usage:
    python run_backtest.py --config config/default_config.yaml --strategy trend_following
    python run_backtest.py --help

Implement đầy đủ ở Giai đoạn 4+ (sau khi có BacktestEngine).
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Futures Paper-Trading Research Agent (Backtest Mode)"
    )
    parser.add_argument(
        "--config",
        default="config/default_config.yaml",
        help="Path to YAML config file (default: config/default_config.yaml)"
    )
    parser.add_argument(
        "--strategy",
        choices=["trend_following", "breakout_retest", "smc_liquidity_sweep", "funding_arbitrage", "all"],
        default="trend_following",
        help="Strategy to backtest (default: trend_following)"
    )
    parser.add_argument(
        "--start", default=None,
        help="Override start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", default=None,
        help="Override end date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--no-fetch", action="store_true",
        help="Chỉ dùng cache local, không fetch dữ liệu mới"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Crypto Futures Paper-Trading Research Agent")
    print("OUT OF SCOPE: Không kết nối API key thật, không đặt lệnh thật")
    print("=" * 60)
    print(f"Config: {args.config}")
    print(f"Strategy: {args.strategy}")
    print()

    # TODO (Giai đoạn 4): Implement engine khởi động:
    # 1. Load config từ YAML
    # 2. Khởi tạo DataLayer, FeatureEngine, RiskManager, PaperBroker
    # 3. Fetch/load data từ cache
    # 4. Chạy BacktestEngine.run()
    # 5. Sinh báo cáo (Giai đoạn 6)

    print("BacktestEngine chưa được implement (Giai đoạn 4).")
    print("Chạy 'pytest tests/' để kiểm tra các unit test hiện có.")
    sys.exit(0)


if __name__ == "__main__":
    main()
