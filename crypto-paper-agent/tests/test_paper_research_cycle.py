from datetime import datetime, timedelta, timezone

import pytest


T = datetime(2026, 10, 1, tzinfo=timezone.utc)


def fold(count=10, pnl=100, dd=0.1):
    return {'completed_positions': count, 'net_pnl_usd': pnl,
            'net_expectancy_usd': pnl / count if count else None, 'max_drawdown_fraction': dd,
            'accounting_verified': True, 'causal_verified': True, 'risk_verified': True}


def test_half_open_chronological_research_windows():
    from src.paper.research_cycle import research_windows
    windows = research_windows(T)
    assert windows['train'] == (T - timedelta(days=360), T - timedelta(days=180))
    assert windows['validation'] == (T - timedelta(days=180), T - timedelta(days=90))
    assert windows['holdout'] == (T - timedelta(days=90), T)
    assert len(windows['folds']) == 3
    assert windows['folds'][0][1] == windows['folds'][1][0]
    assert windows['folds'][2][1] == T


def test_promotion_numeric_gates_have_real_strict_boundaries():
    from src.paper.research_cycle import promotion_verdict
    good = [fold(), fold(), fold()]
    assert promotion_verdict(good, [fold(pnl=0)] * 3)['eligible'] is True
    assert promotion_verdict([fold(4), fold(13), fold(13)], good)['status'] == 'INSUFFICIENT_EVIDENCE'
    assert promotion_verdict([fold(9)] * 3, good)['eligible'] is False
    assert promotion_verdict([fold(dd=0.20001)] * 3, good)['eligible'] is False
    assert promotion_verdict(good, [fold(pnl=-1)] * 3)['eligible'] is False
    assert promotion_verdict([fold(pnl=-1)] * 3, good)['eligible'] is False


@pytest.mark.parametrize('bad', [True, float('nan'), float('inf')])
def test_malformed_research_metric_is_fail_closed(bad):
    from src.paper.research_cycle import promotion_verdict
    value = fold()
    value['net_pnl_usd'] = bad
    with pytest.raises(ValueError):
        promotion_verdict([value, fold(), fold()], [fold()] * 3)


def test_unavailable_recipe_and_used_holdout_block_before_evaluation(config):
    from src.paper.research_cycle import evaluate_research
    candidate = {'strategy_id': 'trend_following', 'identity': 'r1', 'available_at_utc': (T + timedelta(days=1)).isoformat(), 'config': config}
    result = evaluate_research(config, [candidate], {}, T, [])
    assert result['status'] == 'NO_CAUSAL_CANDIDATE'
    candidate['available_at_utc'] = (T - timedelta(days=400)).isoformat()
    result = evaluate_research(config, [candidate], {}, T, [(T - timedelta(days=90), T)])
    assert result['status'] == 'HOLDOUT_ALREADY_USED'
    assert result['eligible'] is False


@pytest.mark.parametrize('stressed', [False, True])
def test_real_shared_account_fold_zero_trades_reconciles_and_cost_contract(config, stressed):
    import time
    from copy import deepcopy
    from test_paper_causal_runner import runner_fixture, batch
    from test_local_paper_session import BASE
    from src.paper.research_cycle import _partition
    runner = runner_fixture(config)
    inputs = {s: {'4h': deepcopy(runner.signal_history[s]),
                  '15m': [batch(BASE - timedelta(minutes=15))[s], batch(BASE)[s],
                           batch(BASE + timedelta(minutes=15))[s]]} for s in runner.strategies}
    result = _partition(runner.recipe, inputs, (BASE, BASE + timedelta(minutes=30)), time.monotonic() + 10, stressed)
    assert result['net_pnl_usd'] == 0
    assert result['completed_positions'] == 0
    assert result['net_expectancy_usd'] is None
    assert result['accounting_verified'] is True
    assert result['stressed_costs'] is stressed


