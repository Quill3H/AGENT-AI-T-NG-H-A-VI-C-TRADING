"""
src/research/ml/splits.py
=========================
Time splits with purge and embargo for overlapping labels (design §5).

Every sample has a signal time `t` and a label end `t1` (exit time). Purge is by calendar time
across all symbols: a BTC label ending inside a test block carries market information about every
coin in that block, so it is removed from training whatever its symbol.
"""
import itertools

import numpy as np
import pandas as pd


def _times(t, t1):
    t, t1 = pd.DatetimeIndex(t), pd.DatetimeIndex(t1)
    if len(t) != len(t1) or (t1 < t).any():
        raise ValueError("t and t1 must have equal length and t1 >= t")
    return t, t1


def _stamp(value, like):
    ts = pd.Timestamp(value)
    if ts.tz is None and like.tz is not None:
        ts = ts.tz_localize(like.tz)
    return ts


def purged_walk_forward(t, t1, first_test, last_test, train_days=730, test_days=30, embargo=pd.Timedelta(days=1)):
    """Rolling splits [(train_positions, test_positions, test_start, test_end)].

    Test blocks of `test_days` from `first_test` to `last_test`. Training samples have
    t in [test_start - train_days, test_start - embargo) and t1 < test_start - embargo, so no
    training label overlaps the test block or the embargo gap before it.
    """
    t, t1 = _times(t, t1)
    first, last = _stamp(first_test, t), _stamp(last_test, t)
    splits, start = [], first
    while start <= last:
        end = min(start + pd.Timedelta(days=test_days), last + pd.Timedelta(days=1))
        cut = start - embargo
        train = np.flatnonzero((t >= start - pd.Timedelta(days=train_days)) & (t < cut) & (t1 < cut))
        test = np.flatnonzero((t >= start) & (t < end))
        if len(test):
            splits.append((train, test, start, end))
        start = end
    return splits


def inner_split(t, t1, train_positions, tail=0.2, embargo=pd.Timedelta(days=1)):
    """Split one training window into (fit, calibrate) by time: the last `tail` share of the
    window's time span calibrates (isotonic map, hyperparameters, DI threshold); fit samples whose
    label reaches into the calibration slice (plus embargo) are purged."""
    t, t1 = _times(t, t1)
    tw, t1w = t[train_positions], t1[train_positions]
    cut = tw.min() + (tw.max() - tw.min()) * (1 - tail)
    fit = train_positions[(tw < cut - embargo) & (t1w < cut - embargo)]
    cal = train_positions[tw >= cut]
    return fit, cal


def cpcv(t, t1, n_groups=12, k_test=2, embargo=pd.Timedelta(days=1)):
    """Combinatorial purged CV (Lopez de Prado 2018, ch. 12).

    Groups are equal calendar spans. Returns (splits, groups) where splits are
    [(train_positions, test_group_ids)] for every choice of k_test groups, and groups[i] is the
    group of sample i. A training sample is purged when its [t, t1] (+ embargo after each test
    group) overlaps any test group.
    """
    t, t1 = _times(t, t1)
    edges = pd.date_range(t.min(), t.max() + pd.Timedelta(seconds=1), periods=n_groups + 1)
    groups = np.clip(edges.searchsorted(t, side="right") - 1, 0, n_groups - 1)
    bounds = [(edges[g], edges[g + 1]) for g in range(n_groups)]
    splits = []
    for test_ids in itertools.combinations(range(n_groups), k_test):
        keep = ~np.isin(groups, test_ids)
        for g in test_ids:
            lo, hi = bounds[g]
            keep &= ~((t1 >= lo) & (t < hi + embargo))
        splits.append((np.flatnonzero(keep), test_ids))
    return splits, groups


def cpcv_paths(n_groups=12, k_test=2):
    """Assign each (split, test group) to one of the n_paths = C(N-1, k-1) backtest paths, so each
    path covers every group exactly once. Returns {path: [(split_index, group), ...]}."""
    combos = list(itertools.combinations(range(n_groups), k_test))
    used = {g: 0 for g in range(n_groups)}
    paths = {}
    for s, ids in enumerate(combos):
        for g in ids:
            paths.setdefault(used[g], []).append((s, g))
            used[g] += 1
    return paths
