"""
binance_vision_downloader.py - Historical Open Interest from Binance Data Vision
================================================================================
Tải dữ liệu Open Interest lịch sử sâu (từ 2021 đến nay) từ kho dữ liệu mở
chính thức của Binance (data.binance.vision).
Hoàn toàn MIỄN PHÍ, PUBLIC, KHÔNG CẦN API KEY.

Cấu trúc URL Binance Vision (Daily Metrics):
  https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/{symbol}-metrics-{YYYY-MM-DD}.zip
  Bên trong zip: {symbol}-metrics-{YYYY-MM-DD}.csv (tần suất ghi nhận 5 phút/lần).

QUY TẮC CHỐNG LOOKAHEAD BIAS (BẮT BUỘC):
  - Dữ liệu 5 phút khi downsample sang các timeframe mục tiêu (4h, 15m, 1m)
    được thực hiện bằng phương pháp FORWARD-FILL (lấy giá trị cuối cùng đã biết
    tại hoặc trước mốc thời gian đóng nến).
  - TUYỆT ĐỐI KHÔNG dùng interpolate (nội suy tuyến tính) vì nội suy sẽ dùng
    giá trị tương lai để suy đoán giá trị quá khứ -> Lookahead bias.
"""
from __future__ import annotations

import concurrent.futures
import io
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from src.data_layer.cache_manager import (
    detect_gaps,
    ensure_utc_index,
    save_to_cache,
    timeframe_to_timedelta,
)

# Base URL của Binance Data Vision
BINANCE_VISION_METRICS_BASE = "https://data.binance.vision/data/futures/um/daily/metrics"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CryptoPaperTradingAgent/1.0"
MAX_RETRIES = 3
BACKOFF_BASE = 1.5


# ---------------------------------------------------------------------------
# Single day downloader
# ---------------------------------------------------------------------------

def download_daily_metrics(
    symbol: str,
    date_str: str,
    timeout: int = 15,
) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
    """
    Tải và giải nén 1 file metrics ngày từ Binance Data Vision.

    Args:
        symbol:   Ký hiệu cặp (vd: "BTCUSDT")
        date_str: Ngày định dạng "YYYY-MM-DD"
        timeout:  Timeout cho HTTP request (giây)

    Returns:
        Tuple: (date_str, DataFrame hoặc None, error_message hoặc None)
    """
    safe_symbol = symbol.replace("/", "").upper()
    filename = f"{safe_symbol}-metrics-{date_str}.zip"
    url = f"{BINANCE_VISION_METRICS_BASE}/{safe_symbol}/{filename}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    return date_str, None, f"HTTP {resp.status}"

                zip_bytes = resp.read()

            # Giải nén trong RAM
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                if not csv_names:
                    return date_str, None, "Không tìm thấy file CSV trong zip"

                with z.open(csv_names[0]) as csv_file:
                    df = pd.read_csv(csv_file)

            # Validate các cột cần thiết
            if "create_time" not in df.columns or "sum_open_interest" not in df.columns:
                return date_str, None, f"Thiếu cột cần thiết. Columns: {list(df.columns)}"

            df["create_time"] = pd.to_datetime(df["create_time"], utc=True)
            df = df.set_index("create_time")
            df = df[["sum_open_interest"]].rename(columns={"sum_open_interest": "open_interest"})
            df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce")
            df = df.dropna().sort_index()

            return date_str, df, None

        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Ngày này không có trên Binance Vision (chưa có hoặc ngày nghỉ/lỗi)
                return date_str, None, "HTTP 404 (Không tồn tại trên Binance Vision)"
            elif attempt == MAX_RETRIES:
                return date_str, None, f"HTTP {e.code}: {e.reason}"
            time.sleep(BACKOFF_BASE ** attempt)

        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == MAX_RETRIES:
                return date_str, None, f"Network error: {str(e)}"
            time.sleep(BACKOFF_BASE ** attempt)

        except Exception as e:
            return date_str, None, f"Lỗi không xác định: {str(e)}"

    return date_str, None, "Vượt quá số lần retry"


# ---------------------------------------------------------------------------
# Multi-day range downloader
# ---------------------------------------------------------------------------

