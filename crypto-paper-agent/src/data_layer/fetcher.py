"""
fetcher.py - Data Layer: OHLCV + OI + Funding Rate Fetcher
============================================================
Kéo dữ liệu lịch sử BTC/USDT Futures từ Binance public API qua ccxt.
KHÔNG cần API key — chỉ dùng public endpoints.

OUT OF SCOPE (tuyệt đối không làm):
  - Không kết nối API key thật
  - Không đặt lệnh thật
  - Không lưu private key

CHỐNG LOOKAHEAD BIAS:
  - Funding rate được forward-fill theo chiều thời gian (không backward-fill).
  - Forward-fill tối đa 480 nến 1m = 8h = 1 chu kỳ funding, sau đó NaN.
  - Caller (backtest engine) chịu trách nhiệm chỉ nhìn dữ liệu đến nến hiện tại.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Dict, Optional

import ccxt
import numpy as np
import pandas as pd
from loguru import logger

from src.data_layer.cache_manager import (
    detect_gaps,
    get_cache_path,
    has_complete_cache,
    load_from_cache,
    save_to_cache,
    timeframe_to_timedelta,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Binance giới hạn 1500 nến mỗi request OHLCV, 500 cho OI/funding
MAX_CANDLES_PER_REQUEST = 1000   # dùng 1000 để an toàn hơn
MAX_OI_PER_REQUEST = 500
MAX_FUNDING_PER_REQUEST = 1000

# Retry config
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2.0


# ---------------------------------------------------------------------------
# Exchange initialization
# ---------------------------------------------------------------------------

def _get_exchange() -> ccxt.binance:
    """
    Khởi tạo exchange Binance Futures (public, không cần API key).
    """
    exchange = ccxt.binance({
        "options": {
            "defaultType": "future",   # Binance USDT-M Futures
        },
        "enableRateLimit": True,       # ccxt tự rate-limit
    })
    return exchange


# ---------------------------------------------------------------------------
# OHLCV Fetcher
# ---------------------------------------------------------------------------

def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    since: pd.Timestamp,
    until: pd.Timestamp,
    config: dict,
) -> pd.DataFrame:
    """
    Kéo OHLCV từ Binance Futures public API.

    Args:
        symbol:    Ký hiệu cặp giao dịch, vd: "BTC/USDT"
        timeframe: Khung thời gian: "4h", "15m", "1m"
        since:     Thời điểm bắt đầu (inclusive), UTC
        until:     Thời điểm kết thúc (inclusive), UTC
        config:    Dict config từ default_config.yaml

    Returns:
        DataFrame với DatetimeIndex (UTC) và các cột:
        open, high, low, close, volume, taker_buy_base_volume

    Lưu ý về chống lookahead bias:
        - Dữ liệu OHLCV là closed candles: mỗi hàng tại timestamp T
          đại diện cho nến đã đóng vào thời điểm T.
        - Nến T chỉ được dùng để ra quyết định SAU khi T đã đóng.
    """
    exchange = _get_exchange()
    since_ms = int(since.timestamp() * 1000)
    until_ms = int(until.timestamp() * 1000)

    logger.info("[Fetcher] Bắt đầu fetch OHLCV {} {} từ {} đến {}", symbol, timeframe, since.date(), until.date())

    all_candles = []
    current_since_ms = since_ms

    while current_since_ms < until_ms:
        candles = _fetch_ohlcv_chunk(exchange, symbol, timeframe, current_since_ms)
        if not candles:
            break

        all_candles.extend(candles)

        last_ts = candles[-1][0]
        if last_ts >= until_ms or len(candles) < MAX_CANDLES_PER_REQUEST:
            break

        # Bước tiếp theo bắt đầu ngay sau candle cuối cùng
        timeframe_ms = _timeframe_to_ms(timeframe)
        current_since_ms = last_ts + timeframe_ms

        # ccxt đã có rate limiting, thêm nhỏ delay để an toàn
        time.sleep(0.2)

    if not all_candles:
        logger.warning("[Fetcher] Không có dữ liệu OHLCV cho {} {} từ {} đến {}", symbol, timeframe, since, until)
        return pd.DataFrame()

    df = _candles_to_dataframe(all_candles)

    # Lọc đúng khoảng thời gian (bao gồm until)
    df = df.loc[since:until]

    # Kiểm tra và log gaps
    detect_gaps(df, timeframe)

    logger.info("[Fetcher] OHLCV {} {} → {} nến", symbol, timeframe, len(df))
    return df


def _fetch_ohlcv_chunk(
    exchange: ccxt.binance,
    symbol: str,
    timeframe: str,
    since_ms: int,
) -> list:
    """Fetch 1 chunk OHLCV với retry và exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            # Ưu tiên lấy trực tiếp từ fapiPublicGetKlines để có cả taker_buy_base_volume (cột 9)
            if hasattr(exchange, "fapiPublicGetKlines"):
                try:
                    safe_symbol = symbol.replace("/", "")
                    raw_klines = exchange.fapiPublicGetKlines({
                        "symbol": safe_symbol,
                        "interval": timeframe,
                        "startTime": since_ms,
                        "limit": MAX_CANDLES_PER_REQUEST,
                    })
                    if raw_klines:
                        candles = [
                            [
                                int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]), float(k[9])
                            ]
                            for k in raw_klines
                        ]
                        return candles
                except (ccxt.RateLimitExceeded, ccxt.NetworkError):
                    raise
                except Exception as ex:
                    logger.debug(f"[Fetcher] fapiPublicGetKlines không thành công ({ex}), fallback sang fetch_ohlcv.")

            candles = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=since_ms,
                limit=MAX_CANDLES_PER_REQUEST,
            )
            return candles
        except ccxt.RateLimitExceeded as e:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] Rate limit exceeded. Chờ {}s rồi thử lại (lần {}/{})", wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
        except ccxt.NetworkError as e:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] Network error: {}. Chờ {}s (lần {}/{})", str(e)[:100], wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
        except ccxt.ExchangeError as e:
            logger.error("[Fetcher] Exchange error khi fetch OHLCV: {}", str(e)[:200])
            return []
    logger.error("[Fetcher] Đã thử {} lần mà vẫn thất bại khi fetch OHLCV.", MAX_RETRIES)
    return []


