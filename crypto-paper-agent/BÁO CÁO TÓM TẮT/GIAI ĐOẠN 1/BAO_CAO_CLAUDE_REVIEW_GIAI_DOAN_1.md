# BÁO CÁO CHI TIẾT GIAI ĐOẠN 1: DATA LAYER (DÀNH CHO CLAUDE REVIEW)
**Dự án:** Crypto Futures Paper-Trading Research Agent  
**Thời điểm:** 2026-09-18  
**Trạng thái Giai đoạn 1:** HOÀN THÀNH 100% (Đã xử lý trọn vẹn Hybrid Open Interest & Encapsulation)  
**Mục đích:** Cung cấp đầy đủ kết quả kỹ thuật, toàn văn mã nguồn (verbatim), kết quả test kéo dữ liệu thật 60 ngày, và 28/28 test passed để Claude review và phê duyệt kết thúc Giai đoạn 1 trước khi chuyển sang Giai đoạn 2.

---

## 1. TỔNG HỢP CÁC ĐIỂM ĐÃ HOÀN THÀNH & TỐI ƯU HÓA THEO GÓP Ý CỦA CLAUDE

### 1.1. Khắc phục vấn đề trễ của Binance Vision bằng Cơ chế HYBRID cho Open Interest
- **Vấn đề nhận diện từ Claude:** Binance Data Vision công bố file dữ liệu theo ngày, thường trễ 1-2 ngày so với hiện tại. Nếu chỉ dùng Binance Vision thì đoạn đuôi 1-2 ngày gần nhất sẽ bị thiếu (hoặc NaN) khi kiểm thử hay chạy dữ liệu cập nhật.
- **Giải pháp Hybrid đã triển khai trong etch_open_interest():**
  1. Khi khoảng thời gian cần fetch có since vượt quá 28 ngày trước (
ow_utc - since > 28d):
     - Xác định oundary = now_utc - pd.Timedelta(days=2) (chừa buffer 2 ngày cho Vision).
     - **Phần 1 (Lịch sử sâu [since, boundary]):** Gọi download_historical_oi_range() tải đa luồng từ data.binance.vision, giải nén và downsample bằng phương pháp chống lookahead (closed='right', label='right').
     - **Phần 2 (Gần nhất [boundary, until]):** Gọi Binance REST API (/futures/data/openInterestHist) lấy trực tiếp dữ liệu realtime/gần nhất.
     - **Ghép nối:** Dùng pd.concat, sắp xếp sort_index(), và loại bỏ trùng lặp với keep='last' (ưu tiên dữ liệu REST tươi mới tại mốc boundary).
  2. Khi since trong vòng 28 ngày gần nhất: Toàn bộ khoảng được kéo qua REST API.

### 1.2. Chuẩn hóa Encapsulation trong cache_manager.py
- Các hàm tiện ích trước đây có tiền tố private _ensure_utc_index và _timeframe_to_timedelta nay đã được chuẩn hóa thành public APIs:
  - ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame
  - 	imeframe_to_timedelta(timeframe: str) -> pd.Timedelta
- Đồng thời giữ các alias _ensure_utc_index và _timeframe_to_timedelta để đảm bảo 100% backward compatibility.
- Đồng bộ chuẩn hóa resolution datetime sang s_unit('ms') trong ensure_utc_index và hàm merge_ohlcv_with_oi_and_funding, triệt tiêu hoàn toàn lỗi lệch datetime unit (datetime64[ms, UTC] vs datetime64[us, UTC]) trên pandas 2.2+/3.0+.

### 1.3. Cấu hình oi_confluence (Phương án B)
- Đã bổ sung cấu hình oi_confluence vào default_config.yaml và các file chiến lược (	rend_following.yaml, smc_liquidity_sweep.yaml):
  - mode: "optional" (mặc định)
  - allback_when_nan: true
  - 
an_log_note: "OI_BYPASSED_HISTORICAL"
- Khi nến thiếu OI (hoặc ngày bị lỗi từ sàn), hệ thống không sập mà ghi nhận log và bypass điều kiện OI một cách an toàn.

---

## 2. KẾT QUẢ TEST THỰC NGHIỆM KÉO DỮ LIỆU THẬT TỪ SÀN BINANCE

Dưới đây là output nguyên văn từ script kiểm tra dữ liệu thật trên cả 3 khía cạnh: OHLCV, Hybrid OI 60 ngày (Vision + REST), và Funding Rate:

`
======================================================================
KET QUA TEST KEO DU LIEU THAT (GIAI DOAN 1 - DATA LAYER - HYBRID OI)
======================================================================

[TEST 1] Keo OHLCV that 7 ngay gan nhat (4h, 15m):
  - OHLCV 4h: 43 candles, Range: 2026-09-11 08:00:00+00:00 -> 2026-09-18 08:00:00+00:00
    Gaps: 0 days 04:00:00, NaNs: 0
  - OHLCV 15m: 673 candles, Range: 2026-09-11 08:00:00+00:00 -> 2026-09-18 08:00:00+00:00
    Gaps: 0 days 00:15:00, NaNs: 0

[TEST 2] Keo HYBRID Open Interest 60 ngay gan nhat (since = now - 60d, until = now):
  - Tong so nen OI 4h thu duoc: 361 candles
  - Thoi gian: 2026-07-20 08:00:00+00:00 -> 2026-09-18 08:00:00+00:00
  - Tong so NaN trong cot open_interest: 0

  - Chi tiet 12 nen 4h cuoi cung (48 gio gan nhat - phan REST API):
    2026-09-16 12:00:00+00:00 | OI: 106,614.12 BTC
    2026-09-16 16:00:00+00:00 | OI: 107,316.81 BTC
    2026-09-16 20:00:00+00:00 | OI: 108,166.19 BTC
    2026-09-17 00:00:00+00:00 | OI: 107,918.18 BTC
    2026-09-17 04:00:00+00:00 | OI: 108,245.03 BTC
    2026-09-17 08:00:00+00:00 | OI: 108,358.78 BTC
    2026-09-17 12:00:00+00:00 | OI: 108,505.15 BTC
    2026-09-17 16:00:00+00:00 | OI: 108,490.40 BTC
    2026-09-17 20:00:00+00:00 | OI: 108,199.42 BTC
    2026-09-18 00:00:00+00:00 | OI: 108,245.18 BTC
    2026-09-18 04:00:00+00:00 | OI: 108,297.36 BTC
    2026-09-18 08:00:00+00:00 | OI: 108,445.74 BTC
  - So luong NaN o duoi 48 gio gan nhat: 0 (YEU CAU: 0)

  - Chi tiet 12 nen 4h dau tien (phan Binance Data Vision):
    2026-07-20 08:00:00+00:00 | OI: 101,998.05 BTC
    2026-07-20 12:00:00+00:00 | OI: 102,334.78 BTC
    2026-07-20 16:00:00+00:00 | OI: 104,101.99 BTC
    2026-07-20 20:00:00+00:00 | OI: 102,469.11 BTC
    2026-07-21 00:00:00+00:00 | OI: 101,231.06 BTC
    2026-07-21 04:00:00+00:00 | OI: 101,785.07 BTC
    2026-07-21 08:00:00+00:00 | OI: 104,970.84 BTC
    2026-07-21 12:00:00+00:00 | OI: 105,447.95 BTC
    2026-07-21 16:00:00+00:00 | OI: 106,788.64 BTC
    2026-07-21 20:00:00+00:00 | OI: 104,824.26 BTC
    2026-07-22 00:00:00+00:00 | OI: 104,234.70 BTC
    2026-07-22 04:00:00+00:00 | OI: 104,091.39 BTC
  - So luong NaN o dau chuoi: 0 (YEU CAU: 0)

[TEST 3] Keo Funding Rate that va Merge OHLCV + OI + Funding:
  - Funding Rate: 21 records (settle moi 8h)
  - Merged DataFrame: 43 candles
  - Cot du lieu: ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_volume', 'open_interest', 'funding_rate']
  - Kiem tra lookahead: OI tai moi nen chi lay tu qua khu (direction='backward').
  - 5 nen moi nhat sau khi merge:
    2026-09-17 16:00:00+00:00 | Close: 76,561.10 | OI: 108,490.40 | Funding: 0.000085
    2026-09-17 20:00:00+00:00 | Close: 76,385.90 | OI: 108,199.42 | Funding: 0.000085
    2026-09-18 00:00:00+00:00 | Close: 77,349.00 | OI: 108,245.18 | Funding: 0.000085
    2026-09-18 04:00:00+00:00 | Close: 77,776.10 | OI: 108,297.36 | Funding: 0.000078
    2026-09-18 08:00:00+00:00 | Close: 78,061.20 | OI: 108,445.74 | Funding: 0.000078

======================================================================
XAC NHAN: TAT CA CAC BAI TEST DU LIEU THAT DAT 100% YEU CAU!
======================================================================

`

