"""Real broker tests for shared causal runner/restart financial equality."""
from copy import deepcopy
from datetime import timedelta

import pytest

from src.execution.order_models import OrderRequest
from src.paper.public_stream import SYMBOLS
from src.paper.live_session import parse_klines
from test_fixed_simulated_funding import fixed_config
from test_local_paper_session import BASE, rows


def runner_fixture(config):
    from src.paper.causal_runner import CausalRunner
    cfg = fixed_config(config)
    for symbol in ('ETHUSDT', 'SOLUSDT'):
        cfg['leverage_brackets'][symbol] = [[5000, 0.02, 0]]
    runner = CausalRunner(cfg, 'trend_following', BASE)
    raw = rows(BASE - timedelta(hours=4 * 210), 210, 240)
    bars, _ = parse_klines(raw, '4h', int(BASE.timestamp() * 1000))
    baseline = batch(BASE - timedelta(minutes=15))
    runner.initialize({s: deepcopy(bars) for s in SYMBOLS}, baseline)
    return runner


def batch(opened, price=100):
    return {s: dict(symbol=s, timeframe='15m', open_time=opened,
                   close_time=opened + timedelta(minutes=15), open=price,
                   high=price + 1, low=price - 1, close=price, volume=5,
                   provisional=False) for s in SYMBOLS}


def test_pending_entry_goes_through_broker_and_does_not_retrofill(config):
    runner = runner_fixture(config)
    req = OrderRequest(symbol='BTCUSDT', direction='LONG', signal_price=100,
                       stop_loss_price=90, signal_time=BASE, requested_quantity=1)
    runner.broker.submit_order(req)
    assert not runner.broker.positions
    runner.advance(batch(BASE))
    assert runner.broker.positions['BTCUSDT'].opened_at == BASE
    assert runner.broker.positions['BTCUSDT'].quantity == 1
    assert runner.last_open['BTCUSDT'] == BASE


def test_invalid_last_symbol_has_no_financial_or_watermark_mutation(config):
    runner = runner_fixture(config)
    before = runner.capture()
    invalid = batch(BASE)
    invalid['SOLUSDT']['volume'] = True
    with pytest.raises(ValueError):
        runner.advance(invalid)
    assert runner.capture() == before


