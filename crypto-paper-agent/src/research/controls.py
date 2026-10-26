"""Research controls that do not inspect prices or simulate execution."""

from numbers import Integral

import numpy as np
import pandas as pd


def _utc_index(values, name):
    if not isinstance(values, pd.DatetimeIndex):
        raise TypeError(f"{name} must be a DatetimeIndex")
    if values.tz is None or any(ts.utcoffset().total_seconds() != 0 for ts in values):
        raise ValueError(f"{name} must use UTC timestamps")
    if values.has_duplicates or not values.is_monotonic_increasing or values.hasnans:
        raise ValueError(f"{name} must be sorted, unique and non-missing")
    return values


def matched_random_entry_sets(eligible_times, signal_times, repetitions, seed):
    """Sample signal-count placebo entries from a causal eligible-time universe.

    Actual signal timestamps are excluded. The caller must replay every sample through the
    strategy's unchanged sizing, exit, holding-period and cost rules.
    """
    eligible = _utc_index(eligible_times, "eligible_times")
    signals = _utc_index(signal_times, "signal_times")
    if not signals.difference(eligible).empty:
        raise ValueError("signal_times must be a subset of eligible_times")
    if isinstance(repetitions, bool) or not isinstance(repetitions, Integral) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    pool = eligible.difference(signals)
    if len(pool) < len(signals):
        raise ValueError("insufficient non-signal eligible times for a matched sample")
    rng = np.random.default_rng(int(seed))
    samples = []
    for _ in range(int(repetitions)):
        positions = np.sort(rng.choice(len(pool), size=len(signals), replace=False))
        samples.append(pool[positions])
    return tuple(samples)