def _candles_to_dataframe(candles: list) -> pd.DataFrame:
    """
    Chuyển list candles từ ccxt sang DataFrame.
    ccxt format: [timestamp_ms, open, high, low, close, volume]
    Binance Futures thêm: taker_buy_base_volume (ở vị trí 6 nếu có)
    """
    if candles and len(candles[0]) > 6:
        cols = ["timestamp", "open", "high", "low", "close", "volume", "taker_buy_base_volume"]
        df = pd.DataFrame([c[:7] for c in candles], columns=cols)
    else:
        cols = ["timestamp", "open", "high", "low", "close", "volume"]
        df = pd.DataFrame(candles, columns=cols)
        df["taker_buy_base_volume"] = df["volume"] * 0.5
        logger.debug("[Fetcher] taker_buy_base_volume không có trong API response, dùng ước tính 50%.")

    # Chuyển timestamp từ ms sang DatetimeIndex UTC
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df.sort_index(inplace=True)

    # Loại bỏ duplicate timestamps
    df = df[~df.index.duplicated(keep="last")]

    return df


# ---------------------------------------------------------------------------
# Open Interest Fetcher
# ---------------------------------------------------------------------------

def fetch_open_interest(
    symbol: str,
    timeframe: str,
    since: pd.Timestamp,
    until: pd.Timestamp,
    config: dict,
) -> pd.DataFrame:
    """
    Kéo Open Interest lịch sử cho BTC/USDT Futures (public endpoint).
    Endpoint REST: GET /futures/data/openInterestHist
    Binance Data Vision: data.binance.vision (daily metrics 5m)

    Cơ chế Hybrid:
      1. Khoảng lịch sử sâu (> boundary = now_utc - 2 ngày): lấy từ Binance Data Vision.
      2. Khoảng thời gian gần nhất (>= boundary đến hiện tại): lấy từ Binance REST API.
      3. Ghép nối 2 phần (concat, sort_index, dedupe), đảm bảo không có NaN ở đuôi gần nhất.

    Args:
        symbol:    Ký hiệu cặp giao dịch, vd: "BTC/USDT"
        timeframe: Khung thời gian: "4h", "15m", "1m" (Binance hỗ trợ: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
        since, until: Khoảng thời gian UTC
        config:    Dict cấu hình từ yaml

    Returns:
        DataFrame với DatetimeIndex (UTC) và cột: open_interest

    Lưu ý về chống lookahead bias:
        - OI tại timestamp T là giá trị đã settle vào cuối interval T.
        - Hoàn toàn an toàn để dùng OI[T] khi ra quyết định tại T.
    """
    # Đảm bảo timezone-aware UTC cho since và until
    if since.tzinfo is None:
        since = since.tz_localize("UTC")
    else:
        since = since.tz_convert("UTC")

    if until.tzinfo is None:
        until = until.tz_localize("UTC")
    else:
        until = until.tz_convert("UTC")

    oi_timeframe = _map_to_oi_timeframe(timeframe)
    futures_symbol = symbol.replace("/", "")
    exchange = _get_exchange()

    now_utc = pd.Timestamp.now(tz="UTC")
    # Buffer 2 ngày cho độ trễ publish của Binance Data Vision
    boundary = now_utc - pd.Timedelta(days=2)
    is_historical_beyond_30d = (now_utc - since).days > 28
    use_vision = config.get("open_interest", {}).get("use_binance_vision_historical", True)

    # 1. Nếu không kích hoạt Binance Vision hoặc khoảng thời gian hoàn toàn nằm trong 28 ngày gần nhất:
    # Lấy toàn bộ qua REST API
    if not (is_historical_beyond_30d and use_vision):
        logger.info(
            "[Fetcher] Fetch OI {} {} hoàn toàn qua REST API từ {} đến {}",
            symbol, oi_timeframe, since.date(), until.date()
        )
        df_rest = _fetch_oi_rest(exchange, futures_symbol, oi_timeframe, since, until)
        detect_gaps(df_rest, oi_timeframe)
        logger.info("[Fetcher] REST API trả về {} records OI cho {} {}", len(df_rest), symbol, oi_timeframe)
        return df_rest

    # 2. Cơ chế Hybrid: kết hợp Binance Vision (lịch sử) + REST API (gần nhất)
    parts: list[pd.DataFrame] = []

    # Phần 1: Binance Vision cho [since, min(until, boundary)]
    vision_end = min(until, boundary)
    if since < vision_end:
        logger.info(
            "[Fetcher] [Hybrid Part 1] Tải OI lịch sử từ Binance Vision cho {} {} từ {} đến {}",
            symbol, oi_timeframe, since.date(), vision_end.date()
        )
        try:
            from src.data_layer.binance_vision_downloader import (
                download_historical_oi_range,
                downsample_oi_to_timeframe,
            )
            df_5m, failed_dates = download_historical_oi_range(
                symbol=futures_symbol,
                start_date=since.strftime("%Y-%m-%d"),
                end_date=vision_end.strftime("%Y-%m-%d"),
            )
            if not df_5m.empty:
                df_vision = downsample_oi_to_timeframe(df_5m, oi_timeframe)
                df_vision = df_vision.loc[since:vision_end]
                parts.append(df_vision)
                logger.info(
                    "[Fetcher] Binance Vision trả về {} records OI [{} → {}]",
                    len(df_vision), since.date(), vision_end.date()
                )
        except Exception as e:
            logger.warning("[Fetcher] Lỗi khi tải Binance Vision: {}. Tiếp tục với REST API nếu có thể...", e)

    # Phần 2: REST API cho [max(since, boundary), until] nếu until > boundary
    if until > boundary:
        rest_since = max(since, boundary)
        logger.info(
            "[Fetcher] [Hybrid Part 2] Fetch OI gần nhất từ REST API cho {} {} từ {} đến {}",
            symbol, oi_timeframe, rest_since.date(), until.date()
        )
        try:
            df_rest = _fetch_oi_rest(exchange, futures_symbol, oi_timeframe, rest_since, until)
            if not df_rest.empty:
                parts.append(df_rest)
                logger.info(
                    "[Fetcher] REST API trả về {} records OI [{} → {}]",
                    len(df_rest), rest_since.date(), until.date()
                )
        except Exception as e:
            logger.warning("[Fetcher] Lỗi khi fetch REST API phần gần nhất: {}", e)

    if not parts:
        logger.warning(
            "[Fetcher] Không có dữ liệu OI cho {} từ {} đến {} (cả Vision lẫn REST đều không có)",
            symbol, since, until
        )
        return pd.DataFrame()

    # Ghép 2 phần: concat, sort, deduplicate (ưu tiên REST cho các điểm trùng lặp ở boundary)
    combined = pd.concat(parts).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    result = combined.loc[since:until]

    detect_gaps(result, oi_timeframe)
    vision_start_str = since.date()
    vision_end_str = vision_end.date() if since < vision_end else "N/A"
    rest_start_str = max(since, boundary).date() if until > boundary else "N/A"
    rest_end_str = until.date() if until > boundary else "N/A"

    logger.info(
        "[Fetcher] Hoàn thành Hybrid OI {} {}: tổng {} records (Vision: [{} → {}], REST: [{} → {}])",
        symbol, oi_timeframe, len(result),
        vision_start_str, vision_end_str, rest_start_str, rest_end_str
    )
    return result


