"""
tests/test_trade_logger.py - Test suite for SQLite Event Store and JSON Exporter
================================================================================
Kiểm tra nghiêm ngặt:
1. Cấu trúc bảng SQLite (runs, orders, trades, funding_events, account_snapshots, run_metrics)
2. Bật Foreign Keys (PRAGMA foreign_keys = ON) và từ chối chèn mồ côi
3. Tính toàn vẹn Transaction (Rollback khi có lỗi)
4. Tính luỹ thừa (Idempotency) khi ghi trùng run_id cùng canonical hash
5. Từ chối xung đột (Conflict Rejection / Fail-closed) khi thay đổi config, rejection reason, trade, funding, snapshot
6. Xuất JSON trade đúng nguyên văn schema Master Spec Mục 4.6 (tập key chính xác, cấu trúc nested)
7. Ràng buộc khóa ghép composite primary keys: không va chạm ID giữa các run
8. Hạch toán AccountSnapshot đúng các trường: reserved_collateral, available_margin, open_positions_count, is_halted
9. Bảo toàn event_id và position_id cho funding_events
10. Đọc cấu hình lồng chuẩn production (nested YAML) mà không serialize dictionary thành string
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
from src.logging.trade_logger import TradeLogger, compute_config_hash, parse_config_metadata


@pytest.fixture
def temp_logger(tmp_path):
    db_file = tmp_path / "test_trades.sqlite"
    return TradeLogger(db_file)


def _make_dummy_run_data(run_id="run_test_001"):
    now = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    config = {
        "strategy": {
            "name": "TREND_FOLLOWING",
            "timeframe_signal": "4h",
            "timeframe_execution": "15m",
        },
        "data": {
            "futures_symbol": "BTCUSDT",
            "start_date": "2023-01-01",
            "end_date": "2023-01-02",
        },
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
        rejection_reasons=["INVARIANT_FAIL_INSUFFICIENT_MARGIN: test"],
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
        conviction_tier="NORMAL_2_PERCENT",
        estimated_liquidation_price=15000.0,
        take_profit_levels=[21010.0],
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
        direction=OrderDirection.LONG,
    )
    snapshot = AccountSnapshot(
        timestamp=now,
        wallet_balance=10000.0,
        reserved_collateral=5000.0,
        available_margin=5000.0,
        unrealized_pnl=0.0,
        equity=10000.0,
        open_positions_count=1,
        is_halted=False,
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
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys;")
        fk_status = cursor.fetchone()[0]
        assert fk_status == 1, "Foreign keys must be ENABLED"

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO orders (run_id, order_id, symbol, direction, order_type, status, requested_at)
                VALUES ('NON_EXISTENT_RUN', 'ORD_ORPHAN', 'BTCUSDT', 'LONG', 'MARKET', 'FILLED', '2023-01-01')
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

    # Đọc lại run
    run_row = temp_logger.get_run(run_id)
    assert run_row is not None
    assert run_row["run_id"] == run_id
    assert run_row["symbol"] == "BTCUSDT"
    assert run_row["strategy_name"] == "TREND_FOLLOWING"
    assert run_row["total_trades"] == 1

    trades_ret = temp_logger.get_trades(run_id)
    assert len(trades_ret) == 1
    assert trades_ret[0]["trade_id"] == "TRD_001"
    assert trades_ret[0]["net_pnl"] == 493.8
    assert trades_ret[0]["initial_risk_usd"] == 505.0
    assert trades_ret[0]["estimated_liquidation_price"] == 15000.0

    orders_ret = temp_logger.get_orders(run_id)
    assert len(orders_ret) == 1
    assert orders_ret[0]["order_id"] == "ORD_001"
    assert orders_ret[0]["rejection_reasons"] == ["INVARIANT_FAIL_INSUFFICIENT_MARGIN: test"]

    snaps_ret = temp_logger.get_account_snapshots(run_id)
    assert len(snaps_ret) == 1
    assert snaps_ret[0]["reserved_collateral"] == 5000.0
    assert snaps_ret[0]["available_margin"] == 5000.0
    assert snaps_ret[0]["open_positions_count"] == 1
    assert snaps_ret[0]["is_halted"] == 0

    fe_ret = temp_logger.get_funding_events(run_id)
    assert len(fe_ret) == 1
    assert fe_ret[0]["event_id"] == "FE_001"
    assert fe_ret[0]["position_id"] == "POS_001"

    metrics_ret = temp_logger.get_run_metrics(run_id)
    assert metrics_ret is not None
    assert metrics_ret["final_equity"] == 10500.0


def test_idempotent_logging(temp_logger):
    """Ghi cùng 1 run_id với cùng canonical payload lần 2 không gây lỗi và không nhân đôi dữ liệu."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_idem_01")

    res1 = temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)
    assert res1 is True

    # Ghi lần 2
    res2 = temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)
    assert res2 is True

    trades_ret = temp_logger.get_trades(run_id)
    assert len(trades_ret) == 1


