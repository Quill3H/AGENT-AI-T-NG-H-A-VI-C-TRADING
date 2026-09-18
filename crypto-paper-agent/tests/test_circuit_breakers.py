"""
test_circuit_breakers.py - Unit tests for Circuit Breakers
==========================================================
Kiểm thử toàn diện 5 kịch bản ngắt mạch rủi ro theo Master Spec và ADR 0002:
1. Daily loss limit: Kích hoạt khóa 24h khi tổng lỗ rolling 24h >= 5% vốn.
2. Giảm risk: Sau đúng 3 lệnh thua liên tiếp -> risk_multiplier giảm còn 0.5.
3. Phục hồi risk: Sau đúng 3 lệnh thắng liên tiếp (ADR 0002) -> risk_multiplier trở lại 1.0.
4. Reset streak thắng: Khi có lệnh thua xen ngang, chuỗi thắng phải reset về 0, không cộng dồn.
5. Trading lockout window: is_trading_allowed trả về False trong 24h và True sau khi hết hạn.
"""
from datetime import datetime, timedelta, timezone
import pytest
from src.risk.circuit_breakers import CircuitBreakerState


class TestCircuitBreakers:
    def test_daily_loss_limit_triggers_24h_lock(self):
        """Khi lỗ rolling 24h >= 5% vốn (500$ trên vốn 10,000$), khóa giao dịch đúng 24h."""
        cb = CircuitBreakerState(daily_loss_limit_pct=0.05)
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        equity = 10000.0

        # Lệnh 1: Thua 200$ lúc 10:00 -> chưa chạm 500$
        cb.record_trade_result(pnl=-200.0, timestamp=t0, equity=equity)
        assert not cb.is_locked
        assert cb.locked_until is None

        # Lệnh 2: Thua thêm 300$ lúc 12:00 -> Tổng lỗ 24h là 500$ (đủ 5%)
        t1 = t0 + timedelta(hours=2)
        cb.record_trade_result(pnl=-300.0, timestamp=t1, equity=equity)
        assert cb.is_locked
        assert cb.locked_until == t1 + timedelta(hours=24)

    def test_risk_reduction_after_exactly_3_consecutive_losses(self):
        """Thua đúng 3 lệnh liên tiếp -> Giảm 50% risk (multiplier = 0.5)."""
        cb = CircuitBreakerState(consecutive_losses_threshold=3, risk_reduction_on_streak=0.5)
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        equity = 10000.0

        # Lệnh 1 thua
        cb.record_trade_result(pnl=-50.0, timestamp=t0, equity=equity)
        assert cb.consecutive_losses == 1
        assert cb.risk_multiplier == 1.0

        # Lệnh 2 thua
        cb.record_trade_result(pnl=-50.0, timestamp=t0 + timedelta(hours=1), equity=equity)
        assert cb.consecutive_losses == 2
        assert cb.risk_multiplier == 1.0

        # Lệnh 3 thua -> Đạt ngưỡng 3
        cb.record_trade_result(pnl=-50.0, timestamp=t0 + timedelta(hours=2), equity=equity)
        assert cb.consecutive_losses == 3
        assert cb.risk_multiplier == 0.5
        assert cb.get_effective_risk_percent(0.02) == 0.01

    def test_risk_recovery_after_exactly_3_consecutive_wins(self):
        """
        Sau khi đã bị giảm risk xuống 0.5:
        - 1 lệnh thắng: risk vẫn 0.5
        - 2 lệnh thắng: risk vẫn 0.5
        - Đúng 3 lệnh thắng liên tiếp: risk phục hồi về 1.0 (ADR 0002).
        """
        cb = CircuitBreakerState(
            consecutive_losses_threshold=3,
            consecutive_wins_to_recover=3,
            risk_reduction_on_streak=0.5,
        )
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        equity = 10000.0

        # Tạo chuỗi thua 3 lệnh để kích hoạt risk 0.5
        for i in range(3):
            cb.record_trade_result(pnl=-30.0, timestamp=t0 + timedelta(hours=i), equity=equity)
        assert cb.risk_multiplier == 0.5

        # Lệnh thắng 1
        cb.record_trade_result(pnl=50.0, timestamp=t0 + timedelta(hours=4), equity=equity)
        assert cb.consecutive_wins == 1
        assert cb.risk_multiplier == 0.5

        # Lệnh thắng 2
        cb.record_trade_result(pnl=50.0, timestamp=t0 + timedelta(hours=5), equity=equity)
        assert cb.consecutive_wins == 2
        assert cb.risk_multiplier == 0.5

        # Lệnh thắng 3 -> Đạt đủ 3 lệnh thắng liên tiếp
        cb.record_trade_result(pnl=50.0, timestamp=t0 + timedelta(hours=6), equity=equity)
        assert cb.risk_multiplier == 1.0
        assert cb.consecutive_wins == 0  # Reset sau khi đã phục hồi

    def test_intervening_loss_resets_recovery_win_streak(self):
        """
        Nếu đang trong quá trình phục hồi (risk=0.5) mà có 1 lệnh thua xen giữa,
        chuỗi thắng phải reset về 0 ngay lập tức, không được cộng dồn xuyên qua lệnh thua.
        """
        cb = CircuitBreakerState(
            consecutive_losses_threshold=3,
            consecutive_wins_to_recover=3,
            risk_reduction_on_streak=0.5,
        )
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        equity = 10000.0

        # 3 lệnh thua kích hoạt risk 0.5
        for i in range(3):
            cb.record_trade_result(pnl=-30.0, timestamp=t0 + timedelta(hours=i), equity=equity)
        assert cb.risk_multiplier == 0.5

        # Thắng 2 lệnh liên tiếp
        cb.record_trade_result(pnl=50.0, timestamp=t0 + timedelta(hours=4), equity=equity)
        cb.record_trade_result(pnl=50.0, timestamp=t0 + timedelta(hours=5), equity=equity)
        assert cb.consecutive_wins == 2
        assert cb.risk_multiplier == 0.5

        # Lệnh thứ 3 là THUA (-20$) -> Reset chuỗi thắng về 0!
        cb.record_trade_result(pnl=-20.0, timestamp=t0 + timedelta(hours=6), equity=equity)
        assert cb.consecutive_wins == 0
        assert cb.consecutive_losses == 1
        assert cb.risk_multiplier == 0.5

        # Cần thắng tiếp 3 lệnh nữa mới phục hồi
        cb.record_trade_result(pnl=40.0, timestamp=t0 + timedelta(hours=7), equity=equity)
        cb.record_trade_result(pnl=40.0, timestamp=t0 + timedelta(hours=8), equity=equity)
        assert cb.risk_multiplier == 0.5  # Vẫn chỉ mới 2 lệnh thắng
        cb.record_trade_result(pnl=40.0, timestamp=t0 + timedelta(hours=9), equity=equity)
        assert cb.risk_multiplier == 1.0  # Đã đủ 3 lệnh thắng liên tiếp sau cú ngắt

    def test_is_trading_allowed_lockout_duration(self):
        """Kiểm tra is_trading_allowed trả về False trong suốt 24h và True sau khi hết hạn."""
        cb = CircuitBreakerState(daily_loss_limit_pct=0.05)
        t0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        equity = 10000.0

        # Lệnh thua lớn kích hoạt khóa
        cb.record_trade_result(pnl=-600.0, timestamp=t0, equity=equity)
        assert cb.is_locked

        # Kiểm tra tại các mốc thời gian trong khoảng 24h
        assert not cb.is_trading_allowed(t0 + timedelta(hours=1))
        assert not cb.is_trading_allowed(t0 + timedelta(hours=12))
        assert not cb.is_trading_allowed(t0 + timedelta(hours=23, minutes=59))

        # Đúng sau 24h (hoặc 24h + 1 giây) -> Tự động mở khóa
        unlock_time = t0 + timedelta(hours=24, seconds=1)
        assert cb.is_trading_allowed(unlock_time)
        assert not cb.is_locked
        assert cb.locked_until is None

    def test_invalid_inputs_rejected(self):
        """Kiểm tra từ chối các giá trị phi số, NaN, Inf, âm không hợp lệ."""
        cb = CircuitBreakerState()
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        
        # pnl là NaN / Inf / bool / str
        with pytest.raises(ValueError, match="pnl must be finite"):
            cb.record_trade_result(pnl=float("nan"), timestamp=t0, equity=10000.0)
        with pytest.raises(ValueError, match="pnl must be finite"):
            cb.record_trade_result(pnl=float("inf"), timestamp=t0, equity=10000.0)
        with pytest.raises(TypeError, match="pnl must be numeric"):
            cb.record_trade_result(pnl=True, timestamp=t0, equity=10000.0)
        with pytest.raises(TypeError, match="pnl must be numeric"):
            cb.record_trade_result(pnl="50.0", timestamp=t0, equity=10000.0)

        # equity là âm, NaN, bool
        with pytest.raises(ValueError, match="equity must be non-negative"):
            cb.record_trade_result(pnl=50.0, timestamp=t0, equity=-100.0)
        with pytest.raises(ValueError, match="equity must be non-negative"):
            cb.record_trade_result(pnl=50.0, timestamp=t0, equity=float("nan"))
        with pytest.raises(TypeError, match="equity must be numeric"):
            cb.record_trade_result(pnl=50.0, timestamp=t0, equity=False)

        # get_effective_risk_percent với input không hợp lệ
        with pytest.raises(ValueError, match="base_risk_percent must be positive"):
            cb.get_effective_risk_percent(-0.01)
        with pytest.raises(ValueError, match="base_risk_percent must be positive"):
            cb.get_effective_risk_percent(float("nan"))
        with pytest.raises(TypeError, match="base_risk_percent must be numeric"):
            cb.get_effective_risk_percent(True)

    def test_time_reversal_rejected(self):
        """Từ chối ghi nhận sự kiện lùi thời gian (time reversal)."""
        cb = CircuitBreakerState()
        t1 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

        cb.record_trade_result(pnl=50.0, timestamp=t1, equity=10000.0)
        with pytest.raises(ValueError, match="time reversal"):
            cb.record_trade_result(pnl=50.0, timestamp=t0, equity=10050.0)

    def test_breakeven_trade_resets_streaks(self):
        """
        Lệnh hòa (pnl == 0) ngắt cả chuỗi thắng và thua về 0 theo ADR 0006,
        nhưng giữ nguyên mức risk_multiplier hiện tại.
        """
        cb = CircuitBreakerState(
            consecutive_losses_threshold=3,
            consecutive_wins_to_recover=3,
            risk_reduction_on_streak=0.5,
        )
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        equity = 10000.0

        # Thua 2 lệnh
        cb.record_trade_result(pnl=-50.0, timestamp=t0, equity=equity)
        cb.record_trade_result(pnl=-50.0, timestamp=t0 + timedelta(hours=1), equity=equity)
        assert cb.consecutive_losses == 2

        # Lệnh hòa (pnl = 0) -> Reset consecutive_losses về 0
        cb.record_trade_result(pnl=0.0, timestamp=t0 + timedelta(hours=2), equity=equity)
        assert cb.consecutive_losses == 0
        assert cb.consecutive_wins == 0
        assert cb.risk_multiplier == 1.0

        # Thua tiếp 3 lệnh -> kích hoạt risk 0.5
        for i in range(3):
            cb.record_trade_result(pnl=-50.0, timestamp=t0 + timedelta(hours=3 + i), equity=equity)
        assert cb.risk_multiplier == 0.5

        # Thắng 2 lệnh
        cb.record_trade_result(pnl=50.0, timestamp=t0 + timedelta(hours=7), equity=equity)
        cb.record_trade_result(pnl=50.0, timestamp=t0 + timedelta(hours=8), equity=equity)
        assert cb.consecutive_wins == 2

        # Lệnh hòa xen giữa -> Reset consecutive_wins về 0, risk_multiplier vẫn là 0.5
        cb.record_trade_result(pnl=0.0, timestamp=t0 + timedelta(hours=9), equity=equity)
        assert cb.consecutive_wins == 0
        assert cb.risk_multiplier == 0.5

    def test_sliding_window_pruning_in_is_trading_allowed(self):
        """is_trading_allowed tự động loại bỏ các lệnh cũ hơn 24h ngay cả khi không có lệnh mới."""
        cb = CircuitBreakerState()
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        equity = 10000.0

        cb.record_trade_result(pnl=-200.0, timestamp=t0, equity=equity)
        assert cb.rolling_24h_pnl == -200.0
        assert len(cb.trade_history_24h) == 1

        # Tại t0 + 25h: is_trading_allowed prune các giao dịch cũ
        allowed = cb.is_trading_allowed(t0 + timedelta(hours=25))
        assert allowed is True
        assert cb.rolling_24h_pnl == 0.0
        assert len(cb.trade_history_24h) == 0

    def test_non_extended_lockout(self):
        """Trong thời gian bị khóa, ghi nhận thêm lệnh không được gia hạn mốc locked_until."""
        cb = CircuitBreakerState(daily_loss_limit_pct=0.05)
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        equity = 10000.0

        # Lỗ 600$ (6%) -> Khóa 24h đến t0 + 24h
        cb.record_trade_result(pnl=-600.0, timestamp=t0, equity=equity)
        expected_lock_until = t0 + timedelta(hours=24)
        assert cb.locked_until == expected_lock_until

        # Tại t0 + 2h ghi nhận thêm PnL (ví dụ lệnh đóng trễ) -> locked_until không bị kéo dài đến t0 + 26h
        cb.record_trade_result(pnl=-100.0, timestamp=t0 + timedelta(hours=2), equity=equity)
        assert cb.locked_until == expected_lock_until

    # -------------------------------------------------------------
    # F4 Regression Tests: Unified Clock & Breaker Resilience
    # -------------------------------------------------------------
    def test_f4_scenario_a_query_advances_time_and_blocks_past_event(self):
        """
        F4 Scenario A: Đồng hồ đơn nhất monotonic.
        Sau khi is_trading_allowed(T2) được gọi, đồng hồ nội bộ tiến tới T2.
        Nếu sau đó record_trade_result(T1) với T1 < T2 được gọi, hệ thống phải
        từ chối do lùi thời gian (time reversal).
        """
        cb = CircuitBreakerState()
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(hours=1)
        t2 = t0 + timedelta(hours=2)

        cb.record_trade_result(pnl=50.0, timestamp=t0, equity=10000.0)
        assert cb.current_timestamp == t0

        # Query kiểm tra tại T2 -> Đồng hồ nội bộ nhảy tới T2
        assert cb.is_trading_allowed(t2) is True
        assert cb.current_timestamp == t2

        # Ghi nhận kết quả giao dịch tại T1 (< T2) -> PHẢI BỊ TỪ CHỐI
        with pytest.raises(ValueError, match="time reversal"):
            cb.record_trade_result(pnl=50.0, timestamp=t1, equity=10050.0)

    def test_f4_scenario_b_lock_expiry_and_new_breach_without_intervening_query(self):
        """
        F4 Scenario B: Khóa hết hạn và kích hoạt khóa mới mà không cần có lệnh query xen giữa.
        Tại T0: vi phạm lỗ 24h -> khóa 24h đến T0 + 24h.
        Không có lệnh is_trading_allowed nào được gọi trong 24h.
        Tại T0 + 25h: có kết quả trade mới lỗ 600$ (vốn 10,000$).
        record_trade_result tự động advance_time tới T0 + 25h, mở khóa cũ đã hết hạn,
        prune khoản lỗ 25h trước, và kích hoạt KHÓA MỚI 24h đến T0 + 49h!
        """
        cb = CircuitBreakerState(daily_loss_limit_pct=0.05)
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        equity = 10000.0

        # Kích hoạt khóa 24h tại T0
        cb.record_trade_result(pnl=-600.0, timestamp=t0, equity=equity)
        assert cb.is_locked is True
        assert cb.locked_until == t0 + timedelta(hours=24)

        # KHÔNG GỌI is_trading_allowed, mà ghi nhận trực tiếp kết quả tại T0 + 25h
        t_new = t0 + timedelta(hours=25)
        cb.record_trade_result(pnl=-600.0, timestamp=t_new, equity=equity)

        # Phải kích hoạt khóa MỚI từ t_new
        assert cb.is_locked is True
        assert cb.locked_until == t_new + timedelta(hours=24)
        assert cb.rolling_24h_pnl == -600.0  # Khoản lỗ cũ tại t0 đã bị prune

    def test_f4_query_going_backwards_rejected(self):
        """F4: Gọi is_trading_allowed với thời gian lùi lại quá khứ phải bị từ chối."""
        cb = CircuitBreakerState()
        t2 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

        assert cb.is_trading_allowed(t2) is True
        with pytest.raises(ValueError, match="time reversal"):
            cb.is_trading_allowed(t1)

    def test_f4_same_timestamp_multiple_events(self):
        """F4: Nhiều giao dịch đóng tại cùng một timestamp (t0 == t0) được phép ghi nhận bình thường."""
        cb = CircuitBreakerState()
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        cb.record_trade_result(pnl=-100.0, timestamp=t0, equity=10000.0)
        cb.record_trade_result(pnl=-150.0, timestamp=t0, equity=9900.0)

        assert cb.rolling_24h_pnl == -250.0
        assert len(cb.trade_history_24h) == 2
        assert cb.current_timestamp == t0

    def test_f4_unsupported_recovery_mode_rejected(self):
        """F4: Cấu hình recovery_mode không nằm trong danh mục hỗ trợ phải raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported recovery_mode"):
            CircuitBreakerState(recovery_mode="unsupported_custom_mode")

    def test_f4_zero_equity_halts_trading(self):
        """F4: Khi equity giảm về <= 0 (cháy tài khoản), hệ thống chuyển sang halted vĩnh viễn."""
        cb = CircuitBreakerState()
        t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        cb.record_trade_result(pnl=-10000.0, timestamp=t0, equity=0.0)

        assert cb.is_halted is True
        assert cb.is_locked is True
        # Thậm chí 10 năm sau vẫn không được phép giao dịch
        t_future = t0 + timedelta(days=3650)
        assert cb.is_trading_allowed(t_future) is False


