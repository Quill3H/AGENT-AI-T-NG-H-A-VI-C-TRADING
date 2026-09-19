"""
cache_manager.py - Data Layer: Parquet Cache Manager
======================================================
Lưu và đọc dữ liệu OHLCV/OI/Funding từ local Parquet files.
Không gọi lại API nếu dữ liệu đã có đủ trong khoảng thời gian yêu cầu.

Cấu trúc file:
  data/raw/<exchange>/<symbol>/<timeframe>/<data_type>.parquet
  Ví dụ: data/raw/binance/BTCUSDT/4h/ohlcv.parquet

CHỐNG LOOKAHEAD BIAS: module này chỉ đọc/ghi dữ liệu, không tự ý
forward-fill hay backfill — việc đó thuộc về fetcher.py với logic rõ ràng.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_cache_path(
    base_dir: str,
    exchange: str,
    symbol: str,
    timeframe: str,
    data_type: str,
) -> Path:
    """
    Trả về đường dẫn file Parquet tương ứng.

    Args:
        base_dir:  Thư mục gốc cache (vd: "data/raw")
        exchange:  Tên sàn (vd: "binance")
        symbol:    Ký hiệu không có slash (vd: "BTCUSDT")
        timeframe: Khung thời gian (vd: "4h", "15m", "1m")
        data_type: "ohlcv" | "open_interest" | "funding_rate"

    Returns:
        Path đến file .parquet (chưa cần tồn tại)
    """
    safe_symbol = symbol.replace("/", "").upper()
    return Path(base_dir) / exchange / safe_symbol / timeframe / f"{data_type}.parquet"


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def save_to_cache(
    df: pd.DataFrame,
    base_dir: str,
    exchange: str,
    symbol: str,
    timeframe: str,
    data_type: str,
) -> None:
    """
    Lưu DataFrame vào Parquet.
    - Tự động tạo thư mục nếu chưa có.
    - Nếu file đã tồn tại, merge dữ liệu mới vào (tránh duplicate theo timestamp).
    - Index phải là DatetimeTZAware (UTC).
    """
    path = get_cache_path(base_dir, exchange, symbol, timeframe, data_type)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Đảm bảo index là datetime UTC
    df = ensure_utc_index(df)

    if path.exists():
        existing = _read_parquet(path)
        # Merge: ưu tiên dữ liệu mới (giữ lại dữ liệu cũ ở những index chưa có)
        combined = pd.concat([existing, df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)
        df_to_write = combined
    else:
        df_to_write = df.sort_index()

    table = pa.Table.from_pandas(df_to_write, preserve_index=True)
    pq.write_table(table, path, compression="snappy")
    logger.debug(
        "[Cache] Saved {} {} {} {} → {} rows → {}",
        exchange, symbol, timeframe, data_type, len(df_to_write), path
    )


def load_from_cache(
    base_dir: str,
    exchange: str,
    symbol: str,
    timeframe: str,
    data_type: str,
    since: pd.Timestamp,
    until: pd.Timestamp,
) -> Optional[pd.DataFrame]:
    """
    Đọc từ cache, trả về None nếu không đủ dữ liệu cho khoảng yêu cầu.

    Args:
        since: Thời điểm bắt đầu (inclusive), timezone-aware UTC
        until: Thời điểm kết thúc (inclusive), timezone-aware UTC

    Returns:
        DataFrame với DatetimeIndex UTC, hoặc None nếu không đủ dữ liệu.
    """
    path = get_cache_path(base_dir, exchange, symbol, timeframe, data_type)
    if not path.exists():
        logger.debug("[Cache] Miss (file not found): {}", path)
        return None

    df = _read_parquet(path)
    if df.empty:
        logger.debug("[Cache] Miss (empty file): {}", path)
        return None

    df = ensure_utc_index(df)
    df_slice = df.loc[since:until]

    if not _is_cache_sufficient(df_slice, since, until, timeframe):
        logger.debug(
            "[Cache] Miss (insufficient data): {} rows for {} to {}",
            len(df_slice), since, until
        )
        return None

    logger.debug(
        "[Cache] Hit: {} {} {} {} → {} rows",
        exchange, symbol, timeframe, data_type, len(df_slice)
    )
    return df_slice


def has_complete_cache(
    base_dir: str,
    exchange: str,
    symbol: str,
    timeframe: str,
    data_type: str,
    since: pd.Timestamp,
    until: pd.Timestamp,
) -> bool:
    """
    Kiểm tra nhanh xem cache có đủ không (không load toàn bộ data).
    Dùng để quyết định có cần fetch mới không.
    """
    path = get_cache_path(base_dir, exchange, symbol, timeframe, data_type)
    if not path.exists():
        return False

    try:
        schema = pq.read_schema(path)
        if "timestamp" in schema.names:
            cols_to_read = ["timestamp"]
        elif "__index_level_0__" in schema.names:
            cols_to_read = ["__index_level_0__"]
        else:
            cols_to_read = []
        df_index = pq.read_table(path, columns=cols_to_read).to_pandas()
        df_index = ensure_utc_index(df_index)
        if len(df_index) == 0 or not isinstance(df_index.index, pd.DatetimeIndex):
            return False
        cached_min = df_index.index.min()
        cached_max = df_index.index.max()
        coverage_end = cached_max + timeframe_to_timedelta(timeframe)
        return bool(cached_min <= since and (cached_max >= until or coverage_end >= until))
    except Exception as e:
        logger.warning("[Cache] Không thể đọc metadata từ {}: {}", path, e)
        return False


# ---------------------------------------------------------------------------
# Data Quality & Gap Detection
# ---------------------------------------------------------------------------

def detect_gaps(
    df: pd.DataFrame,
    timeframe: str,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Phát hiện khoảng trống dữ liệu (missing candles).

    Args:
        df:        DataFrame với DatetimeIndex đã sắp xếp.
        timeframe: Chuỗi timeframe (vd: "4h", "15m", "1m")

    Returns:
        List các (gap_start, gap_end). Rỗng nếu không có gap.
    """
    if df.empty or len(df) < 2:
        return []

    expected_freq = timeframe_to_timedelta(timeframe)
    gaps = []
    timestamps = df.index.sort_values()

    for i in range(1, len(timestamps)):
        actual_delta = timestamps[i] - timestamps[i - 1]
        if actual_delta > expected_freq * 1.5:  # cho phép 50% tolerance
            gaps.append((timestamps[i - 1], timestamps[i]))

    if gaps:
        logger.warning(
            "[Cache] Phát hiện {} khoảng trống dữ liệu trong {} nến (timeframe={}):",
            len(gaps), len(df), timeframe
        )
        for gs, ge in gaps[:5]:  # chỉ log 5 gap đầu tiên
            logger.warning("  Gap: {} → {} ({} thiếu)", gs, ge,
                           int((ge - gs) / expected_freq) - 1)
        if len(gaps) > 5:
            logger.warning("  ... và {} gaps khác.", len(gaps) - 5)

    return gaps


