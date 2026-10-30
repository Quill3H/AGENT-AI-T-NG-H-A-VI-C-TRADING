"""Economic eligibility is separate from a successful engineering replay."""
import copy

import pytest

from src.research.acceptance import evaluate_acceptance


def valid_inputs():
    return (
        dict(total_net_pnl=100., expectancy_usd=2., profit_factor=1.5,
             max_drawdown_pct=3., total_trades=50, initial_equity=1000., final_equity=1100.),
        dict(mode='historical', historical_verified=True, source='binance_usdm',
             datasets=[dict(sha256='a' * 64, source='checksummed_fixture')]),
        dict(max_drawdown_pct=10., min_completed_trades=30),
    )


def test_good_metrics_only_make_a_candidate_eligible_for_review():
    metrics, provenance, contract = valid_inputs()
    assert evaluate_acceptance(metrics, data_provenance=provenance,
                               risk_contract=contract) == dict(verdict='ELIGIBLE_FOR_REVIEW', reasons=[])


def test_original_losing_path_is_rejected_despite_high_win_rate():
    metrics, provenance, contract = valid_inputs()
    metrics.update(total_net_pnl=-91280.33, expectancy_usd=-14.141,
                   profit_factor=.7504, max_drawdown_pct=92.6019, win_rate=49.20,
                   final_equity=8719.67, initial_equity=100000.)
    result = evaluate_acceptance(metrics, data_provenance=provenance, risk_contract=contract)
    assert result['verdict'] == 'REJECTED'
    assert {'NONPOSITIVE_NET_PNL', 'NONPOSITIVE_EXPECTANCY', 'PROFIT_FACTOR_NOT_ABOVE_ONE',
            'DRAWDOWN_LIMIT_EXCEEDED'} <= set(result['reasons'])


def test_synthetic_cannot_become_historical_by_good_performance():
    metrics, provenance, contract = valid_inputs()
    provenance.update(mode='synthetic', historical_verified=False)
    assert evaluate_acceptance(metrics, data_provenance=provenance,
                               risk_contract=contract)['verdict'] == 'REJECTED'


def test_no_declared_risk_contract_does_not_invent_a_drawdown_ceiling():
    metrics, provenance, _ = valid_inputs()
    result = evaluate_acceptance(metrics, data_provenance=provenance)
    assert result['verdict'] == 'NOT_EVALUATED'
    assert 'RISK_CONTRACT_REQUIRED' in result['reasons']


@pytest.mark.parametrize('field,value', [('total_net_pnl', True), ('expectancy_usd', float('nan')),
                                      ('profit_factor', float('inf')), ('max_drawdown_pct', -1),
                                      ('total_trades', 1.5), ('final_equity', 0)])
def test_invalid_metrics_fail_closed(field, value):
    metrics, provenance, contract = valid_inputs()
    metrics[field] = value
    assert evaluate_acceptance(metrics, data_provenance=provenance,
                               risk_contract=contract)['verdict'] == 'REJECTED'


@pytest.mark.parametrize('contract', [{}, {'max_drawdown_pct': True},
                                    {'max_drawdown_pct': 95, 'min_completed_trades': False},
                                    {'max_drawdown_pct': float('nan')}])
def test_malformed_contract_cannot_pass(contract):
    metrics, provenance, _ = valid_inputs()
    assert evaluate_acceptance(metrics, data_provenance=provenance,
                               risk_contract=contract)['verdict'] != 'ELIGIBLE_FOR_REVIEW'


def test_hashless_or_unverified_provenance_cannot_pass_and_inputs_are_not_mutated():
    metrics, provenance, contract = valid_inputs()
    provenance['datasets'][0]['sha256'] = 'not-a-hash'
    before = copy.deepcopy((metrics, provenance, contract))
    assert evaluate_acceptance(metrics, data_provenance=provenance,
                               risk_contract=contract)['verdict'] == 'REJECTED'
    assert before == (metrics, provenance, contract)


def test_insufficient_lifecycles_does_not_force_extra_trades():
    metrics, provenance, contract = valid_inputs()
    metrics['total_trades'] = 2
    result = evaluate_acceptance(metrics, data_provenance=provenance, risk_contract=contract)
    assert result['verdict'] == 'REJECTED'
    assert 'INSUFFICIENT_COMPLETED_TRADES' in result['reasons']
