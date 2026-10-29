"""Binance Vision dataset loader: funding events computed milliseconds after the boundary settle at the boundary."""
import pandas as pd
import pytest

from src.data_layer.vision_dataset import attach_funding, snap_funding_to_settlement


def _funding(times, rates):
    return pd.DataFrame({"funding_rate": rates}, index=pd.DatetimeIndex(pd.to_datetime(times, utc=True, format="ISO8601"), name="timestamp"))


def test_late_millisecond_event_snaps_to_settlement_boundary():
    raw = _funding(["2024-01-01 08:00:00.006", "2024-01-01 16:00:00"], [0.0001, 0.0002])
    snapped = snap_funding_to_settlement(raw)
    assert list(snapped.index) == list(pd.to_datetime(["2024-01-01 08:00", "2024-01-01 16:00"], utc=True))
    assert snapped["funding_source_time"].iloc[0] == pd.Timestamp("2024-01-01 08:00:00.006", tz="UTC")


def test_event_far_from_boundary_is_rejected():
    raw = _funding(["2024-01-01 08:00:05"], [0.0001])
    with pytest.raises(ValueError, match="not within"):
        snap_funding_to_settlement(raw)


def test_settlement_bar_is_ready_only_with_its_own_event():
    raw = _funding(["2024-01-01 00:00:00.003", "2024-01-01 08:00:00.004"], [0.0001, -0.0003])
    idx = pd.date_range("2024-01-01 07:30", "2024-01-01 08:15", freq="15min", tz="UTC")
    bars = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    out = attach_funding(bars, snap_funding_to_settlement(raw))
    at_8 = out.loc[pd.Timestamp("2024-01-01 08:00", tz="UTC")]
    assert at_8["funding_rate"] == -0.0003
    assert at_8["funding_time"] == pd.Timestamp("2024-01-01 08:00", tz="UTC")
    assert bool(at_8["funding_readiness"]) is True
    # A bar before 08:00 must only see the 00:00 rate (no look-ahead).
    assert out.loc[pd.Timestamp("2024-01-01 07:45", tz="UTC"), "funding_rate"] == 0.0001