@pytest.mark.parametrize('short', [False, True])
def test_actual_recipe_shared_fold_breakout_retest_fill_exit_and_costs(config, short):
    import time
    from copy import deepcopy
    from src.paper.causal_runner import validate_bar
    from src.paper.recipes import recipe_snapshot
    from src.paper.research_cycle import _partition
    from test_paper_causal_runner import runner_fixture, batch
    from test_local_paper_session import BASE
    seed = runner_fixture(config)
    seed.config['fees'] = {'taker_pct': .0005, 'maker_pct': .0002, 'slippage_pct': .0003}
    inputs = {s: {'4h': deepcopy(seed.signal_history[s]),
                  '15m': [batch(BASE - timedelta(minutes=15))[s]]} for s in seed.strategies}
    for symbol in inputs:
        opened_price = 100.
        for group, (closed_price, high, low, volume) in enumerate([(104.,105.,99.,10.), (102.,105.,100.,.5), (108.,109.,101.,5.)]):
            pieces = []
            for n in range(16):
                opened = BASE + timedelta(hours=4 * group, minutes=15 * n)
                first, last = opened_price, closed_price
                h, l = high, low
                if short: first, last, h, l = 200-first, 200-last, 200-low, 200-high
                bar = validate_bar(dict(open_time=opened, close_time=opened + timedelta(minutes=15),
                    open=first, high=h, low=l, close=last, volume=volume), symbol, '15m')
                pieces.append(bar)
                opened_price = closed_price
            inputs[symbol]['15m'].extend(pieces)
            inputs[symbol]['4h'].append(validate_bar(dict(open_time=pieces[0]['open_time'], close_time=pieces[-1]['close_time'],
                open=pieces[0]['open'], high=max(b['high'] for b in pieces), low=min(b['low'] for b in pieces),
                close=pieces[-1]['close'], volume=sum(b['volume'] for b in pieces)), symbol, '4h'))
    recipe = recipe_snapshot('breakout_retest', seed.config, BASE)
    result = _partition(recipe, inputs, (BASE, BASE + timedelta(hours=12)), time.monotonic()+30)
    stressed = _partition(recipe, inputs, (BASE, BASE + timedelta(hours=12)), time.monotonic()+30, stressed=True)
    assert result['completed_positions'] == 1
    assert result['net_pnl_usd'] > 0
    assert result['net_pnl_usd'] > stressed['net_pnl_usd']
    assert result['accounting_verified'] is True
    assert result['sample_unit'] == 'completed_position_lifecycle'
    altered = deepcopy(inputs)
    for symbol in altered:
        future = dict(altered[symbol]['15m'][-1], open_time=BASE + timedelta(days=1),
                      close_time=BASE + timedelta(days=1, minutes=15), open=1e6, high=2e6, low=1., close=1e6)
        altered[symbol]['15m'].append(future)
    assert _partition(recipe, altered, (BASE, BASE + timedelta(hours=12)), time.monotonic()+30) == result


def test_missing_research_history_is_blocked_not_eligible(config):
    from src.paper.recipes import recipe_snapshot
    from src.paper.research_cycle import evaluate_research
    recipe = recipe_snapshot('trend_following', config, T - timedelta(days=400))
    result = evaluate_research(config, [recipe], {}, T, [])
    assert result['status'] == 'DATA_OR_EXECUTION_BLOCKED'
    assert result['eligible'] is False
    assert result['holdout_consumed'] is False


def test_selection_is_frozen_and_holdout_claim_precedes_any_final_fold(config, monkeypatch):
    from src.paper import research_cycle as module
    from src.paper.recipes import recipe_snapshot
    from test_paper_causal_runner import runner_fixture
    first = recipe_snapshot('trend_following', config, T - timedelta(days=400))
    second = recipe_snapshot('breakout_retest', config, T - timedelta(days=400))
    warm = runner_fixture(config).signal_history
    inputs = {s: {'4h': bars, '15m': []} for s, bars in warm.items()}
    steps, claimed = [], []
    windows = module.research_windows(T)
    def partition(recipe, inputs, window, deadline, stressed=False):
        steps.append((recipe['identity'], window, stressed))
        if window in windows['folds']:
            assert claimed and claimed[0]['selected_recipe_identity'] == first['identity']
            return fold(pnl=-10)  # Fails; the runner-up must never see this holdout.
        return fold(pnl=200 if recipe['identity'] == first['identity'] else 100)
    monkeypatch.setattr(module, '_partition', partition)
    result = module.evaluate_research(config, [first, second], inputs, T, [], on_holdout_claim=claimed.append)
    assert result['eligible'] is False
    assert result['holdout_consumed'] is True
    assert result['selected_recipe_identity'] == first['identity']
    assert len(claimed) == 1
    assert all(identity == first['identity'] for identity, window, _ in steps if window in windows['folds'])


def test_holdout_claim_commit_failure_blocks_evaluation(config, monkeypatch):
    from src.paper import research_cycle as module
    from src.paper.recipes import recipe_snapshot
    from test_paper_causal_runner import runner_fixture
    recipe = recipe_snapshot('trend_following', config, T - timedelta(days=400))
    inputs = {s: {'4h': bars, '15m': []} for s, bars in runner_fixture(config).signal_history.items()}
    windows = module.research_windows(T)
    def partition(recipe, inputs, window, deadline, stressed=False):
        assert window not in windows['folds'], 'final holdout was inspected before durable claim'
        return fold()
    def commit(claim):
        raise OSError('fixture holdout claim disk failure')
    monkeypatch.setattr(module, '_partition', partition)
    with pytest.raises(OSError, match='disk failure'):
        module.evaluate_research(config, [recipe], inputs, T, [], on_holdout_claim=commit)


@pytest.mark.parametrize('persisted', [False, True])
def test_claimed_eligible_verdict_cannot_allocate_capital_without_evidence_contract(tmp_path, persisted):
    from test_paper_replay_recovery import create
    session, _ = create(tmp_path)
    try:
        capital = session.runner.trials.total_capital_injected
        events = session._all_events()
        # Neither a response flag nor a saved response is independent evidence.
        verdict = {'eligible': True, 'historical_verified': True, 'status': 'ELIGIBLE_PAPER'}
        with pytest.raises(ValueError, match='independent evidence.*risk contract'):
            session._checked_research_recipe(verdict, persisted=persisted)
        assert session.runner.trials.total_capital_injected == capital
        assert session._all_events() == events
        state = session.state()
        assert state['research']['automatic_promotion_connected'] is False
        assert state['research']['historical_verified'] is False
    finally:
        session.shutdown()
