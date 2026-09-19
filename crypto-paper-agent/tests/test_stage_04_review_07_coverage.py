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


# =====================================================================
# K1: NO CALLER / STACK INSPECTION & UNCONDITIONAL FUNDING PROVENANCE
# =====================================================================

def test_k1_no_caller_stack_inspection_or_inspect_import_in_broker_code():
    """
    K1: Kiểm tra AST và mã nguồn của paper_broker.py:
    - Tuyệt đối không import inspect hoặc inspect submodules.
    - Không gọi sys._getframe, currentframe hoặc bất kỳ hàm kiểm tra call stack nào.
    - Không có phương thức _is_legacy_probe_caller hoặc bất kỳ logic nhận diện tên test/caller.
    """
    import ast
    broker_path = ROOT / "src" / "execution" / "paper_broker.py"
    source_code = broker_path.read_text(encoding="utf-8")
    tree = ast.parse(source_code, filename=str(broker_path))

    for node in ast.walk(tree):
        # 1. Chặn import inspect
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "inspect", "paper_broker.py must not import inspect"
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "inspect", "paper_broker.py must not import from inspect"

        # 2. Chặn _getframe hoặc currentframe
        elif isinstance(node, ast.Attribute):
            assert node.attr not in ("_getframe", "currentframe"), (
                f"paper_broker.py must not inspect call frames ({node.attr})"
            )

        # 3. Chặn hàm _is_legacy_probe_caller
        elif isinstance(node, ast.FunctionDef):
            assert node.name != "_is_legacy_probe_caller", (
                "paper_broker.py must not contain _is_legacy_probe_caller"
            )

    # Kiểm tra chuỗi thô để tránh dynamic tricks
    assert "inspect.currentframe" not in source_code
    assert "_is_legacy_probe_caller" not in source_code
    assert "test_stage_04_review_05" not in source_code
    assert "test_stage_04_review_06" not in source_code


def test_k1_funding_provenance_identical_across_caller_and_stack_names():
    """
    K1: Kiểm tra tính bất biến của broker trước tên hàm, caller stack hoặc module:
    - Cùng một candle thiếu provenance gọi từ test_stage_04_review_05_* hay production_*
      đều phải bị ném ValueError với cùng thông điệp lỗi.
    - Cùng một candle hợp lệ gọi từ test hay production đều phải thành công như nhau.
    """
    t_open = T_BASE
    t_settle = t_open + timedelta(minutes=2)  # 08:00 UTC

    def _setup_open_position():
        b = PaperBroker(config=get_config())
        b.process_candle(make_candle(t_open))
        b.submit_order(make_req(t_open))
        b.process_candle(make_candle(t_open + timedelta(minutes=1)))
        assert "BTCUSDT" in b.positions
        return b

    # 1. Invalid candle: thiếu funding_readiness và funding_time
    invalid_candle = make_candle(t_settle, funding_rate=0.001)

    def test_stage_04_review_05_probe_caller(broker, candle_data):
        return broker.process_candle(candle_data)

    def production_live_caller(broker, candle_data):
        return broker.process_candle(candle_data)

    b1 = _setup_open_position()
    b2 = _setup_open_position()

    err1 = None
    try:
        test_stage_04_review_05_probe_caller(b1, invalid_candle)
    except ValueError as e:
        err1 = str(e)

    err2 = None
    try:
        production_live_caller(b2, invalid_candle)
    except ValueError as e:
        err2 = str(e)

    assert err1 is not None, "Legacy probe caller name must not bypass missing funding_readiness"
    assert err2 is not None, "Production caller must fail-closed on missing funding_readiness"
    assert err1 == err2, f"Exceptions must be identical regardless of caller name: {err1!r} vs {err2!r}"

    # 2. Valid candle: có đầy đủ funding_readiness và funding_time
    valid_candle = make_candle(
        t_settle,
        funding_rate=0.001,
        funding_readiness=True,
        funding_time=t_settle,
    )

    b3 = _setup_open_position()
    b4 = _setup_open_position()

    evs1 = test_stage_04_review_05_probe_caller(b3, valid_candle)
    evs2 = production_live_caller(b4, valid_candle)

    assert b3.wallet_balance == b4.wallet_balance
    assert b3.positions["BTCUSDT"].isolated_collateral == b4.positions["BTCUSDT"].isolated_collateral
    assert len(b3.funding_history) == len(b4.funding_history) == 1
    assert len(evs1) == len(evs2)


def test_k1_config_flag_cannot_relax_funding_provenance():
    """
    K1: Không cấu hình nào (kể cả strict_provenance=False) được phép nới lỏng
    quy tắc fail-closed của funding provenance & readiness tại settlement.
    """
    cfg = get_config()
    cfg["funding_rate"]["strict_provenance"] = False  # Cố gắng nới lỏng bằng config

    b = PaperBroker(config=cfg)
    t0 = T_BASE
    b.process_candle(make_candle(t0))
    b.submit_order(make_req(t0))
    b.process_candle(make_candle(t0 + timedelta(minutes=1)))
    assert "BTCUSDT" in b.positions

    t_settle = t0 + timedelta(minutes=2)
    # Candle thiếu funding_readiness vẫn phải bị từ chối
    candle_missing_readiness = make_candle(t_settle, funding_rate=0.001, funding_time=t_settle)
    with pytest.raises(ValueError, match="Missing funding_readiness"):
        b.process_candle(candle_missing_readiness)

    # Candle thiếu funding_time vẫn phải bị từ chối
    candle_missing_time = make_candle(t_settle, funding_rate=0.001, funding_readiness=True)
    with pytest.raises(ValueError, match="Missing funding source timestamp"):
        b.process_candle(candle_missing_time)

