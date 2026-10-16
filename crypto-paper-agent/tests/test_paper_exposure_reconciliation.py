"""Restore must reconcile broker-authored execution, not trust exposure totals."""
from copy import deepcopy
from datetime import timedelta

import pytest

from src.execution.order_models import OrderRequest, ExitReason
from src.paper.causal_runner import CausalRunner
from src.paper.public_stream import SYMBOLS
from src.paper.recovery_state import pack, unpack
from test_local_paper_session import BASE
from test_paper_causal_runner import batch, runner_fixture


def opened_runner(config, direction='SHORT', fees=None, **kwargs):
    runner = runner_fixture(config)
    if fees:
        seed = runner
        revised = deepcopy(seed.config)
        revised['fees'] = fees
        runner = CausalRunner(revised, 'trend_following', BASE)
        runner.initialize(seed.signal_history, batch(BASE - timedelta(minutes=15)))
    runner.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction=direction,
        signal_price=100, stop_loss_price=110 if direction == 'SHORT' else 90,
        signal_time=BASE, requested_quantity=1, **kwargs))
    runner.advance(batch(BASE))
    assert runner.broker.positions['BTCUSDT'].quantity == 1
    return runner


def restore(runner, checkpoint=None, events=None):
    return CausalRunner.restore(runner.config, checkpoint or runner.capture(),
        runner.all_inputs(), events if events is not None else runner.ledger_events())


@pytest.mark.parametrize('field,value', [
    ('quantity', 10), ('entry_price', 1000), ('initial_margin', 10),
    ('isolated_collateral', 0), ('leverage', 5), ('liquidation_price', 1),
    ('initial_stop_loss_price', 115), ('initial_liquidation_price', 1),
    ('_last_unrealized_pnl', 100), ('take_profit_price', 99), ('stop_loss_price', 95),
    ('cumulative_funding', 1),
    ('direction', 'SHORT'),
])
def test_restore_rejects_exposure_changed_without_execution(config, field, value):
    runner = opened_runner(config)
    checkpoint = runner.capture()
    checkpoint['broker']['value']['positions']['value']['BTCUSDT']['value'][field] = pack(value)
    with pytest.raises(ValueError, match='execution|exposure|lifecycle|liquidation|mark'):
        restore(runner, checkpoint)


def test_restore_does_not_normalize_corrupt_lifecycle_or_missing_initial_fields(config):
    runner = opened_runner(config)
    for field, value in [('metadata', {'lifecycle_id': 'wrong', 'lifecycle_quantity': 1}),
                         ('initial_stop_loss_price', None), ('initial_liquidation_price', None)]:
        checkpoint = runner.capture()
        checkpoint['broker']['value']['positions']['value']['BTCUSDT']['value'][field] = pack(value)
        with pytest.raises(ValueError):
            restore(runner, checkpoint)


def test_missing_exposure_is_not_explained_by_balanced_zero_fee_wallet(config):
    runner = opened_runner(config)
    checkpoint = runner.capture()
    checkpoint['broker']['value']['positions'] = pack({})
    with pytest.raises(ValueError, match='execution|exposure|lifecycle'):
        restore(runner, checkpoint)


def test_missing_filled_execution_cannot_leave_an_unaccounted_position(config):
    runner = opened_runner(config)
    checkpoint = runner.capture()
    checkpoint['broker']['value']['_order_seq'] = 0
    checkpoint['ledger_counts']['order_history'] = 0
    events = [e for e in runner.ledger_events() if e['kind'] != 'order_history']
    with pytest.raises(ValueError, match='execution|exposure|lifecycle'):
        restore(runner, checkpoint, events)


def test_pending_close_cannot_have_a_future_or_non_utc_decision(config):
    runner = opened_runner(config)
    checkpoint = runner.capture()
    checkpoint['broker']['value']['pending_closes'] = pack({'BTCUSDT': BASE + timedelta(days=1)})
    with pytest.raises(ValueError, match='pending close|execution'):
        restore(runner, checkpoint)


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
def test_partial_funding_trailing_and_final_lifecycle_restore_exactly(config, direction):
    runner = opened_runner(config, direction, leverage=2,
        fees={'taker_pct': .001, 'maker_pct': .0002, 'slippage_pct': 0})
    broker = runner.broker
    position = broker.positions['BTCUSDT']
    sign = 1 if direction == 'LONG' else -1
    broker._execute_exit(position, 100 + sign * 5, BASE + timedelta(minutes=15),
                         ExitReason.MANUAL, quantity=.4)
    for i in range(1, 17):
        bars = batch(BASE + timedelta(minutes=15 * i))
        signals = {s: dict(bars[s], open_time=BASE, close_time=BASE + timedelta(hours=4),
            timeframe='4h', volume=80) for s in SYMBOLS} if i == 15 else None
        runner.advance(bars, signals)
    broker = runner.broker
    assert len(broker.funding_history) == 1
    assert broker.positions['BTCUSDT'].cumulative_funding == pytest.approx(-sign * .006)
    assert broker.update_stop_loss('BTCUSDT', 99 if direction == 'LONG' else 101)
    resumed = restore(runner)
    assert resumed.capture() == runner.capture()
    assert resumed.broker.positions == broker.positions
    broker.request_close('BTCUSDT', broker.current_time)
    resumed.broker.request_close('BTCUSDT', resumed.broker.current_time)
    next_bar = batch(BASE + timedelta(minutes=15 * 17))
    runner.advance(next_bar)
    resumed.advance(next_bar)
    assert not runner.broker.positions
    assert sum(t.quantity for t in runner.broker.trade_history) == pytest.approx(1)
    assert restored_closed_equity(runner) == resumed.broker.equity
    assert resumed.broker.equity == pytest.approx(10001.792 if direction == 'LONG' else 10001.808)


