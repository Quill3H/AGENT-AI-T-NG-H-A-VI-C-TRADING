"""
tests/test_report_metrics.py - Test suite for Performance Metrics Calculation
=============================================================================
Kiểm tra các công thức tính toán chỉ số hiệu năng:
1. Expectancy (USD & R-multiple)
2. Initial Risk và Realized R-multiple
3. Profit Factor (bao gồm case loss=0 -> None, all losses, all wins)
4. Peak-to-valley Maximum Drawdown (USD & %)
5. Daily Sharpe Ratio (resampling 1D UTC, sqrt(365), edge cases)
6. Tổng hợp toàn diện calculate_backtest_metrics
"""
from datetime import datetime, timedelta, timezone
import math
import pytest

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    OrderDirection,
    OrderStatus,
    TradeRecord,
)
from src.report.metrics import (
    calculate_backtest_metrics,
    calculate_daily_sharpe,
    calculate_max_drawdown,
    calculate_trade_metrics,
    classify_benchmark_win_rate,
)


def _create_mock_trade(net_pnl, initial_risk=None, realized_r=None, gross_pnl=None, entry_fee=0.0, exit_fee=0.0):
    t_now = datetime(2023, 1, 1, tzinfo=timezone.utc)
    return {
        "trade_id": "T1",
        "symbol": "BTCUSDT",
        "direction": OrderDirection.LONG,
        "quantity": 1.0,
        "entry_price": 20000.0,
        "exit_price": 21000.0,
        "entry_time": t_now,
        "exit_time": t_now + timedelta(hours=4),
        "leverage": 1.0,
        "initial_margin": 20000.0,
        "gross_price_pnl": gross_pnl if gross_pnl is not None else net_pnl,
        "entry_fee": entry_fee,
        "exit_fee": exit_fee,
        "funding_cashflow": 0.0,
        "net_pnl": net_pnl,
        "return_pct": 5.0,
        "exit_reason": ExitReason.TAKE_PROFIT,
        "intrabar_estimated": False,
        "initial_risk_usd": initial_risk,
        "realized_r_multiple": realized_r,
    }


def test_expectancy_usd_and_r():
    """Kiểm tra công thức Expectancy USD và Expectancy R."""
    # 4 trades: +100 (R=+2), -50 (R=-1), +200 (R=+4), -100 (R=-2)
    trades = [
        _create_mock_trade(net_pnl=100.0, initial_risk=50.0, realized_r=2.0),
        _create_mock_trade(net_pnl=-50.0, initial_risk=50.0, realized_r=-1.0),
        _create_mock_trade(net_pnl=200.0, initial_risk=50.0, realized_r=4.0),
        _create_mock_trade(net_pnl=-100.0, initial_risk=50.0, realized_r=-2.0),
    ]
    res = calculate_trade_metrics(trades)

    # Expectancy USD = (100 - 50 + 200 - 100) / 4 = 150 / 4 = 37.5
    assert math.isclose(res["expectancy_usd"], 37.5, abs_tol=1e-4)

    # Expectancy R = (2.0 - 1.0 + 4.0 - 2.0) / 4 = 3.0 / 4 = 0.75 R
    assert math.isclose(res["expectancy_r"], 0.75, abs_tol=1e-4)

    # Win rate = 2/4 = 50.0%
    assert res["win_rate"] == 50.0


def test_profit_factor_edge_cases():
    """Kiểm tra Profit Factor với các trường hợp biên: loss=0, all losses, no trades."""
    # Case 1: All wins, no losses (total_loss == 0) -> Profit Factor phải bằng None (JSON null)
    wins_only = [
        _create_mock_trade(net_pnl=100.0),
        _create_mock_trade(net_pnl=200.0),
    ]
    res_wins = calculate_trade_metrics(wins_only)
    assert res_wins["profit_factor"] is None, "Profit Factor must be None when total losses are 0"

    # Case 2: All losses -> Profit Factor = 0.0
    losses_only = [
        _create_mock_trade(net_pnl=-100.0),
        _create_mock_trade(net_pnl=-50.0),
    ]
    res_loss = calculate_trade_metrics(losses_only)
    assert res_loss["profit_factor"] == 0.0

    # Case 3: Mixed: wins = 300, losses = -100 -> PF = 3.0
    mixed = [
        _create_mock_trade(net_pnl=300.0),
        _create_mock_trade(net_pnl=-100.0),
    ]
    res_mixed = calculate_trade_metrics(mixed)
    assert math.isclose(res_mixed["profit_factor"], 3.0, abs_tol=1e-4)

    # Case 4: No trades -> PF = None
    res_empty = calculate_trade_metrics([])
    assert res_empty["profit_factor"] is None
    assert res_empty["expectancy_usd"] == 0.0
    assert res_empty["expectancy_r"] is None