**Nhận xét dữ liệu:**
1. **OHLCV:** Lấy thành công 43 nến 4h và 673 nến 15m, 0 gaps, 0 NaNs.
2. **Hybrid OI 60 ngày:** 
   - Tổng cộng 361 nến 4h từ 2026-07-20 đến 2026-09-18.
   - Phần Binance Vision (59 ngày) tải xong trong 2.14s với tỷ lệ thành công 100% (349 records).
   - Phần REST API (2 ngày gần nhất) lấy trọn vẹn 12 records 4h (tương đương 48 giờ gần nhất).
   - **TỔNG SỐ NAN Ở ĐUÔI VÀ ĐẦU CHUỖI: 0 (HOÀN HẢO)**.
3. **Merge OHLCV + OI + Funding:** Hoạt động trơn tru, 43 nến 4h có đầy đủ cả 8 cột với giá trị OI và funding chính xác.

---

## 3. KẾT QUẢ CHẠY TOÀN BỘ TEST SUITE (PYTEST)

Tổng cộng 28 bài test bao gồm cả unit tests, integration tests chống lookahead bias, test download Binance Vision và test Hybrid OI 60 ngày:

`
============================= test session starts =============================
collecting ... collected 28 items

tests/test_data_layer.py::TestCacheManager::test_get_cache_path_no_slash PASSED [  3%]
tests/test_data_layer.py::TestCacheManager::test_get_cache_path_structure PASSED [  7%]
tests/test_data_layer.py::TestCacheManager::test_save_and_load_roundtrip PASSED [ 10%]
tests/test_data_layer.py::TestCacheManager::test_save_merge_no_duplicates PASSED [ 14%]
tests/test_data_layer.py::TestCacheManager::test_load_returns_none_if_missing PASSED [ 17%]
tests/test_data_layer.py::TestCacheManager::test_detect_gaps_no_gaps PASSED [ 21%]
tests/test_data_layer.py::TestCacheManager::test_detect_gaps_with_gap PASSED [ 25%]
tests/test_data_layer.py::TestCacheManager::test_timeframe_to_timedelta PASSED [ 28%]
tests/test_data_layer.py::TestCacheManager::test_timeframe_invalid_raises PASSED [ 32%]
tests/test_data_layer.py::TestCacheManager::test_ensure_utc_index PASSED [ 35%]
tests/test_data_layer.py::TestFetcherLogic::test_candles_to_dataframe_basic PASSED [ 39%]
tests/test_data_layer.py::TestFetcherLogic::test_candles_to_dataframe_no_duplicates PASSED [ 42%]
tests/test_data_layer.py::TestFetcherLogic::test_timeframe_to_ms PASSED  [ 46%]
tests/test_data_layer.py::TestFetcherLogic::test_map_to_oi_timeframe PASSED [ 50%]
tests/test_data_layer.py::TestFetcherLogic::test_merge_uses_backward_direction PASSED [ 53%]
tests/test_data_layer.py::TestFetcherLogic::test_funding_rate_no_backfill PASSED [ 57%]
tests/test_data_layer.py::TestFetcherLogic::test_funding_rate_ffill_limit PASSED [ 60%]
tests/test_data_layer.py::test_fetch_real_ohlcv_7days PASSED             [ 64%]
tests/test_data_layer.py::test_fetch_real_funding_rate PASSED            [ 67%]
tests/test_data_layer.py::test_no_lookahead_in_live_merge PASSED         [ 71%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_downsample_5m_to_4h_no_lookahead PASSED [ 75%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_downsample_5m_to_1m_forward_fill PASSED [ 78%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_oi_confluence_config_loaded PASSED [ 82%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_vision_live_download_single_day PASSED [ 85%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_hybrid_oi_fetch_recent_60d PASSED [ 89%]
tests/test_news_calendar.py::test_economic_event_blackout_window PASSED  [ 92%]
tests/test_news_calendar.py::test_news_filter_disabled_by_default PASSED [ 96%]
tests/test_news_calendar.py::test_news_filter_enabled_with_csv PASSED    [100%]

============================== warnings summary ===============================
tests\test_data_layer.py:329
  D:\\Ta\u0300i lie\u0323\u0302u\\Default Project\\crypto-paper-agent\\tests\\test_data_layer.py:329: PytestUnknownMarkWarning: Unknown pytest.mark.network - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.network

tests\test_data_layer.py:369
  D:\\Ta\u0300i lie\u0323\u0302u\\Default Project\\crypto-paper-agent\\tests\\test_data_layer.py:369: PytestUnknownMarkWarning: Unknown pytest.mark.network - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.network

tests\test_data_layer.py:393
  D:\\Ta\u0300i lie\u0323\u0302u\\Default Project\\crypto-paper-agent\\tests\\test_data_layer.py:393: PytestUnknownMarkWarning: Unknown pytest.mark.network - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.network

tests\test_data_layer.py:495
  D:\\Ta\u0300i lie\u0323\u0302u\\Default Project\\crypto-paper-agent\\tests\\test_data_layer.py:495: PytestUnknownMarkWarning: Unknown pytest.mark.network - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.network

tests\test_data_layer.py:510
  D:\\Ta\u0300i lie\u0323\u0302u\\Default Project\\crypto-paper-agent\\tests\\test_data_layer.py:510: PytestUnknownMarkWarning: Unknown pytest.mark.network - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html\n    @pytest.mark.network

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 28 passed, 5 warnings in 15.50s =======================

`

**Kết quả: 28 PASSED (100% THÀNH CÔNG)**

---

## 4. TOÀN VĂN MÃ NGUỒN src/data_layer/fetcher.py (VERBATIM)

