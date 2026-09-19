"""
tests/test_stage_04_review_07_coverage.py
=========================================
Bộ kiểm thử bổ sung độ bao phủ (coverage) theo tiêu chí nghiệm thu Review 08:
- J1: Funding provenance & readiness contract (missing / None / wrong-type / false / zero / stale / future).
- J2: Transactional funding settlement (toàn bộ state bất biến nếu solver lỗi hoặc bracket hỏng).
- J3: Finalize force_close với nhiều vị thế (LONG/SHORT/multi-symbol) khi Circuit Breaker kích hoạt lồng nhau.
"""

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
import yaml

from src.execution.order_models import OrderDirection, OrderRequest, ExitReason
from src.execution.paper_broker import PaperBroker

ROOT = Path(__file__).resolve().parents[1]
T_BASE = datetime(2026, 9, 1, 7, 58, tzinfo=timezone.utc)


def get_config():
    with open(ROOT / "config" / "default_config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["fees"]["slippage_pct"] = 0.0005
    cfg["fees"]["taker_pct"] = 0.0004
    cfg["leverage_brackets"]["ETHUSDT"] = copy.deepcopy(cfg["leverage_brackets"]["BTCUSDT"])
    cfg["leverage_brackets"]["SOLUSDT"] = copy.deepcopy(cfg["leverage_brackets"]["BTCUSDT"])
    return cfg


def make_candle(t, symbol="BTCUSDT", price=100.0, **kwargs):
    d = {
        "open_time": t,
        "symbol": symbol,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "timeframe": "1m",
    }
    d.update(kwargs)
    return d


def make_req(t, symbol="BTCUSDT", direction=OrderDirection.LONG, qty=10.0, sl=95.0, tp=110.0):
    return OrderRequest(
        symbol=symbol,
        direction=direction,
        signal_price=100.0,
        stop_loss_price=sl,
        take_profit_price=tp,
        signal_time=t,
        leverage=2.0,
        base_risk_percent=0.02,
        conviction_tier="normal",
        requested_quantity=qty,
    )


def open_position(broker, symbol="BTCUSDT", direction=OrderDirection.LONG, t_start=T_BASE):
    broker.process_candle(make_candle(t_start, symbol=symbol))
    sl = 95.0 if direction == OrderDirection.LONG else 105.0
    tp = 110.0 if direction == OrderDirection.LONG else 90.0
    broker.submit_order(make_req(t_start, symbol=symbol, direction=direction, sl=sl, tp=tp))
    broker.process_candle(make_candle(t_start + timedelta(minutes=1), symbol=symbol))
    assert symbol in broker.positions


def snapshot_financial_state(broker, symbol="BTCUSDT"):
    pos = broker.positions.get(symbol)
    return {
        "wallet": broker.wallet_balance,
        "collateral": None if pos is None else pos.isolated_collateral,
        "cumulative_funding": None if pos is None else pos.cumulative_funding,
        "funding_count": len(broker.funding_history),
        "cashflows": list(broker.circuit_breaker.trade_history_24h),
        "settled_keys": set(broker.settled_funding_keys),
        "batch_time": broker.current_batch_open_time,
        "symbols_batch": set(broker.symbols_in_current_batch),
        "last_sym_time": broker.last_candle_open_time_per_symbol.get(symbol),
    }


# =====================================================================
# J1: Funding Provenance & Readiness Contract
# =====================================================================

def test_j1_missing_readiness_flag_fail_closed():
    """Thiếu hoàn toàn trường funding_readiness tại mốc settlement -> Fail-closed trước mutation."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before = snapshot_financial_state(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)  # 08:00 UTC

    with pytest.raises(ValueError, match="Missing funding_readiness"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_time=t_settle))
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j1_none_readiness_flag_fail_closed():
    """funding_readiness là None -> Fail-closed trước mutation."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before = snapshot_financial_state(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)

    with pytest.raises(TypeError, match="Invalid funding_readiness type"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=None, funding_time=t_settle))
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j1_wrong_type_readiness_flag_fail_closed():
    """funding_readiness không phải bool (e.g. 'true', 1) -> Fail-closed với TypeError."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before = snapshot_financial_state(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)

    with pytest.raises(TypeError, match="Invalid funding_readiness type"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness="true", funding_time=t_settle))
    assert snapshot_financial_state(b, "BTCUSDT") == before

    with pytest.raises(TypeError, match="Invalid funding_readiness type"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=1, funding_time=t_settle))
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j1_false_readiness_flag_fail_closed():
    """funding_readiness là False -> Báo lỗi Funding data marked not ready."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before = snapshot_financial_state(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)

    with pytest.raises(ValueError, match="Funding data marked not ready"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=False, funding_time=t_settle))
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j1_missing_funding_time_fail_closed():
    """Có funding_readiness=True nhưng thiếu funding_time -> Fail-closed trước mutation."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before = snapshot_financial_state(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)

    with pytest.raises(ValueError, match="Missing funding source timestamp"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=True))
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j1_none_funding_time_fail_closed():
    """funding_time là None -> Fail-closed trước mutation."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before = snapshot_financial_state(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)

    with pytest.raises(ValueError, match="Missing funding source timestamp"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=True, funding_time=None))
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j1_wrong_type_funding_time_fail_closed():
    """funding_time sai kiểu dữ liệu -> Fail-closed với TypeError."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before = snapshot_financial_state(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)

    with pytest.raises(TypeError):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=True, funding_time=True))
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j1_future_and_stale_funding_time_fail_closed():
    """funding_time ở tương lai hoặc quá 24h -> Fail-closed trước mutation."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before = snapshot_financial_state(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)

    # Future
    with pytest.raises(ValueError, match="is in future relative to open_time"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=True, funding_time=t_settle + timedelta(minutes=1)))
    assert snapshot_financial_state(b, "BTCUSDT") == before

    # Stale (>24h)
    with pytest.raises(ValueError, match="excessively stale"):
        b.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=True, funding_time=t_settle - timedelta(hours=25)))
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j1_zero_funding_rate_allowed_with_valid_metadata():
    """Funding rate = 0.0 là hợp lệ khi metadata đầy đủ và hợp chuẩn."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    t_settle = T_BASE + timedelta(minutes=2)

    res = b.process_candle(
        make_candle(t_settle, funding_rate=0.0, funding_readiness=True, funding_time=t_settle)
    )
    assert len(b.funding_history) == 1
    assert b.funding_history[0].funding_rate == 0.0
    assert b.funding_history[0].cashflow_usd == 0.0
    assert ("BTCUSDT", t_settle) in b.settled_funding_keys


# =====================================================================
# J2: Solver Failure During Settlement Has Zero Mutation (Transactional)
# =====================================================================

def test_j2_solver_failure_on_short_position_has_zero_mutation():
    """Kiểm tra transactional rollback cho vị thế SHORT khi solver lỗi do bracket corrupt."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT", direction=OrderDirection.SHORT)
    before = snapshot_financial_state(b, "BTCUSDT")
    b.config["leverage_brackets"]["BTCUSDT"] = "corrupt"
    t_settle = T_BASE + timedelta(minutes=2)

    with pytest.raises((ValueError, TypeError)):
        b.process_candle(
            make_candle(
                t_settle,
                funding_rate=0.001,
                funding_readiness=True,
                funding_time=t_settle,
            )
        )
    assert snapshot_financial_state(b, "BTCUSDT") == before