def test_max_drawdown_peak_to_valley():
    """Kiểm tra tính toán Max Drawdown chuẩn xác từ chuỗi equity biến thiên."""
    t0 = datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
    equities = [10000.0, 12000.0, 9000.0, 11000.0, 8000.0, 15000.0]
    snapshots = []
    for i, eq in enumerate(equities):
        snapshots.append({
            "timestamp": t0 + timedelta(hours=i),
            "equity": eq,
        })

    # Đỉnh cao nhất trước sập sâu nhất là 12000, đáy sâu nhất là 8000
    # DD_usd = 12000 - 8000 = 4000 USD
    # DD_pct = 4000 / 12000 * 100 = 33.3333%
    max_dd_usd, max_dd_pct = calculate_max_drawdown(snapshots, initial_capital=10000.0)
    assert math.isclose(max_dd_usd, 4000.0, abs_tol=1e-4)
    assert math.isclose(max_dd_pct, 33.3333, abs_tol=1e-3)


def test_daily_sharpe_ratio_calculation():
    """Kiểm tra tính toán Sharpe Ratio chuẩn hoá resampled 1D UTC."""
    t0 = datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
    
    # 1. Ít hơn 2 ngày quan sát -> None
    snap_1day = [
        {"timestamp": t0, "equity": 10000.0},
        {"timestamp": t0 + timedelta(hours=12), "equity": 10100.0},
    ]
    assert calculate_daily_sharpe(snap_1day) is None

    # 2. Chuỗi phẳng (equity không đổi -> std = 0) -> hữu hạn, deterministic
    snap_flat = [
        {"timestamp": t0, "equity": 10000.0},
        {"timestamp": t0 + timedelta(days=1), "equity": 10000.0},
        {"timestamp": t0 + timedelta(days=2), "equity": 10000.0},
        {"timestamp": t0 + timedelta(days=3), "equity": 10000.0},
    ]
    assert calculate_daily_sharpe(snap_flat) == 0.0

    # 3. Chuỗi biến động đa ngày với giá trị xác định
    # 5 ngày với equity kết ngày: 10000, 10100, 10200, 10150, 10300
    snap_multi = [
        {"timestamp": t0, "equity": 10000.0},
        {"timestamp": t0 + timedelta(days=1), "equity": 10100.0},
        {"timestamp": t0 + timedelta(days=2), "equity": 10200.0},
        {"timestamp": t0 + timedelta(days=3), "equity": 10150.0},
        {"timestamp": t0 + timedelta(days=4), "equity": 10300.0},
    ]
    sharpe = calculate_daily_sharpe(snap_multi, risk_free_rate=0.0)
    assert sharpe is not None
    assert isinstance(sharpe, float)
    assert sharpe > 0.0  # Tăng trưởng dương phải có Sharpe dương


def test_calculate_backtest_metrics_reconciliation():
    """Kiểm tra tích hợp hàm calculate_backtest_metrics với mock PaperBroker."""
    class MockBroker:
        def __init__(self):
            self.initial_balance = 10000.0
            self.equity = 10250.0
            self.wallet_balance = 10250.0
            self.available_margin = 10250.0
            self.trade_history = [
                _create_mock_trade(net_pnl=300.0, initial_risk=100.0, realized_r=3.0),
                _create_mock_trade(net_pnl=-50.0, initial_risk=50.0, realized_r=-1.0),
            ]
            self.order_history = []
            t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
            self.account_snapshots = [
                AccountSnapshot(
                    timestamp=t0,
                    wallet_balance=10000.0,
                    reserved_collateral=0.0,
                    available_margin=10000.0,
                    unrealized_pnl=0.0,
                    equity=10000.0,
                    open_positions_count=0,
                ),
                AccountSnapshot(
                    timestamp=t0 + timedelta(days=2),
                    wallet_balance=10250.0,
                    reserved_collateral=0.0,
                    available_margin=10250.0,
                    unrealized_pnl=0.0,
                    equity=10250.0,
                    open_positions_count=0,
                ),
            ]

        def verify_accounting_invariants(self):
            return True

    broker = MockBroker()
    config = {"symbol": "BTCUSDT", "strategy": "trend_following"}
    metrics = calculate_backtest_metrics(
        broker=broker,
        config=config,
        start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2023, 1, 3, tzinfo=timezone.utc),
        bars_15m_count=192,
        bars_4h_count=12,
    )

    assert metrics["total_trades"] == 2
    assert metrics["win_rate"] == 50.0
    assert metrics["loss_rate"] == 50.0
    assert metrics["initial_capital"] == 10000.0
    assert metrics["final_equity"] == 10250.0
    assert metrics["total_return_pct"] == 2.5
    assert metrics["profit_factor"] == 6.0  # 300 / 50 = 6.0
    assert metrics["expectancy_usd"] == 125.0  # (300 - 50) / 2 = 125.0
    assert metrics["expectancy_r"] == 1.0  # (3.0 - 1.0) / 2 = 1.0 R
    assert metrics["average_realized_rrr"] == 1.0
    assert metrics["accounting_invariants_verified"] is True