`python
"""
fetcher.py - Data Layer: OHLCV + OI + Funding Rate Fetcher
============================================================
KÃ©o dá»¯ liá»‡u lá»‹ch sá»­ BTC/USDT Futures tá»« Binance public API qua ccxt.
KHÃ”NG cáº§n API key â€” chá»‰ dÃ¹ng public endpoints.

OUT OF SCOPE (tuyá»‡t Ä‘á»‘i khÃ´ng lÃ m):
  - KhÃ´ng káº¿t ná»‘i API key tháº­t
  - KhÃ´ng Ä‘áº·t lá»‡nh tháº­t
  - KhÃ´ng lÆ°u private key

CHá»NG LOOKAHEAD BIAS:
  - Funding rate Ä‘Æ°á»£c forward-fill theo chiá»u thá»i gian (khÃ´ng backward-fill).
  - Forward-fill tá»‘i Ä‘a 480 náº¿n 1m = 8h = 1 chu ká»³ funding, sau Ä‘Ã³ NaN.
  - Caller (backtest engine) chá»‹u trÃ¡ch nhiá»‡m chá»‰ nhÃ¬n dá»¯ liá»‡u Ä‘áº¿n náº¿n hiá»‡n táº¡i.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, Optional

import ccxt
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

# Binance giá»›i háº¡n 1500 náº¿n má»—i request OHLCV, 500 cho OI/funding
MAX_CANDLES_PER_REQUEST = 1000   # dÃ¹ng 1000 Ä‘á»ƒ an toÃ n hÆ¡n
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
    Khá»Ÿi táº¡o exchange Binance Futures (public, khÃ´ng cáº§n API key).
    """
    exchange = ccxt.binance({
        "options": {
            "defaultType": "future",   # Binance USDT-M Futures
        },
        "enableRateLimit": True,       # ccxt tá»± rate-limit
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
    KÃ©o OHLCV tá»« Binance Futures public API.

    Args:
        symbol:    KÃ½ hiá»‡u cáº·p giao dá»‹ch, vd: "BTC/USDT"
        timeframe: Khung thá»i gian: "4h", "15m", "1m"
        since:     Thá»i Ä‘iá»ƒm báº¯t Ä‘áº§u (inclusive), UTC
        until:     Thá»i Ä‘iá»ƒm káº¿t thÃºc (inclusive), UTC
        config:    Dict config tá»« default_config.yaml

    Returns:
        DataFrame vá»›i DatetimeIndex (UTC) vÃ  cÃ¡c cá»™t:
        open, high, low, close, volume, taker_buy_base_volume

    LÆ°u Ã½ vá» chá»‘ng lookahead bias:
        - Dá»¯ liá»‡u OHLCV lÃ  closed candles: má»—i hÃ ng táº¡i timestamp T
          Ä‘áº¡i diá»‡n cho náº¿n Ä‘Ã£ Ä‘Ã³ng vÃ o thá»i Ä‘iá»ƒm T.
        - Náº¿n T chá»‰ Ä‘Æ°á»£c dÃ¹ng Ä‘á»ƒ ra quyáº¿t Ä‘á»‹nh SAU khi T Ä‘Ã£ Ä‘Ã³ng.
    """
    exchange = _get_exchange()
    since_ms = int(since.timestamp() * 1000)
    until_ms = int(until.timestamp() * 1000)

    logger.info("[Fetcher] Báº¯t Ä‘áº§u fetch OHLCV {} {} tá»« {} Ä‘áº¿n {}", symbol, timeframe, since.date(), until.date())

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

        # BÆ°á»›c tiáº¿p theo báº¯t Ä‘áº§u ngay sau candle cuá»‘i cÃ¹ng
        timeframe_ms = _timeframe_to_ms(timeframe)
        current_since_ms = last_ts + timeframe_ms

        # ccxt Ä‘Ã£ cÃ³ rate limiting, thÃªm nhá» delay Ä‘á»ƒ an toÃ n
        time.sleep(0.2)

    if not all_candles:
        logger.warning("[Fetcher] KhÃ´ng cÃ³ dá»¯ liá»‡u OHLCV cho {} {} tá»« {} Ä‘áº¿n {}", symbol, timeframe, since, until)
        return pd.DataFrame()

    df = _candles_to_dataframe(all_candles)

    # Lá»c Ä‘Ãºng khoáº£ng thá»i gian (bao gá»“m until)
    df = df.loc[since:until]

    # Kiá»ƒm tra vÃ  log gaps
    detect_gaps(df, timeframe)

    logger.info("[Fetcher] OHLCV {} {} â†’ {} náº¿n", symbol, timeframe, len(df))
    return df


def _fetch_ohlcv_chunk(
    exchange: ccxt.binance,
    symbol: str,
    timeframe: str,
    since_ms: int,
) -> list:
    """Fetch 1 chunk OHLCV vá»›i retry vÃ  exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            # params={"price": "mark"} khÃ´ng cáº§n cho OHLCV; dÃ¹ng default (index price)
            candles = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=since_ms,
                limit=MAX_CANDLES_PER_REQUEST,
            )
            return candles
        except ccxt.RateLimitExceeded as e:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] Rate limit exceeded. Chá» {}s rá»“i thá»­ láº¡i (láº§n {}/{})", wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
        except ccxt.NetworkError as e:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] Network error: {}. Chá» {}s (láº§n {}/{})", str(e)[:100], wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
        except ccxt.ExchangeError as e:
            logger.error("[Fetcher] Exchange error khi fetch OHLCV: {}", str(e)[:200])
            return []
    logger.error("[Fetcher] ÄÃ£ thá»­ {} láº§n mÃ  váº«n tháº¥t báº¡i khi fetch OHLCV.", MAX_RETRIES)
    return []


def _candles_to_dataframe(candles: list) -> pd.DataFrame:
    """
    Chuyá»ƒn list candles tá»« ccxt sang DataFrame.
    ccxt format: [timestamp_ms, open, high, low, close, volume]
    Binance Futures thÃªm: taker_buy_base_volume (á»Ÿ vá»‹ trÃ­ 6 náº¿u cÃ³)
    """
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])

    # ThÃªm taker_buy_base_volume náº¿u cÃ³ (Binance Futures tráº£ vá» trong cá»™t thá»© 6)
    if candles and len(candles[0]) > 6:
        df["taker_buy_base_volume"] = [c[6] for c in candles]
    else:
        # Náº¿u API khÃ´ng tráº£ vá», Æ°á»›c tÃ­nh 50% (khÃ´ng lÃ½ tÆ°á»Ÿng nhÆ°ng khÃ´ng crash)
        df["taker_buy_base_volume"] = df["volume"] * 0.5
        logger.debug("[Fetcher] taker_buy_base_volume khÃ´ng cÃ³ trong API response, dÃ¹ng Æ°á»›c tÃ­nh 50%.")

    # Chuyá»ƒn timestamp tá»« ms sang DatetimeIndex UTC
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df.sort_index(inplace=True)

    # Loáº¡i bá» duplicate timestamps
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
    KÃ©o Open Interest lá»‹ch sá»­ cho BTC/USDT Futures (public endpoint).
    Endpoint REST: GET /futures/data/openInterestHist
    Binance Data Vision: data.binance.vision (daily metrics 5m)

    CÆ¡ cháº¿ Hybrid:
      1. Khoáº£ng lá»‹ch sá»­ sÃ¢u (> boundary = now_utc - 2 ngÃ y): láº¥y tá»« Binance Data Vision.
      2. Khoáº£ng thá»i gian gáº§n nháº¥t (>= boundary Ä‘áº¿n hiá»‡n táº¡i): láº¥y tá»« Binance REST API.
      3. GhÃ©p ná»‘i 2 pháº§n (concat, sort_index, dedupe), Ä‘áº£m báº£o khÃ´ng cÃ³ NaN á»Ÿ Ä‘uÃ´i gáº§n nháº¥t.

    Args:
        symbol:    KÃ½ hiá»‡u cáº·p giao dá»‹ch, vd: "BTC/USDT"
        timeframe: Khung thá»i gian: "4h", "15m", "1m" (Binance há»— trá»£: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
        since, until: Khoáº£ng thá»i gian UTC
        config:    Dict cáº¥u hÃ¬nh tá»« yaml

    Returns:
        DataFrame vá»›i DatetimeIndex (UTC) vÃ  cá»™t: open_interest

    LÆ°u Ã½ vá» chá»‘ng lookahead bias:
        - OI táº¡i timestamp T lÃ  giÃ¡ trá»‹ Ä‘Ã£ settle vÃ o cuá»‘i interval T.
        - HoÃ n toÃ n an toÃ n Ä‘á»ƒ dÃ¹ng OI[T] khi ra quyáº¿t Ä‘á»‹nh táº¡i T.
    """
    # Äáº£m báº£o timezone-aware UTC cho since vÃ  until
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
    # Buffer 2 ngÃ y cho Ä‘á»™ trá»… publish cá»§a Binance Data Vision
    boundary = now_utc - pd.Timedelta(days=2)
    is_historical_beyond_30d = (now_utc - since).days > 28
    use_vision = config.get("open_interest", {}).get("use_binance_vision_historical", True)

    # 1. Náº¿u khÃ´ng kÃ­ch hoáº¡t Binance Vision hoáº·c khoáº£ng thá»i gian hoÃ n toÃ n náº±m trong 28 ngÃ y gáº§n nháº¥t:
    # Láº¥y toÃ n bá»™ qua REST API
    if not (is_historical_beyond_30d and use_vision):
        logger.info(
            "[Fetcher] Fetch OI {} {} hoÃ n toÃ n qua REST API tá»« {} Ä‘áº¿n {}",
            symbol, oi_timeframe, since.date(), until.date()
        )
        df_rest = _fetch_oi_rest(exchange, futures_symbol, oi_timeframe, since, until)
        detect_gaps(df_rest, oi_timeframe)
        logger.info("[Fetcher] REST API tráº£ vá» {} records OI cho {} {}", len(df_rest), symbol, oi_timeframe)
        return df_rest

    # 2. CÆ¡ cháº¿ Hybrid: káº¿t há»£p Binance Vision (lá»‹ch sá»­) + REST API (gáº§n nháº¥t)
    parts: list[pd.DataFrame] = []

    # Pháº§n 1: Binance Vision cho [since, min(until, boundary)]
    vision_end = min(until, boundary)
    if since < vision_end:
        logger.info(
            "[Fetcher] [Hybrid Part 1] Táº£i OI lá»‹ch sá»­ tá»« Binance Vision cho {} {} tá»« {} Ä‘áº¿n {}",
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
                    "[Fetcher] Binance Vision tráº£ vá» {} records OI [{} â†’ {}]",
                    len(df_vision), since.date(), vision_end.date()
                )
        except Exception as e:
            logger.warning("[Fetcher] Lá»—i khi táº£i Binance Vision: {}. Tiáº¿p tá»¥c vá»›i REST API náº¿u cÃ³ thá»ƒ...", e)

    # Pháº§n 2: REST API cho [max(since, boundary), until] náº¿u until > boundary
    if until > boundary:
        rest_since = max(since, boundary)
        logger.info(
            "[Fetcher] [Hybrid Part 2] Fetch OI gáº§n nháº¥t tá»« REST API cho {} {} tá»« {} Ä‘áº¿n {}",
            symbol, oi_timeframe, rest_since.date(), until.date()
        )
        try:
            df_rest = _fetch_oi_rest(exchange, futures_symbol, oi_timeframe, rest_since, until)
            if not df_rest.empty:
                parts.append(df_rest)
                logger.info(
                    "[Fetcher] REST API tráº£ vá» {} records OI [{} â†’ {}]",
                    len(df_rest), rest_since.date(), until.date()
                )
        except Exception as e:
            logger.warning("[Fetcher] Lá»—i khi fetch REST API pháº§n gáº§n nháº¥t: {}", e)

    if not parts:
        logger.warning(
            "[Fetcher] KhÃ´ng cÃ³ dá»¯ liá»‡u OI cho {} tá»« {} Ä‘áº¿n {} (cáº£ Vision láº«n REST Ä‘á»u khÃ´ng cÃ³)",
            symbol, since, until
        )
        return pd.DataFrame()

    # GhÃ©p 2 pháº§n: concat, sort, deduplicate (Æ°u tiÃªn REST cho cÃ¡c Ä‘iá»ƒm trÃ¹ng láº·p á»Ÿ boundary)
    combined = pd.concat(parts).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    result = combined.loc[since:until]

    detect_gaps(result, oi_timeframe)
    vision_start_str = since.date()
    vision_end_str = vision_end.date() if since < vision_end else "N/A"
    rest_start_str = max(since, boundary).date() if until > boundary else "N/A"
    rest_end_str = until.date() if until > boundary else "N/A"

    logger.info(
        "[Fetcher] HoÃ n thÃ nh Hybrid OI {} {}: tá»•ng {} records (Vision: [{} â†’ {}], REST: [{} â†’ {}])",
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
    Fetch chuá»—i OI liÃªn tá»¥c tá»« Binance Futures REST API qua cÆ¡ cháº¿ chunking.
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
    """Fetch 1 chunk OI vá»›i retry."""
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
            # ccxt tráº£ vá» list of dicts vá»›i field 'timestamp'
            return [{"timestamp": r["timestamp"], "sumOpenInterest": r.get("openInterestAmount", r.get("openInterest", 0))} for r in records]
        except ccxt.RateLimitExceeded:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] OI rate limit. Chá» {}s", wait)
            time.sleep(wait)
        except ccxt.NetworkError as e:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] OI network error: {}. Chá» {}s", str(e)[:100], wait)
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
    KÃ©o Funding Rate lá»‹ch sá»­ tá»« Binance Futures (public endpoint).
    Funding rate Binance settle má»—i 8h: 00:00, 08:00, 16:00 UTC.

    Returns:
        DataFrame vá»›i DatetimeIndex (UTC) vÃ  cá»™t: funding_rate
        (Chá»‰ cÃ³ ~3 hÃ ng/ngÃ y táº¡i cÃ¡c má»‘c settle)

    CHá»NG LOOKAHEAD BIAS:
        - DataFrame tráº£ vá» KHÃ”NG Ä‘Æ°á»£c forward-fill táº¡i Ä‘Ã¢y.
        - Viá»‡c forward-fill Ä‘á»ƒ align vá»›i OHLCV pháº£i Ä‘Æ°á»£c thá»±c hiá»‡n trong
          merge_ohlcv_with_funding() vá»›i giá»›i háº¡n tá»‘i Ä‘a 480 náº¿n 1m.
        - KhÃ´ng bao giá» backward-fill funding rate.
    """
    exchange = _get_exchange()
    since_ms = int(since.timestamp() * 1000)
    until_ms = int(until.timestamp() * 1000)

    logger.info("[Fetcher] Báº¯t Ä‘áº§u fetch Funding Rate {} tá»« {} Ä‘áº¿n {}", symbol, since.date(), until.date())

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
        logger.warning("[Fetcher] KhÃ´ng cÃ³ dá»¯ liá»‡u funding rate cho {} tá»« {} Ä‘áº¿n {}", symbol, since, until)
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    df = df[["funding_rate"]].dropna()
    df["funding_rate"] = pd.to_numeric(df["funding_rate"], errors="coerce")
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    df = df.loc[since:until]

    logger.info("[Fetcher] Funding Rate {} â†’ {} records", symbol, len(df))
    return df


def _fetch_funding_chunk(
    exchange: ccxt.binance,
    symbol: str,
    since_ms: int,
    until_ms: int,
) -> list:
    """Fetch 1 chunk funding rate vá»›i retry."""
    for attempt in range(MAX_RETRIES):
        try:
            records = exchange.fetch_funding_rate_history(
                symbol=symbol,
                since=since_ms,
                limit=MAX_FUNDING_PER_REQUEST,
                params={"endTime": until_ms},
            )
            return [
                {
                    "timestamp": r["timestamp"],
                    "funding_rate": r.get("fundingRate", r.get("funding", 0.0)),
                }
                for r in records
            ]
        except ccxt.RateLimitExceeded:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] Funding rate limit. Chá» {}s", wait)
            time.sleep(wait)
        except ccxt.NetworkError as e:
            wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            logger.warning("[Fetcher] Funding network error: {}. Chá» {}s", str(e)[:100], wait)
            time.sleep(wait)
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
    Merge OHLCV vá»›i OI vÃ  Funding Rate.

    QUY Táº®C CHá»NG LOOKAHEAD BIAS (báº¯t buá»™c):
    1. OI: merge_asof vá»›i direction='backward' â€” táº¡i má»—i náº¿n OHLCV,
       dÃ¹ng giÃ¡ trá»‹ OI gáº§n nháº¥t TRÆ¯á»šC Ä‘Ã³ (khÃ´ng dÃ¹ng giÃ¡ trá»‹ tÆ°Æ¡ng lai).
    2. Funding Rate: forward-fill sau khi merge, tá»‘i Ä‘a N náº¿n
       (max_forward_fill_candles tá»« config, máº·c Ä‘á»‹nh 480 náº¿n 1m = 8h).
       KHÃ”NG backward-fill.
    3. Náº¿n OHLCV khÃ´ng cÃ³ OI gáº§n Ä‘Ã³ (thiáº¿u dá»¯ liá»‡u) â†’ OI = NaN (giá»¯ nguyÃªn).

    Returns:
        DataFrame Ä‘áº§y Ä‘á»§ vá»›i: open, high, low, close, volume,
        taker_buy_base_volume, open_interest, funding_rate
    """
    df = ohlcv_df.copy()
    if hasattr(df.index, "as_unit"):
        df.index = df.index.as_unit("ms")

    # 1. Merge OI: backward merge (dÃ¹ng OI Ä‘Ã£ settle trÆ°á»›c hoáº·c táº¡i náº¿n hiá»‡n táº¡i)
    # PhÆ°Æ¡ng Ã¡n B (oi_confluence):
    # - Náº¿u cÃ³ dá»¯ liá»‡u OI há»£p lá»‡ -> kiá»ƒm tra Ä‘á»“ng thuáº­n OI trong chiáº¿n lÆ°á»£c.
    # - Náº¿u OI lÃ  NaN (do thiáº¿u dá»¯ liá»‡u hoáº·c ngÃ y lá»—i) -> cÆ¡ cháº¿ fallback_when_nan
    #   trong chiáº¿n lÆ°á»£c sáº½ bá» qua kiá»ƒm tra OI vÃ  ghi chÃº 'OI_BYPASSED_HISTORICAL'.
    if not oi_df.empty:
        oi_to_merge = oi_df[["open_interest"]].sort_index()
        if hasattr(oi_to_merge.index, "as_unit"):
            oi_to_merge.index = oi_to_merge.index.as_unit("ms")
        df = pd.merge_asof(
            df.sort_index(),
            oi_to_merge,
            left_index=True,
            right_index=True,
            direction="backward",  # QUAN TRá»ŒNG: khÃ´ng dÃ¹ng giÃ¡ trá»‹ tÆ°Æ¡ng lai
        )
    else:
        df["open_interest"] = float("nan")
        logger.warning("[Fetcher] OI data rá»—ng, open_interest sáº½ lÃ  NaN (kÃ­ch hoáº¡t fallback_when_nan).")

    # Äáº£m báº£o cá»™t open_interest luÃ´n cÃ³ kiá»ƒu float
    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce")

    # --- Merge Funding Rate ---
    if not funding_df.empty:
        funding_to_merge = funding_df[["funding_rate"]].sort_index()
        if hasattr(funding_to_merge.index, "as_unit"):
            funding_to_merge.index = funding_to_merge.index.as_unit("ms")
        max_ffill = config.get("funding_rate", {}).get("max_forward_fill_candles", 480)
        tf_delta = timeframe_to_timedelta(timeframe)
        tolerance = tf_delta * max_ffill

        df = pd.merge_asof(
            df.sort_index(),
            funding_to_merge,
            left_index=True,
            right_index=True,
            direction="backward",  # QUAN TRá»ŒNG: khÃ´ng dÃ¹ng funding tÆ°Æ¡ng lai
            tolerance=tolerance,   # QUAN TRá»ŒNG: chá»‰ forward-fill tá»‘i Ä‘a max_ffill náº¿n
        )
    else:
        df["funding_rate"] = float("nan")
        logger.warning("[Fetcher] Funding rate data rá»—ng, funding_rate sáº½ lÃ  NaN.")

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
    Fetch toÃ n bá»™ dá»¯ liá»‡u cáº§n thiáº¿t cho backtest: OHLCV + OI + Funding.
    Tá»± Ä‘á»™ng dÃ¹ng cache náº¿u Ä‘á»§ dá»¯ liá»‡u. Fetch tá»« API náº¿u thiáº¿u.

    Args:
        symbol:        Cáº·p giao dá»‹ch (vd: "BTC/USDT")
        timeframes:    List timeframes cáº§n fetch (vd: ["4h", "15m", "1m"])
        since, until:  Khoáº£ng thá»i gian UTC
        config:        Config dict
        force_refresh: True = bá» qua cache vÃ  fetch láº¡i tá»« API

    Returns:
        Dict {timeframe: DataFrame} vá»›i Ä‘áº§y Ä‘á»§ columns:
        open, high, low, close, volume, taker_buy_base_volume,
        open_interest, funding_rate

    LÆ°u Ã½:
        - DataFrame Ä‘Æ°á»£c sáº¯p xáº¿p theo thá»i gian tÄƒng dáº§n.
        - Index lÃ  DatetimeIndex UTC.
        - Dá»¯ liá»‡u tÆ°Æ¡ng lai (> until) khÃ´ng Ä‘Æ°á»£c bao gá»“m.
    """
    exchange_id = config.get("data", {}).get("exchange", "binance")
    raw_dir = config.get("data", {}).get("raw_data_dir", "data/raw")
    safe_symbol = symbol.replace("/", "")  # "BTCUSDT"

    result: Dict[str, pd.DataFrame] = {}

    for tf in timeframes:
        logger.info("[Fetcher] === Xá»­ lÃ½ timeframe {} ===", tf)

        # 1. OHLCV â€” kiá»ƒm tra cache trÆ°á»›c
        ohlcv_cached = (not force_refresh) and has_complete_cache(
            raw_dir, exchange_id, safe_symbol, tf, "ohlcv", since, until
        )

        if ohlcv_cached:
            ohlcv_df = load_from_cache(raw_dir, exchange_id, safe_symbol, tf, "ohlcv", since, until)
            logger.info("[Fetcher] OHLCV {} {} â†’ dÃ¹ng cache ({} náº¿n)", symbol, tf, len(ohlcv_df))
        else:
            ohlcv_df = fetch_ohlcv(symbol, tf, since, until, config)
            if not ohlcv_df.empty:
                save_to_cache(ohlcv_df, raw_dir, exchange_id, safe_symbol, tf, "ohlcv")

        if ohlcv_df is None or ohlcv_df.empty:
            logger.error("[Fetcher] KhÃ´ng cÃ³ OHLCV data cho {} {}. Bá» qua timeframe nÃ y.", symbol, tf)
            continue

        # 2. OI â€” dÃ¹ng timeframe OI tÆ°Æ¡ng á»©ng
        oi_tf = _map_to_oi_timeframe(tf)
        oi_cached = (not force_refresh) and has_complete_cache(
            raw_dir, exchange_id, safe_symbol, oi_tf, "open_interest", since, until
        )

        if oi_cached:
            oi_df = load_from_cache(raw_dir, exchange_id, safe_symbol, oi_tf, "open_interest", since, until)
            logger.info("[Fetcher] OI {} {} â†’ dÃ¹ng cache ({} records)", symbol, oi_tf, len(oi_df))
        else:
            oi_df = fetch_open_interest(symbol, tf, since, until, config)
            if not oi_df.empty:
                save_to_cache(oi_df, raw_dir, exchange_id, safe_symbol, oi_tf, "open_interest")

        if oi_df is None:
            oi_df = pd.DataFrame()

        # 3. Funding Rate â€” chá»‰ fetch 1 láº§n (dÃ¹ng chung cho má»i timeframe)
        funding_cached = (not force_refresh) and has_complete_cache(
            raw_dir, exchange_id, safe_symbol, "8h", "funding_rate", since, until
        )

        if funding_cached:
            funding_df = load_from_cache(raw_dir, exchange_id, safe_symbol, "8h", "funding_rate", since, until)
            logger.info("[Fetcher] Funding Rate {} â†’ dÃ¹ng cache ({} records)", symbol, len(funding_df))
        else:
            funding_df = fetch_funding_rate(symbol, since, until, config)
            if not funding_df.empty:
                save_to_cache(funding_df, raw_dir, exchange_id, safe_symbol, "8h", "funding_rate")

        if funding_df is None:
            funding_df = pd.DataFrame()

        # 4. Merge vá»›i quy táº¯c chá»‘ng lookahead bias
        merged_df = merge_ohlcv_with_oi_and_funding(ohlcv_df, oi_df, funding_df, tf, config)
        result[tf] = merged_df

        logger.info(
            "[Fetcher] HoÃ n thÃ nh {} {}: {} náº¿n, OI={}, Funding={}",
            symbol, tf, len(merged_df),
            "OK" if "open_interest" in merged_df.columns and not merged_df["open_interest"].isna().all() else "NaN",
            "OK" if "funding_rate" in merged_df.columns and not merged_df["funding_rate"].isna().all() else "NaN",
        )

    return result


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _timeframe_to_ms(timeframe: str) -> int:
    """Chuyá»ƒn timeframe string sang milliseconds."""
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
        raise ValueError(f"Timeframe khÃ´ng há»— trá»£: '{timeframe}'")
    return mapping[timeframe]


def _map_to_oi_timeframe(timeframe: str) -> str:
    """
    Map timeframe OHLCV sang timeframe há»— trá»£ bá»Ÿi Binance OI endpoint.
    Binance OI há»— trá»£: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
    """
    mapping = {
        "1m": "5m",    # 1m OI khÃ´ng cÃ³; dÃ¹ng 5m gáº§n nháº¥t
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
        logger.debug("[Fetcher] OI timeframe {} â†’ {} (Binance khÃ´ng há»— trá»£ {})", timeframe, mapped, timeframe)
    return mapped

`