@pytest.mark.parametrize('field,value', [('direction', 'SHORT'), ('reference_price', 101),
                                       ('order_type', 'LIMIT_ENTRY')])
def test_pending_record_common_fields_must_match_broker_request(config, field, value):
    from src.execution.order_models import OrderDirection, OrderType
    runner = runner_fixture(config)
    runner.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG', signal_price=100,
        stop_loss_price=90, signal_time=BASE, requested_quantity=1))
    events = runner.ledger_events()
    order = next(e for e in events if e['kind'] == 'order_history')['payload']['value']
    order[field] = pack(OrderDirection(value) if field == 'direction' else
        OrderType(value) if field == 'order_type' else value)
    with pytest.raises(ValueError, match='pending|execution'):
        restore(runner, events=events)


def restored_closed_equity(runner):
    return restore(runner).broker.equity


def test_valid_zero_equity_halted_failure_survives_multiple_restarts(config):
    runner = opened_runner(config)
    runner.advance(batch(BASE + timedelta(minutes=15), 10100))
    assert runner.broker.equity == 0
    assert not runner.broker.positions
    assert runner.broker.circuit_breaker.is_halted
    assert runner.broker.circuit_breaker.locked_until is None
    assert runner.trials.current['status'] == 'FAILED'
    for _ in range(3):
        runner = restore(runner)
        assert runner.broker.equity == 0
        assert runner.broker.is_halted
        assert runner.broker.circuit_breaker.is_halted
        assert runner.trials.total_capital_injected == 10000
        assert runner.trials.current['status'] == 'FAILED'


@pytest.mark.parametrize('scenario', ['expiry', 'invalidation'])
def test_paused_breakout_does_not_reenter_obsolete_setup(config, scenario):
    seed = runner_fixture(config)
    seed.config['fees'] = deepcopy(config['fees'])
    runner = CausalRunner(seed.config, 'breakout_retest', BASE)
    runner.initialize(seed.signal_history, batch(BASE - timedelta(minutes=15)))
    previous = 100.
    groups = 9 if scenario == 'expiry' else 3
    for group in range(groups):
        if group == 0:
            close, high, low, volume = 104., 105., 99., 10.
        elif group == groups - 1:
            close, high, low, volume = 102., 105., 100., .5
        elif scenario == 'invalidation':
            close, high, low, volume = 90., 105., 89., .5
        else:
            close, high, low, volume = 104., 105., 103., 5.
        if group == 1:
            assert runner.strategies['BTCUSDT'].setup.direction == 'LONG'
            runner.set_intent('PAUSED', BASE + timedelta(hours=4))
        if group == groups - 1:
            assert runner.strategies['BTCUSDT'].setup.direction is None
            runner = restore(runner)
            runner.set_intent('RUNNING', BASE + timedelta(hours=4 * group))
        first_open = previous
        for index in range(16):
            opened = BASE + timedelta(hours=4 * group, minutes=15 * index)
            bars = {s: dict(symbol=s, timeframe='15m', open_time=opened,
                close_time=opened + timedelta(minutes=15), open=previous,
                high=max(high, previous), low=min(low, previous), close=close,
                volume=volume, provisional=False)
                for s in SYMBOLS}
            signals = {s: dict(bars[s], timeframe='4h',
                open_time=BASE + timedelta(hours=4 * group), open=first_open,
                high=max(high, first_open), low=min(low, first_open),
                volume=volume * 16) for s in SYMBOLS} if index == 15 else None
            runner.advance(bars, signals)
            previous = close
    runner.advance(batch(BASE + timedelta(hours=4 * groups), 102))
    assert not runner.broker.positions
    assert not runner.broker.pending_orders
    assert not runner.broker.trade_history
    assert not any(o.status.value == 'FILLED' for o in runner.broker.order_history)