def _fetch_oi_rest(
    exchange: ccxt.binance,
    futures_symbol: str,
    oi_timeframe: str,
    since: pd.Timestamp,
    until: pd.Timestamp,
) -> pd.DataFrame:
    """
    Fetch chuỗi OI liên tục từ Binance Futures REST API qua cơ chế chunking.
    """
    all_records = []
    current_since = since

    while current_since < until:
        chunk = _fetch_oi_chunk(exchange, futures_symbol, oi_timeframe, current_since, until)
        if not chunk:
            break

        all_records.extend(chunk)
        last_ts = pd.to_datetime(chunk[-1]["timestamp"], unit="ms", utc=True)

        if last_ts >= until or len(chunk) < MAX_OI_PER_REQUEST:
            break

        timeframe_ms = _timeframe_to_ms(oi_timeframe)
        new_since = last_ts + pd.Timedelta(milliseconds=timeframe_ms)
        if new_since <= current_since:
            break
        current_since = new_since
        time.sleep(0.3)

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")

    if "sumOpenInterest" in df.columns:
        df = df[["sumOpenInterest"]].rename(columns={"sumOpenInterest": "open_interest"})
    elif "openInterest" in df.columns:
        df = df[["openInterest"]].rename(columns={"openInterest": "open_interest"})

    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce")
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    return df.loc[since:until]