def test_restart_restores_full_exposure_pending_and_risk_state(config):
    from src.paper.causal_runner import CausalRunner
    runner = runner_fixture(config)
    runner.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='SHORT',
        signal_price=100, stop_loss_price=110, signal_time=BASE, requested_quantity=1))
    runner.advance(batch(BASE))
    runner.broker.submit_order(OrderRequest(symbol='ETHUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE + timedelta(minutes=15), requested_quantity=1))
    checkpoint = runner.capture()
    restored = CausalRunner.restore(runner.config, checkpoint, runner.all_inputs(), runner.ledger_events())
    assert restored.broker.positions == runner.broker.positions
    assert restored.broker.pending_orders == runner.broker.pending_orders
    assert vars(restored.broker.circuit_breaker) == vars(runner.broker.circuit_breaker)
    for i in range(1, 17):
        bars = batch(BASE + timedelta(minutes=15 * i))
        signals = None
        if i == 15:
            signals = {s: dict(bars[s], open_time=BASE, close_time=BASE + timedelta(hours=4),
                                timeframe='4h', volume=80) for s in SYMBOLS}
        runner.advance(bars, signals)
        restored.advance(bars, signals)
        if i == 1:
            assert set(restored.broker.positions) == {'BTCUSDT', 'ETHUSDT'}
    assert restored.broker.wallet_balance == runner.broker.wallet_balance
    assert restored.broker.funding_history == runner.broker.funding_history
    assert len(restored.broker.funding_history) == 2
    assert restored.broker.trade_history == runner.broker.trade_history


def test_signal_requires_exact_causal_closed_bar(config):
    runner = runner_fixture(config)
    for i in range(15):
        runner.advance(batch(BASE + timedelta(minutes=15 * i)))
    before = runner.capture()
    with pytest.raises(ValueError, match='signal'):
        runner.advance(batch(BASE + timedelta(minutes=225)))
    assert runner.capture() == before


def test_breakout_setup_roundtrip_is_exact(config):
    from src.paper.causal_runner import CausalRunner
    original = runner_fixture(config)
    runner = CausalRunner(original.config, 'breakout_retest', BASE)
    runner.initialize(original.signal_history, batch(BASE - timedelta(minutes=15)))
    runner.advance(batch(BASE))
    restored = CausalRunner.restore(runner.config, runner.capture(), runner.all_inputs(), runner.ledger_events())
    assert vars(restored.strategies['BTCUSDT']) == vars(runner.strategies['BTCUSDT'])


def test_later_operator_pause_cannot_cancel_a_past_outage_entry(config):
    runner = runner_fixture(config)
    runner.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    runner.set_intent('PAUSED', BASE + timedelta(minutes=30))
    runner.advance(batch(BASE))
    assert runner.broker.positions['BTCUSDT'].opened_at == BASE
    assert runner.broker.order_history[0].status.value == 'FILLED'
    runner.advance(batch(BASE + timedelta(minutes=15)))
    assert runner.intent_at(BASE + timedelta(minutes=15)) == 'RUNNING'
    runner.advance(batch(BASE + timedelta(minutes=30)))
    assert runner.intent_at(BASE + timedelta(minutes=30)) == 'PAUSED'
    assert runner.broker.positions['BTCUSDT'].quantity == 1


def test_stop_replays_past_entry_before_causal_reduce_only_exit(config):
    runner = runner_fixture(config)
    runner.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    runner.set_intent('STOPPING', BASE + timedelta(minutes=30))
    runner.advance(batch(BASE))
    assert runner.broker.positions
    runner.advance(batch(BASE + timedelta(minutes=15)))
    assert runner.broker.positions
    runner.advance(batch(BASE + timedelta(minutes=30)))
    assert not runner.broker.positions
    assert runner.broker.trade_history[0].exit_time == BASE + timedelta(minutes=30)
    assert runner.intent == 'STOPPED'


def test_shadow_fork_does_not_mutate_published_financial_records(config):
    from src.paper.recovery_state import pack
    runner = runner_fixture(config)
    runner.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG',
        signal_price=100, stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    before = pack(runner.broker.order_history)
    shadow = runner.fork()
    shadow.advance(batch(BASE))
    assert pack(runner.broker.order_history) == before
    assert runner.broker.pending_orders
    assert not shadow.broker.pending_orders
    assert shadow.broker.positions
    assert not runner.broker.positions


def test_cross_timeframe_disagreement_blocks_before_close_batch_mutation(config):
    runner = runner_fixture(config)
    for i in range(15):
        runner.advance(batch(BASE + timedelta(minutes=15 * i)))
    bars = batch(BASE + timedelta(minutes=225))
    signals = {s: dict(bars[s], open_time=BASE, close_time=BASE + timedelta(hours=4),
                       timeframe='4h', volume=80) for s in SYMBOLS}
    signals['SOLUSDT']['high'] = 200
    before = runner.capture()
    with pytest.raises(ValueError, match='timeframe|aggregate'):
        runner.advance(bars, signals)
    assert runner.capture() == before


@pytest.mark.parametrize('case', ['order_sequence', 'watermark', 'funding_keys', 'stop', 'breaker_rules'])
def test_restoration_rejects_semantically_inconsistent_machine(config, case):
    from src.paper.causal_runner import CausalRunner
    from src.paper.recovery_state import pack, unpack
    runner = runner_fixture(config)
    runner.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='SHORT',
        signal_price=100, stop_loss_price=110, signal_time=BASE, requested_quantity=1))
    runner.advance(batch(BASE))
    checkpoint = runner.capture()
    machine = unpack(checkpoint['broker'])
    if case == 'order_sequence': machine['_order_seq'] = 0
    elif case == 'watermark':
        checkpoint['last_open'] = pack({s: BASE + timedelta(minutes=15) for s in SYMBOLS})
    elif case == 'funding_keys': machine['_settled_funding_keys'].add(('BTCUSDT', BASE))
    elif case == 'stop': machine['positions']['BTCUSDT'].stop_loss_price = None
    else: machine['circuit_breaker']['__circuit_breaker__']['daily_loss_limit_pct'] = .9
    breaker = machine.pop('circuit_breaker')
    checkpoint['broker'] = pack(machine)
    checkpoint['broker']['value']['circuit_breaker'] = {
        'kind': 'breaker', 'value': pack(breaker['__circuit_breaker__'])}
    with pytest.raises(ValueError):
        CausalRunner.restore(runner.config, checkpoint, runner.all_inputs(), runner.ledger_events())
