"""
tests/test_data_layer.py - Unit Tests cho Giai đoạn 1: Data Layer
==================================================================
Gồm:
1. Tests cho cache_manager: save/load, gap detection, path building
2. Tests cho fetcher: merge logic, forward-fill funding rate
3. Integration test THỰC TẾ: kéo ~7 ngày OHLCV 4h từ Binance (network required)
4. Anti-lookahead bias test: xác nhận merge_asof chỉ dùng data trong quá khứ

Chú ý: Tests network có marker @pytest.mark.network, chạy tách biệt.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import timezone
from pathlib import Path
import sys
import os

# Add project root to path
_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from src.data_layer.cache_manager import (
    get_cache_path,
    save_to_cache,
    load_from_cache,
    detect_gaps,
    timeframe_to_timedelta,
    ensure_utc_index,
    _timeframe_to_timedelta,
    _ensure_utc_index,
)
from src.data_layer.fetcher import (
    merge_ohlcv_with_oi_and_funding,
    _timeframe_to_ms,
    _map_to_oi_timeframe,
    _candles_to_dataframe,
)


def test_funding_adapter_does_not_synthesize_missing_rate_as_zero():
    from src.data_layer.fetcher import _fetch_funding_chunk

    class MissingRateExchange:
        def fetch_funding_rate_history(self, **kwargs):
            return [{"timestamp": 1672531200000}]

    with pytest.raises(ValueError, match="refusing to synthesize a zero rate"):
        _fetch_funding_chunk(MissingRateExchange(), "BTC/USDT:USDT", 0, 1)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ohlcv_df():
    """DataFrame OHLCV tổng hợp không có lookahead."""
    timestamps = pd.date_range("2024-01-01", periods=48, freq="4h", tz="UTC")
    np.random.seed(42)
    prices = 45000 + np.cumsum(np.random.randn(48) * 100)
    df = pd.DataFrame({
        "open": prices,
        "high": prices + np.abs(np.random.randn(48) * 50),
        "low": prices - np.abs(np.random.randn(48) * 50),
        "close": prices + np.random.randn(48) * 20,
        "volume": np.abs(np.random.randn(48) * 1000 + 5000),
        "taker_buy_base_volume": np.abs(np.random.randn(48) * 500 + 2500),
    }, index=timestamps)
    return df


@pytest.fixture
def sample_oi_df():
    """DataFrame OI tổng hợp (chỉ có data mỗi 4h)."""
    timestamps = pd.date_range("2024-01-01", periods=48, freq="4h", tz="UTC")
    df = pd.DataFrame({
        "open_interest": np.abs(np.random.randn(48) * 1e8 + 5e9),
    }, index=timestamps)
    return df


@pytest.fixture
def sample_funding_df():
    """DataFrame Funding Rate tổng hợp (settle mỗi 8h)."""
    timestamps = pd.date_range("2024-01-01", periods=24, freq="8h", tz="UTC")
    df = pd.DataFrame({
        "funding_rate": np.random.randn(24) * 0.0001,  # +-0.01% typical
    }, index=timestamps)
    return df


@pytest.fixture
def minimal_config():
    """Config tối thiểu cho tests."""
    return {
        "data": {"exchange": "binance", "raw_data_dir": "data/raw"},
        "funding_rate": {"max_forward_fill_candles": 480},
        "open_interest": {"use_binance_vision_historical": True},
        "oi_confluence": {
            "mode": "optional",
            "fallback_when_nan": True,
            "nan_log_note": "OI_BYPASSED_HISTORICAL",
        },
    }


# ---------------------------------------------------------------------------
# 1. Cache Manager Tests
# ---------------------------------------------------------------------------

class TestCacheManager:
    def test_get_cache_path_no_slash(self):
        """Ký tự / trong symbol phải được loại bỏ."""
        path = get_cache_path("data/raw", "binance", "BTC/USDT", "4h", "ohlcv")
        assert "BTCUSDT" in str(path)
        assert "/" not in path.name
        assert str(path).endswith("ohlcv.parquet")

    def test_get_cache_path_structure(self):
        """Path phải có cấu trúc: base/exchange/symbol/timeframe/type.parquet"""
        path = get_cache_path("data/raw", "binance", "BTCUSDT", "15m", "open_interest")
        parts = path.parts
        assert "binance" in parts
        assert "BTCUSDT" in parts
        assert "15m" in parts
        assert path.name == "open_interest.parquet"

    def test_save_and_load_roundtrip(self, sample_ohlcv_df, tmp_path):
        """Lưu và đọc lại phải cho kết quả giống nhau."""
        save_to_cache(sample_ohlcv_df, str(tmp_path), "binance", "BTCUSDT", "4h", "ohlcv")

        path = get_cache_path(str(tmp_path), "binance", "BTCUSDT", "4h", "ohlcv")
        assert path.exists(), "File Parquet phải được tạo."

        since = sample_ohlcv_df.index.min()
        until = sample_ohlcv_df.index.max()
        loaded = load_from_cache(str(tmp_path), "binance", "BTCUSDT", "4h", "ohlcv", since, until)

        assert loaded is not None, "load_from_cache phải trả về data (không phải None)."
        assert len(loaded) == len(sample_ohlcv_df), f"Số hàng không khớp: {len(loaded)} vs {len(sample_ohlcv_df)}"
        pd.testing.assert_index_equal(loaded.index, sample_ohlcv_df.index)

    def test_save_merge_no_duplicates(self, sample_ohlcv_df, tmp_path):
        """Lưu 2 lần cùng data không được tạo duplicate."""
        save_to_cache(sample_ohlcv_df, str(tmp_path), "binance", "BTCUSDT", "4h", "ohlcv")
        save_to_cache(sample_ohlcv_df, str(tmp_path), "binance", "BTCUSDT", "4h", "ohlcv")

        since = sample_ohlcv_df.index.min()
        until = sample_ohlcv_df.index.max()
        loaded = load_from_cache(str(tmp_path), "binance", "BTCUSDT", "4h", "ohlcv", since, until)

        assert loaded is not None
        assert len(loaded) == len(sample_ohlcv_df), f"Không được có duplicate: {len(loaded)} vs {len(sample_ohlcv_df)}"

    def test_load_returns_none_if_missing(self, tmp_path):
        """load_from_cache trả None nếu file không tồn tại."""
        result = load_from_cache(
            str(tmp_path), "binance", "BTCUSDT", "4h", "ohlcv",
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-01-08", tz="UTC"),
        )
        assert result is None

    def test_detect_gaps_no_gaps(self, sample_ohlcv_df):
        """DataFrame liên tục không có gaps."""
        gaps = detect_gaps(sample_ohlcv_df, "4h")
        assert gaps == [], f"Không được có gap trong dữ liệu liên tục, nhưng got: {gaps}"

    def test_detect_gaps_with_gap(self):
        """Kiểm tra phát hiện gap thực sự bằng cách drop hẳn 3 nến ở giữa."""
        # Tạo 20 nến liên tục, sau đó xóa 3 nến ở giữa để tạo gap 16h
        all_ts = pd.date_range("2024-01-01", periods=20, freq="4h", tz="UTC")
        full_df = pd.DataFrame({"close": 1.0}, index=all_ts)

        # Xóa hàng 8, 9, 10 (tạo nhảy từ ts[7] lên ts[11] = 16h gap > 4h * 1.5)
        df_with_gap = full_df.drop(full_df.index[8:11])
        assert len(df_with_gap) == 17

        gaps = detect_gaps(df_with_gap, "4h")
        assert len(gaps) >= 1, f"Phải phát hiện ít nhất 1 gap, got: {gaps}"

    def test_timeframe_to_timedelta(self):
        """Kiểm tra chuyển đổi timeframe sang timedelta (cả public lẫn alias)."""
        assert timeframe_to_timedelta("1m") == pd.Timedelta(minutes=1)
        assert timeframe_to_timedelta("4h") == pd.Timedelta(hours=4)
        assert timeframe_to_timedelta("1d") == pd.Timedelta(days=1)
        # Kiểm tra alias _timeframe_to_timedelta vẫn hoạt động tốt
        assert _timeframe_to_timedelta("15m") == pd.Timedelta(minutes=15)

    def test_timeframe_invalid_raises(self):
        """Timeframe không hợp lệ phải raise ValueError."""
        with pytest.raises(ValueError, match="không hỗ trợ"):
            timeframe_to_timedelta("99h")

    def test_ensure_utc_index(self):
        """DataFrame không có timezone phải được localize UTC (cả public lẫn alias)."""
        df = pd.DataFrame({"close": [1.0, 2.0]},
                          index=pd.date_range("2024-01-01", periods=2, freq="h"))
        assert df.index.tz is None
        result = ensure_utc_index(df)
        assert result.index.tz is not None
        assert str(result.index.tz) == "UTC"
        # Kiểm tra alias _ensure_utc_index
        result_alias = _ensure_utc_index(df)
        assert str(result_alias.index.tz) == "UTC"


# ---------------------------------------------------------------------------
# 2. Fetcher Logic Tests (không cần network)
# ---------------------------------------------------------------------------

class TestFetcherLogic:
    def test_candles_to_dataframe_basic(self):
        """Chuyển đổi raw ccxt candles sang DataFrame."""
        candles = [
            [1704067200000, 44000, 44500, 43500, 44200, 1000],  # 2024-01-01 00:00 UTC
            [1704081600000, 44200, 44800, 43800, 44600, 1200],  # 2024-01-01 04:00 UTC
        ]
        df = _candles_to_dataframe(candles)
        assert list(df.columns) == ["open", "high", "low", "close", "volume", "taker_buy_base_volume"]
        assert df.index.tz is not None
        assert str(df.index.tz) == "UTC"
        assert len(df) == 2

    def test_candles_to_dataframe_no_duplicates(self):
        """Candles có timestamp trùng phải được dedup."""
        ts = 1704067200000
        candles = [
            [ts, 44000, 44500, 43500, 44100, 1000],
            [ts, 44000, 44500, 43500, 44200, 1100],  # duplicate timestamp, giá trị khác
        ]
        df = _candles_to_dataframe(candles)
        assert len(df) == 1, "Duplicate timestamp phải bị loại bỏ"
        assert df.iloc[0]["close"] == 44200, "Giữ lại giá trị cuối (keep='last')"

    def test_timeframe_to_ms(self):
        """Kiểm tra chuyển đổi timeframe sang milliseconds."""
        assert _timeframe_to_ms("1m") == 60_000
        assert _timeframe_to_ms("4h") == 14_400_000
        assert _timeframe_to_ms("1d") == 86_400_000

    def test_map_to_oi_timeframe(self):
        """Kiểm tra map timeframe sang OI timeframe tương thích Binance."""
        assert _map_to_oi_timeframe("4h") == "4h"    # supported
        assert _map_to_oi_timeframe("1m") == "5m"    # 1m → 5m (không có 1m OI)
        assert _map_to_oi_timeframe("15m") == "15m"  # supported

    def test_merge_uses_backward_direction(self, sample_ohlcv_df, sample_oi_df, sample_funding_df, minimal_config):
        """
        ANTI-LOOKAHEAD TEST: merge_asof direction='backward' phải KHÔNG dùng
        giá trị OI/Funding từ tương lai.
        """
        # Tạo OHLCV dày hơn OI (giả lập 15m OHLCV merge với 1h OI)
        ohlcv_15m = sample_ohlcv_df.resample("15min").ffill()

        merged = merge_ohlcv_with_oi_and_funding(
            ohlcv_15m, sample_oi_df, sample_funding_df, "15m", minimal_config
        )

        # Với direction='backward': mỗi nến OHLCV tại T có OI <= T
        # Nếu dùng 'forward' sẽ có OI > T → lookahead
        assert "open_interest" in merged.columns
        assert "funding_rate" in merged.columns

        # Kiểm tra: với mỗi nến OHLCV, OI phải đến từ timestamp <= timestamp nến đó
        for ts in merged.index:
            oi_val = merged.loc[ts, "open_interest"]
            if not pd.isna(oi_val):
                # Tìm OI source tương ứng
                oi_candidates = sample_oi_df[sample_oi_df.index <= ts]
                if not oi_candidates.empty:
                    expected_oi = oi_candidates.iloc[-1]["open_interest"]
                    assert abs(oi_val - expected_oi) < 1e-6, (
                        f"Tại {ts}: OI={oi_val} != expected={expected_oi} "
                        f"(có thể lookahead!)"
                    )

    def test_funding_rate_no_backfill(self, sample_ohlcv_df, sample_funding_df, minimal_config):
        """
        ANTI-LOOKAHEAD TEST: funding rate không được backward-fill.
        Nến T trước funding event F phải có funding_rate từ trước F, không phải từ F.
        """
        # Tạo OHLCV với 1 nến trước mốc funding settle đầu tiên
        oi_empty = pd.DataFrame()
        merged = merge_ohlcv_with_oi_and_funding(
            sample_ohlcv_df, oi_empty, sample_funding_df, "4h", minimal_config
        )

        # Nến đầu tiên (2024-01-01 00:00) trùng với funding settle đầu tiên
        # → được gán funding_rate tại thời điểm đó (backward merge tìm được)
        assert "funding_rate" in merged.columns

        # Nến tiếp theo (2024-01-01 04:00) chưa có funding settle mới
        # → phải dùng forward-fill từ 00:00, KHÔNG dùng giá trị 08:00 (tương lai)
        ts_0400 = pd.Timestamp("2024-01-01 04:00:00", tz="UTC")
        ts_0800 = pd.Timestamp("2024-01-01 08:00:00", tz="UTC")
        if ts_0400 in merged.index and ts_0800 in merged.index:
            fr_0400 = merged.loc[ts_0400, "funding_rate"]
            fr_0800 = merged.loc[ts_0800, "funding_rate"]
            # 04:00 phải dùng funding từ 00:00 (forward-fill), KHÔNG phải từ 08:00
            if not pd.isna(fr_0400) and not pd.isna(fr_0800):
                # Nếu họ khác nhau thì 04:00 không được bằng 08:00 (sẽ là lookahead)
                # Kiểm tra gián tiếp: 04:00 phải bằng funding settle tại 00:00
                fr_0000 = sample_funding_df.loc[pd.Timestamp("2024-01-01 00:00:00", tz="UTC"), "funding_rate"]
                assert abs(fr_0400 - fr_0000) < 1e-10, (
                    "Nến 04:00 phải dùng funding settle lúc 00:00 (forward-fill), "
                    f"không phải lúc 08:00. Got: {fr_0400}, expected: {fr_0000}"
                )

    def test_funding_rate_ffill_limit(self, sample_ohlcv_df, minimal_config):
        """
        Funding rate chỉ được forward-fill tối đa max_forward_fill_candles.
        Sau giới hạn đó phải là NaN.
        """
        # Tạo funding chỉ có 1 row, OHLCV có 48 nến 4h = 192h
        funding_single = pd.DataFrame(
            {"funding_rate": [0.0001]},
            index=pd.DatetimeIndex([pd.Timestamp("2024-01-01", tz="UTC")])
        )
        # Config: chỉ ffill tối đa 2 nến
        cfg = {
            "funding_rate": {"max_forward_fill_candles": 2},
        }
        oi_empty = pd.DataFrame()
        merged = merge_ohlcv_with_oi_and_funding(
            sample_ohlcv_df, oi_empty, funding_single, "4h", cfg
        )
        # Chỉ 3 nến đầu (index 0,1,2) có funding, phần còn lại phải NaN
        non_nan = merged["funding_rate"].notna().sum()
        # limit=2 nghĩa là row gốc + 2 ffill = 3 rows tổng
        assert non_nan <= 3, f"Quá nhiều non-NaN sau ffill limit=2: {non_nan}"


# ---------------------------------------------------------------------------
# 3. Integration Test (cần network — chạy riêng)
# ---------------------------------------------------------------------------

@pytest.mark.network
def test_fetch_real_ohlcv_7days(minimal_config):
    """
    INTEGRATION: Kéo 7 ngày OHLCV 4h BTC/USDT từ Binance (public API).
    Kiểm tra:
    - Số nến đúng (7 ngày × 6 nến/ngày = 42 nến, thực tế có thể 41-43)
    - Không có giá trị âm
    - Close trong [Low, High]
    - Index là DatetimeIndex UTC liên tục
    """
    from src.data_layer.fetcher import fetch_ohlcv

    since = pd.Timestamp("2024-01-01", tz="UTC")
    until = pd.Timestamp("2024-01-08", tz="UTC")

    df = fetch_ohlcv("BTC/USDT", "4h", since, until, minimal_config)

    assert df is not None and not df.empty, "Phải fetch được data"
    assert df.index.tz is not None, "Index phải có timezone"
    assert str(df.index.tz) == "UTC"

    # 7 ngày × 6 nến/ngày = 42 nến (có thể +-1 do boundary)
    assert 40 <= len(df) <= 44, f"Số nến không hợp lý: {len(df)}"

    # Giá không được âm
    for col in ["open", "high", "low", "close", "volume"]:
        assert (df[col] >= 0).all(), f"Cột {col} có giá trị âm"

    # Close phải trong [Low, High]
    assert (df["close"] >= df["low"]).all(), "Close < Low (dữ liệu lỗi)"
    assert (df["close"] <= df["high"]).all(), "Close > High (dữ liệu lỗi)"

    # High >= Low
    assert (df["high"] >= df["low"]).all(), "High < Low (dữ liệu lỗi)"

    # Giá BTC tháng 1/2024 phải trong khoảng hợp lý (40k-50k)
    assert df["close"].min() > 30000, f"Giá BTC thấp bất thường: {df['close'].min()}"
    assert df["close"].max() < 60000, f"Giá BTC cao bất thường: {df['close'].max()}"


@pytest.mark.network
def test_fetch_real_funding_rate(minimal_config):
    """
    INTEGRATION: Kéo Funding Rate 7 ngày BTC/USDT từ Binance (public API).
    Kiểm tra:
    - Mỗi ngày có ~3 records (00:00, 08:00, 16:00 UTC)
    - Funding rate trong khoảng hợp lý (-0.1% đến +0.1%)
    """
    from src.data_layer.fetcher import fetch_funding_rate

    since = pd.Timestamp("2024-01-01", tz="UTC")
    until = pd.Timestamp("2024-01-08", tz="UTC")

    df = fetch_funding_rate("BTC/USDT", since, until, minimal_config)

    assert df is not None and not df.empty, "Phải fetch được funding rate data"

    # 7 ngày × 3 settlements/ngày ≈ 21 records
    assert 18 <= len(df) <= 24, f"Số funding records không hợp lý: {len(df)}"

    # Funding rate Binance thường trong khoảng +-0.1%
    assert (df["funding_rate"].abs() <= 0.01).all(), f"Funding rate quá cao: {df['funding_rate'].abs().max()}"


@pytest.mark.network
def test_no_lookahead_in_live_merge(minimal_config, tmp_path):
    """
    INTEGRATION ANTI-LOOKAHEAD: fetch thật 3 ngày, sau đó xác nhận
    mỗi nến N chỉ có OI và Funding từ timestamp <= N.
    """
    from src.data_layer.fetcher import fetch_ohlcv, fetch_open_interest, fetch_funding_rate

    now = pd.Timestamp.now(tz="UTC").floor("4h")
    since = now - pd.Timedelta(days=3)
    until = now

    ohlcv = fetch_ohlcv("BTC/USDT", "4h", since, until, minimal_config)
    oi = fetch_open_interest("BTC/USDT", "4h", since, until, minimal_config)
    funding = fetch_funding_rate("BTC/USDT", since, until, minimal_config)

    if ohlcv.empty or oi.empty or funding.empty:
        pytest.skip("Network không khả dụng, bỏ qua integration test")

    merged = merge_ohlcv_with_oi_and_funding(ohlcv, oi, funding, "4h", minimal_config)

    # Kiểm tra từng nến: OI và funding không được "nhìn thấy tương lai"
    for ts in merged.index:
        oi_val = merged.loc[ts, "open_interest"]
        if not pd.isna(oi_val):
            # OI tại T phải có trong oi_df tại timestamp <= T
            oi_before = oi[oi.index <= ts]
            assert not oi_before.empty, f"OI tại {ts} đến từ đâu?"

        fr_val = merged.loc[ts, "funding_rate"]
        if not pd.isna(fr_val):
            # Funding tại T phải có trong funding_df tại timestamp <= T
            funding_before = funding[funding.index <= ts]
            assert not funding_before.empty, f"Funding tại {ts} đến từ đâu?"


# ---------------------------------------------------------------------------
# 4. Binance Vision Downloader Tests (Phương án A + B)
# ---------------------------------------------------------------------------

class TestBinanceVisionDownloader:
    def test_downsample_5m_to_4h_no_lookahead(self):
        """
        ANTI-LOOKAHEAD TEST: Downsample 5m sang 4h phải lấy giá trị OI
        cuối cùng tại hoặc trước thời điểm nến 4h đóng, không dùng giá trị tương lai.
        """
        from src.data_layer.binance_vision_downloader import downsample_oi_to_timeframe

        # Tạo 5m OI trong 8 tiếng (96 nến 5m)
        idx_5m = pd.date_range("2024-01-01 00:00:00", periods=96, freq="5min", tz="UTC")
        # Giá trị OI tăng dần theo thời gian: 100, 101, 102...
        df_5m = pd.DataFrame({"open_interest": np.arange(100, 100 + 96, dtype=float)}, index=idx_5m)

        df_4h = downsample_oi_to_timeframe(df_5m, "4h")

        assert not df_4h.empty
        # Kiểm tra mốc 04:00:00 UTC
        ts_4h = pd.Timestamp("2024-01-01 04:00:00", tz="UTC")
        if ts_4h in df_4h.index:
            oi_at_4h = df_4h.loc[ts_4h, "open_interest"]
            # Giá trị tại 04:00:00 phải khớp với 5m nến tại hoặc trước 04:00:00
            oi_known = df_5m.loc[df_5m.index <= ts_4h, "open_interest"].iloc[-1]
            assert oi_at_4h == oi_known, f"Lookahead phát hiện: {oi_at_4h} != {oi_known}"

    def test_downsample_5m_to_1m_forward_fill(self):
        """
        Downsample 5m sang 1m: phải forward-fill từng phút, không nội suy tương lai.
        """
        from src.data_layer.binance_vision_downloader import downsample_oi_to_timeframe

        idx_5m = pd.date_range("2024-01-01 00:00:00", periods=2, freq="5min", tz="UTC")
        # 00:00 có OI = 1000, 00:05 có OI = 2000
        df_5m = pd.DataFrame({"open_interest": [1000.0, 2000.0]}, index=idx_5m)

        df_1m = downsample_oi_to_timeframe(df_5m, "1m")

        # Các phút 00:01, 00:02, 00:03, 00:04 PHẢI CÓ GIÁ TRỊ 1000 (forward-fill từ 00:00)
        # TUYỆT ĐỐI KHÔNG được là giá trị trung gian như 1200, 1400... (linear interpolation)
        for m in [1, 2, 3, 4]:
            ts = pd.Timestamp(f"2024-01-01 00:0{m}:00", tz="UTC")
            val = df_1m.loc[ts, "open_interest"]
            assert val == 1000.0, f"Phút {ts} bị nội suy: {val} != 1000.0"

        # Phút 00:05 mới được chuyển sang 2000.0
        ts_05 = pd.Timestamp("2024-01-01 00:05:00", tz="UTC")
        assert df_1m.loc[ts_05, "open_interest"] == 2000.0

    def test_oi_confluence_config_loaded(self):
        """
        Kiểm tra cấu hình oi_confluence được nạp đúng từ default_config.yaml.
        """
        import yaml
        config_path = _root / "config" / "default_config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        assert "oi_confluence" in cfg, "Thiếu mục oi_confluence trong default_config.yaml"
        oi_cfg = cfg["oi_confluence"]
        assert oi_cfg["mode"] == "optional", "Mode mặc định phải là optional"
        assert oi_cfg["fallback_when_nan"] is True, "fallback_when_nan phải là True"
        assert oi_cfg["nan_log_note"] == "OI_BYPASSED_HISTORICAL"

    @pytest.mark.network
    def test_vision_live_download_single_day(self):
        """
        INTEGRATION: Thử tải thực tế 1 ngày (2022-01-01) từ Binance Data Vision.
        """
        from src.data_layer.binance_vision_downloader import download_daily_metrics

        date_str, df, err = download_daily_metrics("BTCUSDT", "2022-01-01")
        assert err is None, f"Lỗi tải: {err}"
        assert df is not None and not df.empty, "DataFrame không được rỗng"
        # 1 ngày có 288 nến 5m (24h * 12 nến/h)
        assert 280 <= len(df) <= 288, f"Số nến 5m không hợp lý: {len(df)}"
        assert "open_interest" in df.columns
        assert (df["open_interest"] > 50000).all()  # OI BTC đầu 2022 khoảng ~75k BTC

    @pytest.mark.network
    def test_hybrid_oi_fetch_recent_60d(self, minimal_config):
        """
        INTEGRATION HYBRID OI: Thử kéo thực tế 60 ngày gần nhất (since = now - 60d, until = now)
        cho timeframe 4h.
        Xác nhận:
        1. Dữ liệu được trả về đầy đủ.
        2. Phần lịch sử (> 2 ngày trước) và phần gần nhất (1-2 ngày gần nhất) đều có dữ liệu.
        3. Đặc biệt: 1-2 ngày gần nhất KHÔNG ĐƯỢC LÀ NaN!
        """
        from src.data_layer.fetcher import fetch_open_interest

        now = pd.Timestamp.now(tz="UTC").floor("4h")
        since = now - pd.Timedelta(days=60)
        until = now

        oi = fetch_open_interest("BTC/USDT", "4h", since, until, minimal_config)
        if oi.empty:
            pytest.skip("Network không khả dụng, bỏ qua test hybrid OI")

        assert "open_interest" in oi.columns
        assert not oi.empty
        # 60 ngày x 6 nến 4h/ngày = ~360 nến (chấp nhận >= 300 nến)
        assert len(oi) >= 300, f"Số nến OI không đủ: {len(oi)}"

        # Kiểm tra đuôi gần nhất: 12 nến 4h cuối cùng (tương đương 48 giờ gần nhất)
        recent_tail = oi.tail(12)
        assert len(recent_tail) > 0
        assert not recent_tail["open_interest"].isna().any(), "Đuôi 1-2 ngày gần nhất có chứa NaN!"
        assert (recent_tail["open_interest"] > 0).all(), "Giá trị OI ở đuôi phải lớn hơn 0"

        # Kiểm tra đầu lịch sử: 12 nến đầu tiên
        early_head = oi.head(12)
        assert not early_head["open_interest"].isna().any(), "Đầu chuỗi 60 ngày có chứa NaN!"


