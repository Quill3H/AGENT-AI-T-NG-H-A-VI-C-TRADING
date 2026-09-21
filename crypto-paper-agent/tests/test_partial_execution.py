"""Broker regression oracle for partial closes, expiry and intrabar ambiguity."""

from datetime import datetime, timedelta, timezone
import pytest
from src.execution.paper_broker import PaperBroker
from src.execution.order_models import (
    OrderRequest,
    OrderType,
    OrderDirection,
    OrderStatus,
    ExitReason,
)

T = datetime(2024, 1, 1, 7, 59, tzinfo=timezone.utc)


def candle(t, o=100, h=101, l=99, c=100, **kw):
    return dict(
        symbol="BTCUSDT",
        timeframe="1m",
        open_time=t,
        close_time=t + timedelta(minutes=1),
        open=o,
        high=h,
        low=l,
        close=c,
        volume=1.0,
        **kw
    )


def request(**kw):
    return OrderRequest(
        "BTCUSDT",
        OrderDirection.LONG,
        100.0,
        95.0,
        T,
        requested_quantity=10.0,
        leverage=2.0,
        partial_exits=[[1.5, 0.4], [3.0, 0.3]],
        **kw
    )


def test_partial_then_funding_preserves_cash_collateral_and_streak():
    b = PaperBroker({"fees": {"taker_pct": 0.001, "slippage_pct": 0}})
    b.submit_order(request())
    b.process_candle(candle(T, h=108, c=108))
    p = b.positions["BTCUSDT"]
    assert p.quantity == 6
    assert p.initial_margin == 300
    assert p.entry_fee == pytest.approx(0.6)
    assert p.stop_loss_price == 100  # BE effective next candle
    assert b.circuit_breaker.consecutive_wins == 0
    b.process_candle(
        candle(
            T + timedelta(minutes=1),
            o=108,
            h=109,
            l=107,
            c=108,
            funding_rate=0.001,
            funding_time=T + timedelta(minutes=1),
            funding_readiness=True,
        )
    )
    assert b.funding_history[0].cashflow_usd == pytest.approx(-0.648)
    assert p.isolated_collateral == pytest.approx(299.352)
    b.finalize(T + timedelta(minutes=2), force_close=True)
    assert sum(t.entry_fee for t in b.trade_history) == pytest.approx(1.0)
    assert sum(t.funding_cashflow for t in b.trade_history) == pytest.approx(-0.648)
    assert b.circuit_breaker.consecutive_wins == 1
    b.verify_accounting_invariants()


def test_same_bar_stop_wins_over_partial_tp_and_invalid_partial_is_atomic():
    b = PaperBroker({"fees": {"slippage_pct": 0}})
    b.submit_order(request())
    b.process_candle(candle(T, h=120, l=94))
    assert (
        len(b.trade_history) == 1
        and b.trade_history[0].exit_reason == ExitReason.STOP_LOSS
    )
    b = PaperBroker()
    b.submit_order(request())
    b.process_candle(candle(T))
    wallet = b.wallet_balance
    with pytest.raises(ValueError):
        b._execute_exit(
            b.positions["BTCUSDT"],
            101,
            T + timedelta(minutes=1),
            ExitReason.MANUAL,
            quantity=11,
        )
    assert b.wallet_balance == wallet and b.positions["BTCUSDT"].quantity == 10


def test_limit_wait_expiry_and_no_same_bar_profit():
    b = PaperBroker({"fees": {"slippage_pct": 0}})
    b.submit_order(
        request(order_type=OrderType.LIMIT_ENTRY, expires_at=T + timedelta(minutes=1))
    )
    b.process_candle(candle(T, o=105, h=106, l=104, c=105))
    assert not b.positions and b.pending_orders
    b.process_candle(candle(T + timedelta(minutes=1)))
    assert b.order_history[0].status == OrderStatus.CANCELLED
    b = PaperBroker({"fees": {"slippage_pct": 0}})
    b.submit_order(request(order_type=OrderType.LIMIT_ENTRY))
    b.process_candle(candle(T, o=110, h=120, l=99, c=110))
    assert b.positions and not b.trade_history


def test_partial_cashflow_can_lock_and_force_remainder():
    cfg = {
        "fees": {"taker_pct": 0, "slippage_pct": 0},
        "circuit_breakers": {"daily_loss_limit_pct": 0.00001},
    }
    b = PaperBroker(cfg)
    b.submit_order(request())
    b.process_candle(candle(T))
    b._execute_exit(
        b.positions["BTCUSDT"],
        99,
        T + timedelta(minutes=1),
        ExitReason.MANUAL,
        quantity=4,
    )
    assert b.circuit_breaker.is_locked and not b.positions
    b.verify_accounting_invariants()


def test_gap_partial_occurs_before_settlement_quantity():
    b = PaperBroker({"fees": {"taker_pct": 0, "slippage_pct": 0}})
    b.submit_order(request())
    b.process_candle(candle(T))
    b.process_candle(
        candle(
            T + timedelta(minutes=1),
            o=108,
            h=109,
            l=107,
            c=108,
            funding_rate=0.001,
            funding_time=T + timedelta(minutes=1),
            funding_readiness=True,
        )
    )
    assert b.trade_history[0].quantity == 4
    assert b.funding_history[0].position_quantity == 6
    b.verify_accounting_invariants()


def test_nonpositive_partial_target_rejects_before_cash_mutation():
    b = PaperBroker({"fees": {"slippage_pct": 0}})
    req = OrderRequest(
        "BTCUSDT",
        OrderDirection.SHORT,
        100.0,
        105.0,
        T,
        requested_quantity=1.0,
        leverage=2.0,
        partial_exits=[[30.0, 0.4]],
    )
    before = b.wallet_balance
    b.submit_order(req)
    b.process_candle(candle(T))
    assert b.order_history[0].status == OrderStatus.REJECTED
    assert (
        "EXECUTION_REJECT_INVALID_PARTIAL_TARGET"
        in b.order_history[0].rejection_reasons
    )
    assert not b.positions and b.wallet_balance == before
