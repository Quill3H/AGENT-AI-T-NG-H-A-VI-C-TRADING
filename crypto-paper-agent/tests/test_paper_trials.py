from datetime import datetime, timedelta, timezone

import pytest


T = datetime(2026, 10, 1, tzinfo=timezone.utc)
RECIPE = {'identity': 'r1', 'strategy_id': 'trend_following', 'available_at_utc': T.isoformat()}


def test_failure_and_target_literal_boundaries_are_recorded_once():
    from src.paper.trials import TrialBook
    book = TrialBook(RECIPE, T)
    assert book.observe(5000, T) == []
    target = book.observe(15000, T + timedelta(minutes=15))
    assert [e['kind'] for e in target] == ['TRIAL_TARGET_REACHED']
    assert book.observe(16000, T + timedelta(minutes=30)) == []
    failure = book.observe(4999.99, T + timedelta(minutes=45))
    assert [e['kind'] for e in failure] == ['TRIAL_FAILED']
    assert book.observe(4998, T + timedelta(hours=1)) == []
    assert book.current['target_reached'] is True
    assert book.current['status'] == 'FAILED'
    assert book.total_capital_injected == 10000


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf')])
def test_unknown_equity_never_causes_reset_or_promotion(value):
    from src.paper.trials import TrialBook
    book = TrialBook(RECIPE, T)
    with pytest.raises(ValueError):
        book.observe(value, T)
    assert book.total_capital_injected == 10000
    assert len(book.trials) == 1


def test_replacement_requires_causal_eligible_verdict_and_reconciliation():
    from src.paper.trials import TrialBook
    book = TrialBook(RECIPE, T)
    book.observe(4990, T)
    replacement = dict(RECIPE, identity='r2', strategy_id='breakout_retest')
    verdict = {'eligible': True, 'identity': 'v1', 'selected_recipe_identity': 'r2', 'cutoff_utc': T.isoformat()}
    with pytest.raises(ValueError):
        book.promote(replacement, T, False, verdict)
    assert book.total_capital_injected == 10000
    result = book.promote(replacement, T + timedelta(minutes=15), True, verdict)
    assert result['capital_usd'] == 10000
    assert book.total_capital_injected == 20000
    assert book.trials[0]['final_equity_usd'] == 4990
    assert book.promote(replacement, T + timedelta(minutes=15), True, verdict) == result
    assert book.total_capital_injected == 20000


def test_future_recipe_or_failed_verdict_never_allocates():
    from src.paper.trials import TrialBook
    book = TrialBook(RECIPE, T)
    book.observe(4900, T)
    future = dict(RECIPE, identity='r2', available_at_utc=(T + timedelta(days=1)).isoformat())
    verdict = {'eligible': True, 'identity': 'v1', 'selected_recipe_identity': 'r2', 'cutoff_utc': T.isoformat()}
    with pytest.raises(ValueError):
        book.promote(future, T, True, verdict)
    with pytest.raises(ValueError):
        book.promote(dict(RECIPE, identity='r2'), T, True, dict(verdict, eligible=False))
    assert book.total_capital_injected == 10000


def test_trial_book_roundtrip_keeps_loss_history_and_capital():
    from src.paper.trials import TrialBook
    book = TrialBook(RECIPE, T)
    book.observe(4990, T)
    book.promote(dict(RECIPE, identity='r2'), T, True,
                 {'eligible': True, 'identity': 'v1', 'selected_recipe_identity': 'r2', 'cutoff_utc': T.isoformat()})
    assert TrialBook.restore(book.capture()).capture() == book.capture()