def test_transactional_rollback_on_failure(temp_logger):
    """Nếu xảy ra lỗi giữa chừng trong transaction, toàn bộ dữ liệu phải rollback sạch sẽ."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_rollback_01")

    bad_trades = [
        {
            "trade_id": "TRD_FAIL",
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "quantity": "NOT_A_FLOAT",
            "entry_price": 20000.0,
            "exit_price": 21000.0,
            "entry_time": "2023-01-01",
            "exit_time": "2023-01-02",
        }
    ]

    with pytest.raises((ValueError, TypeError)):
        temp_logger.log_backtest_run(run_id, config, metrics, orders, bad_trades, fundings, snapshots)

    assert temp_logger.get_run(run_id) is None
    assert len(temp_logger.get_orders(run_id)) == 0


def test_export_trades_json_exact_master_spec_schema(temp_logger, tmp_path):
    """
    Kiểm tra xuất trades.json đúng nguyên văn schema Master Spec Section 4.6.
    So sánh chính xác tập key gốc và tập key nested (market_context, outcome).
    """
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_export_spec_01")
    temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)

    json_file = tmp_path / "trades_exported.json"
    json_str = temp_logger.export_trades_json(run_id, output_path=json_file)

    assert json_file.is_file()
    data = json.loads(json_str)
    assert isinstance(data, list)
    assert len(data) == 1

    t0 = data[0]

    # Tập key gốc bắt buộc theo Section 4.6
    expected_root_keys = {
        "trade_id",
        "timestamp",
        "asset",
        "direction",
        "strategy_used",
        "conviction_tier",
        "entry_price",
        "stop_loss_price",
        "take_profit_levels",
        "nominal_position_size_usd",
        "leverage",
        "margin_used_usd",
        "risk_amount_usd",
        "risk_ratio_percent",
        "estimated_liquidation_price",
        "market_context",
        "outcome",
    }
    assert set(t0.keys()) == expected_root_keys, f"Root keys mismatch: {set(t0.keys()) ^ expected_root_keys}"

    # Nested market_context
    expected_market_context_keys = {
        "oi_trend_4h",
        "funding_rate_8h",
        "cvd_divergence",
        "fvg_consequent_encroachment",
    }
    assert isinstance(t0["market_context"], dict)
    assert set(t0["market_context"].keys()) == expected_market_context_keys
    for k, v in t0["market_context"].items():
        assert v is None, f"Expected null for unmeasured field '{k}', got {v}"

    # Nested outcome
    expected_outcome_keys = {
        "exit_price",
        "pnl_usd",
        "fees_paid_usd",
        "net_return_percent",
        "max_adverse_excursion_mae",
        "max_favorable_excursion_mfe",
        "rule_compliance",
    }
    assert isinstance(t0["outcome"], dict)
    assert set(t0["outcome"].keys()) == expected_outcome_keys
    assert t0["outcome"]["max_adverse_excursion_mae"] is None
    assert t0["outcome"]["max_favorable_excursion_mfe"] is None
    assert t0["outcome"]["rule_compliance"] is True

    # Giá trị đo lường
    assert t0["asset"] == "BTCUSDT"
    assert t0["direction"] == "LONG"
    assert t0["strategy_used"] == "TREND_FOLLOWING"
    assert t0["conviction_tier"] == "NORMAL_2_PERCENT"
    assert t0["entry_price"] == 20010.0
    assert t0["stop_loss_price"] == 19000.0
    assert t0["take_profit_levels"] == [21010.0]
    assert t0["nominal_position_size_usd"] == 10005.0
    assert t0["leverage"] == 1.0
    assert t0["margin_used_usd"] == 10005.0
    assert t0["risk_amount_usd"] == 505.0
    # Actual risk is 505 / 10,000 = 5.05%; the tier label must not overwrite it.
    assert t0["risk_ratio_percent"] == 5.05
    assert t0["estimated_liquidation_price"] == 15000.0
    assert t0["outcome"]["exit_price"] == 21010.0
    assert t0["outcome"]["pnl_usd"] == 493.8
    assert t0["outcome"]["fees_paid_usd"] == 8.2

    # Timestamp Unix epoch seconds UTC
    assert isinstance(t0["timestamp"], int)
    assert t0["timestamp"] > 1600000000

    # Tuyệt đối không chứa NaN hoặc Infinity
    assert "NaN" not in json_str
    assert "Infinity" not in json_str


def test_rejection_reason_persistence(temp_logger):
    """Kiểm tra bảng orders lưu và truy xuất chính xác rejection_reasons_json."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_rej_01")
    orders[0].rejection_reasons = ["INSUFFICIENT_MARGIN: required 6000 > available 5000", "RISK_LIMIT_EXCEEDED"]

    temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)

    retrieved = temp_logger.get_orders(run_id)
    assert len(retrieved) == 1
    assert retrieved[0]["order_type"] == "MARKET_ENTRY"
    assert retrieved[0]["rejection_reasons"] == ["INSUFFICIENT_MARGIN: required 6000 > available 5000", "RISK_LIMIT_EXCEEDED"]