def _fetch_oi_chunk(
    exchange: ccxt.binance,
    futures_symbol: str,
    timeframe: str,
    since: pd.Timestamp,
    until: pd.Timestamp,
) -> list:
    """Fetch 1 chunk OI với retry."""
    since_ms = int(since.timestamp() * 1000)
    until_ms = int(until.timestamp() * 1000)

    for attempt in range(MAX_RETRIES):
        try:
            # ccxt wrapper cho /futures/data/openInterestHist
            records = exchange.fetch_open_interest_history(
                symbol=futures_symbol,
                timeframe=timeframe,
                since=since_ms,
                limit=MAX_OI_PER_REQUEST,
                params={"endTime": until_ms},
            )
            # ccxt trả về list of dicts với field 'timestamp'
            return [{"timestamp": r["timestamp"], "sumOpenInterest": r.get("openInterestAmount", r.get("openInterest", 0))} for r in records]
        except ccxt.RateLimitExceeded:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] OI rate limit. Chờ {}s", wait)
            time.sleep(wait)
        except ccxt.NetworkError as e:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] OI network error: {}. Chờ {}s", str(e)[:100], wait)
            time.sleep(wait)
        except Exception as e:
            logger.error("[Fetcher] OI fetch error: {}", str(e)[:200])
            return []
    return []


# ---------------------------------------------------------------------------
# Funding Rate Fetcher
# ---------------------------------------------------------------------------

def fetch_funding_rate(
    symbol: str,
    since: pd.Timestamp,
    until: pd.Timestamp,
    config: dict,
) -> pd.DataFrame:
    """
    Kéo Funding Rate lịch sử từ Binance Futures (public endpoint).
    Funding rate Binance settle mỗi 8h: 00:00, 08:00, 16:00 UTC.

    Returns:
        DataFrame với DatetimeIndex (UTC) và cột: funding_rate
        (Chỉ có ~3 hàng/ngày tại các mốc settle)

    CHỐNG LOOKAHEAD BIAS:
        - DataFrame trả về KHÔNG được forward-fill tại đây.
        - Việc forward-fill để align với OHLCV phải được thực hiện trong
          merge_ohlcv_with_funding() với giới hạn tối đa 480 nến 1m.
        - Không bao giờ backward-fill funding rate.
    """
    exchange = _get_exchange()
    since_ms = int(since.timestamp() * 1000)
    until_ms = int(until.timestamp() * 1000)

    logger.info("[Fetcher] Bắt đầu fetch Funding Rate {} từ {} đến {}", symbol, since.date(), until.date())

    all_records = []
    current_since_ms = since_ms

    while current_since_ms < until_ms:
        chunk = _fetch_funding_chunk(exchange, symbol, current_since_ms, until_ms)
        if not chunk:
            break

        all_records.extend(chunk)
        last_ts = chunk[-1]["timestamp"]

        if last_ts >= until_ms or len(chunk) < MAX_FUNDING_PER_REQUEST:
            break

        current_since_ms = last_ts + 1
        time.sleep(0.2)

    if not all_records:
        logger.warning("[Fetcher] Không có dữ liệu funding rate cho {} từ {} đến {}", symbol, since, until)
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df = df[["funding_rate"]].dropna()
    df["funding_rate"] = pd.to_numeric(df["funding_rate"], errors="coerce")
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    df = df.loc[since:until]

    logger.info("[Fetcher] Funding Rate {} → {} records", symbol, len(df))
    return df


