"""Kill switch: manual emergency stop and automatic stop when the data feed goes quiet."""
from datetime import datetime, timedelta, timezone

import pytest

from src.execution.order_models import ExitReason, OrderDirection, OrderRequest, OrderStatus
from src.execution.paper_broker import PaperBroker

T0 = datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)


def _candle(t, price=100.0):
    return {"symbol": "BTCUSDT", "timeframe": "15m", "open_time": t, "open": price, "high": price + 1, "low": price - 1, "close": price, "volume": 1.0}


def _order(t):
    return OrderRequest(symbol="BTCUSDT", direction=OrderDirection.LONG, signal_price=100.0, stop_loss_price=95.0,
                        signal_time=t, conviction_tier="normal", leverage=2.0, base_risk_percent=0.02)


def _broker_with_position(config, **risk):
    config = {**config, "risk": {**config["risk"], **risk}}
    broker = PaperBroker(config=config, initial_balance=10000.0)
    broker.process_candle(_candle(T0))
    broker.submit_order(_order(T0 + timedelta(minutes=15)))
    broker.process_candle(_candle(T0 + timedelta(minutes=15)))
    assert "BTCUSDT" in broker.positions
    return broker


def test_manual_kill_switch_flattens_and_blocks_new_orders(config):
    broker = _broker_with_position(config)
    broker.engage_kill_switch(T0 + timedelta(minutes=30), "owner pressed stop")
    assert broker.positions == {}
    assert broker.trade_history[-1].exit_reason == ExitReason.KILL_SWITCH
    assert broker.submit_order(_order(T0 + timedelta(minutes=30))).status == OrderStatus.REJECTED
    assert broker.equity == pytest.approx(broker.wallet_balance)


def test_data_gap_beyond_limit_engages_kill_switch_at_next_open(config):
    broker = _broker_with_position(config, max_data_gap_minutes=60)
    late = T0 + timedelta(hours=10)  # skips the 08:00 funding boundary too
    broker.process_candle(_candle(late, price=90.0))
    assert broker.positions == {}
    assert broker.kill_switch_reason.startswith("DATA_GAP")
    exit_record = broker.trade_history[-1]
    assert exit_record.exit_reason == ExitReason.KILL_SWITCH
    assert exit_record.exit_price == pytest.approx(90.0 * (1 - broker.slippage_pct))


def test_gap_within_limit_is_normal(config):
    broker = _broker_with_position(config, max_data_gap_minutes=60)
    broker.process_candle(_candle(T0 + timedelta(minutes=75)))
    assert "BTCUSDT" in broker.positions and broker.kill_switch_reason is None


@pytest.mark.parametrize("bad", [0, -5, True, float("nan")])
def test_invalid_gap_limit_rejected(config, bad):
    with pytest.raises(ValueError):
        PaperBroker(config={**config, "risk": {**config["risk"], "max_data_gap_minutes": bad}}, initial_balance=10000.0)
