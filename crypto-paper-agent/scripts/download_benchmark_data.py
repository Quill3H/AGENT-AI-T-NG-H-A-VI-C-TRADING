"""
scripts/download_benchmark_data.py
==================================
Tải dữ liệu benchmark 3 năm (2021-01-01 -> 2023-12-31) BTCUSDT
cho khung 4h, 15m, và Funding Rate từ Binance Futures public API.
Lưu vào Parquet cache để run_backtest --no-fetch có thể chạy hoàn toàn offline.
"""
from datetime import datetime
from pathlib import Path
import sys
import pandas as pd
import yaml
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_layer.fetcher import fetch_all


def main():
    config_path = PROJECT_ROOT / "config" / "default_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Đảm bảo đường dẫn tuyệt đối cho raw_data_dir
    config["data"]["raw_data_dir"] = str(PROJECT_ROOT / "data" / "raw")

    start_dt = pd.Timestamp("2021-01-01 00:00:00", tz="UTC")
    end_dt = pd.Timestamp("2023-12-31 23:59:59", tz="UTC")

    symbol = config.get("data", {}).get("symbol", "BTC/USDT")
    timeframes = ["4h", "15m"]

    logger.info(f"Downloading benchmark data for {symbol} ({start_dt} to {end_dt})...")
    res = fetch_all(
        symbol=symbol,
        timeframes=timeframes,
        since=start_dt,
        until=end_dt,
        config=config,
        force_refresh=False,
    )

    for tf in timeframes:
        df = res.get(tf, pd.DataFrame())
        logger.info(f"Timeframe {tf}: {len(df)} bars ({df.index[0]} -> {df.index[-1]})")

    logger.info("Download completed successfully.")


if __name__ == "__main__":
    main()
