"""
tests/test_no_lookahead.py
==========================
Kiểm thử tính bất biến nhân quả (Causal Invariance / Anti-Lookahead Bias Test).
Theo đúng mục 5 trong CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md:

Quy tắc:
Bắt buộc có unit test riêng shuffle/thay đổi ngẫu nhiên toàn bộ dữ liệu tương lai
(sau thời điểm T) để đảm bảo việc thay đổi dữ liệu tương lai tuyệt đối không ảnh hưởng
tới bất kỳ feature nào tại thời điểm T (và các thời điểm < T trong quá khứ).
"""
import numpy as np
import pandas as pd
import pytest

from src.features import add_all_features


@pytest.fixture
def base_market_dataframe() -> pd.DataFrame:
    """Tạo chuỗi dữ liệu 300 nến đầy đủ OHLCV, volume, taker_buy và open_interest."""
    np.random.seed(123)
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")

    returns = np.random.normal(0.0002, 0.01, n)
    close = 50000.0 * np.exp(np.cumsum(returns))
    high = close * (1.0 + np.abs(np.random.normal(0, 0.003, n)))
    low = close * (1.0 - np.abs(np.random.normal(0, 0.003, n)))
    open_p = (high + low) / 2.0
    volume = np.random.uniform(50, 500, n)
    taker_buy = volume * np.random.uniform(0.3, 0.7, n)
    open_interest = 10000.0 + np.cumsum(np.random.normal(0, 50, n))

    df = pd.DataFrame(
        {
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "taker_buy_base_volume": taker_buy,
            "open_interest": open_interest,
        },
        index=dates,
    )
    return df


class TestNoLookaheadBias:
    """Kiểm tra triệt để chống Lookahead Bias."""

    @pytest.mark.parametrize("cutoff_t", [80, 150, 220])
    @pytest.mark.parametrize("use_fallback", [False, True])
    def test_future_data_tampering_does_not_alter_past_features(
        self, base_market_dataframe, config, cutoff_t, use_fallback
    ):
        """
        Tại thời điểm T:
        Thay đổi ngẫu nhiên toàn bộ dữ liệu từ T + 1 đến cuối chuỗi (giá tăng x10, xáo trộn).
        Tính lại toàn bộ feature trên chuỗi bị sửa đổi.
        Khẳng định: Mọi feature tại t <= T giữa 2 chuỗi là BẰNG NHAU TUYỆT ĐỐI.
        """
        df_original = base_market_dataframe.copy()
        features_orig = add_all_features(
            df_original, config=config, use_fallback_indicators=use_fallback
        )

        # Tạo bản sao và bóp méo hoàn toàn dữ liệu tương lai (sau cutoff_t)
        df_tampered = df_original.copy()
        n = len(df_tampered)

        np.random.seed(999)
        tampered_slice = slice(cutoff_t + 1, n)

        # Nhân giá lên 10 lần và đảo ngược biến động
        df_tampered.loc[df_tampered.index[tampered_slice], "close"] *= 10.0
        df_tampered.loc[df_tampered.index[tampered_slice], "high"] *= 12.0
        df_tampered.loc[df_tampered.index[tampered_slice], "low"] *= 8.0
        df_tampered.loc[df_tampered.index[tampered_slice], "open"] *= 10.0
        df_tampered.loc[df_tampered.index[tampered_slice], "volume"] *= 50.0
        df_tampered.loc[df_tampered.index[tampered_slice], "taker_buy_base_volume"] *= 50.0
        df_tampered.loc[df_tampered.index[tampered_slice], "open_interest"] = np.nan

        # Tính lại toàn bộ features trên dataframe đã bị phá hoại tương lai
        features_tampered = add_all_features(
            df_tampered, config=config, use_fallback_indicators=use_fallback
        )

        # Kiểm tra tất cả các cột feature:
        feature_columns = [
            "ema_20", "ema_50", "ema_200",
            "rsi_14",
            "macd", "macd_signal", "macd_hist",
            "atr_14",
            "oi_delta_pct",
            "cvd",
            "cvd_divergence",
        ]

        # Cắt lấy phần quá khứ và hiện tại (t <= cutoff_t)
        past_orig = features_orig.iloc[: cutoff_t + 1][feature_columns]
        past_tamp = features_tampered.iloc[: cutoff_t + 1][feature_columns]

        # Kiểm tra từng cột
        for col in feature_columns:
            s_orig = past_orig[col]
            s_tamp = past_tamp[col]

            if col == "cvd_divergence":
                # Kiểu chuỗi categorical
                mismatches = s_orig != s_tamp
                if mismatches.any():
                    mismatch_idx = past_orig.index[mismatches]
                    pytest.fail(
                        f"Lookahead bias phát hiện tại cột '{col}' ở các index: {mismatch_idx}! "
                        f"Dữ liệu tương lai đã làm thay đổi giá trị quá khứ."
                    )
            else:
                # Kiểu số float
                # NaN phải xuất hiện ở đúng cùng một vị trí
                assert s_orig.isna().equals(s_tamp.isna()), (
                    f"Lookahead bias tại cột '{col}': vị trí NaN bị thay đổi bởi tương lai!"
                )
                valid = s_orig.dropna().index
                np.testing.assert_allclose(
                    s_orig.loc[valid].values,
                    s_tamp.loc[valid].values,
                    rtol=1e-7,
                    atol=1e-7,
                    err_msg=f"Lookahead bias tại cột '{col}'! Dữ liệu tương lai thay đổi giá trị tại t <= {cutoff_t}",
                )