def _fetch_funding_chunk(
    exchange: ccxt.binance,
    symbol: str,
    since_ms: int,
    until_ms: int,
) -> list:
    """Fetch 1 chunk funding rate với retry."""
    for attempt in range(MAX_RETRIES):
        try:
            records = exchange.fetch_funding_rate_history(
                symbol=symbol,
                since=since_ms,
                limit=MAX_FUNDING_PER_REQUEST,
                params={"endTime": until_ms},
            )
            normalized = []
            for idx, record in enumerate(records):
                if not isinstance(record, dict):
                    raise TypeError(f"Funding record {idx} must be a mapping")
                if "timestamp" not in record:
                    raise ValueError(f"Funding record {idx} is missing timestamp")
                raw_rate = record.get("fundingRate")
                if raw_rate is None:
                    raw_rate = record.get("funding")
                if raw_rate is None:
                    raise ValueError(
                        f"Funding record {idx} is missing both fundingRate and funding; "
                        "refusing to synthesize a zero rate"
                    )
                if type(raw_rate) is bool:
                    raise TypeError(f"Funding record {idx} rate cannot be boolean")
                rate = float(raw_rate)
                if not math.isfinite(rate):
                    raise ValueError(f"Funding record {idx} rate must be finite, got {rate}")
                normalized.append({"timestamp": record["timestamp"], "funding_rate": rate})
            return normalized
        except ccxt.RateLimitExceeded:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] Funding rate limit. Chờ {}s", wait)
            time.sleep(wait)
        except ccxt.NetworkError as e:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] Funding network error: {}. Chờ {}s", str(e)[:100], wait)
            time.sleep(wait)
        except (TypeError, ValueError, KeyError):
            # Malformed exchange payload is an integrity failure, not a
            # recoverable empty response.  Propagate it to keep funding
            # accounting fail-closed.
            raise
        except Exception as e:
            logger.error("[Fetcher] Funding fetch error: {}", str(e)[:200])
            return []
    return []


# ---------------------------------------------------------------------------
# Merge & Align
# ---------------------------------------------------------------------------

