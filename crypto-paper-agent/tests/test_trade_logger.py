"""
tests/test_trade_logger.py - Test suite for SQLite Event Store and JSON Exporter
================================================================================
Kiểm tra nghiêm ngặt:
1. Cấu trúc bảng SQLite (runs, orders, trades, funding_events, account_snapshots, run_metrics)
2. Bật Foreign Keys (PRAGMA foreign_keys = ON) và từ chối cascade trái phép
3. Tính toàn vẹn Transaction (Rollback khi có lỗi)
4. Tính luỹ thừa (Idempotency) khi ghi trùng run_id cùng payload
5. Từ chối xung đột (Conflict Rejection / Fail-closed) khi trùng run_id khác payload
6. Xuất JSON trade chuẩn Section 4.6 (không chứa NaN, timestamp epoch UTC, unmeasured null)
"""
from datetime import datetime, timezone
import json
import sqlite3
import pytest

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    FundingEvent,
    OrderDirection,
    OrderExecutionRecord,
    OrderStatus,
    OrderType,
    TradeRecord,
)
from src.logging.trade_logger import TradeLogger


@pytest.fixture
def temp_logger(tmp_path):
    db_file = tmp_path / "test_trades.sqlite"
    return TradeLogger(db_file)


def _make_dummy_run_data(run_id="run_test_001"):
    now = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    config = {
        "strategy": "trend_following",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "initial_capital": 10000.0,
    }
    metrics = {
        "initial_capital": 10000.0,
        "final_equity": 10500.0,
        "total_trades": 1,
        "win_rate": 100.0,
        "profit_factor": None,
        "max_drawdown_pct": 2.5,
        "sharpe_ratio": 1.85,
    }
    order = OrderExecutionRecord(
        order_id="ORD_001",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        status=OrderStatus.FILLED,
        requested_at=now,
        processed_at=now,
        reference_price=20000.0,
        actual_fill_price=20010.0,
        slippage_usd=5.0,
        filled_quantity=0.5,
        notional_usd=10005.0,
        fee_usd=4.0,
        metadata={"signal_tier": "A"},
    )
    trade = TradeRecord(
        trade_id="TRD_001",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=0.5,
        entry_price=20010.0,
        exit_price=21010.0,
        entry_time=now,
        exit_time=datetime(2023, 1, 2, 12, 0, tzinfo=timezone.utc),
        leverage=1.0,
        initial_margin=10005.0,
        gross_price_pnl=500.0,
        entry_fee=4.0,
        exit_fee=4.2,
        funding_cashflow=2.0,
        net_pnl=493.8,
        return_pct=4.94,
        exit_reason=ExitReason.TAKE_PROFIT,
        intrabar_estimated=False,
        initial_stop_loss_price=19000.0,
        initial_risk_usd=505.0,
        realized_r_multiple=0.978,
        conviction_tier="strong",
    )
    funding = FundingEvent(
        event_id="FE_001",
        timestamp=now,
        symbol="BTCUSDT",
        position_id="POS_001",
        funding_rate=0.0001,
        settlement_mark_price=20050.0,
        position_quantity=0.5,
        cashflow_usd=1.0025,
    )
    snapshot = AccountSnapshot(
        timestamp=now,
        wallet_balance=10000.0,
        reserved_collateral=0.0,
        available_margin=10000.0,
        unrealized_pnl=0.0,
        equity=10000.0,
        open_positions_count=0,
    )
    return run_id, config, metrics, [order], [trade], [funding], [snapshot]


def test_schema_tables_created(temp_logger):
    """Kiểm tra tất cả 6 bảng bắt buộc được tạo tự động."""
    with temp_logger.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}

    expected_tables = {"runs", "orders", "trades", "funding_events", "account_snapshots", "run_metrics"}
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_foreign_keys_enforced(temp_logger):
    """Kiểm tra foreign keys được bật và từ chối chèn mồ côi không có run cha."""
    with temp_logger.get_connection() as conn:
        # Kiểm tra pragma
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys;")
        fk_status = cursor.fetchone()[0]
        assert fk_status == 1, "Foreign keys must be ENABLED"

        # Cố gắng insert vào orders với run_id không tồn tại
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO orders (order_id, run_id, symbol, direction, order_type, status, requested_at)
                VALUES ('ORD_ORPHAN', 'NON_EXISTENT_RUN', 'BTCUSDT', 'LONG', 'MARKET', 'FILLED', '2023-01-01')
                """
            )


def test_log_run_and_retrieve_roundtrip(temp_logger):
    """Kiểm tra ghi run và đọc lại dữ liệu chính xác hoàn toàn."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_roundtrip_01")

    success = temp_logger.log_backtest_run(
        run_id=run_id,
        config=config,
        metrics=metrics,
        orders=orders,
        trades=trades,
        funding_events=fundings,
        account_snapshots=snapshots,
    )
    assert success is True

    # Đọc lại
    run_row = temp_logger.get_run(run_id)
    assert run_row is not None
    assert run_row["run_id"] == run_id
    assert run_row["symbol"] == "BTCUSDT"
    assert run_row["total_trades"] == 1

    trades_ret = temp_logger.get_trades(run_id)
    assert len(trades_ret) == 1
    assert trades_ret[0]["trade_id"] == "TRD_001"
    assert trades_ret[0]["net_pnl"] == 493.8
    assert trades_ret[0]["initial_risk_usd"] == 505.0

    orders_ret = temp_logger.get_orders(run_id)
    assert len(orders_ret) == 1
    assert orders_ret[0]["order_id"] == "ORD_001"

    snaps_ret = temp_logger.get_account_snapshots(run_id)
    assert len(snaps_ret) == 1

    fe_ret = temp_logger.get_funding_events(run_id)
    assert len(fe_ret) == 1

    metrics_ret = temp_logger.get_run_metrics(run_id)
    assert metrics_ret is not None
    assert metrics_ret["final_equity"] == 10500.0