def download_historical_oi_range(
    symbol: str,
    start_date: str,
    end_date: str,
    max_workers: int = 8,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Tải toàn bộ dữ liệu OI hàng ngày trong khoảng [start_date, end_date].
    Chạy đa luồng song song với ThreadPoolExecutor để tăng tốc độ.

    Args:
        symbol:      Ký hiệu cặp (vd: "BTCUSDT")
        start_date:  Ngày bắt đầu "YYYY-MM-DD"
        end_date:    Ngày kết thúc "YYYY-MM-DD"
        max_workers: Số luồng tải song song (mặc định: 8)

    Returns:
        Tuple: (DataFrame 5-minute tổng hợp, List các ngày tải thất bại)
    """
    dates = pd.date_range(start=start_date, end=end_date, freq="D").strftime("%Y-%m-%d").tolist()
    total_days = len(dates)
    logger.info("[BinanceVision] Bắt đầu tải OI {} cho {} ngày ({} → {})...", symbol, total_days, start_date, end_date)

    dfs: List[pd.DataFrame] = []
    failed_dates: List[str] = []

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_date = {
            executor.submit(download_daily_metrics, symbol, d): d for d in dates
        }

        completed = 0
        for future in concurrent.futures.as_completed(future_to_date):
            d = future_to_date[future]
            try:
                date_str, df, err = future.result()
                if df is not None and not df.empty:
                    dfs.append(df)
                else:
                    failed_dates.append(date_str)
                    logger.debug("[BinanceVision] Bỏ qua ngày {}: {}", date_str, err)
            except Exception as exc:
                failed_dates.append(d)
                logger.warning("[BinanceVision] Lỗi ngoại lệ ngày {}: {}", d, exc)

            completed += 1
            if completed % 100 == 0 or completed == total_days:
                logger.info("[BinanceVision] Tiến độ: {}/{} ngày ({:.1f}%)", completed, total_days, (completed / total_days) * 100)

    elapsed = time.time() - t0

    if not dfs:
        logger.warning("[BinanceVision] Không tải được dữ liệu ngày nào trong khoảng {} → {}", start_date, end_date)
        return pd.DataFrame(), failed_dates

    # Gộp toàn bộ các ngày thành 1 DataFrame liên tục
    combined_5m = pd.concat(dfs).sort_index()
    combined_5m = combined_5m[~combined_5m.index.duplicated(keep="last")]

    logger.info(
        "[BinanceVision] Tải xong trong {:.2f}s! Thành công: {}/{} ngày ({:.2f}%). Thất bại: {} ngày.",
        elapsed, len(dfs), total_days, (len(dfs) / total_days) * 100, len(failed_dates)
    )

    if failed_dates:
        logger.warning(
            "[BinanceVision] Danh sách ngày không tải được (sẽ dùng Fallback Phương án B nếu cần): {}",
            failed_dates[:10] + ([f"... và {len(failed_dates)-10} ngày khác"] if len(failed_dates) > 10 else [])
        )

    return combined_5m, sorted(failed_dates)


# ---------------------------------------------------------------------------
# Anti-Lookahead Downsampler
# ---------------------------------------------------------------------------

def downsample_oi_to_timeframe(
    df_5m: pd.DataFrame,
    target_timeframe: str,
) -> pd.DataFrame:
    """
    Downsample chuỗi Open Interest 5 phút về khung thời gian mục tiêu.

    QUY TẮC CHỐNG LOOKAHEAD BIAS:
      - Tại mỗi mốc đóng nến T của target_timeframe, ta lấy giá trị OI 5 phút
        gần nhất được ghi nhận tại hoặc trước T (direction='backward' / last known).
      - KHÔNG dùng nội suy tuyến tính (linear interpolation) vì sẽ nhìn thấy
        giá trị OI của tương lai.
      - Nếu target_timeframe là 1m: giá trị 5 phút được forward-fill (kéo dài)
        sang các nến 1m kế tiếp cho đến khi có bản ghi 5 phút mới.

    Args:
        df_5m:            DataFrame 5 phút gốc với index UTC
        target_timeframe: "4h", "15m", "1m", v.v.

    Returns:
        DataFrame với DatetimeIndex UTC theo target_timeframe và cột 'open_interest'.
    """
    if df_5m.empty:
        return pd.DataFrame()

    df_5m = ensure_utc_index(df_5m)
    freq_delta = timeframe_to_timedelta(target_timeframe)

    if target_timeframe == "1m":
        # Khung 1m: resample lên 1m và forward-fill tối đa 5 nến
        resampled = df_5m.resample("1min").ffill(limit=5)
    else:
        # Khung 15m, 4h, 1d...: dùng closed='right', label='right' để đảm bảo
        # giá trị tại mốc đóng nến T chỉ chứa dữ liệu đến T (chống lookahead bias)
        resample_str = target_timeframe.replace("m", "min")
        resampled = df_5m.resample(resample_str, closed="right", label="right").last().ffill(limit=2)

    resampled = resampled.dropna()
    resampled.sort_index(inplace=True)
    return resampled


# ---------------------------------------------------------------------------
# High-level Sync to Parquet Cache
# ---------------------------------------------------------------------------

def sync_vision_oi_to_cache(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframes: List[str],
    base_dir: str = "data/raw",
    exchange: str = "binance",
    max_workers: int = 8,
) -> Dict[str, object]:
    """
    Tải toàn bộ OI lịch sử từ Binance Vision, downsample sang các timeframe
    yêu cầu, và merge trực tiếp vào Parquet Cache.

    Args:
        symbol:      Ký hiệu cặp (vd: "BTC/USDT" hoặc "BTCUSDT")
        start_date:  Ngày bắt đầu "YYYY-MM-DD"
        end_date:    Ngày kết thúc "YYYY-MM-DD"
        timeframes:  Danh sách timeframe cần downsample (vd: ["4h", "15m", "1m"])
        base_dir:    Thư mục gốc cache (vd: "data/raw")
        exchange:    Tên sàn ("binance")
        max_workers: Số luồng tải

    Returns:
        Dict báo cáo kết quả đồng bộ.
    """
    safe_symbol = symbol.replace("/", "").upper()

    # 1. Tải dữ liệu 5 phút gốc
    df_5m, failed_dates = download_historical_oi_range(
        symbol=safe_symbol,
        start_date=start_date,
        end_date=end_date,
        max_workers=max_workers,
    )

    if df_5m.empty:
        logger.error("[BinanceVision] Không có dữ liệu để đồng bộ vào cache.")
        return {
            "symbol": safe_symbol,
            "status": "FAILED",
            "total_5m_rows": 0,
            "failed_dates": failed_dates,
        }

    # 2. Downsample và lưu cache cho từng timeframe
    saved_summary = {}
    for tf in timeframes:
        df_downsampled = downsample_oi_to_timeframe(df_5m, tf)
        if not df_downsampled.empty:
            save_to_cache(
                df=df_downsampled,
                base_dir=base_dir,
                exchange=exchange,
                symbol=safe_symbol,
                timeframe=tf,
                data_type="open_interest",
            )
            saved_summary[tf] = len(df_downsampled)
            logger.info("[BinanceVision] Đã lưu cache OI {} {} → {} nến", safe_symbol, tf, len(df_downsampled))
        else:
            saved_summary[tf] = 0

    total_expected_days = len(pd.date_range(start_date, end_date, freq="D"))
    successful_days = total_expected_days - len(failed_dates)
    coverage_pct = (successful_days / total_expected_days) * 100 if total_expected_days > 0 else 0.0

    report = {
        "symbol": safe_symbol,
        "status": "SUCCESS",
        "start_date": start_date,
        "end_date": end_date,
        "total_days_requested": total_expected_days,
        "successful_days": successful_days,
        "failed_days_count": len(failed_dates),
        "failed_dates": failed_dates,
        "coverage_pct": round(coverage_pct, 2),
        "total_5m_rows": len(df_5m),
        "saved_rows_per_timeframe": saved_summary,
    }

    logger.info(
        "[BinanceVision] Đồng bộ hoàn tất! Độ bao phủ: {:.2f}% ({} / {} ngày)",
        coverage_pct, successful_days, total_expected_days
    )
    return report
