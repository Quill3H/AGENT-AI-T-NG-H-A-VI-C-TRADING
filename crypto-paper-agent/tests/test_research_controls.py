import pandas as pd
import pytest

from src.research.controls import matched_random_entry_sets


def test_matched_random_entries_are_reproducible_equal_count_and_exclude_signals():
    eligible = pd.date_range("2026-01-01", periods=20, freq="15min", tz="UTC")
    signals = eligible[[2, 8, 14]]

    first = matched_random_entry_sets(eligible, signals, repetitions=4, seed=42)
    second = matched_random_entry_sets(eligible, signals, repetitions=4, seed=42)

    assert len(first) == 4
    assert all(len(sample) == len(signals) for sample in first)
    assert all(sample.is_monotonic_increasing and not sample.has_duplicates for sample in first)
    assert all(len(sample.intersection(signals)) == 0 for sample in first)
    assert [sample.tolist() for sample in first] == [sample.tolist() for sample in second]


@pytest.mark.parametrize("eligible,signals", [
    (pd.DatetimeIndex(["2026-01-01T00:15Z", "2026-01-01T00:00Z"]),
     pd.DatetimeIndex(["2026-01-01T00:00Z"])),
    (pd.DatetimeIndex(["2026-01-01T00:00Z", "2026-01-01T00:00Z"]),
     pd.DatetimeIndex(["2026-01-01T00:00Z"])),
    (pd.DatetimeIndex(["2026-01-01T00:00", "2026-01-01T00:15"]),
     pd.DatetimeIndex(["2026-01-01T00:00"])),
])
def test_matched_random_entries_reject_an_invalid_eligible_index(eligible, signals):
    with pytest.raises(ValueError):
        matched_random_entry_sets(eligible, signals, repetitions=1, seed=1)


def test_matched_random_entries_reject_signals_outside_or_an_insufficient_pool():
    eligible = pd.date_range("2026-01-01", periods=4, freq="15min", tz="UTC")
    with pytest.raises(ValueError, match="subset"):
        matched_random_entry_sets(eligible, pd.DatetimeIndex(["2025-12-31T23:45Z"]), 1, 1)
    with pytest.raises(ValueError, match="insufficient"):
        matched_random_entry_sets(eligible, eligible[:3], 1, 1)


@pytest.mark.parametrize("repetitions,seed", [(0, 1), (True, 1), (1, True), (1, -1)])
def test_matched_random_entries_reject_invalid_repeat_or_seed(repetitions, seed):
    eligible = pd.date_range("2026-01-01", periods=4, freq="15min", tz="UTC")
    with pytest.raises((TypeError, ValueError), match="seed|repetitions"):
        matched_random_entry_sets(eligible, eligible[:1], repetitions, seed)
