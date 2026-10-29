"""
src/research/ml/gates.py
========================
Gate D of the ML study (design §8), with every threshold fixed here before any dev run. Gate D
runs on seen data, so it can only reject a candidate or let it go to forward paper (gate P, which
model_governance.promotion_decision implements). Gate F was dropped by the owner on 2026-10-23
(no ALGO/VET/SAND final); evidence comes from forward paper only.

A check that cannot be computed is NOT_EVALUATED and blocks the verdict like a FAIL.
"""
import math

import numpy as np
import pandas as pd

from src.research.ml import stats
from src.research.model_governance import max_drawdown

BANK_ANNUAL = 0.059
K_MAX = 24
DSR_MIN = 0.95
PBO_MAX = 0.25
OOS_LOSS_MAX = 0.10  # D4 alternative when the configurations are equally good (see gate_d)
PERM_P_MAX = 0.01
PERM_MIN_REPS = 200
BOOT_REPS = 5000
BOOT_BLOCK_DAYS = 20
IC_MIN = 0.02
IC_T_MIN = 2.0
COIN_SHARE_MAX = 0.30
TOP5_SHARE_MAX = 0.50
YEAR_SHARE_MIN = 0.75  # positive in at least 3 of 4 calendar years

PASS, FAIL, NOT_EVALUATED = "PASS", "FAIL", "NOT_EVALUATED"
NA = NOT_EVALUATED


def annual_return(daily):
    r = np.asarray(daily, dtype=float)
    if len(r) == 0:
        return 0.0
    return float(np.prod(1 + r) ** (365.0 / len(r)) - 1)


def _equity(daily):
    return np.concatenate([[1.0], np.cumprod(1 + np.asarray(daily, dtype=float))])


def ret_over_dd(daily):
    dd = max_drawdown(_equity(daily))
    return annual_return(daily) / dd if dd > 0 else math.inf


def _status(ok):
    return PASS if ok else FAIL


def gate_d(daily, daily_cost2x, trial_matrix, null_sharpes, monthly_ic, profit_by_symbol, trade_pnls,
           c1_daily=None, simple_daily=None, boot_reps=BOOT_REPS, seed=0):
    """Evaluate D1-D8. daily / daily_cost2x / c1_daily / simple_daily: pd.Series of daily returns
    (calendar days, zero on flat days). trial_matrix: DataFrame (days x configurations actually
    run, selected one included). null_sharpes: daily Sharpes of the permutation runs."""
    out = {}
    out["D1_return"] = _status(annual_return(daily) >= BANK_ANNUAL and annual_return(daily_cost2x) > 0)
    if c1_daily is None:
        out["D2_vs_C1"] = NA
    else:
        a, b = daily.align(c1_daily, join="inner", fill_value=0.0)
        out["D2_vs_C1"] = _status(ret_over_dd(a) >= ret_over_dd(b) and stats.sharpe(a) >= stats.sharpe(b))
    k = trial_matrix.shape[1]
    if k > K_MAX:
        out["D3_dsr"] = FAIL  # the budget itself was broken
    else:
        srs = [stats.sharpe(trial_matrix[c].dropna()) for c in trial_matrix.columns]
        dsr = stats.deflated_sharpe(daily.to_numpy(), srs, n_trials=max(k, 2))
        out["D3_dsr"] = NA if dsr is None else _status(dsr >= DSR_MIN)
    # PBO sits near 0.5 when every configuration has the same real edge (the in-sample pick is a
    # coin flip among equals), as the synthetic self-test showed; D4 therefore also passes when the
    # in-sample pick keeps a positive out-of-sample Sharpe in at least 90% of the CSCV splits.
    if k < 2:
        out["D4_pbo"] = NA
    else:
        pbo = stats.pbo_cscv(trial_matrix.fillna(0.0).to_numpy())
        out["D4_pbo"] = _status(pbo["pbo"] <= PBO_MAX or pbo["prob_oos_loss"] <= OOS_LOSS_MAX)
    if len(null_sharpes) < PERM_MIN_REPS:
        out["D5_permutation"] = NA
    else:
        out["D5_permutation"] = _status(stats.permutation_p_value(stats.sharpe(daily), null_sharpes) <= PERM_P_MAX)
    if simple_daily is None:
        out["D6_vs_simple"] = NA
    else:
        a, b = daily.align(simple_daily, join="inner", fill_value=0.0)
        diffs = stats.bootstrap(lambda x, y: stats.sharpe(x) - stats.sharpe(y), (a.to_numpy(), b.to_numpy()),
                                mean_block=BOOT_BLOCK_DAYS, reps=boot_reps, seed=seed)
        out["D6_vs_simple"] = _status(np.quantile(diffs, 0.05) > 0)
    yearly = daily.groupby(pd.DatetimeIndex(daily.index).year).apply(lambda r: float(np.prod(1 + r) - 1))
    total = sum(v for v in profit_by_symbol.values())
    coin_share = max(profit_by_symbol.values()) / total if total > 0 else math.inf
    pnls = np.sort(np.asarray(trade_pnls, dtype=float))[::-1]
    top5 = pnls[:5].sum() / pnls.sum() if pnls.sum() > 0 else math.inf
    out["D7_stability"] = _status((yearly > 0).mean() >= YEAR_SHARE_MIN and coin_share <= COIN_SHARE_MAX
                                  and top5 <= TOP5_SHARE_MAX)
    ic = np.asarray(monthly_ic, dtype=float)
    out["D8_ic"] = NA if len(ic) < 12 else _status(ic.mean() >= IC_MIN and stats.newey_west_t(ic) >= IC_T_MIN)
    out["verdict"] = PASS if all(v == PASS for v in out.values()) else FAIL
    return out
