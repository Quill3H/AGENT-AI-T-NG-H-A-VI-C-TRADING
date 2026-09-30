from datetime import datetime, timezone

import pytest


def test_snapshot_is_frozen_and_changes_with_cost_and_risk(config):
    from src.paper.recipes import recipe_snapshot
    when = datetime(2026, 10, 1, tzinfo=timezone.utc)
    snapshot = recipe_snapshot('trend_following', config, when)
    same = recipe_snapshot('trend_following', config, when)
    assert snapshot == same
    config['fees']['taker_pct'] *= 2
    assert snapshot['config']['fees']['taker_pct'] == 0.0005
    assert snapshot['identity'] != recipe_snapshot('trend_following', config, when)['identity']
    config['risk']['max_leverage'] = 4
    assert same['config']['risk']['max_leverage'] == 5
    assert snapshot['formula_version'] == 'pandas-fallback-v1'


def test_recipe_rejects_naive_availability_and_unregistered_code(config):
    from src.paper.recipes import recipe_snapshot
    with pytest.raises(ValueError):
        recipe_snapshot('trend_following', config, datetime(2026, 10, 1))
    with pytest.raises(ValueError):
        recipe_snapshot('funding_arbitrage', config, datetime.now(timezone.utc))


def test_registered_adapter_returns_actual_breakout_rulebook(config):
    from src.paper.recipes import make_strategy
    from src.strategies.breakout_retest import BreakoutRetestStrategy
    strategy = make_strategy('breakout_retest', config, 'ETHUSDT')
    assert isinstance(strategy, BreakoutRetestStrategy)
    assert strategy.symbol == 'ETHUSDT'