def test_idempotent_logging(temp_logger):
    """Ghi cùng 1 run_id với cùng payload lần 2 không gây lỗi và không nhân đôi dữ liệu."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_idem_01")

    res1 = temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)
    assert res1 is True

    # Ghi lần 2
    res2 = temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)
    assert res2 is True

    # Số bản ghi không bị duplicate
    trades_ret = temp_logger.get_trades(run_id)
    assert len(trades_ret) == 1


def test_conflict_rejection_fail_closed(temp_logger):
    """Ghi cùng 1 run_id nhưng payload khác nhau phải raise ValueError (fail-closed)."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_conflict_01")

    temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)

    # Payload khác (thay đổi final_equity)
    conflicting_metrics = dict(metrics)
    conflicting_metrics["final_equity"] = 99999.0

    with pytest.raises(ValueError, match="already exists with differing payload"):
        temp_logger.log_backtest_run(run_id, config, conflicting_metrics, orders, trades, fundings, snapshots)


def test_transactional_rollback_on_failure(temp_logger):
    """Nếu xảy ra lỗi giữa chừng trong transaction, toàn bộ dữ liệu phải rollback sạch sẽ."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_rollback_01")

    # Tạo trade hỏng (vi phạm constraint non-null hoặc kiểu dữ liệu)
    bad_trades = [
        {
            "trade_id": "TRD_FAIL",
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "quantity": "NOT_A_FLOAT_WILL_FAIL_CONVERSION",  # Sẽ gây ValueError/TypeError khi float()
            "entry_price": 20000.0,
            "exit_price": 21000.0,
            "entry_time": "2023-01-01",
            "exit_time": "2023-01-02",
        }
    ]

    with pytest.raises((ValueError, TypeError)):
        temp_logger.log_backtest_run(run_id, config, metrics, orders, bad_trades, fundings, snapshots)

    # Kiểm tra database không có rác của run_id này
    assert temp_logger.get_run(run_id) is None
    assert len(temp_logger.get_orders(run_id)) == 0


def test_export_trades_json_strict_schema(temp_logger, tmp_path):
    """Kiểm tra export_trades_json tuân thủ nghiêm ngặt Master Spec Section 4.6."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_export_01")
    temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)

    json_file = tmp_path / "trades_exported.json"
    json_str = temp_logger.export_trades_json(run_id, output_path=json_file)

    assert json_file.is_file()
    data = json.loads(json_str)
    assert isinstance(data, list)
    assert len(data) == 1

    t0 = data[0]
    # Schema check
    required_keys = [
        "trade_id", "symbol", "direction", "entry_time", "exit_time",
        "entry_price", "exit_price", "quantity", "leverage", "initial_margin",
        "pnl_gross", "pnl_net", "fee_total", "funding_total", "return_pct",
        "exit_reason", "conviction_tier", "initial_stop_loss", "initial_risk_usd",
        "realized_r_multiple", "market_context", "mae_usd", "mfe_usd"
    ]
    for k in required_keys:
        assert k in t0, f"Missing required key '{k}' in exported trade JSON"

    # Timestamp Unix epoch seconds UTC
    assert isinstance(t0["entry_time"], int)
    assert isinstance(t0["exit_time"], int)
    assert t0["entry_time"] > 1600000000

    # Null cho unmeasured fields
    assert t0["market_context"] is None
    assert t0["mae_usd"] is None
    assert t0["mfe_usd"] is None

    # Không cho phép NaN/Inf
    assert "NaN" not in json_str
    assert "Infinity" not in json_str
