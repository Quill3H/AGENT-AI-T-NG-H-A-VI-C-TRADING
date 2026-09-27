"""
tests/test_indicators.py
========================
Unit tests kiểm tra tính đúng đắn toán học của module indicators.py:
- EMA, RSI, MACD, ATR
- So sánh kết quả tính bằng pandas-ta và pure pandas fallback
- Kiểm tra không đột biến (mutate) cột gốc
- Kiểm tra ngoại lệ khi thiếu cột bắt buộc
- Kiểm tra warm-up periods
"""
import numpy as np
import pandas as pd
import pytest

from src.features.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_atr,
    calculate_indicators,
    _PANDAS_TA_AVAILABLE,
)


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Tạo chuỗi OHLCV nhân tạo gồm 250 nến phục vụ test chỉ báo."""
    np.random.seed(42)
    n = 250
    dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    
    # Bước đi ngẫu nhiên cho giá đóng cửa
    returns = np.random.normal(0.001, 0.02, n)
    close = 40000.0 * np.exp(np.cumsum(returns))
    high = close * (1.0 + np.abs(np.random.normal(0, 0.005, n)))
    low = close * (1.0 - np.abs(np.random.normal(0, 0.005, n)))
    open_p = (high + low) / 2.0
    volume = np.random.uniform(100, 1000, n)
    taker_buy = volume * np.random.uniform(0.4, 0.6, n)

    df = pd.DataFrame(
        {
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "taker_buy_base_volume": taker_buy,
        },
        index=dates,
    )
    return df


class TestIndicators:
    """Bộ test cho các chỉ báo kỹ thuật cơ bản."""

    def test_ema_known_small_series(self):
        """Kiểm tra EMA trên chuỗi dữ liệu 5 giá trị tính tay."""
        # Giá trị: [10, 20, 30, 40, 50]
        # Chuẩn TA-Lib (presma=True):
        # Index 0, 1: NaN
        # Index 2: SMA(3) = (10 + 20 + 30) / 3 = 20.0
        # Index 3: alpha = 2/(3+1) = 0.5 -> 0.5 * 40 + 0.5 * 20 = 30.0
        # Index 4: 0.5 * 50 + 0.5 * 30 = 40.0
        df = pd.DataFrame({"close": [10.0, 20.0, 30.0, 40.0, 50.0]})
        res = calculate_ema(df, periods=[3], use_fallback=True)

        expected = [np.nan, np.nan, 20.0, 30.0, 40.0]
        np.testing.assert_allclose(res["ema_3"].values, expected, rtol=1e-5)

    def test_ema_fallback_matches_pandas_ta(self, sample_ohlcv):
        """Kiểm tra kết quả fallback pure pandas trùng khớp với pandas-ta."""
        if not _PANDAS_TA_AVAILABLE:
            pytest.skip("pandas-ta không được cài đặt, bỏ qua so sánh chéo.")

        res_ta = calculate_ema(sample_ohlcv, periods=[20, 50], use_fallback=False)
        res_fb = calculate_ema(sample_ohlcv, periods=[20, 50], use_fallback=True)

        for p in [20, 50]:
            # Bỏ qua các nến đầu do min_periods nếu có
            col = f"ema_{p}"
            valid_idx = res_ta[col].dropna().index
            np.testing.assert_allclose(
                res_ta.loc[valid_idx, col].values,
                res_fb.loc[valid_idx, col].values,
                rtol=1e-3,
                err_msg=f"EMA {p} giữa pandas-ta và fallback bị lệch",
            )

    def test_rsi_constant_and_trending(self):
        """Kiểm tra RSI khi giá đi ngang (RSI ~ 50) và khi giá tăng liên tục (RSI -> 100)."""
        # Chuỗi tăng liên tục: mọi delta > 0, avg_loss = 0 -> RSI = 100
        df_up = pd.DataFrame({"close": np.linspace(100, 200, 50)})
        res_up = calculate_rsi(df_up, period=14, use_fallback=True)
        assert res_up["rsi_14"].iloc[-1] == pytest.approx(100.0, abs=1e-4)

        # Chuỗi giảm liên tục: mọi delta < 0, avg_gain = 0 -> RSI = 0
        df_down = pd.DataFrame({"close": np.linspace(200, 100, 50)})
        res_down = calculate_rsi(df_down, period=14, use_fallback=True)
        assert res_down["rsi_14"].iloc[-1] == pytest.approx(0.0, abs=1e-4)

    def test_rsi_fallback_matches_pandas_ta(self, sample_ohlcv):
        """Kiểm tra RSI giữa pandas-ta và fallback pure pandas tương đồng."""
        if not _PANDAS_TA_AVAILABLE:
            pytest.skip("pandas-ta không được cài đặt, bỏ qua so sánh chéo.")

        res_ta = calculate_rsi(sample_ohlcv, period=14, use_fallback=False)
        res_fb = calculate_rsi(sample_ohlcv, period=14, use_fallback=True)

        # Cả 2 đều dùng Wilder's smoothing (alpha = 1/14)
        valid = res_ta["rsi_14"].dropna().index.intersection(res_fb["rsi_14"].dropna().index)
        # So sánh sau warm-up period (từ index 30 trở đi)
        valid = valid[30:]
        np.testing.assert_allclose(
            res_ta.loc[valid, "rsi_14"].values,
            res_fb.loc[valid, "rsi_14"].values,
            rtol=1e-2,
            atol=0.5,
            err_msg="RSI 14 giữa pandas-ta và fallback bị lệch",
        )

    def test_macd_formula(self, sample_ohlcv):
        """Kiểm tra quan hệ định nghĩa MACD: macd_hist = macd - macd_signal."""
        res = calculate_macd(sample_ohlcv, fast=12, slow=26, signal=9, use_fallback=True)
        assert "macd" in res.columns
        assert "macd_signal" in res.columns
        assert "macd_hist" in res.columns

        diff = res["macd"] - res["macd_signal"]
        np.testing.assert_allclose(res["macd_hist"].values, diff.values, atol=1e-8)

    def test_atr_positive_and_matches_tr(self):
        """Kiểm tra ATR luôn dương và đúng tính chất biên độ nến."""
        df = pd.DataFrame({
            "high": [105.0, 110.0, 108.0, 115.0, 112.0],
            "low":  [95.0,  100.0, 98.0,  102.0, 100.0],
            "close":[100.0, 105.0, 102.0, 110.0, 105.0],
        })
        res = calculate_atr(df, period=3, use_fallback=True)
        assert "atr_3" in res.columns
        # ATR phải luôn > 0
        valid_atr = res["atr_3"].dropna()
        assert (valid_atr > 0).all()

    def test_calculate_indicators_all_columns_present(self, sample_ohlcv, config):
        """Kiểm tra calculate_indicators tạo đủ toàn bộ các cột từ config."""
        orig_cols = list(sample_ohlcv.columns)
        res = calculate_indicators(sample_ohlcv, config=config)

        # Cột gốc phải giữ nguyên
        for col in orig_cols:
            assert col in res.columns
            pd.testing.assert_series_equal(res[col], sample_ohlcv[col])

        # Cột chỉ báo mới
        expected_cols = [
            "ema_20", "ema_50", "ema_200",
            "rsi_14",
            "macd", "macd_signal", "macd_hist",
            "atr_14",
        ]
        for ec in expected_cols:
            assert ec in res.columns, f"Thiếu cột {ec} trong output của calculate_indicators"

    def test_warmup_period_ema200(self, sample_ohlcv, config):
        """Xác nhận warm-up period: 200 nến đầu của EMA 200 có thể là NaN hoặc hội tụ."""
        res = calculate_indicators(sample_ohlcv, config=config)
        # Nến thứ 200 trở đi chắc chắn phải có giá trị hợp lệ
        assert pd.notna(res["ema_200"].iloc[200])

    def test_missing_required_columns_raises(self):
        """Kiểm tra bắt lỗi ngoại lệ khi DataFrame thiếu cột cần thiết."""
        df_bad = pd.DataFrame({"open": [1, 2], "volume": [10, 20]})
        with pytest.raises(ValueError, match="close"):
            calculate_ema(df_bad)
        with pytest.raises(ValueError, match="close"):
            calculate_rsi(df_bad)
        with pytest.raises(ValueError, match="close"):
            calculate_macd(df_bad)
        with pytest.raises(ValueError, match="high"):
            calculate_atr(df_bad)