def test_j2_solver_failure_preserves_ledger_and_all_broker_state():
    """Kiểm tra mọi trường của broker (balance, collateral, history, CB, clocks) bất biến khi solver lỗi."""
    b = PaperBroker(config=get_config())
    open_position(b, "BTCUSDT")
    before_state = snapshot_financial_state(b, "BTCUSDT")
    b.config["leverage_brackets"]["BTCUSDT"] = []  # empty brackets list -> ValueError
    t_settle = T_BASE + timedelta(minutes=2)

    with pytest.raises(ValueError):
        b.process_candle(
            make_candle(
                t_settle,
                funding_rate=0.001,
                funding_readiness=True,
                funding_time=t_settle,
            )
        )
    assert snapshot_financial_state(b, "BTCUSDT") == before_state


# =====================================================================
# J3: Finalize Force Close Survives Nested Breaker Closure
# =====================================================================

def test_j3_finalize_force_close_mixed_long_short_nested_breaker():
    """Finalize force_close với 1 LONG và 1 SHORT, đợt đóng thứ nhất kích hoạt breaker lock."""
    b = PaperBroker(config=get_config())
    t0 = T_BASE
    # Nến 1: Submit LONG cho BTC, SHORT cho ETH
    b.process_candle(make_candle(t0, symbol="BTCUSDT"))
    b.submit_order(make_req(t0, symbol="BTCUSDT", direction=OrderDirection.LONG, qty=10.0))
    b.process_candle(make_candle(t0, symbol="ETHUSDT"))
    b.submit_order(make_req(t0, symbol="ETHUSDT", direction=OrderDirection.SHORT, qty=10.0, sl=105.0, tp=90.0))

    # Nến 2: Khớp cả 2 lệnh
    t1 = t0 + timedelta(minutes=1)
    b.process_candle(make_candle(t1, symbol="BTCUSDT"))
    b.process_candle(make_candle(t1, symbol="ETHUSDT"))
    assert len(b.positions) == 2

    # Giảm giá mark của cả 2 để LONG lỗ nặng (> daily limit)
    b.last_mark_prices["BTCUSDT"] = 1.0
    b.last_mark_prices["ETHUSDT"] = 1.0

    t2 = t1 + timedelta(minutes=1)
    summary = b.finalize(timestamp=t2, force_close=True)
    assert b.is_finalized
    assert summary["open_positions_count"] == 0
    assert not b.positions
    assert len(b.trade_history) == 2

    # Idempotence: gọi lại nhiều lần không double close và trả về kết quả giống hệt
    again = b.finalize(timestamp=t2 + timedelta(minutes=1), force_close=True)
    assert again == summary
    assert len(b.trade_history) == 2


def test_j3_finalize_force_close_three_symbols_nested_breaker_at_second():
    """Finalize force_close với 3 symbols (BTC, ETH, SOL), breaker kích hoạt ở vị thế thứ hai."""
    b = PaperBroker(config=get_config())
    t0 = T_BASE
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    for sym in symbols:
        b.process_candle(make_candle(t0, symbol=sym))
        b.submit_order(make_req(t0, symbol=sym, direction=OrderDirection.LONG, qty=5.0))

    t1 = t0 + timedelta(minutes=1)
    for sym in symbols:
        b.process_candle(make_candle(t1, symbol=sym))
    assert len(b.positions) == 3

    # Mark price: BTC lãi nhỏ (không khóa CB), ETH lỗ nặng (khóa CB và đóng SOL), SOL đang mở
    b.last_mark_prices["BTCUSDT"] = 101.0
    b.last_mark_prices["ETHUSDT"] = 1.0
    b.last_mark_prices["SOLUSDT"] = 100.0

    t2 = t1 + timedelta(minutes=1)
    summary = b.finalize(timestamp=t2, force_close=True)
    assert b.is_finalized
    assert summary["open_positions_count"] == 0
    assert not b.positions
    assert len(b.trade_history) == 3

    # Idempotent call
    again = b.finalize(timestamp=t2 + timedelta(minutes=2), force_close=True)
    assert again == summary
    assert len(b.trade_history) == 3
