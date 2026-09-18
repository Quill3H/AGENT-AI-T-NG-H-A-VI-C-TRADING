"""
tests/test_execution_models.py - Test cho các Model Lệnh và Vị thế
==================================================================
Kiểm tra tính bất biến, validation kiểu dữ liệu, các Enum và phương thức tính toán.
"""
from datetime import datetime, timezone
import pytest

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    FundingEvent,
    OrderDirection,
    OrderExecutionRecord,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionStatus,
    TradeRecord,
)


def test_order_request_valid():
    """Tạo OrderRequest hợp lệ."""
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    req = OrderRequest(
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        signal_price=50000.0,
        stop_loss_price=49000.0,
        take_profit_price=53000.0,
        signal_time=t0,
        leverage=3.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
    )
    assert req.symbol == "BTCUSDT"
    assert req.direction == OrderDirection.LONG
    assert req.signal_price == 50000.0
    assert req.stop_loss_price == 49000.0
    assert req.take_profit_price == 53000.0
    assert req.signal_time.tzinfo == timezone.utc


def test_order_request_direction_sl_validation():
    """Stop-loss sai chiều so với direction phải bị từ chối ngay tại model."""
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

    # LONG: SL >= signal price -> lỗi
    with pytest.raises(ValueError, match="stop_loss_price.*must be < signal_price"):
        OrderRequest(
            symbol="BTCUSDT",
            direction=OrderDirection.LONG,
            signal_price=50000.0,
            stop_loss_price=51000.0,
            signal_time=t0,
        )

    # SHORT: SL <= signal price -> lỗi
    with pytest.raises(ValueError, match="stop_loss_price.*must be > signal_price"):
        OrderRequest(
            symbol="BTCUSDT",
            direction=OrderDirection.SHORT,
            signal_price=50000.0,
            stop_loss_price=49000.0,
            signal_time=t0,
        )


def test_order_request_direction_tp_validation():
    """Take-profit sai chiều so với direction phải bị từ chối."""
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

    # LONG: TP <= signal price -> lỗi
    with pytest.raises(ValueError, match="take_profit_price.*must be > signal_price"):
        OrderRequest(
            symbol="BTCUSDT",
            direction=OrderDirection.LONG,
            signal_price=50000.0,
            stop_loss_price=49000.0,
            take_profit_price=49500.0,
            signal_time=t0,
        )

    # SHORT: TP >= signal price -> lỗi
    with pytest.raises(ValueError, match="take_profit_price.*must be < signal_price"):
        OrderRequest(
            symbol="BTCUSDT",
            direction=OrderDirection.SHORT,
            signal_price=50000.0,
            stop_loss_price=51000.0,
            take_profit_price=52000.0,
            signal_time=t0,
        )


def test_position_unrealized_pnl_calculation():
    """Kiểm tra công thức tính Unrealized PnL cho cả LONG và SHORT."""
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

    # LONG Position
    pos_long = Position(
        position_id="POS_BTC_001",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=2.0,
        entry_price=50000.0,
        initial_margin=20000.0,
        isolated_collateral=20000.0,
        leverage=5.0,
        stop_loss_price=48000.0,
        liquidation_price=40500.0,
        opened_at=t0,
    )

    assert pos_long.calculate_unrealized_pnl(52000.0) == 4000.0   # Lời 2 * 2000
    assert pos_long.calculate_unrealized_pnl(48000.0) == -4000.0  # Lỗ 2 * -2000

    # SHORT Position
    pos_short = Position(
        position_id="POS_BTC_002",
        symbol="BTCUSDT",
        direction=OrderDirection.SHORT,
        quantity=1.5,
        entry_price=50000.0,
        initial_margin=15000.0,
        isolated_collateral=15000.0,
        leverage=5.0,
        stop_loss_price=52000.0,
        liquidation_price=59500.0,
        opened_at=t0,
    )

    assert pos_short.calculate_unrealized_pnl(48000.0) == 3000.0  # Lời 1.5 * (50000 - 48000)
    assert pos_short.calculate_unrealized_pnl(51000.0) == -1500.0 # Lỗ 1.5 * (50000 - 51000)
