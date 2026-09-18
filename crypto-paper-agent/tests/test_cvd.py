"""
tests/test_cvd.py
=================
Unit tests kiểm tra module cvd.py:
- Tính CVD cộng dồn đúng công thức
- Nhận diện đúng kịch bản phân kỳ tăng (BULLISH divergence)
- Nhận diện đúng kịch bản phân kỳ giảm (BEARISH divergence)
- Xác nhận độ trễ xác nhận (confirmation lag) không bị leak về quá khứ
"""
import numpy as np
import pandas as pd
import pytest

from src.features.cvd import calculate_cvd, calculate_cvd_divergence


class TestCVD:
    """Bộ test kiểm tra CVD và CVD Divergence."""

    def test_cvd_calculation_known_values(self):
        """Kiểm tra cộng dồn delta khối lượng với dữ liệu biết trước."""
        # Volume: [100, 200, 150]
        # Taker buy: [60, 80, 100]
        # Taker sell = Volume - Taker buy: [40, 120, 50]
        # Delta = Taker buy - Taker sell = [20, -40, 50]
        # CVD = cumsum(Delta) = [20, -20, 30]
        df = pd.DataFrame({
            "volume": [100.0, 200.0, 150.0],
            "taker_buy_base_volume": [60.0, 80.0, 100.0],
        })
        res = calculate_cvd(df)

        assert "cvd" in res.columns
        expected_cvd = [20.0, -20.0, 30.0]
        np.testing.assert_allclose(res["cvd"].values, expected_cvd)

    def test_cvd_divergence_bullish_scenario(self):
        """
        Kịch bản BULLISH Divergence rõ ràng:
        - Swing Low 1 (L1) tại index 5: Low = 100.0, CVD = 50.0
        - Đỉnh trung gian tại index 9: High = 120.0
        - Swing Low 2 (L2) tại index 13: Low = 90.0 (Lower Low), CVD = 75.0 (Higher Low)
        - swing_n = 2: Cần 2 nến xác nhận sau L2 -> Được xác nhận tại index 15 (13 + 2).
        """
        n = 20
        swing_n = 2
        lookback = 18

        # Khởi tạo giá nền cao
        high = [130.0] * n
        low = [110.0] * n
        cvd = [100.0] * n

        # Tạo Swing Low 1 tại index 5 (L1)
        # Nến 3, 4: low = 110
        # Nến 5: low = 100 (đáy)
        # Nến 6, 7: low = 110
        low[5] = 100.0
        cvd[5] = 50.0

        # Đỉnh giữa tại index 9
        high[9] = 140.0

        # Tạo Swing Low 2 tại index 13 (L2)
        # Nến 11, 12: low = 110
        # Nến 13: low = 90.0 (thấp hơn L1: Lower Low)
        # Nến 14, 15: low = 110
        low[13] = 90.0
        cvd[13] = 75.0  # CVD tại L2 cao hơn tại L1 (Higher Low)

        df = pd.DataFrame({"high": high, "low": low, "cvd": cvd})
        res = calculate_cvd_divergence(df, lookback=lookback, swing_n=swing_n)

        # 1. Tại chính thời điểm L2 xảy ra (index 13): Chưa đủ nến xác nhận -> KHÔNG ĐƯỢC là BULLISH
        assert res["cvd_divergence"].iloc[13] != "BULLISH", (
            "Lookahead Bias! Tín hiệu phân kỳ bị gán ngược về nến index 13 trước khi được xác nhận."
        )

        # 2. Tại nến index 14: Mới có 1 nến sau L2 -> Chưa đủ 2 nến xác nhận
        assert res["cvd_divergence"].iloc[14] != "BULLISH"

        # 3. Tại nến index 15 (13 + swing_n): Đã đủ 2 nến xác nhận L2 -> Bắt đầu ghi nhận BULLISH
        assert res["cvd_divergence"].iloc[15] == "BULLISH", (
            "Tại index 15 (13 + 2), L2 phải được xác nhận và phát hiện BULLISH divergence!"
        )

    def test_cvd_divergence_bearish_scenario(self):
        """
        Kịch bản BEARISH Divergence rõ ràng:
        - Swing High 1 (H1) tại index 4: High = 150.0, CVD = 200.0
        - Đáy trung gian tại index 8: Low = 120.0
        - Swing High 2 (H2) tại index 12: High = 165.0 (Higher High), CVD = 160.0 (Lower High)
        - swing_n = 2: Xác nhận tại index 14 (12 + 2).
        """
        n = 20
        swing_n = 2
        lookback = 18

        high = [130.0] * n
        low = [110.0] * n
        cvd = [100.0] * n

        # Tạo Swing High 1 tại index 4 (H1)
        high[4] = 150.0
        cvd[4] = 200.0

        # Đáy giữa tại index 8
        low[8] = 95.0

        # Tạo Swing High 2 tại index 12 (H2)
        high[12] = 165.0  # Cao hơn H1: Higher High
        cvd[12] = 160.0  # CVD thấp hơn H1: Lower High

        df = pd.DataFrame({"high": high, "low": low, "cvd": cvd})
        res = calculate_cvd_divergence(df, lookback=lookback, swing_n=swing_n)

        # Chưa xác nhận tại index 12
        assert res["cvd_divergence"].iloc[12] != "BEARISH"
        # Chưa đủ nến tại index 13
        assert res["cvd_divergence"].iloc[13] != "BEARISH"
        # Đã đủ 2 nến xác nhận tại index 14
        assert res["cvd_divergence"].iloc[14] == "BEARISH"

    def test_cvd_divergence_none_when_in_agreement(self):
        """Khi giá và CVD đồng thuận (cùng tạo Higher High) -> Không có phân kỳ (NONE)."""
        n = 20
        swing_n = 2
        lookback = 18

        high = [130.0] * n
        low = [110.0] * n
        cvd = [100.0] * n

        # H1
        high[4] = 150.0
        cvd[4] = 150.0
        # Đáy giữa
        low[8] = 100.0
        # H2: Giá cao hơn VÀ CVD cũng cao hơn (đồng thuận xu hướng tăng)
        high[12] = 165.0
        cvd[12] = 220.0

        df = pd.DataFrame({"high": high, "low": low, "cvd": cvd})
        res = calculate_cvd_divergence(df, lookback=lookback, swing_n=swing_n)

        assert res["cvd_divergence"].iloc[14] == "NONE"