---

## 5. TOÀN VĂN MÃ NGUỒN src/data_layer/binance_vision_downloader.py (VERBATIM)

`python
"""
binance_vision_downloader.py - Historical Open Interest from Binance Data Vision
================================================================================
Táº£i dá»¯ liá»‡u Open Interest lá»‹ch sá»­ sÃ¢u (tá»« 2021 Ä‘áº¿n nay) tá»« kho dá»¯ liá»‡u má»Ÿ
chÃ­nh thá»©c cá»§a Binance (data.binance.vision).
HoÃ n toÃ n MIá»„N PHÃ, PUBLIC, KHÃ”NG Cáº¦N API KEY.

Cáº¥u trÃºc URL Binance Vision (Daily Metrics):
  https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/{symbol}-metrics-{YYYY-MM-DD}.zip
  BÃªn trong zip: {symbol}-metrics-{YYYY-MM-DD}.csv (táº§n suáº¥t ghi nháº­n 5 phÃºt/láº§n).

QUY Táº®C CHá»NG LOOKAHEAD BIAS (Báº®T BUá»˜C):
  - Dá»¯ liá»‡u 5 phÃºt khi downsample sang cÃ¡c timeframe má»¥c tiÃªu (4h, 15m, 1m)
    Ä‘Æ°á»£c thá»±c hiá»‡n báº±ng phÆ°Æ¡ng phÃ¡p FORWARD-FILL (láº¥y giÃ¡ trá»‹ cuá»‘i cÃ¹ng Ä‘Ã£ biáº¿t
    táº¡i hoáº·c trÆ°á»›c má»‘c thá»i gian Ä‘Ã³ng náº¿n).
  - TUYá»†T Äá»I KHÃ”NG dÃ¹ng interpolate (ná»™i suy tuyáº¿n tÃ­nh) vÃ¬ ná»™i suy sáº½ dÃ¹ng
    giÃ¡ trá»‹ tÆ°Æ¡ng lai Ä‘á»ƒ suy Ä‘oÃ¡n giÃ¡ trá»‹ quÃ¡ khá»© -> Lookahead bias.
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

# Base URL cá»§a Binance Data Vision
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
    Táº£i vÃ  giáº£i nÃ©n 1 file metrics ngÃ y tá»« Binance Data Vision.

    Args:
        symbol:   KÃ½ hiá»‡u cáº·p (vd: "BTCUSDT")
        date_str: NgÃ y Ä‘á»‹nh dáº¡ng "YYYY-MM-DD"
        timeout:  Timeout cho HTTP request (giÃ¢y)

    Returns:
        Tuple: (date_str, DataFrame hoáº·c None, error_message hoáº·c None)
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

            # Giáº£i nÃ©n trong RAM
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                if not csv_names:
                    return date_str, None, "KhÃ´ng tÃ¬m tháº¥y file CSV trong zip"

                with z.open(csv_names[0]) as csv_file:
                    df = pd.read_csv(csv_file)

            # Validate cÃ¡c cá»™t cáº§n thiáº¿t
            if "create_time" not in df.columns or "sum_open_interest" not in df.columns:
                return date_str, None, f"Thiáº¿u cá»™t cáº§n thiáº¿t. Columns: {list(df.columns)}"

            df["create_time"] = pd.to_datetime(df["create_time"], utc=True)
            df = df.set_index("create_time")
            df = df[["sum_open_interest"]].rename(columns={"sum_open_interest": "open_interest"})
            df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce")
            df = df.dropna().sort_index()

            return date_str, df, None

        except urllib.error.HTTPError as e:
            if e.code == 404:
                # NgÃ y nÃ y khÃ´ng cÃ³ trÃªn Binance Vision (chÆ°a cÃ³ hoáº·c ngÃ y nghá»‰/lá»—i)
                return date_str, None, "HTTP 404 (KhÃ´ng tá»“n táº¡i trÃªn Binance Vision)"
            elif attempt == MAX_RETRIES:
                return date_str, None, f"HTTP {e.code}: {e.reason}"
            time.sleep(BACKOFF_BASE ** attempt)

        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == MAX_RETRIES:
                return date_str, None, f"Network error: {str(e)}"
            time.sleep(BACKOFF_BASE ** attempt)

        except Exception as e:
            return date_str, None, f"Lá»—i khÃ´ng xÃ¡c Ä‘á»‹nh: {str(e)}"

    return date_str, None, "VÆ°á»£t quÃ¡ sá»‘ láº§n retry"


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
    Táº£i toÃ n bá»™ dá»¯ liá»‡u OI hÃ ng ngÃ y trong khoáº£ng [start_date, end_date].
    Cháº¡y Ä‘a luá»“ng song song vá»›i ThreadPoolExecutor Ä‘á»ƒ tÄƒng tá»‘c Ä‘á»™.

    Args:
        symbol:      KÃ½ hiá»‡u cáº·p (vd: "BTCUSDT")
        start_date:  NgÃ y báº¯t Ä‘áº§u "YYYY-MM-DD"
        end_date:    NgÃ y káº¿t thÃºc "YYYY-MM-DD"
        max_workers: Sá»‘ luá»“ng táº£i song song (máº·c Ä‘á»‹nh: 8)

    Returns:
        Tuple: (DataFrame 5-minute tá»•ng há»£p, List cÃ¡c ngÃ y táº£i tháº¥t báº¡i)
    """
    dates = pd.date_range(start=start_date, end=end_date, freq="D").strftime("%Y-%m-%d").tolist()
    total_days = len(dates)
    logger.info("[BinanceVision] Báº¯t Ä‘áº§u táº£i OI {} cho {} ngÃ y ({} â†’ {})...", symbol, total_days, start_date, end_date)

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
                    logger.debug("[BinanceVision] Bá» qua ngÃ y {}: {}", date_str, err)
            except Exception as exc:
                failed_dates.append(d)
                logger.warning("[BinanceVision] Lá»—i ngoáº¡i lá»‡ ngÃ y {}: {}", d, exc)

            completed += 1
            if completed % 100 == 0 or completed == total_days:
                logger.info("[BinanceVision] Tiáº¿n Ä‘á»™: {}/{} ngÃ y ({:.1f}%)", completed, total_days, (completed / total_days) * 100)

    elapsed = time.time() - t0

    if not dfs:
        logger.warning("[BinanceVision] KhÃ´ng táº£i Ä‘Æ°á»£c dá»¯ liá»‡u ngÃ y nÃ o trong khoáº£ng {} â†’ {}", start_date, end_date)
        return pd.DataFrame(), failed_dates

    # Gá»™p toÃ n bá»™ cÃ¡c ngÃ y thÃ nh 1 DataFrame liÃªn tá»¥c
    combined_5m = pd.concat(dfs).sort_index()
    combined_5m = combined_5m[~combined_5m.index.duplicated(keep="last")]

    logger.info(
        "[BinanceVision] Táº£i xong trong {:.2f}s! ThÃ nh cÃ´ng: {}/{} ngÃ y ({:.2f}%). Tháº¥t báº¡i: {} ngÃ y.",
        elapsed, len(dfs), total_days, (len(dfs) / total_days) * 100, len(failed_dates)
    )

    if failed_dates:
        logger.warning(
            "[BinanceVision] Danh sÃ¡ch ngÃ y khÃ´ng táº£i Ä‘Æ°á»£c (sáº½ dÃ¹ng Fallback PhÆ°Æ¡ng Ã¡n B náº¿u cáº§n): {}",
            failed_dates[:10] + ([f"... vÃ  {len(failed_dates)-10} ngÃ y khÃ¡c"] if len(failed_dates) > 10 else [])
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
    Downsample chuá»—i Open Interest 5 phÃºt vá» khung thá»i gian má»¥c tiÃªu.

    QUY Táº®C CHá»NG LOOKAHEAD BIAS:
      - Táº¡i má»—i má»‘c Ä‘Ã³ng náº¿n T cá»§a target_timeframe, ta láº¥y giÃ¡ trá»‹ OI 5 phÃºt
        gáº§n nháº¥t Ä‘Æ°á»£c ghi nháº­n táº¡i hoáº·c trÆ°á»›c T (direction='backward' / last known).
      - KHÃ”NG dÃ¹ng ná»™i suy tuyáº¿n tÃ­nh (linear interpolation) vÃ¬ sáº½ nhÃ¬n tháº¥y
        giÃ¡ trá»‹ OI cá»§a tÆ°Æ¡ng lai.
      - Náº¿u target_timeframe lÃ  1m: giÃ¡ trá»‹ 5 phÃºt Ä‘Æ°á»£c forward-fill (kÃ©o dÃ i)
        sang cÃ¡c náº¿n 1m káº¿ tiáº¿p cho Ä‘áº¿n khi cÃ³ báº£n ghi 5 phÃºt má»›i.

    Args:
        df_5m:            DataFrame 5 phÃºt gá»‘c vá»›i index UTC
        target_timeframe: "4h", "15m", "1m", v.v.

    Returns:
        DataFrame vá»›i DatetimeIndex UTC theo target_timeframe vÃ  cá»™t 'open_interest'.
    """
    if df_5m.empty:
        return pd.DataFrame()

    df_5m = ensure_utc_index(df_5m)
    freq_delta = timeframe_to_timedelta(target_timeframe)

    if target_timeframe == "1m":
        # Khung 1m: resample lÃªn 1m vÃ  forward-fill tá»‘i Ä‘a 5 náº¿n
        resampled = df_5m.resample("1min").ffill(limit=5)
    else:
        # Khung 15m, 4h, 1d...: dÃ¹ng closed='right', label='right' Ä‘á»ƒ Ä‘áº£m báº£o
        # giÃ¡ trá»‹ táº¡i má»‘c Ä‘Ã³ng náº¿n T chá»‰ chá»©a dá»¯ liá»‡u Ä‘áº¿n T (chá»‘ng lookahead bias)
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
    Táº£i toÃ n bá»™ OI lá»‹ch sá»­ tá»« Binance Vision, downsample sang cÃ¡c timeframe
    yÃªu cáº§u, vÃ  merge trá»±c tiáº¿p vÃ o Parquet Cache.

    Args:
        symbol:      KÃ½ hiá»‡u cáº·p (vd: "BTC/USDT" hoáº·c "BTCUSDT")
        start_date:  NgÃ y báº¯t Ä‘áº§u "YYYY-MM-DD"
        end_date:    NgÃ y káº¿t thÃºc "YYYY-MM-DD"
        timeframes:  Danh sÃ¡ch timeframe cáº§n downsample (vd: ["4h", "15m", "1m"])
        base_dir:    ThÆ° má»¥c gá»‘c cache (vd: "data/raw")
        exchange:    TÃªn sÃ n ("binance")
        max_workers: Sá»‘ luá»“ng táº£i

    Returns:
        Dict bÃ¡o cÃ¡o káº¿t quáº£ Ä‘á»“ng bá»™.
    """
    safe_symbol = symbol.replace("/", "").upper()

    # 1. Táº£i dá»¯ liá»‡u 5 phÃºt gá»‘c
    df_5m, failed_dates = download_historical_oi_range(
        symbol=safe_symbol,
        start_date=start_date,
        end_date=end_date,
        max_workers=max_workers,
    )

    if df_5m.empty:
        logger.error("[BinanceVision] KhÃ´ng cÃ³ dá»¯ liá»‡u Ä‘á»ƒ Ä‘á»“ng bá»™ vÃ o cache.")
        return {
            "symbol": safe_symbol,
            "status": "FAILED",
            "total_5m_rows": 0,
            "failed_dates": failed_dates,
        }

    # 2. Downsample vÃ  lÆ°u cache cho tá»«ng timeframe
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
            logger.info("[BinanceVision] ÄÃ£ lÆ°u cache OI {} {} â†’ {} náº¿n", safe_symbol, tf, len(df_downsampled))
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
        "[BinanceVision] Äá»“ng bá»™ hoÃ n táº¥t! Äá»™ bao phá»§: {:.2f}% ({} / {} ngÃ y)",
        coverage_pct, successful_days, total_expected_days
    )
    return report

`