def merge_ohlcv_with_oi_and_funding(
    ohlcv_df: pd.DataFrame,
    oi_df: pd.DataFrame,
    funding_df: pd.DataFrame,
    timeframe: str,
    config: dict,
) -> pd.DataFrame:
    """
    Merge OHLCV với OI và Funding Rate.

    QUY TẮC CHỐNG LOOKAHEAD BIAS (bắt buộc):
    1. OI: merge_asof với direction='backward' — tại mỗi nến OHLCV,
       dùng giá trị OI gần nhất TRƯỚC đó (không dùng giá trị tương lai).
    2. Funding Rate: forward-fill sau khi merge, tối đa N nến
       (max_forward_fill_candles từ config, mặc định 480 nến 1m = 8h).
       KHÔNG backward-fill.
    3. Nến OHLCV không có OI gần đó (thiếu dữ liệu) → OI = NaN (giữ nguyên).

    Returns:
        DataFrame đầy đủ với: open, high, low, close, volume,
        taker_buy_base_volume, open_interest, funding_rate
    """
    df = ohlcv_df.copy()
    if hasattr(df.index, "as_unit"):
        df.index = df.index.as_unit("ms")

    # 1. Merge OI: backward merge (dùng OI đã settle trước hoặc tại nến hiện tại)
    # Phương án B (oi_confluence):
    # - Nếu có dữ liệu OI hợp lệ -> kiểm tra đồng thuận OI trong chiến lược.
    # - Nếu OI là NaN (do thiếu dữ liệu hoặc ngày lỗi) -> cơ chế fallback_when_nan
    #   trong chiến lược sẽ bỏ qua kiểm tra OI và ghi chú 'OI_BYPASSED_HISTORICAL'.
    if not oi_df.empty:
        oi_to_merge = oi_df[["open_interest"]].sort_index()
        if hasattr(oi_to_merge.index, "as_unit"):
            oi_to_merge.index = oi_to_merge.index.as_unit("ms")
        df = pd.merge_asof(
            df.sort_index(),
            oi_to_merge,
            left_index=True,
            right_index=True,
            direction="backward",  # QUAN TRỌNG: không dùng giá trị tương lai
        )
    else:
        df["open_interest"] = float("nan")
        logger.warning("[Fetcher] OI data rỗng, open_interest sẽ là NaN (kích hoạt fallback_when_nan).")

    # Đảm bảo cột open_interest luôn có kiểu float
    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce")

    # --- Merge Funding Rate & Provenance Metadata (Stage 5 / Section 4.5) ---
    if not funding_df.empty:
        funding_to_merge = funding_df[["funding_rate"]].copy().sort_index()
        if hasattr(funding_to_merge.index, "as_unit"):
            funding_to_merge.index = funding_to_merge.index.as_unit("ms")
        funding_to_merge["funding_time"] = funding_to_merge.index

        max_ffill = config.get("funding_rate", {}).get("max_forward_fill_candles", 480)
        tf_delta = timeframe_to_timedelta(timeframe)
        tolerance = tf_delta * max_ffill

        df = pd.merge_asof(
            df.sort_index(),
            funding_to_merge,
            left_index=True,
            right_index=True,
            direction="backward",  # QUAN TRỌNG: không dùng funding tương lai
            tolerance=tolerance,   # QUAN TRỌNG: chỉ forward-fill tối đa max_ffill nến
        )

        is_finite_rate = df["funding_rate"].notna() & np.isfinite(df["funding_rate"])
        has_valid_time = df["funding_time"].notna()
        not_future = df["funding_time"] <= df.index
        not_stale = df["funding_time"] >= (df.index - pd.Timedelta(hours=24))

        df["funding_readiness"] = (is_finite_rate & has_valid_time & not_future & not_stale).astype(bool)
    else:
        df["funding_rate"] = float("nan")
        df["funding_time"] = pd.NaT
        df["funding_readiness"] = False
        logger.warning("[Fetcher] Funding rate data rỗng, funding_rate sẽ là NaN.")

    return df


# ---------------------------------------------------------------------------
# High-level orchestrator
# ---------------------------------------------------------------------------

