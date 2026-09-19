"""
Script tải dữ liệu nến OHLCV và Funding Rate thực tế từ Binance Futures Public API.
Lưu dữ liệu dưới dạng parquet vào thư mục data/raw/binance/{symbol}/.

Cách dùng:
    python scripts/fetch_market_data.py --symbol BTCUSDT --interval 15m --limit 500
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fetch_klines(symbol: str = "BTCUSDT", interval: str = "15m", limit: int = 500) -> pd.DataFrame:
    """Tải nến OHLCV từ Binance USD-M Futures REST API."""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    records = []
    for item in data:
        open_ts = pd.to_datetime(item[0], unit="ms", utc=True)
        records.append({
            "timestamp": open_ts,
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
    return df


def fetch_funding_rate(symbol: str = "BTCUSDT", limit: int = 100) -> pd.DataFrame:
    """Tải lịch sử Funding Rate từ Binance USD-M Futures REST API."""
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {
        "symbol": symbol.upper(),
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    records = []
    for item in data:
        funding_ts = pd.to_datetime(item["fundingTime"], unit="ms", utc=True)
        records.append({
            "timestamp": funding_ts,
            "funding_rate": float(item["fundingRate"]),
            "mark_price": float(item.get("markPrice", 0.0)),
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Binance Futures market data cache.")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    parser.add_argument("--interval", type=str, default="15m", help="Kline interval (default: 15m)")
    parser.add_argument("--kline-limit", type=int, default=500, help="Number of klines to fetch (default: 500)")
    parser.add_argument("--funding-limit", type=int, default=100, help="Number of funding rates to fetch (default: 100)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    kline_dir = PROJECT_ROOT / "data" / "raw" / "binance" / symbol / args.interval
    funding_dir = PROJECT_ROOT / "data" / "raw" / "binance" / symbol / "8h"

    kline_dir.mkdir(parents=True, exist_ok=True)
    funding_dir.mkdir(parents=True, exist_ok=True)

    kline_file = kline_dir / "ohlcv.parquet"
    funding_file = funding_dir / "funding_rate.parquet"

    print(f"[*] Đang tải dữ liệu {symbol} {args.interval} và Funding 8h từ Binance Futures...")
    try:
        df_klines = fetch_klines(symbol=symbol, interval=args.interval, limit=args.kline_limit)
        df_funding = fetch_funding_rate(symbol=symbol, limit=args.funding_limit)
    except Exception as exc:
        print(f"[!] Lỗi kết nối mạng hoặc API: {exc}")
        print("[*] Ghi chú: Chạy lệnh này trên máy có kết nối Internet đến fapi.binance.com.")
        return 1

    df_klines.to_parquet(kline_file)
    df_funding.to_parquet(funding_file)

    print(f"[+] Đã lưu {len(df_klines)} nến vào: {kline_file}")
    print(f"[+] Đã lưu {len(df_funding)} mốc funding vào: {funding_file}")
    print("[+] Hoàn tất fetch dữ liệu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
