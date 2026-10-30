"""Bounded PAPER selection: immutable recipes, one frozen holdout, actual broker."""
from copy import deepcopy
from datetime import timedelta
import math
import time

from src.paper.causal_runner import CausalRunner, validate_bar, stored_bar
from src.paper.compact_store import digest
from src.paper.public_stream import SYMBOLS
from src.paper.recipes import recipe_snapshot
from src.paper.trials import utc, finite
from src.paper.history_source import check_interruption
from src.report.metrics import calculate_trade_metrics, calculate_max_drawdown


def promotion_block_reason(config):
    """No source-backed risk/evidence contract is implemented for automatic promotion.

    A client flag or a profitable diagnostic cannot supply independent evidence.
    Keep the old numeric gates for comparison without authorizing fresh capital.
    """
    if 'paper_funding_model' in config:
        return 'FIXED_SIMULATED_FUNDING_IS_DIAGNOSTIC_ONLY'
    return 'INDEPENDENT_EVIDENCE_AND_DECLARED_RISK_CONTRACT_NOT_CONFIGURED'


def research_windows(cutoff):
    end = utc(cutoff)
    return {'train': (end - timedelta(days=360), end - timedelta(days=180)),
            'validation': (end - timedelta(days=180), end - timedelta(days=90)),
            'holdout': (end - timedelta(days=90), end),
            'folds': [(end - timedelta(days=90 - i * 30), end - timedelta(days=60 - i * 30)) for i in range(3)]}


def _checked_fold(fold):
    if type(fold) is not dict or type(fold.get('completed_positions')) is not int or fold['completed_positions'] < 0:
        raise ValueError('invalid research completed-position count')
    pnl, dd = finite(fold['net_pnl_usd']), finite(fold['max_drawdown_fraction'])
    if not 0 <= dd or (fold['completed_positions'] and not math.isclose(
            finite(fold['net_expectancy_usd']), pnl / fold['completed_positions'], rel_tol=1e-6, abs_tol=1e-4)):
        raise ValueError('invalid/inconsistent research metric')
    if fold['completed_positions'] == 0 and fold['net_expectancy_usd'] is not None:
        raise ValueError('zero-position expectancy must be unknown')
    return all(fold.get(k) is True for k in ('accounting_verified', 'causal_verified', 'risk_verified'))


def promotion_verdict(folds, stressed_folds):
    """Legacy numerical diagnostic only; evaluate_research adds admission checks."""
    if len(folds) != 3 or len(stressed_folds) != 3:
        raise ValueError('research requires three independent temporal accounts per cost run')
    gates = [_checked_fold(f) for f in list(folds) + list(stressed_folds)]
    count = sum(f['completed_positions'] for f in folds)
    sparse = count < 30 or any(f['completed_positions'] < 5 for f in folds)
    pnl = sum(f['net_pnl_usd'] for f in folds)
    checks = {'execution': all(gates), 'sample': not sparse, 'positive_expectancy': pnl > 0,
              'positive_folds': sum(f['net_pnl_usd'] > 0 for f in folds) >= 2,
              'drawdown': all(f['max_drawdown_fraction'] <= .2 for f in folds),
              'doubled_cost_nonnegative': sum(f['net_pnl_usd'] for f in stressed_folds) >= 0}
    eligible = all(checks.values())
    return {'eligible': eligible, 'status': 'ELIGIBLE_PAPER' if eligible else
            'INSUFFICIENT_EVIDENCE' if sparse else 'REJECTED', 'gates': checks,
            'completed_positions': count, 'aggregate_net_pnl_usd': pnl,
            'sample_unit': 'completed_position_lifecycle'}


def _budget(deadline, cancel_event=None):
    check_interruption(cancel_event)
    if time.monotonic() >= deadline:
        raise TimeoutError('bounded paper research evaluation budget exhausted')


def _partition(recipe, inputs, window, deadline, stressed=False, cancel_event=None):
    start, end = window
    cfg = deepcopy(recipe['config'])
    if 'paper_funding_model' in cfg:
        cfg['paper_funding_model']['effective_at_utc'] = start.isoformat()
    if stressed:
        for key in ('taker_pct', 'maker_pct', 'slippage_pct'):
            cfg['fees'][key] *= 2
    # Historical evaluation is retrospective diagnostics; deployment availability
    # is never backdated. The evaluator alone uses frozen formulas on old inputs.
    runner = CausalRunner(cfg, recipe['strategy_id'], start)
    histories, base, execution, signals = {}, {}, {}, {}
    for symbol in SYMBOLS:
        raw = inputs[symbol]
        histories[symbol] = [b for b in raw['4h'] if b['close_time'] <= start][-210:]
        prior = [b for b in raw['15m'] if b['close_time'] == start]
        if len(prior) != 1 or len(histories[symbol]) != 210:
            raise ValueError('research warmup/baseline coverage missing')
        base[symbol] = prior[0]
        execution[symbol] = [b for b in raw['15m'] if start <= b['open_time'] < end]
        if (not execution[symbol] or execution[symbol][0]['open_time'] != start
                or execution[symbol][-1]['close_time'] != end):
            raise ValueError('research partition coverage missing')
        signals[symbol] = {b['close_time']: b for b in raw['4h'] if start < b['close_time'] <= end}
    runner.initialize(histories, base)
    for index, first in enumerate(execution['BTCUSDT']):
        _budget(deadline, cancel_event)
        bars = {s: execution[s][index] for s in SYMBOLS}
        closed = first['close_time']
        signal = {s: signals[s][closed] for s in SYMBOLS} if closed.hour % 4 == 0 and closed.minute == 0 else None
        runner.advance(bars, signal)
        runner.execution_inputs.clear()
    runner.broker.finalize(end, force_close=True)
    runner.broker.verify_accounting_invariants()
    metrics = calculate_trade_metrics(runner.broker.trade_history)
    _, drawdown = calculate_max_drawdown(runner.broker.account_snapshots)
    count = metrics['total_trades']
    # Flat final accounting independently reconciles completed position returns.
    pnl = runner.broker.equity - runner.broker.initial_balance
    if not math.isclose(pnl, metrics['total_net_pnl'], rel_tol=1e-8, abs_tol=1e-4):
        raise ValueError('research completed-position/account equity reconciliation failed')
    return {'completed_positions': count, 'net_pnl_usd': pnl,
            'net_expectancy_usd': pnl / count if count else None, 'max_drawdown_fraction': drawdown / 100,
            'accounting_verified': True, 'causal_verified': True, 'risk_verified': True,
            'range_utc': [start.isoformat(), end.isoformat()], 'config_sha256': digest(cfg),
            'ledger_sha256': digest(runner.ledger_events()), 'sample_unit': metrics['sample_unit'],
            'stressed_costs': stressed}