def fetch_all(
    symbol: str,
    timeframes: list[str],
    since: pd.Timestamp,
    until: pd.Timestamp,
    config: dict,
    force_refresh: bool = False,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch toàn bộ dữ liệu cần thiết cho backtest: OHLCV + OI + Funding.
    Tự động dùng cache nếu đủ dữ liệu. Fetch từ API nếu thiếu.

    Args:
        symbol:        Cặp giao dịch (vd: "BTC/USDT")
        timeframes:    List timeframes cần fetch (vd: ["4h", "15m", "1m"])
        since, until:  Khoảng thời gian UTC
        config:        Config dict
        force_refresh: True = bỏ qua cache và fetch lại từ API

    Returns:
        Dict {timeframe: DataFrame} với đầy đủ columns:
        open, high, low, close, volume, taker_buy_base_volume,
        open_interest, funding_rate

    Lưu ý:
        - DataFrame được sắp xếp theo thời gian tăng dần.
        - Index là DatetimeIndex UTC.
        - Dữ liệu tương lai (> until) không được bao gồm.
    """
    exchange_id = config.get("data", {}).get("exchange", "binance")
    raw_dir = config.get("data", {}).get("raw_data_dir", "data/raw")
    safe_symbol = symbol.replace("/", "")  # "BTCUSDT"

    result: Dict[str, pd.DataFrame] = {}

    for tf in timeframes:
        logger.info("[Fetcher] === Xử lý timeframe {} ===", tf)

        # 1. OHLCV — kiểm tra cache trước
        ohlcv_cached = (not force_refresh) and has_complete_cache(
            raw_dir, exchange_id, safe_symbol, tf, "ohlcv", since, until
        )

        if ohlcv_cached:
            ohlcv_df = load_from_cache(raw_dir, exchange_id, safe_symbol, tf, "ohlcv", since, until)
            logger.info("[Fetcher] OHLCV {} {} → dùng cache ({} nến)", symbol, tf, len(ohlcv_df))
        else:
            ohlcv_df = fetch_ohlcv(symbol, tf, since, until, config)
            if not ohlcv_df.empty:
                save_to_cache(ohlcv_df, raw_dir, exchange_id, safe_symbol, tf, "ohlcv")

        if ohlcv_df is None or ohlcv_df.empty:
            logger.error("[Fetcher] Không có OHLCV data cho {} {}. Bỏ qua timeframe này.", symbol, tf)
            continue

        # 2. OI — dùng timeframe OI tương ứng
        oi_tf = _map_to_oi_timeframe(tf)
        oi_cached = (not force_refresh) and has_complete_cache(
            raw_dir, exchange_id, safe_symbol, oi_tf, "open_interest", since, until
        )

        if oi_cached:
            oi_df = load_from_cache(raw_dir, exchange_id, safe_symbol, oi_tf, "open_interest", since, until)
            logger.info("[Fetcher] OI {} {} → dùng cache ({} records)", symbol, oi_tf, len(oi_df))
        else:
            oi_df = fetch_open_interest(symbol, tf, since, until, config)
            if not oi_df.empty:
                save_to_cache(oi_df, raw_dir, exchange_id, safe_symbol, oi_tf, "open_interest")

        if oi_df is None:
            oi_df = pd.DataFrame()

        # 3. Funding Rate — chỉ fetch 1 lần (dùng chung cho mọi timeframe)
        funding_cached = (not force_refresh) and has_complete_cache(
            raw_dir, exchange_id, safe_symbol, "8h", "funding_rate", since, until
        )

        if funding_cached:
            funding_df = load_from_cache(raw_dir, exchange_id, safe_symbol, "8h", "funding_rate", since, until)
            logger.info("[Fetcher] Funding Rate {} → dùng cache ({} records)", symbol, len(funding_df))
        else:
            funding_df = fetch_funding_rate(symbol, since, until, config)
            if not funding_df.empty:
                save_to_cache(funding_df, raw_dir, exchange_id, safe_symbol, "8h", "funding_rate")

        if funding_df is None:
            funding_df = pd.DataFrame()

        # 4. Merge với quy tắc chống lookahead bias
        merged_df = merge_ohlcv_with_oi_and_funding(ohlcv_df, oi_df, funding_df, tf, config)
        result[tf] = merged_df

        logger.info(
            "[Fetcher] Hoàn thành {} {}: {} nến, OI={}, Funding={}",
            symbol, tf, len(merged_df),
            "OK" if "open_interest" in merged_df.columns and not merged_df["open_interest"].isna().all() else "NaN",
            "OK" if "funding_rate" in merged_df.columns and not merged_df["funding_rate"].isna().all() else "NaN",
        )

    return result


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _timeframe_to_ms(timeframe: str) -> int:
    """Chuyển timeframe string sang milliseconds."""
    mapping = {
        "1m": 60_000,
        "3m": 180_000,
        "5m": 300_000,
        "15m": 900_000,
        "30m": 1_800_000,
        "1h": 3_600_000,
        "2h": 7_200_000,
        "4h": 14_400_000,
        "6h": 21_600_000,
        "8h": 28_800_000,
        "12h": 43_200_000,
        "1d": 86_400_000,
    }
    if timeframe not in mapping:
        raise ValueError(f"Timeframe không hỗ trợ: '{timeframe}'")
    return mapping[timeframe]


def _map_to_oi_timeframe(timeframe: str) -> str:
    """
    Map timeframe OHLCV sang timeframe hỗ trợ bởi Binance OI endpoint.
    Binance OI hỗ trợ: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
    """
    mapping = {
        "1m": "5m",    # 1m OI không có; dùng 5m gần nhất
        "3m": "5m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "8h": "8h",
        "12h": "12h",
        "1d": "1d",
    }
    mapped = mapping.get(timeframe, "1h")
    if mapped != timeframe:
        logger.debug("[Fetcher] OI timeframe {} → {} (Binance không hỗ trợ {})", timeframe, mapped, timeframe)
    return mapped
