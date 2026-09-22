"""
Script tải dữ liệu nến OHLCV và Funding Rate thực tế từ Binance Futures Public API.
Lưu dữ liệu dưới dạng parquet vào thư mục data/raw/binance/{symbol}/.

Cách dùng:
    python scripts/fetch_market_data.py --symbol BTCUSDT --interval 15m --limit 500
"""

import argparse
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALID_INTERVALS = frozenset(
    {
        "1s",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
        "3d",
        "1w",
        "1M",
    }
)
MAX_KLINE_LIMIT = 1500
MAX_FUNDING_LIMIT = 1000
SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,20}$")


def _validate_request(symbol: str, interval: str, kline_limit: int, funding_limit: int) -> str | None:
    normalized_symbol = symbol.upper()
    if not SYMBOL_RE.fullmatch(normalized_symbol):
        return "symbol must contain only 3-20 uppercase letters or digits"
    if interval not in VALID_INTERVALS:
        return f"unsupported interval {interval!r}"
    if not 1 <= kline_limit <= MAX_KLINE_LIMIT:
        return f"kline-limit must be between 1 and {MAX_KLINE_LIMIT}"
    if not 1 <= funding_limit <= MAX_FUNDING_LIMIT:
        return f"funding-limit must be between 1 and {MAX_FUNDING_LIMIT}"
    return None


def _atomic_parquet_write(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temp_name)
    try:
        frame.to_parquet(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


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
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "raw"),
        help="Cache root (default: project data/raw)",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Explicitly allow public Binance HTTP requests",
    )
    args = parser.parse_args()

    if not args.allow_network:
        sys.stderr.write(
            "ERROR [NETWORK_DISABLED]: public HTTP fetch requires --allow-network.\n"
        )
        return 2
    if args.kline_limit <= 0 or args.funding_limit <= 0:
        sys.stderr.write("ERROR [INVALID_ARGUMENTS]: limits must be positive integers.\n")
        return 2

    symbol = args.symbol.upper()
    validation_error = _validate_request(
        symbol, args.interval, args.kline_limit, args.funding_limit
    )
    if validation_error:
        sys.stderr.write(f"ERROR [INVALID_ARGUMENTS]: {validation_error}.\n")
        return 2
    output_root = Path(args.output_dir).resolve()
    kline_dir = output_root / "binance" / symbol / args.interval
    funding_dir = output_root / "binance" / symbol / "8h"

    kline_file = kline_dir / "ohlcv.parquet"
    funding_file = funding_dir / "funding_rate.parquet"

    if kline_file.exists() or funding_file.exists():
        sys.stderr.write(
            "ERROR [OUTPUT_EXISTS]: refusing to overwrite an existing market-data cache.\n"
        )
        return 2

    print(f"[*] Fetching {symbol} {args.interval} candles and 8h funding from Binance Futures...")
    try:
        df_klines = fetch_klines(symbol=symbol, interval=args.interval, limit=args.kline_limit)
        df_funding = fetch_funding_rate(symbol=symbol, limit=args.funding_limit)
    except Exception as exc:
        print(f"[!] Network or public API failure: {exc}")
        print("[*] The host must be able to reach fapi.binance.com.")
        return 1

    if df_klines.empty or df_funding.empty:
        sys.stderr.write("ERROR [DATASET_UNAVAILABLE]: Binance returned an empty dataset.\n")
        return 2

    _atomic_parquet_write(df_klines, kline_file)
    _atomic_parquet_write(df_funding, funding_file)

    print(f"[+] Saved {len(df_klines)} candles to: {kline_file}")
    print(f"[+] Saved {len(df_funding)} funding events to: {funding_file}")
    print("[+] Fetch completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