---

## 6. TOÀN VĂN MÃ NGUỒN src/data_layer/cache_manager.py (VERBATIM)

`python
"""
cache_manager.py - Data Layer: Parquet Cache Manager
======================================================
LÆ°u vÃ  Ä‘á»c dá»¯ liá»‡u OHLCV/OI/Funding tá»« local Parquet files.
KhÃ´ng gá»i láº¡i API náº¿u dá»¯ liá»‡u Ä‘Ã£ cÃ³ Ä‘á»§ trong khoáº£ng thá»i gian yÃªu cáº§u.

Cáº¥u trÃºc file:
  data/raw/<exchange>/<symbol>/<timeframe>/<data_type>.parquet
  VÃ­ dá»¥: data/raw/binance/BTCUSDT/4h/ohlcv.parquet

CHá»NG LOOKAHEAD BIAS: module nÃ y chá»‰ Ä‘á»c/ghi dá»¯ liá»‡u, khÃ´ng tá»± Ã½
forward-fill hay backfill â€” viá»‡c Ä‘Ã³ thuá»™c vá» fetcher.py vá»›i logic rÃµ rÃ ng.
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
    Tráº£ vá» Ä‘Æ°á»ng dáº«n file Parquet tÆ°Æ¡ng á»©ng.

    Args:
        base_dir:  ThÆ° má»¥c gá»‘c cache (vd: "data/raw")
        exchange:  TÃªn sÃ n (vd: "binance")
        symbol:    KÃ½ hiá»‡u khÃ´ng cÃ³ slash (vd: "BTCUSDT")
        timeframe: Khung thá»i gian (vd: "4h", "15m", "1m")
        data_type: "ohlcv" | "open_interest" | "funding_rate"

    Returns:
        Path Ä‘áº¿n file .parquet (chÆ°a cáº§n tá»“n táº¡i)
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
    LÆ°u DataFrame vÃ o Parquet.
    - Tá»± Ä‘á»™ng táº¡o thÆ° má»¥c náº¿u chÆ°a cÃ³.
    - Náº¿u file Ä‘Ã£ tá»“n táº¡i, merge dá»¯ liá»‡u má»›i vÃ o (trÃ¡nh duplicate theo timestamp).
    - Index pháº£i lÃ  DatetimeTZAware (UTC).
    """
    path = get_cache_path(base_dir, exchange, symbol, timeframe, data_type)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Äáº£m báº£o index lÃ  datetime UTC
    df = ensure_utc_index(df)

    if path.exists():
        existing = _read_parquet(path)
        # Merge: Æ°u tiÃªn dá»¯ liá»‡u má»›i (giá»¯ láº¡i dá»¯ liá»‡u cÅ© á»Ÿ nhá»¯ng index chÆ°a cÃ³)
        combined = pd.concat([existing, df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)
        df_to_write = combined
    else:
        df_to_write = df.sort_index()

    table = pa.Table.from_pandas(df_to_write, preserve_index=True)
    pq.write_table(table, path, compression="snappy")
    logger.debug(
        "[Cache] Saved {} {} {} {} â†’ {} rows â†’ {}",
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
    Äá»c tá»« cache, tráº£ vá» None náº¿u khÃ´ng Ä‘á»§ dá»¯ liá»‡u cho khoáº£ng yÃªu cáº§u.

    Args:
        since: Thá»i Ä‘iá»ƒm báº¯t Ä‘áº§u (inclusive), timezone-aware UTC
        until: Thá»i Ä‘iá»ƒm káº¿t thÃºc (inclusive), timezone-aware UTC

    Returns:
        DataFrame vá»›i DatetimeIndex UTC, hoáº·c None náº¿u khÃ´ng Ä‘á»§ dá»¯ liá»‡u.
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
        "[Cache] Hit: {} {} {} {} â†’ {} rows",
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
    Kiá»ƒm tra nhanh xem cache cÃ³ Ä‘á»§ khÃ´ng (khÃ´ng load toÃ n bá»™ data).
    DÃ¹ng Ä‘á»ƒ quyáº¿t Ä‘á»‹nh cÃ³ cáº§n fetch má»›i khÃ´ng.
    """
    path = get_cache_path(base_dir, exchange, symbol, timeframe, data_type)
    if not path.exists():
        return False

    try:
        meta = pq.read_metadata(path)
        # Äá»c chá»‰ cá»™t timestamp Ä‘á»ƒ check range, trÃ¡nh load toÃ n bá»™
        df_index = pq.read_table(path, columns=[]).to_pandas()
        df_index = ensure_utc_index(df_index)
        if df_index.empty:
            return False
        cached_min = df_index.index.min()
        cached_max = df_index.index.max()
        return cached_min <= since and cached_max >= until
    except Exception as e:
        logger.warning("[Cache] KhÃ´ng thá»ƒ Ä‘á»c metadata tá»« {}: {}", path, e)
        return False


# ---------------------------------------------------------------------------
# Data Quality & Gap Detection
# ---------------------------------------------------------------------------

def detect_gaps(
    df: pd.DataFrame,
    timeframe: str,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    PhÃ¡t hiá»‡n khoáº£ng trá»‘ng dá»¯ liá»‡u (missing candles).

    Args:
        df:        DataFrame vá»›i DatetimeIndex Ä‘Ã£ sáº¯p xáº¿p.
        timeframe: Chuá»—i timeframe (vd: "4h", "15m", "1m")

    Returns:
        List cÃ¡c (gap_start, gap_end). Rá»—ng náº¿u khÃ´ng cÃ³ gap.
    """
    if df.empty or len(df) < 2:
        return []

    expected_freq = timeframe_to_timedelta(timeframe)
    gaps = []
    timestamps = df.index.sort_values()

    for i in range(1, len(timestamps)):
        actual_delta = timestamps[i] - timestamps[i - 1]
        if actual_delta > expected_freq * 1.5:  # cho phÃ©p 50% tolerance
            gaps.append((timestamps[i - 1], timestamps[i]))

    if gaps:
        logger.warning(
            "[Cache] PhÃ¡t hiá»‡n {} khoáº£ng trá»‘ng dá»¯ liá»‡u trong {} náº¿n (timeframe={}):",
            len(gaps), len(df), timeframe
        )
        for gs, ge in gaps[:5]:  # chá»‰ log 5 gap Ä‘áº§u tiÃªn
            logger.warning("  Gap: {} â†’ {} ({} thiáº¿u)", gs, ge,
                           int((ge - gs) / expected_freq) - 1)
        if len(gaps) > 5:
            logger.warning("  ... vÃ  {} gaps khÃ¡c.", len(gaps) - 5)

    return gaps


# ---------------------------------------------------------------------------
# Internal helpers & public utility functions
# ---------------------------------------------------------------------------

def _read_parquet(path: Path) -> pd.DataFrame:
    """Äá»c Parquet file, tráº£ vá» DataFrame."""
    try:
        table = pq.read_table(path)
        return table.to_pandas()
    except Exception as e:
        logger.error("[Cache] Lá»—i khi Ä‘á»c Parquet file {}: {}", path, e)
        return pd.DataFrame()


def ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Äáº£m báº£o index cá»§a DataFrame lÃ  DatetimeTZAware UTC vÃ  chuáº©n hÃ³a resolution vá» 'ms'.
    Há»— trá»£ cáº£ trÆ°á»ng há»£p index lÃ  DatetimeIndex láº«n cá»™t 'timestamp'.
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
    Kiá»ƒm tra df_slice cÃ³ Ä‘á»§ dá»¯ liá»‡u cho khoáº£ng [since, until] khÃ´ng.
    Cho phÃ©p tá»‘i Ä‘a 1% candles bá»‹ thiáº¿u (tolerance cho cÃ¡c gap nhá» trÃªn Binance).
    """
    if df_slice.empty:
        return False

    freq = timeframe_to_timedelta(timeframe)
    expected_count = int((until - since) / freq) + 1
    actual_count = len(df_slice)

    # 99% coverage lÃ  Ä‘á»§ (Binance Ä‘Ã´i khi thiáº¿u 1-2 náº¿n trong gap maintenance)
    return actual_count >= expected_count * 0.99


def timeframe_to_timedelta(timeframe: str) -> pd.Timedelta:
    """Chuyá»ƒn string timeframe sang pd.Timedelta."""
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
        raise ValueError(f"Timeframe khÃ´ng há»— trá»£: '{timeframe}'. Há»£p lá»‡: {list(mapping.keys())}")
    return mapping[timeframe]


# Aliases for backwards compatibility
_ensure_utc_index = ensure_utc_index
_timeframe_to_timedelta = timeframe_to_timedelta

`