# ---------------------------------------------------------------------------
# Internal helpers & public utility functions
# ---------------------------------------------------------------------------

def _read_parquet(path: Path) -> pd.DataFrame:
    """Đọc Parquet file, trả về DataFrame."""
    try:
        table = pq.read_table(path)
        return table.to_pandas()
    except Exception as e:
        logger.error("[Cache] Lỗi khi đọc Parquet file {}: {}", path, e)
        return pd.DataFrame()


def ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Đảm bảo index của DataFrame là DatetimeTZAware UTC và chuẩn hóa resolution về 'ms'.
    Hỗ trợ cả trường hợp index là DatetimeIndex lẫn cột 'timestamp'.
    """
    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

    if isinstance(df.index, pd.DatetimeIndex):
        if hasattr(df.index, "as_unit"):
            df.index = df.index.as_unit("ms")
    return df


def _is_cache_sufficient(
    df_slice: pd.DataFrame,
    since: pd.Timestamp,
    until: pd.Timestamp,
    timeframe: str,
) -> bool:
    """
    Kiểm tra df_slice có đủ dữ liệu cho khoảng [since, until] không.
    Cho phép tối đa 1% candles bị thiếu (tolerance cho các gap nhỏ trên Binance).
    """
    if df_slice.empty:
        return False

    freq = timeframe_to_timedelta(timeframe)
    expected_count = int((until - since) / freq) + 1
    actual_count = len(df_slice)

    # 99% coverage là đủ (Binance đôi khi thiếu 1-2 nến trong gap maintenance)
    return actual_count >= expected_count * 0.99


def timeframe_to_timedelta(timeframe: str) -> pd.Timedelta:
    """Chuyển string timeframe sang pd.Timedelta."""
    mapping = {
        "1m": pd.Timedelta(minutes=1),
        "3m": pd.Timedelta(minutes=3),
        "5m": pd.Timedelta(minutes=5),
        "15m": pd.Timedelta(minutes=15),
        "30m": pd.Timedelta(minutes=30),
        "1h": pd.Timedelta(hours=1),
        "2h": pd.Timedelta(hours=2),
        "4h": pd.Timedelta(hours=4),
        "6h": pd.Timedelta(hours=6),
        "8h": pd.Timedelta(hours=8),
        "12h": pd.Timedelta(hours=12),
        "1d": pd.Timedelta(days=1),
        "3d": pd.Timedelta(days=3),
        "1w": pd.Timedelta(weeks=1),
    }
    if timeframe not in mapping:
        raise ValueError(f"Timeframe không hỗ trợ: '{timeframe}'. Hợp lệ: {list(mapping.keys())}")
    return mapping[timeframe]


# Aliases for backwards compatibility
_ensure_utc_index = ensure_utc_index
_timeframe_to_timedelta = timeframe_to_timedelta
