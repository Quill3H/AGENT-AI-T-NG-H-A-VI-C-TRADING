"""
tests/test_oi_features.py
=========================
Unit tests kiểm tra module oi_features.py:
- Tính % thay đổi Open Interest (oi_delta_pct) đúng công thức
- Cơ chế lan truyền NaN (NaN propagation) khi OI bị thiếu
- Xử lý an toàn khi không có cột open_interest hoặc cột toàn NaN (không raise lỗi)
- Không mutate các cột gốc
"""
import numpy as np
import pandas as pd
import pytest

from src.features.oi_features import calculate_oi_features


class TestOIFeatures:
    """Bộ test kiểm tra tính năng Open Interest."""

    def test_oi_delta_pct_known_values(self):
        """Kiểm tra công thức oi_delta_pct với dữ liệu biết trước."""
        # OI: [100.0, 110.0, 121.0, 108.9]
        # Lookback = 1
        # t=0: NaN
        # t=1: (110 - 100) / 100 * 100 = 10.0%
        # t=2: (121 - 110) / 110 * 100 = 10.0%
        # t=3: (108.9 - 121) / 121 * 100 = -10.0%
        df = pd.DataFrame({"open_interest": [100.0, 110.0, 121.0, 108.9]})
        res = calculate_oi_features(df, lookback=1)

        assert "oi_delta_pct" in res.columns
        assert pd.isna(res["oi_delta_pct"].iloc[0])
        assert res["oi_delta_pct"].iloc[1] == pytest.approx(10.0, rel=1e-4)
        assert res["oi_delta_pct"].iloc[2] == pytest.approx(10.0, rel=1e-4)
        assert res["oi_delta_pct"].iloc[3] == pytest.approx(-10.0, rel=1e-4)

    def test_oi_delta_pct_lookback_from_config(self, config):
        """Kiểm tra đọc lookback từ config (mặc định 20)."""
        n = 50
        df = pd.DataFrame({"open_interest": np.linspace(1000, 2000, n)})
        res = calculate_oi_features(df, config=config)

        # 20 dòng đầu phải là NaN do shift(20)
        assert res["oi_delta_pct"].iloc[:20].isna().all()
        # Dòng thứ 20 (index 20) phải có giá trị hợp lệ
        assert pd.notna(res["oi_delta_pct"].iloc[20])

    def test_nan_propagation_when_oi_has_nan(self):
        """Kiểm tra lan truyền NaN: nếu OI tại t hoặc t-N là NaN thì oi_delta_pct là NaN."""
        df = pd.DataFrame({
            "open_interest": [100.0, 120.0, np.nan, 150.0, 160.0]
        })
        res = calculate_oi_features(df, lookback=1)

        # t=0: NaN (shift)
        assert pd.isna(res["oi_delta_pct"].iloc[0])
        # t=1: hợp lệ
        assert res["oi_delta_pct"].iloc[1] == pytest.approx(20.0)
        # t=2: OI tại t là NaN -> oi_delta_pct phải là NaN
        assert pd.isna(res["oi_delta_pct"].iloc[2])
        # t=3: OI tại t-1 là NaN -> oi_delta_pct phải là NaN
        assert pd.isna(res["oi_delta_pct"].iloc[3])
        # t=4: OI(4)=160, OI(3)=150 -> hợp lệ
        assert res["oi_delta_pct"].iloc[4] == pytest.approx((160 - 150) / 150 * 100)

    def test_missing_oi_column_does_not_raise(self):
        """Khi DataFrame không có cột open_interest, không được raise lỗi và gán cột toàn NaN."""
        df = pd.DataFrame({"close": [10, 20, 30]})
        res = calculate_oi_features(df, lookback=5)

        assert "oi_delta_pct" in res.columns
        assert res["oi_delta_pct"].isna().all()
        assert len(res) == 3

    def test_all_nan_oi_column_does_not_raise(self):
        """Khi cột open_interest toàn bộ là NaN, không được raise lỗi và gán cột toàn NaN."""
        df = pd.DataFrame({"open_interest": [np.nan, np.nan, np.nan]})
        res = calculate_oi_features(df, lookback=2)

        assert "oi_delta_pct" in res.columns
        assert res["oi_delta_pct"].isna().all()

    def test_original_columns_not_mutated(self):
        """Đảm bảo hàm không làm thay đổi các cột gốc."""
        df = pd.DataFrame({"open_interest": [100.0, 200.0], "close": [1.0, 2.0]})
        df_copy = df.copy()
        res = calculate_oi_features(df, lookback=1)

        pd.testing.assert_frame_equal(df, df_copy)
        assert "oi_delta_pct" in res.columns
        assert "close" in res.columns