@pytest.mark.parametrize('case', ['allocation_recipe', 'allocation_trial', 'allocation_capital', 'target_time', 'failure_time', 'active_failed'])
def test_restore_checks_lifecycle_not_only_outer_checksum(case):
    from src.paper.trials import TrialBook
    from src.paper.compact_store import digest
    book = TrialBook(RECIPE, T)
    book.observe(4990, T)
    book.promote(dict(RECIPE, identity='r2'), T, True,
                 {'eligible': True, 'identity': 'v1', 'selected_recipe_identity': 'r2', 'cutoff_utc': T.isoformat()})
    payload = book.capture()
    if case == 'allocation_recipe': payload['allocations']['v1']['recipe_identity'] = 'not-r2'
    elif case == 'allocation_trial': payload['allocations']['v1']['trial_id'] = 'trial-9999'
    elif case == 'allocation_capital': payload['allocations']['v1']['capital_usd'] = True
    elif case == 'target_time': payload['trials'][1]['target_at_utc'] = T.isoformat()
    elif case == 'failure_time': payload['trials'][0]['failed_at_utc'] = (T + timedelta(days=1)).isoformat()
    else: payload['trials'][1]['current_equity_usd'] = 4990
    payload['checksum'] = digest({k: v for k, v in payload.items() if k != 'checksum'})
    with pytest.raises(ValueError):
        TrialBook.restore(payload)


def failed_runner(config):
    from test_paper_causal_runner import runner_fixture, batch
    from test_local_paper_session import BASE
    from src.execution.order_models import OrderRequest
    runner = runner_fixture(config)
    runner.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='LONG', leverage=3,
        signal_price=100, stop_loss_price=99.75, signal_time=BASE, requested_quantity=240))
    narrow = batch(BASE)
    narrow['BTCUSDT'].update(low=99.99, high=100.05)
    runner.advance(narrow)
    assert 'BTCUSDT' in runner.broker.positions, runner.broker.order_history[0].rejection_reasons
    assert runner.broker.positions['BTCUSDT'].quantity == 240
    runner.advance(batch(BASE + timedelta(minutes=15), 60))
    assert runner.broker.equity < 5000
    return runner


def test_real_broker_gap_failure_blocks_entries_and_preserves_funds(config):
    from test_local_paper_session import BASE
    from test_paper_causal_runner import batch
    from src.execution.order_models import OrderRequest
    from src.paper.causal_runner import CausalRunner
    runner = failed_runner(config)
    assert runner.trials.current['status'] == 'FAILED'
    assert runner.trials.current['final_equity_usd'] == runner.broker.equity
    assert runner.trials.total_capital_injected == 10000
    assert len([e for e in runner.trial_events if e['kind'] == 'TRIAL_FAILED']) == 1
    equity = runner.broker.equity
    runner.broker.submit_order(OrderRequest(symbol='ETHUSDT', direction='LONG',
        signal_price=60, stop_loss_price=50, signal_time=BASE + timedelta(minutes=30), requested_quantity=1))
    runner.advance(batch(BASE + timedelta(minutes=30), 60))
    assert not runner.broker.positions
    assert not runner.broker.pending_orders
    assert runner.broker.equity == equity
    restored = CausalRunner.restore(runner.config, runner.capture(), runner.all_inputs(), runner.ledger_events())
    assert restored.trials.capture() == runner.trials.capture()
    assert restored.broker.equity == equity


def test_runner_promotion_cannot_bypass_breaker_or_repeat_allocation(config):
    from src.paper.recipes import recipe_snapshot
    from test_local_paper_session import BASE
    runner = failed_runner(config)
    lock = runner.broker.circuit_breaker.locked_until
    assert lock is not None
    recipe = recipe_snapshot('breakout_retest', runner.config, BASE)
    stamp = BASE + timedelta(minutes=30)
    verdict = {'eligible': True, 'identity': 'literal-internal-fixture-verdict',
               'selected_recipe_identity': recipe['identity'], 'cutoff_utc': stamp.isoformat()}
    old_equity = runner.broker.equity
    runner.promote(recipe, verdict, stamp)
    assert runner.broker.wallet_balance == 10000
    assert runner.broker.circuit_breaker.locked_until == lock
    assert runner.broker.circuit_breaker.is_locked
    assert runner.trials.trials[0]['final_equity_usd'] == old_equity
    assert runner.recipe['strategy_id'] == 'breakout_retest'
    runner.promote(recipe, verdict, stamp)
    assert runner.trials.total_capital_injected == 20000
    assert len(runner.trials.trials) == 2
