"""Hand accounting oracles; fixed charges must never fabricate public provenance."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from src.execution.order_models import OrderRequest, OrderStatus
from src.execution.paper_broker import PaperBroker


UTC = timezone.utc
T = datetime(2026, 9, 1, 7, 30, tzinfo=UTC)


def fixed_config(config):
    result = deepcopy(config)
    result['fees'] = {'taker_pct': 0.0, 'maker_pct': 0.0, 'slippage_pct': 0.0}
    result['news_filter']['enabled'] = False
    result['paper_funding_model'] = {
        'kind': 'FIXED_SIMULATED', 'version': 'fixed-001', 'rate': 0.0001,
        'effective_at_utc': '2020-01-01T00:00:00+00:00',
        'settlement_hours_utc': [0, 8, 16], 'price_proxy': 'CANDLE_OPEN',
        'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
    }
    return result


def bar(t, price=10000.0):
    return dict(symbol='BTCUSDT', timeframe='15m', open_time=t,
                open=price, high=price + 1, low=price - 1, close=price)


def enter(broker, direction='LONG', signal=T + timedelta(minutes=15)):
    broker.process_candle(bar(T))
    order = broker.submit_order(OrderRequest(symbol='BTCUSDT', direction=direction,
        signal_price=10000, stop_loss_price=9900 if direction == 'LONG' else 10100,
        signal_time=signal, requested_quantity=1, leverage=2,
        base_risk_percent=0.02, conviction_tier='normal'))
    assert order.status == OrderStatus.PENDING
    broker.process_candle(bar(signal))
    assert broker.positions['BTCUSDT'].quantity == 1


@pytest.mark.parametrize('direction,cashflow,wallet', [('LONG', -1, 9999), ('SHORT', 1, 10001)])
def test_fixed_funding_hand_oracle_without_exchange_metadata(config, direction, cashflow, wallet):
    broker = PaperBroker(config=fixed_config(config))
    enter(broker, direction)
    broker.process_candle(bar(T + timedelta(minutes=30)))
    event = broker.funding_history[0]
    assert event.cashflow_usd == cashflow
    assert broker.wallet_balance == wallet
    assert broker.positions['BTCUSDT'].cumulative_funding == cashflow
    assert broker.positions['BTCUSDT'].isolated_collateral == 5000 + cashflow
    assert event.settlement_mark_price == 10000
    broker.verify_accounting_invariants()


def test_new_entry_at_settlement_does_not_pay_prior_exposure(config):
    broker = PaperBroker(config=fixed_config(config))
    enter(broker, signal=T + timedelta(minutes=30))
    assert broker.wallet_balance == 10000
    assert broker.funding_history == []


def test_gap_exit_precedes_fixed_charge(config):
    broker = PaperBroker(config=fixed_config(config))
    enter(broker)
    broker.process_candle(bar(T + timedelta(minutes=30), 9890))
    assert broker.funding_history == []
    assert not broker.positions
    assert broker.trade_history[0].net_pnl == -110


def test_repeat_settlement_is_rejected_without_duplicate_cashflow(config):
    broker = PaperBroker(config=fixed_config(config))
    enter(broker)
    event_bar = bar(T + timedelta(minutes=30))
    broker.process_candle(event_bar)
    before = deepcopy(broker.__dict__)
    with pytest.raises(ValueError):
        broker.process_candle(event_bar)
    assert broker.wallet_balance == before['wallet_balance']
    assert broker.funding_history == before['funding_history']


def test_public_mode_still_requires_exact_provenance(config):
    cfg = fixed_config(config)
    del cfg['paper_funding_model']
    broker = PaperBroker(config=cfg)
    enter(broker)
    with pytest.raises(ValueError, match='funding'):
        broker.process_candle(bar(T + timedelta(minutes=30)))
    assert broker.wallet_balance == 10000
    assert not broker.funding_history


@pytest.mark.parametrize('field,value', [
    ('kind', 'PUBLIC'), ('rate', True), ('rate', float('nan')),
    ('rate', float('inf')), ('rate', 0), ('version', ''),
    ('effective_at_utc', '2026-01-01'), ('settlement_hours_utc', [0, 8, True]),
    ('settlement_hours_utc', [0, 8]), ('price_proxy', 'FUTURE_CLOSE'),
    ('symbols', ['BTCUSDT']),
])
def test_malformed_fixed_model_fails_before_account_creation(config, field, value):
    cfg = fixed_config(config)
    cfg['paper_funding_model'][field] = value
    with pytest.raises((TypeError, ValueError)):
        PaperBroker(config=cfg)


def test_fixed_model_effective_time_blocks_historical_charge(config):
    cfg = fixed_config(config)
    cfg['paper_funding_model']['effective_at_utc'] = '2026-09-01T08:15:00+00:00'
    broker = PaperBroker(config=cfg)
    enter(broker)
    with pytest.raises(ValueError, match='effective'):
        broker.process_candle(bar(T + timedelta(minutes=30)))
    assert broker.wallet_balance == 10000
    assert not broker.funding_history