def test_account_snapshot_field_mapping(temp_logger):
    """Kiểm tra bảng account_snapshots map đúng các trường thực tế, không dùng trường ảo default về 0."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_snap_map_01")
    snapshots[0] = AccountSnapshot(
        timestamp=datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc),
        wallet_balance=12345.67,
        reserved_collateral=2345.67,
        available_margin=10000.0,
        unrealized_pnl=150.25,
        equity=12495.92,
        open_positions_count=2,
        is_halted=True,
    )

    temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)

    ret = temp_logger.get_account_snapshots(run_id)
    assert len(ret) == 1
    s = ret[0]
    assert s["wallet_balance"] == 12345.67
    assert s["reserved_collateral"] == 2345.67
    assert s["available_margin"] == 10000.0
    assert s["unrealized_pnl"] == 150.25
    assert s["equity"] == 12495.92
    assert s["open_positions_count"] == 2
    assert s["is_halted"] == 1


def test_funding_event_identity(temp_logger):
    """Kiểm tra bảng funding_events bảo toàn chính xác event_id và position_id."""
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_fnd_id_01")
    fundings[0] = FundingEvent(
        event_id="FND_BTCUSDT_20230101_0042",
        timestamp=datetime(2023, 1, 1, 8, 0, tzinfo=timezone.utc),
        symbol="BTCUSDT",
        position_id="POS_BTCUSDT_20230101_0007",
        funding_rate=0.00015,
        settlement_mark_price=20100.0,
        position_quantity=0.8,
        cashflow_usd=-2.412,
        direction=OrderDirection.LONG,
    )

    temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)

    ret = temp_logger.get_funding_events(run_id)
    assert len(ret) == 1
    f = ret[0]
    assert f["event_id"] == "FND_BTCUSDT_20230101_0042"
    assert f["position_id"] == "POS_BTCUSDT_20230101_0007"
    assert f["funding_rate"] == 0.00015
    assert f["payment"] == -2.412
    assert f["direction"] == "LONG"


def test_multi_run_deterministic_id_collision(temp_logger):
    """
    Kiểm tra hai run khác nhau có cùng deterministic order_id/trade_id/event_id
    được ghi vào cùng 1 SQLite DB mà không bị IntegrityError nhờ composite primary keys.
    """
    run_1, cfg_1, m_1, o_1, t_1, f_1, s_1 = _make_dummy_run_data("run_collision_01")
    run_2, cfg_2, m_2, o_2, t_2, f_2, s_2 = _make_dummy_run_data("run_collision_02")

    # Đảm bảo cả hai run có cùng order_id, trade_id, event_id
    assert o_1[0].order_id == o_2[0].order_id == "ORD_001"
    assert t_1[0].trade_id == t_2[0].trade_id == "TRD_001"
    assert f_1[0].event_id == f_2[0].event_id == "FE_001"

    success_1 = temp_logger.log_backtest_run(run_1, cfg_1, m_1, o_1, t_1, f_1, s_1)
    success_2 = temp_logger.log_backtest_run(run_2, cfg_2, m_2, o_2, t_2, f_2, s_2)

    assert success_1 is True
    assert success_2 is True

    assert len(temp_logger.get_orders(run_1)) == 1
    assert len(temp_logger.get_orders(run_2)) == 1
    assert len(temp_logger.get_trades(run_1)) == 1
    assert len(temp_logger.get_trades(run_2)) == 1


def test_full_payload_idempotency_conflict(temp_logger):
    """
    Kiểm tra tính toàn vẹn Idempotency:
    Cùng run_id nhưng thay đổi riêng rẽ từng phần trong khi final_equity và total_trades
    giữ nguyên đều phải bị từ chối (fail-closed với ValueError):
    1. Thay đổi config
    2. Thay đổi rejection reason
    3. Thay đổi một trade
    4. Thay đổi funding event
    5. Thay đổi snapshot
    """
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_conflict_full")
    temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, snapshots)

    # 1. Thay đổi riêng config
    cfg_alt = dict(config)
    cfg_alt["slippage_pct"] = 0.0009
    with pytest.raises(ValueError, match="differing payload"):
        temp_logger.log_backtest_run(run_id, cfg_alt, metrics, orders, trades, fundings, snapshots)

    # 2. Thay đổi riêng rejection reason
    o_alt = [OrderExecutionRecord(**orders[0].__dict__)]
    o_alt[0].rejection_reasons = ["DIFFERENT_REJECTION_REASON"]
    with pytest.raises(ValueError, match="differing payload"):
        temp_logger.log_backtest_run(run_id, config, metrics, o_alt, trades, fundings, snapshots)

    # 3. Thay đổi riêng một trade (thay đổi exit_price, pnl giữ nguyên)
    t_alt = [TradeRecord(**trades[0].__dict__)]
    t_alt[0].exit_price = 21500.0
    with pytest.raises(ValueError, match="differing payload"):
        temp_logger.log_backtest_run(run_id, config, metrics, orders, t_alt, fundings, snapshots)

    # 4. Thay đổi riêng funding event
    f_alt = [FundingEvent(**fundings[0].__dict__)]
    f_alt[0].funding_rate = 0.0005
    with pytest.raises(ValueError, match="differing payload"):
        temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, f_alt, snapshots)

    # 5. Thay đổi riêng snapshot (available_margin thay đổi, equity giữ nguyên)
    s_alt = [AccountSnapshot(**snapshots[0].__dict__)]
    s_alt[0].available_margin = 9999.0
    with pytest.raises(ValueError, match="differing payload"):
        temp_logger.log_backtest_run(run_id, config, metrics, orders, trades, fundings, s_alt)


def test_payload_hash_preserves_sub_eight_decimal_float_changes():
    """Distinct ledger floats must never collapse to one idempotency hash."""
    from src.logging.trade_logger import compute_canonical_payload_hash

    base = dict(
        config={},
        run_metadata={},
        orders=[],
        funding_events=[],
        account_snapshots=[],
        metrics={},
    )
    hash_a = compute_canonical_payload_hash(trades=[{"net_pnl": 1.000000001}], **base)
    hash_b = compute_canonical_payload_hash(trades=[{"net_pnl": 1.000000002}], **base)
    assert hash_a != hash_b


def test_query_order_is_deterministic_for_equal_timestamps(temp_logger):
    run_id, config, metrics, orders, trades, fundings, snapshots = _make_dummy_run_data("run_ordering")
    first = TradeRecord(**trades[0].__dict__)
    second = TradeRecord(**trades[0].__dict__)
    first.trade_id = "TRD_Z"
    second.trade_id = "TRD_A"
    metrics["total_trades"] = 2
    temp_logger.log_backtest_run(run_id, config, metrics, orders, [first, second], fundings, snapshots)
    assert [row["trade_id"] for row in temp_logger.get_trades(run_id)] == ["TRD_A", "TRD_Z"]


def test_nested_production_config_mapping():
    """Kiểm tra parse_config_metadata đọc đúng cấu trúc nested production YAML không bị serialize dict."""
    prod_config = {
        "strategy": {
            "name": "TREND_FOLLOWING",
            "enabled": True,
            "timeframe_signal": "4h",
            "timeframe_execution": "15m",
        },
        "data": {
            "symbol": "BTC/USDT",
            "futures_symbol": "BTCUSDT",
            "start_date": "2021-01-01",
            "end_date": "2023-12-31",
            "raw_data_dir": "data/raw",
        },
    }

    meta = parse_config_metadata(prod_config)
    assert meta["strategy_name"] == "TREND_FOLLOWING"
    assert meta["symbol"] == "BTCUSDT"
    assert meta["timeframe_signal"] == "4h"
    assert meta["timeframe_execution"] == "15m"
    assert meta["start_date"] == "2021-01-01"
    assert meta["end_date"] == "2023-12-31"
    assert "{" not in meta["strategy_name"]


def test_config_hash_does_not_normalize_unrelated_keys(tmp_path):
    base = {"strategy": "TREND_FOLLOWING", "metadata": {"directory_name": "alpha"}}
    changed = {"strategy": "TREND_FOLLOWING", "metadata": {"directory_name": "beta"}}
    assert compute_config_hash(base) != compute_config_hash(changed)


def test_enabled_news_calendar_identity_uses_content_digest(tmp_path):
    first = tmp_path / "one" / "calendar.csv"
    second = tmp_path / "two" / "calendar.csv"
    first.parent.mkdir()
    second.parent.mkdir()
    content = "datetime_utc,event,impact\n2023-01-01T00:00:00Z,CPI,HIGH\n"
    first.write_text(content, encoding="utf-8")
    second.write_text(content, encoding="utf-8")
    config_a = {"news_filter": {"enabled": True, "calendar_file": str(first)}}
    config_b = {"news_filter": {"enabled": True, "calendar_file": str(second)}}
    config_c = {"news_filter": {"enabled": True, "calendar_file": str(second)}}
    second.write_text(content.replace("CPI", "FOMC"), encoding="utf-8")
    assert compute_config_hash(config_a) != compute_config_hash(config_b)
    second.write_text(content, encoding="utf-8")
    assert compute_config_hash(config_a) == compute_config_hash(config_c)

@pytest.mark.parametrize('as_path', [True, False])
def test_calendar_identity_idempotent_and_path_equivalent(tmp_path, as_path):
    from src.logging.trade_logger import canonicalize_config
    f = tmp_path / 'calendar.csv'
    f.write_text('datetime_utc,event\n', encoding='utf-8')
    cfg = {'news_filter': {'enabled': True, 'calendar_file': f if as_path else str(f)}}
    canonical = canonicalize_config(cfg)
    assert canonical['news_filter']['calendar_content_sha256']
    assert canonicalize_config(canonical) == canonical
    assert compute_config_hash(cfg) == compute_config_hash(canonical)
    assert compute_config_hash(cfg) == compute_config_hash({'news_filter': {'enabled': True, 'calendar_file': str(f)}})


def test_snapshot_uses_parsed_bytes_after_source_changes(tmp_path):
    from src.logging.trade_logger import snapshot_run_config
    from src.features.news_calendar import NewsCalendarFilter
    f = tmp_path / 'calendar.csv'
    f.write_text('datetime_utc,event\n2024-01-01T00:00:00Z,CPI\n', encoding='utf-8')
    cfg = {'news_filter': {'enabled': True, 'calendar_file': f}}
    news = NewsCalendarFilter(cfg)
    expected = compute_config_hash(cfg)
    f.write_text('datetime_utc,event\n', encoding='utf-8')
    frozen = snapshot_run_config(cfg, news)
    assert compute_config_hash(frozen) == expected
    assert compute_config_hash(cfg) != expected
    assert len(news.events) == 1
