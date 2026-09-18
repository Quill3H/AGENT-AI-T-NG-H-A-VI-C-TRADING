"""
test_position_sizing.py - Unit tests for Position Sizing
=========================================================
Kiểm thử tính toán position size theo công thức chuẩn trong Master Spec,
đối chiếu từng trường kết quả với số liệu tính tay, và kiểm tra bắt lỗi đầy đủ theo ADR 0006 và GPT review R1:
- Từ chối NaN, +Inf, -Inf, bool, string sai
- Bắt lỗi chia cho 0 khi stop_price == entry_price
- Kiểm tra các ràng buộc biên số học và overflow.
"""
import math
import pytest
from src.risk.position_sizing import calculate_position_size


class TestPositionSizing:
    def test_long_position_hand_calculated_values(self):
        """
        Kịch bản tính tay 1 (Vị thế LONG):
        - Vốn (Equity): 10,000 USD
        - Rủi ro (Risk %): 2% (0.02) -> risk_usd = 200 USD
        - Giá vào (Entry): 50,000 USD
        - Giá dừng lỗ (Stop): 49,000 USD -> Khoảng cách: 1,000 USD (2%)
        - Đòn bẩy (Leverage): 5x
        - Kích thước vị thế (Position Size USD): 200 / 0.02 = 10,000 USD
        - Khối lượng (Quantity): 200 / 1,000 = 0.2 BTC
        - Ký quỹ cần (Required Margin): 10,000 / 5 = 2,000 USD
        """
        res = calculate_position_size(
            equity=10000.0,
            risk_percent=0.02,
            entry_price=50000.0,
            stop_price=49000.0,
            leverage=5.0,
        )
        assert pytest.approx(res["risk_usd"], rel=1e-5) == 200.0
        assert pytest.approx(res["stop_distance_pct"], rel=1e-5) == 0.02
        assert pytest.approx(res["position_size_usd"], rel=1e-5) == 10000.0
        assert pytest.approx(res["quantity"], rel=1e-5) == 0.2
        assert pytest.approx(res["required_margin_usd"], rel=1e-5) == 2000.0

    def test_short_position_hand_calculated_values(self):
        """
        Kịch bản tính tay 2 (Vị thế SHORT):
        - Vốn: 20,000 USD
        - Rủi ro: 1% (0.01) -> risk_usd = 200 USD
        - Giá vào: 60,000 USD
        - Giá dừng lỗ: 61,500 USD -> Khoảng cách: 1,500 USD (2.5%)
        - Đòn bẩy: 3x
        - Position Size USD: 200 / 0.025 = 8,000 USD
        - Quantity: 200 / 1,500 = 0.1333333 BTC
        - Required Margin: 8,000 / 3 = 2,666.6667 USD
        """
        res = calculate_position_size(
            equity=20000.0,
            risk_percent=0.01,
            entry_price=60000.0,
            stop_price=61500.0,
            leverage=3.0,
        )
        assert pytest.approx(res["risk_usd"], rel=1e-5) == 200.0
        assert pytest.approx(res["stop_distance_pct"], rel=1e-5) == 0.025
        assert pytest.approx(res["position_size_usd"], rel=1e-5) == 8000.0
        assert pytest.approx(res["quantity"], rel=1e-5) == 200.0 / 1500.0
        assert pytest.approx(res["required_margin_usd"], rel=1e-5) == 8000.0 / 3.0

    def test_stop_equals_entry_raises_value_error(self):
        """Khi stop_price == entry_price, mẫu số khoảng cách bằng 0 -> Phải raise ValueError rõ ràng."""
        with pytest.raises(ValueError, match="Stop loss price cannot be equal to entry price"):
            calculate_position_size(
                equity=10000.0,
                risk_percent=0.02,
                entry_price=50000.0,
                stop_price=50000.0,
                leverage=5.0,
            )

    @pytest.mark.parametrize(
        "equity,risk_percent,entry,stop,leverage,err_match,err_type",
        [
            (-1000.0, 0.02, 50000.0, 49000.0, 5.0, "strictly greater than", ValueError),
            (0.0, 0.02, 50000.0, 49000.0, 5.0, "strictly greater than", ValueError),
            (10000.0, -0.01, 50000.0, 49000.0, 5.0, "strictly greater than", ValueError),
            (10000.0, 0.0, 50000.0, 49000.0, 5.0, "strictly greater than", ValueError),
            (10000.0, 0.02, -50000.0, 49000.0, 5.0, "strictly greater than", ValueError),
            (10000.0, 0.02, 50000.0, -49000.0, 5.0, "strictly greater than", ValueError),
            (10000.0, 0.02, 50000.0, 49000.0, 0.5, "greater than or equal to", ValueError),
            # R1 Regression: Nan and Inf
            (float("nan"), 0.02, 50000.0, 49000.0, 5.0, "finite number", ValueError),
            (10000.0, float("nan"), 50000.0, 49000.0, 5.0, "finite number", ValueError),
            (10000.0, 0.02, float("nan"), 49000.0, 5.0, "finite number", ValueError),
            (10000.0, 0.02, 50000.0, float("nan"), 5.0, "finite number", ValueError),
            (10000.0, 0.02, 50000.0, 49000.0, float("nan"), "finite number", ValueError),
            (float("inf"), 0.02, 50000.0, 49000.0, 5.0, "finite number", ValueError),
            (10000.0, 0.02, float("inf"), 49000.0, 5.0, "finite number", ValueError),
            # R1 Regression: bool rejection
            (True, 0.02, 50000.0, 49000.0, 5.0, "numeric float or int", TypeError),
            (10000.0, False, 50000.0, 49000.0, 5.0, "numeric float or int", TypeError),
            (10000.0, 0.02, 50000.0, 49000.0, True, "numeric float or int", TypeError),
            # R1 Regression: strings rejection
            ("10000", 0.02, 50000.0, 49000.0, 5.0, "numeric float or int", TypeError),
        ],
    )
    def test_invalid_arguments_raise_error(
        self, equity, risk_percent, entry, stop, leverage, err_match, err_type
    ):
        with pytest.raises(err_type, match=err_match):
            calculate_position_size(
                equity=equity,
                risk_percent=risk_percent,
                entry_price=entry,
                stop_price=stop,
                leverage=leverage,
            )
