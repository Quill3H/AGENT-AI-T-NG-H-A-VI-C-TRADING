"""Fail-closed economic eligibility; no function here grants owner acceptance."""
import math
from numbers import Real
import re


def _finite(value):
    return not isinstance(value, bool) and isinstance(value, Real) and math.isfinite(value)


def evaluate_acceptance(metrics, *, data_provenance, risk_contract=None):
    """Evaluate an explicit risk contract without mistaking a replay for validation.

    Provenance must already have been checked against input bytes by the loader.
    This additional check cannot authenticate a caller's arbitrary manifest.
    """
    reasons = []
    if not isinstance(metrics, dict):
        return dict(verdict='REJECTED', reasons=['INVALID_METRICS'])
    provenance = data_provenance if isinstance(data_provenance, dict) else {}
    datasets = provenance.get('datasets')
    if (provenance.get('mode') != 'historical' or provenance.get('historical_verified') is not True
            or not isinstance(provenance.get('source'), str) or not provenance['source'].strip()
            or not isinstance(datasets, list) or not datasets
            or any(not isinstance(d, dict) or not isinstance(d.get('sha256'), str)
                   or re.fullmatch(r'[0-9a-fA-F]{64}', d['sha256']) is None
                   or not isinstance(d.get('source'), str) or not d['source'].strip() for d in datasets)):
        reasons.append('HISTORICAL_PROVENANCE_REQUIRED')

    fields = {
        'total_net_pnl': ('total_net_pnl', 'net_profit_usd'),
        'expectancy_usd': ('expectancy_usd',),
        'profit_factor': ('profit_factor',),
        'max_drawdown_pct': ('max_drawdown_pct', 'max_drawdown_percent'),
        'total_trades': ('total_trades', 'completed_trades'),
        'initial_equity': ('initial_equity', 'initial_equity_usd', 'initial_capital'),
        'final_equity': ('final_equity', 'final_equity_usd'),
    }
    values = {}
    for name, aliases in fields.items():
        value = next((metrics[a] for a in aliases if a in metrics), None)
        if not _finite(value):
            reasons.append('INVALID_' + name.upper())
        else:
            values[name] = value
    for name, reason in (('total_net_pnl', 'NONPOSITIVE_NET_PNL'),
                         ('expectancy_usd', 'NONPOSITIVE_EXPECTANCY'),
                         ('initial_equity', 'NONPOSITIVE_INITIAL_EQUITY'),
                         ('final_equity', 'NONPOSITIVE_FINAL_EQUITY')):
        if name in values and values[name] <= 0:
            reasons.append(reason)
    if 'profit_factor' in values and values['profit_factor'] <= 1:
        reasons.append('PROFIT_FACTOR_NOT_ABOVE_ONE')
    if 'max_drawdown_pct' in values and not 0 <= values['max_drawdown_pct'] <= 100:
        reasons.append('INVALID_MAX_DRAWDOWN_PCT')
    count = values.get('total_trades')
    if count is not None and (int(count) != count or count <= 0):
        reasons.append('INVALID_TOTAL_TRADES')

    contract_ok = isinstance(risk_contract, dict)
    ceiling = risk_contract.get('max_drawdown_pct') if contract_ok else None
    minimum = risk_contract.get('min_completed_trades', 1) if contract_ok else 1
    contract_ok = (contract_ok and _finite(ceiling) and 0 < ceiling < 100
                   and type(minimum) is int and minimum > 0)
    if contract_ok:
        if 'max_drawdown_pct' in values and values['max_drawdown_pct'] > ceiling:
            reasons.append('DRAWDOWN_LIMIT_EXCEEDED')
        if count is not None and count < minimum:
            reasons.append('INSUFFICIENT_COMPLETED_TRADES')
    if reasons:
        if not contract_ok:
            reasons.append('RISK_CONTRACT_REQUIRED')
        return dict(verdict='REJECTED', reasons=reasons)
    if not contract_ok:
        return dict(verdict='NOT_EVALUATED', reasons=['RISK_CONTRACT_REQUIRED'])
    return dict(verdict='ELIGIBLE_FOR_REVIEW', reasons=[])