def test_nan_inf_bool_fail_closed():
    """Kiểm tra fail-closed nghiêm ngặt khi dữ liệu đầu vào chứa NaN, Inf hoặc bool."""
    t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)

    # 1. calculate_daily_sharpe
    with pytest.raises(TypeError, match="cannot be boolean"):
        calculate_daily_sharpe([{"timestamp": t0, "equity": True}])

    with pytest.raises(ValueError, match="must be finite"):
        calculate_daily_sharpe([{"timestamp": t0, "equity": float("nan")}])

    with pytest.raises(ValueError, match="must be finite"):
        calculate_daily_sharpe([{"timestamp": t0, "equity": float("inf")}])

    # 2. calculate_max_drawdown
    with pytest.raises(TypeError, match="initial_capital cannot be boolean"):
        calculate_max_drawdown([], initial_capital=True)

    with pytest.raises(ValueError, match="initial_capital must be finite"):
        calculate_max_drawdown([], initial_capital=float("nan"))

    with pytest.raises(TypeError, match="cannot be boolean"):
        calculate_max_drawdown([{"timestamp": t0, "equity": True}])

    with pytest.raises(ValueError, match="must be finite"):
        calculate_max_drawdown([{"timestamp": t0, "equity": float("-inf")}])

    # 3. calculate_trade_metrics
    with pytest.raises(TypeError, match="cannot be boolean"):
        calculate_trade_metrics([_create_mock_trade(net_pnl=True)])

    with pytest.raises(ValueError, match="must be finite"):
        calculate_trade_metrics([_create_mock_trade(net_pnl=float("nan"))])

    with pytest.raises(TypeError, match="realized_r_multiple cannot be boolean"):
        calculate_trade_metrics([_create_mock_trade(net_pnl=100.0, realized_r=True)])

    with pytest.raises(ValueError, match="realized_r_multiple must be finite"):
        calculate_trade_metrics([_create_mock_trade(net_pnl=100.0, realized_r=float("inf"))])


def test_circuit_breaker_metrics_separation():
    """Kiểm tra phân tách rõ ràng giữa Circuit Breaker rejections và Isolated Margin rejections."""
    class MockCB:
        is_halted = False
        is_locked = True
        risk_multiplier = 0.5
        lock_count = 2

    class MockBrokerWithCB:
        def __init__(self):
            self.initial_balance = 10000.0
            self.equity = 10000.0
            self.wallet_balance = 10000.0
            self.available_margin = 10000.0
            self.circuit_breaker = MockCB()
            self.trade_history = []
            self.order_history = [
                {"status": OrderStatus.REJECTED, "rejection_reasons": ["MARGIN_GATE: Insufficient margin"]},
                {"status": OrderStatus.REJECTED, "rejection_reasons": ["MARGIN_GATE: Insufficient margin"]},
                {"status": OrderStatus.REJECTED, "rejection_reasons": ["CIRCUIT_BREAKER: Risk locked"]},
            ]
            self.account_snapshots = []

        def verify_accounting_invariants(self):
            return True

    broker = MockBrokerWithCB()
    config = {
        "strategy": {"name": "trend_following"},
        "data": {"futures_symbol": "BTCUSDT", "timeframe_signal": "4h", "timeframe_execution": "15m"},
    }
    metrics = calculate_backtest_metrics(
        broker=broker,
        config=config,
        start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2023, 1, 3, tzinfo=timezone.utc),
        bars_15m_count=192,
        bars_4h_count=12,
    )

    assert metrics["circuit_breaker_status"] == "LOCKED"
    assert metrics["circuit_breaker_risk_multiplier"] == 0.5
    assert metrics["circuit_breaker_lock_count"] == 2
    assert metrics["circuit_breaker_rejections_count"] == 1
    assert metrics["margin_rejections_count"] == 2
    assert metrics["orders_rejected_count"] == 3


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (34.99, "BELOW_EXPECTED_RANGE"),
        (35.0, "WITHIN_EXPECTED_RANGE"),
        (45.0, "WITHIN_EXPECTED_RANGE"),
        (45.01, "ABOVE_EXPECTED_RANGE"),
    ],
)
def test_benchmark_comparison_below_within_above(actual, expected):
    result = classify_benchmark_win_rate(actual, total_trades=20)
    assert result["status"] == expected
    assert result["comparison_only"] is True
    assert result["future_performance_guarantee"] is False


def test_benchmark_comparison_no_trades_is_not_misleading():
    assert classify_benchmark_win_rate(0.0, total_trades=0)["status"] == "INSUFFICIENT_DATA"


def test_report_accounting_mismatch_fails_closed():
    class MismatchedBroker:
        initial_balance = 10000.0
        wallet_balance = 10001.0
        equity = 10001.0
        available_margin = 10001.0
        trade_history = []
        order_history = []
        account_snapshots = []
        funding_history = []
        positions = {}

        def verify_accounting_invariants(self):
            return True

    with pytest.raises(AssertionError, match="Report accounting mismatch"):
        calculate_backtest_metrics(
            broker=MismatchedBroker(),
            config={"symbol": "BTCUSDT", "strategy": "trend_following"},
            start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2023, 1, 2, tzinfo=timezone.utc),
            bars_15m_count=0,
            bars_4h_count=0,
        )

