"""Current-main risk configuration survives data-only paper recovery."""
from copy import deepcopy
from datetime import timedelta

import pytest

from src.paper.recovery_state import pack, unpack


@pytest.mark.parametrize('value', [timedelta(minutes=60), timedelta(microseconds=1),
                                  timedelta(days=-1, microseconds=17)])
def test_duration_checkpoint_is_exact_data_only(value):
    assert unpack(pack(value)) == value


@pytest.mark.parametrize('raw', [True, 1.5, '60', float('inf')])
def test_duration_checkpoint_rejects_non_integer_microseconds(raw):
    with pytest.raises(ValueError):
        unpack({'kind': 'duration', 'microseconds': raw})


def test_compact_restore_rejects_changed_gap_policy(config):
    from src.paper.causal_runner import CausalRunner
    from test_paper_causal_runner import runner_fixture
    runner = runner_fixture(config)
    saved = runner.capture()
    changed = deepcopy(saved)
    changed['broker']['value']['max_data_gap'] = pack(timedelta(days=365))
    with pytest.raises(ValueError, match='configuration|static'):
        CausalRunner.restore(runner.config, changed, runner.all_inputs(), runner.ledger_events())


@pytest.mark.parametrize('fixed', [False, True])
def test_positive_paper_diagnostics_cannot_authorize_promotion(config, monkeypatch, fixed):
    from src.paper import research_cycle
    from src.paper.recipes import recipe_snapshot
    from test_paper_causal_runner import runner_fixture
    from test_paper_research_cycle import fold, T
    from test_fixed_simulated_funding import fixed_config
    cfg = fixed_config(config) if fixed else config
    recipe = recipe_snapshot('trend_following', cfg, T - timedelta(days=400))
    inputs = {s: {'4h': bars, '15m': []}
              for s, bars in runner_fixture(cfg).signal_history.items()}
    monkeypatch.setattr(research_cycle, '_partition', lambda *args, **kwargs: fold())
    verdict = research_cycle.evaluate_research(cfg, [recipe], inputs, T, [])
    assert verdict['eligible'] is False
    assert verdict['status'] == 'NOT_ELIGIBLE'
    assert verdict['diagnostics']['eligible'] is True
    assert verdict['historical_verified'] is False
    assert verdict['risk_contract_status'] == 'NOT_EVALUATED'
    assert verdict['promotion_block_reason']