def evaluate_research(config, catalog, inputs, cutoff, used_intervals, budget_seconds=600, on_holdout_claim=None, cancel_event=None):
    cutoff = utc(cutoff)
    if not 0 < finite(budget_seconds) <= 600 or len(catalog) > 8:
        raise ValueError('invalid paper research budget/catalog size')
    windows = research_windows(cutoff)
    result = {'eligible': False, 'cutoff_utc': cutoff.isoformat(),
              'windows': {k: [[a.isoformat(), b.isoformat()] for a, b in v] if k == 'folds'
                          else [v[0].isoformat(), v[1].isoformat()] for k, v in windows.items()},
              'holdout_consumed': False, 'label': 'RETROSPECTIVE_PAPER_DIAGNOSTICS',
              'independent_review': 'NOT_VERIFIED'}

    def finish(status, **details):
        final = {**result, 'status': status, **details}
        return {**final, 'identity': digest(final)}

    causal = [r for r in catalog if utc(r['available_at_utc']) <= cutoff]
    if not causal:
        return finish('NO_CAUSAL_CANDIDATE')
    start, end = windows['holdout']
    if any(utc(a) < end and start < utc(b) for a, b in used_intervals):
        return finish('HOLDOUT_ALREADY_USED')
    deadline = time.monotonic() + budget_seconds
    try:
        checked = {}
        for symbol in SYMBOLS:
            checked[symbol] = {}
            for interval in ('4h', '15m'):
                checked[symbol][interval] = [validate_bar(b, symbol, interval) for b in inputs[symbol][interval]
                                              if utc(b['close_time']) <= cutoff]
                bars = checked[symbol][interval]
                if any(b['open_time'] != a['close_time'] for a, b in zip(bars, bars[1:])):
                    raise ValueError('research data is not chronological/complete')
        result['data_sha256'] = digest({s: {i: [stored_bar(b) for b in bars] for i, bars in tf.items()}
                                        for s, tf in checked.items()})
        rankings = []
        for recipe in sorted(causal, key=lambda r: r['identity']):
            _budget(deadline, cancel_event)
            frozen = recipe_snapshot(recipe['strategy_id'], recipe['config'], utc(recipe['available_at_utc']))
            if frozen != recipe or recipe['config'] != config:
                raise ValueError('research recipe/config identity changed')
            options = {'cancel_event': cancel_event} if cancel_event is not None else {}
            training = _partition(recipe, checked, windows['train'], deadline, **options)
            validation = _partition(recipe, checked, windows['validation'], deadline, **options)
            rankings.append({'recipe': recipe, 'training': training, 'validation': validation})
        viable = [r for r in rankings if r['validation']['completed_positions'] > 0]
        result['candidate_diagnostics'] = rankings
        if not viable:
            return finish('INSUFFICIENT_EVIDENCE')
        chosen = sorted(viable, key=lambda r: (-r['validation']['net_expectancy_usd'],
                                             r['validation']['max_drawdown_fraction'], r['recipe']['identity']))[0]
        recipe = chosen['recipe']
        result['selected_recipe_identity'] = recipe['identity']
        # Claim this interval before looking at any final fold. No runner-up retry.
        result['holdout_consumed'] = True
        result['holdout_interval_utc'] = [start.isoformat(), end.isoformat()]
        if on_holdout_claim is not None:
            on_holdout_claim({'key': 'holdout-claim:' + digest([start.isoformat(), end.isoformat()]),
                              'kind': 'RESEARCH_HOLDOUT_CLAIM', 'selected_recipe_identity': recipe['identity'],
                              'cutoff_utc': cutoff.isoformat(), 'data_sha256': result['data_sha256'],
                              'holdout_interval_utc': result['holdout_interval_utc']})
        folds = [_partition(recipe, checked, window, deadline, **options) for window in windows['folds']]
        stressed = [_partition(recipe, checked, window, deadline, stressed=True, **options) for window in windows['folds']]
        verdict = promotion_verdict(folds, stressed)
        reason = promotion_block_reason(config)
        return finish('NOT_ELIGIBLE' if reason else verdict['status'],
                      **{k: v for k, v in verdict.items() if k not in ('status', 'eligible')},
                      eligible=bool(verdict['eligible'] and reason is None), diagnostics=verdict,
                      promotion_block_reason=reason, historical_verified=False,
                      risk_contract_status='NOT_EVALUATED',
                      folds=folds, stressed_folds=stressed)
    except TimeoutError as exc:
        return finish('BUDGET_EXHAUSTED', reason=str(exc))
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return finish('DATA_OR_EXECUTION_BLOCKED', reason=str(exc))