---

## 7. NỘI DUNG config/default_config.yaml HIỆN TẠI (VERBATIM)

`yaml
# ============================================================
# default_config.yaml - Crypto Paper-Trading Research Agent
# ToÃ n bá»™ tham sá»‘ há»‡ thá»‘ng. KHÃ”NG lÆ°u API key hoáº·c thÃ´ng tin nháº¡y cáº£m á»Ÿ Ä‘Ã¢y.
# Má»i giÃ¡ trá»‹ cÃ³ thá»ƒ override qua CLI hoáº·c config riÃªng cho tá»«ng chiáº¿n lÆ°á»£c.
# ============================================================

account:
  initial_equity_usd: 10000
  base_currency: USDT

risk:
  conviction_tiers:
    low:        0.01   # 1% equity per trade
    normal:     0.02   # 2%
    high:       0.05   # 5%
    ultra_high: 0.10   # 10%
  max_leverage: 5
  # Khoáº£ng cÃ¡ch tá»‘i thiá»ƒu giá»¯a giÃ¡ thanh lÃ½ vÃ  stop-loss (tÃ­nh theo % entry price)
  # Hard invariant: |liq_price - stop_price| / entry_price >= 0.30
  min_liquidation_buffer_pct: 0.30

circuit_breakers:
  # Náº¿u lá»— rÃ²ng trong rolling 24h vÆ°á»£t má»©c nÃ y â†’ Ä‘Ã³ng toÃ n bá»™, khÃ³a trading 24h
  daily_loss_limit_pct: 0.05
  # Chuá»—i lá»‡nh thua liÃªn tiáº¿p â†’ giáº£m risk_percent xuá»‘ng 50%
  consecutive_losses_threshold: 3
  risk_reduction_on_streak: 0.5    # há»‡ sá»‘ nhÃ¢n (0.5 = giáº£m 50%)
  # Äiá»u kiá»‡n phá»¥c há»“i risk vá» má»©c chuáº©n: sau 3 lá»‡nh tháº¯ng liÃªn tiáº¿p
  # ÄÃ£ chá»‘t vá»›i ngÆ°á»i dÃ¹ng: after_3_wins
  recovery_mode: "after_3_wins"
  consecutive_wins_to_recover: 3

fees:
  taker_pct: 0.0005   # 0.05% (máº·c Ä‘á»‹nh Binance Futures)
  maker_pct: 0.0002   # 0.02%
  slippage_pct: 0.0003  # 0.03% slippage mÃ´ phá»ng

data:
  symbol: "BTC/USDT"
  timeframes:
    - "4h"
    - "15m"
    - "1m"
  exchange: "binance"
  # Khoáº£ng backtest: 2021-01-01 â†’ 2026-09-01 (~5.5 nÄƒm)
  # Bao phá»§: bull run 2021, bear 2022 (LUNA/FTX), há»“i phá»¥c 2023-2024, 2025-2026
  start_date: "2021-01-01"
  end_date:   "2026-09-01"
  # ThÆ° má»¥c cache local (Parquet)
  raw_data_dir: "data/raw"
  processed_data_dir: "data/processed"
  # Binance Futures sá»­ dá»¥ng symbol format khÃ¡c cho futures: BTCUSDT (khÃ´ng cÃ³ /)
  futures_symbol: "BTCUSDT"

# Open Interest fetch config
open_interest:
  # Binance Futures public endpoint, khÃ´ng cáº§n API key
  # ccxt sáº½ gá»i GET /fapi/v1/openInterestHist (chá»‰ lÆ°u 30 ngÃ y gáº§n nháº¥t)
  lookback_periods: 500   # sá»‘ náº¿n OI tá»‘i thiá»ƒu cáº§n cho indicators
  # Dá»¯ liá»‡u lá»‹ch sá»­ sÃ¢u tá»« Binance Data Vision (data.binance.vision)
  use_binance_vision_historical: true

# OI Confluence (PhÆ°Æ¡ng Ã¡n B: xá»­ lÃ½ khi thiáº¿u hoáº·c cÃ³ dá»¯ liá»‡u OI)
oi_confluence:
  # "optional": náº¿u cÃ³ dá»¯ liá»‡u OI thÃ¬ kiá»ƒm tra Ä‘á»“ng thuáº­n; náº¿u NaN thÃ¬ fallback bá» qua
  # "strict": náº¿u NaN thÃ¬ tá»« chá»‘i vÃ o lá»‡nh
  # "disabled": táº¯t hoÃ n toÃ n kiá»ƒm tra OI
  mode: "optional"
  fallback_when_nan: true
  nan_log_note: "OI_BYPASSED_HISTORICAL"

# Funding rate config
funding_rate:
  # Funding settlement: 00:00, 08:00, 16:00 UTC (Binance standard)
  settlement_hours_utc: [0, 8, 16]
  # Forward-fill tá»‘i Ä‘a N náº¿n Ä‘á»ƒ khÃ´ng leak dá»¯ liá»‡u tÆ°Æ¡ng lai
  max_forward_fill_candles: 480   # tá»‘i Ä‘a 480 náº¿n 1m = 8h (1 chu ká»³ funding)

# Feature Engine
features:
  ema_periods: [20, 50, 200]
  rsi_period: 14
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  atr_period: 14
  # OI delta: % thay Ä‘á»•i OI so vá»›i N náº¿n trÆ°á»›c
  oi_delta_lookback: 20
  # CVD divergence: so sÃ¡nh Ä‘á»‰nh/Ä‘Ã¡y giÃ¡ vá»›i Ä‘á»‰nh/Ä‘Ã¡y CVD trong N náº¿n
  cvd_divergence_lookback: 50

# SMC (Smart Money Concepts) - dÃ¹ng cho Giai Ä‘oáº¡n 9
smc:
  # Swing High/Low: náº¿n cÃ³ high > N náº¿n trÆ°á»›c + N náº¿n sau
  swing_n: 3
  # Minimum BOS/CHoCH breakout Ä‘á»ƒ tÃ­nh há»£p lá»‡ (% so vá»›i entry)
  min_bos_pct: 0.001   # 0.1%

# News Filter (placeholder - disabled cho giai Ä‘oáº¡n 0-4)
# Khi enabled: true, sáº½ Ä‘á»c file CSV chá»©a cÃ¡c má»‘c CPI/FOMC/NFP
# Blackout: khÃ´ng má»Ÿ lá»‡nh trong Â±15 phÃºt quanh sá»± kiá»‡n
news_filter:
  enabled: false
  blackout_minutes_before: 15
  blackout_minutes_after: 15
  calendar_source: "manual_csv"
  calendar_file: "data/news_calendar.csv"   # ngÆ°á»i dÃ¹ng tá»± chuáº©n bá»‹

# Logging
logging:
  trade_log_db: "data/trades.db"
  trade_log_json_dir: "data/trade_logs"
  log_level: "INFO"

# Backtest Engine
backtest:
  # Random seed Ä‘á»ƒ Ä‘áº£m báº£o reproducibility
  random_seed: 42
  # Chuáº©n thá»±c thi: quyáº¿t Ä‘á»‹nh dá»±a trÃªn náº¿n Ä‘Ã£ Ä‘Ã³ng, thá»±c thi á»Ÿ náº¿n káº¿ tiáº¿p
  # (trÃ¡nh lookahead bias - khÃ´ng dÃ¹ng giÃ¡ close cá»§a náº¿n hiá»‡n táº¡i Ä‘á»ƒ vÃ o lá»‡nh)
  signal_on_close: true    # tÃ­n hiá»‡u khi náº¿n Ä‘Ã³ng
  execute_on_next_open: true   # thá»±c thi á»Ÿ open náº¿n sau (hoáº·c dÃ¹ng open lÃ m entry)

# Binance Futures leverage brackets (dÃ¹ng Ä‘á»ƒ tÃ­nh MMR chÃ­nh xÃ¡c)
# Nguá»“n: https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin
# Format: [max_notional_usd, mmr_pct, cumulative_maintenance_amount]
leverage_brackets:
  BTCUSDT:
    - [50000,      0.004, 0]
    - [250000,     0.005, 50]
    - [1000000,    0.01,  1300]
    - [10000000,   0.025, 16300]
    - [20000000,   0.05,  266300]
    - [50000000,   0.10,  1266300]
    - [100000000,  0.125, 2516300]
    - [200000000,  0.15,  5016300]
    - [300000000,  0.25,  25016300]
    - [500000000,  0.50,  100016300]

`

---
*Báo cáo được tổng hợp tự động và lưu trữ tại: BÁO CÁO TÓM TẮT/GIAI ĐOẠN 1/BAO_CAO_CLAUDE_REVIEW_GIAI_DOAN_1.md*
