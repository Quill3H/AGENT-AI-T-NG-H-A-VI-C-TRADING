"""
src/research/ml/stats.py
========================
Overfitting controls for the ML study (design §7): Deflated Sharpe, PBO by CSCV, stationary block
bootstrap, block label permutation and information coefficient with a Newey-West t-stat.
PSR itself comes from src/research/model_governance.py, so there is one implementation.
"""
import itertools
import math
import statistics

import numpy as np
import pandas as pd

from src.research.model_governance import probabilistic_sharpe

_N = statistics.NormalDist()
EULER_GAMMA = 0.5772156649


def sharpe(returns):
    r = np.asarray(returns, dtype=float)
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    return float(r.mean() / sd) if sd > 0 else 0.0


def expected_max_sharpe(trials, var_sharpe):
    """Expected maximum per-period Sharpe of `trials` skill-less strategies whose Sharpe
    estimates have variance `var_sharpe` (Bailey & Lopez de Prado 2014)."""
    if trials < 2:
        return 0.0
    return math.sqrt(var_sharpe) * ((1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / trials)
                                    + EULER_GAMMA * _N.inv_cdf(1 - 1 / (trials * math.e)))


def deflated_sharpe(returns, trial_sharpes, n_trials=None):
    """DSR: PSR of `returns` against the expected max Sharpe of the trials actually run.
    `trial_sharpes` are the per-period Sharpes of every configuration tried (selected one
    included); n_trials defaults to their count and may be raised (e.g. project-wide trials)."""
    srs = np.asarray(trial_sharpes, dtype=float)
    k = n_trials or len(srs)
    var = float(srs.var(ddof=1)) if len(srs) > 1 else 1.0 / max(len(returns), 2)
    return probabilistic_sharpe(returns, expected_max_sharpe(k, var))


def pbo_cscv(matrix, n_blocks=16):
    """Probability of backtest overfitting (Bailey, Borwein, Lopez de Prado & Zhu 2017).

    matrix: T x K per-period returns of K configurations on the same dates. Rows are cut into
    n_blocks; for every half/half combination the in-sample best configuration's out-of-sample
    rank gives a logit; PBO is the share of logits <= 0 (best IS at or below the OOS median).
    prob_oos_loss is the share of combinations where that selected configuration has a negative
    out-of-sample Sharpe (the paper's "probability of loss").
    """
    m = np.asarray(matrix, dtype=float)
    if m.ndim != 2 or m.shape[1] < 2:
        raise ValueError("need a T x K matrix with K >= 2")
    blocks = np.array_split(np.arange(m.shape[0]), n_blocks)
    logits, losses = [], []
    for is_ids in itertools.combinations(range(n_blocks), n_blocks // 2):
        is_rows = np.concatenate([blocks[b] for b in is_ids])
        oos_rows = np.concatenate([blocks[b] for b in range(n_blocks) if b not in is_ids])
        is_sr = np.array([sharpe(m[is_rows, j]) for j in range(m.shape[1])])
        oos_sr = np.array([sharpe(m[oos_rows, j]) for j in range(m.shape[1])])
        best = int(np.argmax(is_sr))
        rank = (oos_sr < oos_sr[best]).sum() + 0.5 * ((oos_sr == oos_sr[best]).sum() - 1) + 1
        w = rank / (m.shape[1] + 1)
        logits.append(math.log(w / (1 - w)))
        losses.append(oos_sr[best] < 0)
    logits = np.asarray(logits)
    return {"pbo": float((logits <= 0).mean()), "prob_oos_loss": float(np.mean(losses)), "logits": logits}


def stationary_bootstrap_indices(n, mean_block, rng):
    """One resample of positions 0..n-1 (Politis & Romano 1994): blocks of geometric length
    with the given mean, wrapping around the end."""
    p = 1.0 / mean_block
    idx = np.empty(n, dtype=int)
    idx[0] = rng.integers(n)
    restart = rng.random(n) < p
    starts = rng.integers(n, size=n)
    for i in range(1, n):
        idx[i] = starts[i] if restart[i] else (idx[i - 1] + 1) % n
    return idx


def bootstrap(stat, series, mean_block=20, reps=5000, seed=0):
    """Distribution of stat(*resampled series) with the same positions for every series (so a
    paired difference keeps its dependence). series: one array or a tuple of equal-length arrays."""
    arrays = series if isinstance(series, tuple) else (series,)
    arrays = tuple(np.asarray(a, dtype=float) for a in arrays)
    rng = np.random.default_rng(seed)
    n = len(arrays[0])
    return np.array([stat(*(a[idx] for a in arrays))
                     for idx in (stationary_bootstrap_indices(n, mean_block, rng) for _ in range(reps))])


def block_permute(labels, times, groups, block=pd.Timedelta(days=30), rng=None):
    """Labels shuffled in whole calendar blocks within each group (symbol): autocorrelation inside
    a block survives, the link between features and labels does not."""
    rng = rng or np.random.default_rng(0)
    labels = np.asarray(labels)
    out = labels.copy()
    times, groups = pd.DatetimeIndex(times), np.asarray(groups)
    origin = times.min()
    block_id = ((times - origin) // block).astype(int)
    for g in np.unique(groups):
        pos = np.flatnonzero(groups == g)
        ids = np.unique(block_id[pos])
        chunks = [pos[block_id[pos] == b] for b in ids]
        donors = [chunks[i] for i in rng.permutation(len(chunks))]
        for target, donor in zip(chunks, donors):
            take = labels[donor]
            out[target] = take[np.arange(len(target)) % len(take)]
    return out


def permutation_p_value(observed, null_stats):
    null = np.asarray(null_stats, dtype=float)
    return float((1 + (null >= observed).sum()) / (1 + len(null)))


def information_coefficients(frame, period="MS"):
    """Spearman rank correlation of prediction and realised return per calendar period.
    frame columns: time, pred, ret."""
    times = pd.DatetimeIndex(frame["time"])
    f = frame.assign(period=(times.tz_convert(None) if times.tz is not None else times).to_period(period[0]))
    return f.groupby("period").apply(lambda g: g["pred"].rank().corr(g["ret"].rank()) if len(g) > 2 else np.nan,
                                     include_groups=False).dropna()


def newey_west_t(x, lags=None):
    """t-stat of the mean of x with a Bartlett-kernel HAC standard error."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 3:
        return 0.0
    lags = lags if lags is not None else int(math.floor(4 * (n / 100) ** (2 / 9)))
    d = x - x.mean()
    var = d @ d / n
    for k in range(1, lags + 1):
        var += 2 * (1 - k / (lags + 1)) * (d[k:] @ d[:-k]) / n
    return float(x.mean() / math.sqrt(var / n)) if var > 0 else 0.0
