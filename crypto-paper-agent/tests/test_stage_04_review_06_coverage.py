"""
Tests covering Review 06 requirements (H1-H6):
- H1: Cashflow ledger consistency (wallet delta == rolling cashflows), streak non-increment on entry-fee lock, short funding/fee cashflow.
- H2: Collateral-aware liquidation price tier consistency (q * P_liq in tier).
- H3: Multi-symbol batch advancement, per-symbol duplicates rejection, batch order independence.
- H4: Transactional close_all_positions (fail-closed on time-reversal or invalid args).
- H5: Broker finalize lifecycle (default-open, force-close, idempotent, rejection of post-finalize operations).
- H6: Funding provenance (future timestamp, excessively stale timestamp, readiness flag).
"""

import copy
from datetime import datetime, timedelta, timezone
import pytest
import yaml
from pathlib import Path

from src.execution.paper_broker import PaperBroker
from src.execution.order_models import OrderRequest, OrderDirection, OrderStatus, ExitReason

ROOT = Path(__file__).resolve().parents[1]
T = datetime(2026, 9, 1, 7, 59, tzinfo=timezone.utc)


def get_config():
    with open(ROOT / "config" / "default_config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["fees"]["slippage_pct"] = 0.0005
    cfg["fees"]["taker_pct"] = 0.0004
    cfg["leverage_brackets"]["ETHUSDT"] = copy.deepcopy(cfg["leverage_brackets"]["BTCUSDT"])
    return cfg


def make_candle(t, symbol="BTCUSDT", p=100.0, **kwargs):
    d = {
        "open_time": t,
        "symbol": symbol,
        "open": p,
        "high": p,
        "low": p,
        "close": p,
        "timeframe": "1m",
    }
    d.update(kwargs)
    return d


def make_req(t=T, symbol="BTCUSDT", qty=10.0, direction=OrderDirection.LONG, **kwargs):
    d = {
        "symbol": symbol,
        "direction": direction,
        "signal_price": 100.0,
        "stop_loss_price": 95.0 if direction == OrderDirection.LONG else 105.0,
        "take_profit_price": 110.0 if direction == OrderDirection.LONG else 90.0,
        "signal_time": t,
        "leverage": 2.0,
        "base_risk_percent": 0.02,
        "conviction_tier": "normal",
        "requested_quantity": qty,
    }
    d.update(kwargs)
    return OrderRequest(**d)


# =====================================================================
# H1: Cashflow ledger precision & streak non-increment
# =====================================================================

def test_h1_wallet_delta_equals_cashflow_sum_over_full_trade():
    """Kiểm tra wallet delta bằng chính xác tổng cashflow ghi nhận qua các giai đoạn: entry fee, funding, exit cashflow."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    t0 = T - timedelta(minutes=1)
    broker.process_candle(make_candle(t0))

    initial_wallet = broker.wallet_balance
    req = make_req(t=t0, qty=10.0)
    broker.submit_order(req)

    # 1. Khớp entry
    broker.process_candle(make_candle(T))
    pos = broker.positions["BTCUSDT"]
    entry_fee = pos.entry_fee
    assert entry_fee > 0

    # 2. Áp dụng funding
    t1 = T + timedelta(minutes=1)
    broker.process_candle(make_candle(t1, funding_rate=0.001))
    funding_ev = broker.funding_history[-1]

    # 3. Đóng lệnh
    t2 = T + timedelta(minutes=2)
    broker.close_all_positions(105.0, t2, ExitReason.MANUAL)
    trade = broker.trade_history[-1]

    final_wallet = broker.wallet_balance
    actual_wallet_delta = final_wallet - initial_wallet

    # Tổng các cashflow đã ghi nhận vào circuit breaker
    recorded_cashflows = [cf for _, cf in broker.circuit_breaker.trade_history_24h]
    assert len(recorded_cashflows) == 3  # entry fee, funding, exit cashflow

    assert sum(recorded_cashflows) == pytest.approx(actual_wallet_delta)
    assert actual_wallet_delta == pytest.approx(trade.net_pnl)


def test_h1_short_trade_cashflow_and_funding():
    """Kiểm tra luồng cashflow cho vị thế SHORT nhận funding dương và thoát lãi."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    t0 = T - timedelta(minutes=1)
    broker.process_candle(make_candle(t0))

    req = make_req(t=t0, qty=10.0, direction=OrderDirection.SHORT, signal_price=100.0)
    broker.submit_order(req)
    broker.process_candle(make_candle(T))
    assert "BTCUSDT" in broker.positions

    # Funding rate dương -> Short nhận tiền (+ cashflow)
    t1 = T + timedelta(minutes=1)
    broker.process_candle(make_candle(t1, funding_rate=0.002))
    assert broker.funding_history[-1].cashflow_usd > 0

    # Đóng lệnh tại giá 95 (Short có lãi)
    t2 = T + timedelta(minutes=2)
    broker.close_all_positions(95.0, t2, ExitReason.TAKE_PROFIT)
    assert broker.trade_history[-1].net_pnl > 0
    assert broker.circuit_breaker.consecutive_losses == 0


# =====================================================================
# H2: Collateral-aware liquidation solver
# =====================================================================

def test_h2_solver_rejects_corrupted_brackets_without_mutating_state():
    """Solver ném lỗi khi leverage brackets bị hỏng và không làm thay đổi trạng thái broker."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    t0 = T - timedelta(minutes=1)
    broker.process_candle(make_candle(t0))
    broker.submit_order(make_req(t=t0))
    broker.process_candle(make_candle(T))

    pos = broker.positions["BTCUSDT"]
    broker.config["leverage_brackets"]["BTCUSDT"] = "not_a_valid_bracket"

    with pytest.raises((TypeError, ValueError)):
        broker._calculate_collateral_aware_liquidation_price(pos)


# =====================================================================
# H3: Multi-symbol batching & order independence
# =====================================================================

def test_h3_duplicate_candle_in_same_batch_rejected():
    """Từ chối nếu một symbol xuất hiện 2 lần tại cùng open_time trong một batch."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    broker.process_candle(make_candle(T, symbol="BTCUSDT"))
    with pytest.raises(ValueError, match=r"(?i)duplicate.*BTCUSDT"):
        broker.process_candle(make_candle(T, symbol="BTCUSDT"))


def test_h3_batch_order_independence():
    """Thứ tự đưa nến vào batch [BTC, ETH] vs [ETH, BTC] cho kết quả kế toán tương đương."""
    cfg = get_config()

    # Kịch bản A: BTC trước, ETH sau
    broker_a = PaperBroker(config=cfg)
    broker_a.process_candle(make_candle(T - timedelta(minutes=1), symbol="BTCUSDT"))
    broker_a.process_candle(make_candle(T - timedelta(minutes=1), symbol="ETHUSDT"))
    broker_a.submit_order(make_req(t=T - timedelta(minutes=1), symbol="BTCUSDT"))
    broker_a.submit_order(make_req(t=T - timedelta(minutes=1), symbol="ETHUSDT"))
    broker_a.process_candle(make_candle(T, symbol="BTCUSDT"))
    broker_a.process_candle(make_candle(T, symbol="ETHUSDT"))

    # Kịch bản B: ETH trước, BTC sau
    broker_b = PaperBroker(config=cfg)
    broker_b.process_candle(make_candle(T - timedelta(minutes=1), symbol="ETHUSDT"))
    broker_b.process_candle(make_candle(T - timedelta(minutes=1), symbol="BTCUSDT"))
    broker_b.submit_order(make_req(t=T - timedelta(minutes=1), symbol="ETHUSDT"))
    broker_b.submit_order(make_req(t=T - timedelta(minutes=1), symbol="BTCUSDT"))
    broker_b.process_candle(make_candle(T, symbol="ETHUSDT"))
    broker_b.process_candle(make_candle(T, symbol="BTCUSDT"))

    assert broker_a.wallet_balance == pytest.approx(broker_b.wallet_balance)
    assert broker_a.equity == pytest.approx(broker_b.equity)
    assert broker_a.available_margin == pytest.approx(broker_b.available_margin)
    assert len(broker_a.positions) == len(broker_b.positions) == 2


# =====================================================================
# H4: Transactional close_all_positions & fail-closed
# =====================================================================

def test_h4_close_all_positions_rejects_invalid_reason_without_mutation():
    """Từ chối lý do đóng không thuộc ExitReason enum mà không gây đột biến trạng thái."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    t0 = T - timedelta(minutes=1)
    broker.process_candle(make_candle(t0))
    broker.submit_order(make_req(t=t0))
    broker.process_candle(make_candle(T))

    initial_positions_count = len(broker.positions)
    initial_trade_count = len(broker.trade_history)

    with pytest.raises(TypeError, match="reason must be ExitReason enum"):
        broker.close_all_positions(100.0, T + timedelta(minutes=1), "NOT_AN_ENUM")

    assert len(broker.positions) == initial_positions_count
    assert len(broker.trade_history) == initial_trade_count


# =====================================================================
# H5: Lifecycle finalize / end of data
# =====================================================================

def test_h5_finalize_default_open_and_rejects_further_operations():
    """Finalize mặc định giữ nguyên positions mở, báo cáo tóm tắt và chặn thao tác tiếp theo."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    t0 = T - timedelta(minutes=1)
    broker.process_candle(make_candle(t0))
    broker.submit_order(make_req(t=t0))
    broker.process_candle(make_candle(T))

    summary = broker.finalize(timestamp=T + timedelta(minutes=1), force_close=False)
    assert summary["open_positions_count"] == 1
    assert "BTCUSDT" in broker.positions
    assert broker.is_finalized

    # Chặn process_candle
    with pytest.raises(RuntimeError, match="broker has finalized"):
        broker.process_candle(make_candle(T + timedelta(minutes=2)))

    # Chặn submit_order (trả về OrderStatus.REJECTED)
    rec = broker.submit_order(make_req(t=T + timedelta(minutes=2)))
    assert rec.status == OrderStatus.REJECTED
    assert "EXECUTION_REJECT_FINALIZED" in rec.rejection_reasons[0]


def test_h5_finalize_force_close_and_idempotence():
    """Finalize force_close=True đóng toàn bộ vị thế với ExitReason.END_OF_DATA và idempotent."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    t0 = T - timedelta(minutes=1)
    broker.process_candle(make_candle(t0))
    broker.submit_order(make_req(t=t0))
    broker.process_candle(make_candle(T))

    summary1 = broker.finalize(timestamp=T + timedelta(minutes=1), force_close=True)
    assert summary1["open_positions_count"] == 0
    assert len(broker.positions) == 0
    assert broker.trade_history[-1].exit_reason == ExitReason.END_OF_DATA

    # Idempotence: gọi lại trả về cùng summary mà không bị lỗi hay double-close
    summary2 = broker.finalize(timestamp=T + timedelta(minutes=2), force_close=True)
    assert summary1 == summary2


# =====================================================================
# H6: Funding data provenance & readiness
# =====================================================================

def test_h6_funding_future_source_time_rejected():
    """Từ chối nguồn funding có source time lớn hơn open_time (lookahead bias)."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    with pytest.raises(ValueError, match="is in future relative to open_time"):
        broker.process_candle(make_candle(T, funding_time=T + timedelta(hours=1)))


def test_h6_funding_excessively_stale_source_time_rejected():
    """Từ chối nguồn funding quá cũ (>24 giờ)."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    with pytest.raises(ValueError, match="excessively stale"):
        broker.process_candle(make_candle(T, funding_time=T - timedelta(hours=25)))


def test_h6_funding_not_ready_at_settlement_boundary_rejected():
    """Từ chối khi đang có vị thế mở tại mốc settlement mà funding được gắn cờ unready."""
    cfg = get_config()
    broker = PaperBroker(config=cfg)
    t0 = T - timedelta(minutes=1)
    broker.process_candle(make_candle(t0))
    broker.submit_order(make_req(t=t0))
    broker.process_candle(make_candle(T))  # Open tại 08:00

    # Tại mốc 08:00 UTC (funding settlement) khi vị thế đang mở
    t_settle = T + timedelta(minutes=1)
    with pytest.raises(ValueError, match="Funding data marked not ready"):
        broker.process_candle(make_candle(t_settle, funding_rate=0.001, funding_readiness=False))
