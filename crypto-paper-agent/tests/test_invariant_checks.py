"""
test_invariant_checks.py - Unit tests for 6 Hard Invariants
============================================================
Kiểm thử toàn bộ 6 Hard Invariants của Risk Manager theo mục 4.4 Master Spec:
1. Thiếu hoặc sai chiều Stop-Loss
2. Vượt trần đòn bẩy (Leverage Cap)
3. Đệm thanh lý không đủ 30% hoặc thanh lý trước Stop-Loss
4. Vượt trần Conviction Tier
5. Đang bị khóa bởi Circuit Breaker
6. Rơi vào cửa sổ cấm tin tức (News Blackout Window)
Cùng với các kịch bản All-Pass và Multiple-Fails (trả về trọn vẹn danh sách lỗi).
"""
from datetime import datetime, timezone
import pytest
from src.features.news_calendar import EconomicEvent, NewsCalendarFilter
from src.risk.circuit_breakers import CircuitBreakerState
from src.risk.invariant_checks import check_all_invariants


class TestInvariantChecks:
    @pytest.fixture
    def base_order(self):
        return {
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry_price": 50000.0,
            "stop_loss_price": 49000.0,
            "leverage": 3.0,
            "risk_percent": 0.02,
            "conviction_tier": "normal",
            "position_size_usd": 10000.0,
            "timestamp": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        }

    @pytest.fixture
    def base_account(self):
        return {
            "equity": 10000.0,
            "circuit_breaker_state": CircuitBreakerState(),
            "news_filter": None,
            "current_time": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        }

    def test_all_invariants_pass(self, base_order, base_account, config):
        """Lệnh chuẩn hoàn toàn vượt qua toàn bộ 6 invariants."""
        is_valid, reasons = check_all_invariants(base_order, base_account, config)
        assert is_valid is True
        assert len(reasons) == 0

    def test_invariant_1_fail_missing_stop_loss(self, base_order, base_account, config):
        """Invariant 1 fail: Không có Stop-Loss."""
        order = dict(base_order)
        order["stop_loss_price"] = None

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_STOP_LOSS_MISSING" in r for r in reasons)

    def test_invariant_1_fail_invalid_direction_stop_loss(self, base_order, base_account, config):
        """Invariant 1 fail: Long nhưng Stop-Loss lại đặt cao hơn giá Entry."""
        order = dict(base_order)
        order["stop_loss_price"] = 51000.0  # Cao hơn entry 50,000

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_STOP_LOSS_DIRECTION" in r for r in reasons)

    def test_invariant_2_fail_leverage_exceeded(self, base_order, base_account, config):
        """Invariant 2 fail: Đòn bẩy 10x vượt quá trần 5x trong config."""
        order = dict(base_order)
        order["leverage"] = 10.0

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_LEVERAGE_EXCEEDED" in r for r in reasons)

    def test_invariant_3_fail_liquidation_buffer_insufficient(self, base_order, base_account, config):
        """Invariant 3 fail: Đệm giữa giá thanh lý và stop loss không đủ 30% entry."""
        order = dict(base_order)
        order["leverage"] = 5.0
        order["stop_loss_price"] = 45000.0  # P_liq ~ 40,160 -> buffer ~ 4,840 / 50,000 = 9.68% < 30%

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_LIQUIDATION_BUFFER" in r for r in reasons)

    def test_invariant_3_fail_liquidation_before_stop_loss(self, base_order, base_account, config):
        """Invariant 3 fail: Giá thanh lý kích hoạt trước Stop-Loss."""
        order = dict(base_order)
        order["leverage"] = 5.0
        order["stop_loss_price"] = 38000.0  # P_liq ~ 40,160 > SL 38,000 -> Cháy trước khi chạm SL

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_LIQUIDATION_BEFORE_SL" in r for r in reasons)

    def test_invariant_4_fail_conviction_tier_exceeded(self, base_order, base_account, config):
        """Invariant 4 fail: Tier 'normal' tối đa 2%, nhưng lệnh đòi rủi ro 5%."""
        order = dict(base_order)
        order["conviction_tier"] = "normal"
        order["risk_percent"] = 0.05

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_RISK_TIER_EXCEEDED" in r for r in reasons)

    def test_invariant_5_fail_circuit_breaker_locked(self, base_order, base_account, config):
        """Invariant 5 fail: Circuit Breaker đang trong thời gian khóa 24h."""
        cb = CircuitBreakerState()
        cb.is_locked = True
        cb.locked_until = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)

        account = dict(base_account)
        account["circuit_breaker_state"] = cb

        is_valid, reasons = check_all_invariants(base_order, account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_CIRCUIT_BREAKER_LOCKED" in r for r in reasons)

    def test_invariant_6_fail_news_blackout_window(self, base_order, base_account, config):
        """Invariant 6 fail: Thời điểm vào lệnh rơi vào khung cấm tin tức ±15 phút."""
        cfg = dict(config)
        cfg["news_filter"] = {"enabled": True, "blackout_minutes_before": 15, "blackout_minutes_after": 15}

        news_filter = NewsCalendarFilter(config=cfg)
        event_dt = datetime(2026, 9, 1, 10, 10, tzinfo=timezone.utc)
        news_filter.events = [EconomicEvent(timestamp=event_dt, event_name="US CPI Release")]

        account = dict(base_account)
        account["news_filter"] = news_filter

        # base_order có timestamp lúc 10:00 -> cách sự kiện 10 phút (nằm trong window 15m)
        is_valid, reasons = check_all_invariants(base_order, account, cfg)
        assert is_valid is False
        assert any("INVARIANT_FAIL_NEWS_BLACKOUT" in r for r in reasons)

    def test_news_filter_bypassed_when_disabled(self, base_order, base_account, config):
        """Nếu news_filter.enabled = False, tôn trọng triết lý oi_confluence: luôn pass không chặn."""
        news_filter = NewsCalendarFilter(config={"news_filter": {"enabled": False}})
        event_dt = datetime(2026, 9, 1, 10, 10, tzinfo=timezone.utc)
        news_filter.events = [EconomicEvent(timestamp=event_dt, event_name="US CPI Release")]

        account = dict(base_account)
        account["news_filter"] = news_filter

        is_valid, reasons = check_all_invariants(base_order, account, config)
        assert is_valid is True
        assert len(reasons) == 0

    def test_multiple_invariants_fail_simultaneously_returns_all_reasons(
        self, base_order, base_account, config
    ):
        """
        Kiểm tra tính năng quan trọng: Khi nhiều invariants cùng vi phạm,
        hàm LUÔN trả về toàn bộ danh sách lỗi, không dừng ở lỗi đầu tiên.
        Ví dụ vi phạm cùng lúc 3 lỗi:
        1. Thiếu Stop-Loss
        2. Đòn bẩy 10x > 5x
        3. Circuit Breaker đang khóa
        """
        cb = CircuitBreakerState()
        cb.is_locked = True
        cb.locked_until = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)

        account = dict(base_account)
        account["circuit_breaker_state"] = cb

        order = dict(base_order)
        order["stop_loss_price"] = None  # Lỗi 1
        order["leverage"] = 10.0          # Lỗi 2

        is_valid, reasons = check_all_invariants(order, account, config)
        assert is_valid is False
        assert len(reasons) >= 3
        assert any("INVARIANT_FAIL_STOP_LOSS_MISSING" in r for r in reasons)
        assert any("INVARIANT_FAIL_LEVERAGE_EXCEEDED" in r for r in reasons)
        assert any("INVARIANT_FAIL_CIRCUIT_BREAKER_LOCKED" in r for r in reasons)

    def test_invariant_fail_unknown_conviction_tier(self, base_order, base_account, config):
        """Từ chối order có conviction_tier lạ (không có trong config) - không tự ý fallback 10%."""
        order = dict(base_order)
        order["conviction_tier"] = "mega_tier"

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_UNKNOWN_CONVICTION_TIER" in r for r in reasons)

    def test_invariant_fail_actual_risk_exceeds_budget(self, base_order, base_account, config):
        """
        R2 check: Đối soát rủi ro thực tế Quantity * |Entry - Stop| với ngân sách rủi ro tối đa cho phép.
        Ví dụ: Equity = 10,000$, normal tier (2%) -> budget = 200$.
        Nhưng order set position_size_usd = 30,000$ (Quantity = 0.6 BTC), SL = 49,000$ (cách 1,000$).
        Tổn thất thực tế = 0.6 * 1000 = 600$ > 200$ -> BỊ CHẶN!
        """
        order = dict(base_order)
        order["position_size_usd"] = 30000.0  # Qty = 0.6, Risk = 600$

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_ACTUAL_RISK_EXCEEDED" in r for r in reasons)

    def test_invariant_fail_insufficient_margin(self, base_order, base_account, config):
        """
        R2 check: Ký quỹ yêu cầu required_margin_usd vượt quá available_margin (hoặc equity).
        Ví dụ: Position size 50,000$, leverage 3x -> Required margin = 16,666.67$ > Available margin 10,000$.
        """
        order = dict(base_order)
        order["position_size_usd"] = 50000.0
        order["risk_percent"] = 0.05
        order["conviction_tier"] = "high"
        # Đặt stop loss sát để không vi phạm actual risk (SL = 49,960 -> 40$ dist -> 50000/50000 * 40 = 40$)
        order["stop_loss_price"] = 49960.0

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_INSUFFICIENT_MARGIN" in r for r in reasons)

    def test_invariant_fail_missing_circuit_breaker(self, base_order, base_account, config):
        """account_state thiếu circuit_breaker_state hợp lệ phải bị từ chối."""
        account = dict(base_account)
        account["circuit_breaker_state"] = None

        is_valid, reasons = check_all_invariants(base_order, account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_MISSING_CIRCUIT_BREAKER" in r for r in reasons)

    def test_invariant_fail_missing_news_filter_when_enabled(self, base_order, base_account, config):
        """Khi config.news_filter.enabled = True nhưng account thiếu component news_filter hợp lệ."""
        cfg = dict(config)
        cfg["news_filter"] = {"enabled": True}

        account = dict(base_account)
        account["news_filter"] = None

        is_valid, reasons = check_all_invariants(base_order, account, cfg)
        assert is_valid is False
        assert any("INVARIANT_FAIL_MISSING_NEWS_FILTER" in r for r in reasons)

    def test_invariant_fail_missing_simulation_timestamp(self, base_order, base_account, config):
        """Loại bỏ hoàn toàn fallback datetime.now() - nếu thiếu timestamp thì phải reject."""
        order = dict(base_order)
        order["timestamp"] = None

        account = dict(base_account)
        account["current_time"] = None

        is_valid, reasons = check_all_invariants(order, account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_MISSING_TIMESTAMP" in r for r in reasons)

    def test_invariant_fail_future_order_timestamp(self, base_order, base_account, config):
        """Thời điểm của lệnh order['timestamp'] không được lớn hơn admission time (current_time)."""
        order = dict(base_order)
        order["timestamp"] = datetime(2026, 9, 1, 10, 30, tzinfo=timezone.utc)

        account = dict(base_account)
        account["current_time"] = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

        is_valid, reasons = check_all_invariants(order, account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_FUTURE_ORDER_TIMESTAMP" in r for r in reasons)

    def test_invariant_fail_short_stop_loss_direction(self, base_order, base_account, config):
        """Lệnh SHORT nhưng Stop-Loss lại đặt thấp hơn giá Entry."""
        order = dict(base_order)
        order["direction"] = "SHORT"
        order["entry_price"] = 50000.0
        order["stop_loss_price"] = 49000.0  # Thấp hơn entry cho vị thế SHORT là sai chiều!

        is_valid, reasons = check_all_invariants(order, base_account, config)
        assert is_valid is False
        assert any("INVARIANT_FAIL_STOP_LOSS_DIRECTION" in r for r in reasons)

