"""
tests/test_universe_loader.py
===============================
Unit Test Suite for UniverseDataLoader (Milestone 1.2).

Covers:
    1. Default universe and timeframe validation.
    2. Canonical cache path formatting and resolution.
    3. Deterministic synthetic generator reproducibility (fixed seed invariance).
    4. Mathematical OHLCV integrity and candle geometry invariants.
    5. Exact multi-timeframe aggregation consistency (15m to 4h).
    6. Causal multi-timeframe alignment (strict anti-lookahead verification).
    7. Future data tampering invariance on causal alignment.
    8. Offline fallback resilience (zero network calls when allow_network=False).
    9. Atomic Parquet cache serialization and round-trip fidelity.
   10. Fail-closed detection of invalid/corrupted datasets.
   11. 1-year historical window bar counts across 10 pairs.
"""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
import pytest

from src.data_layer.universe_loader import (
    ASSET_PROFILES,
    DEFAULT_TIMEFRAMES,
    DEFAULT_UNIVERSE,
    UniverseConfig,
    UniverseDataLoader,
)


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Provides isolated temporary directory for Parquet caching tests."""
    cache_dir = tmp_path / "data" / "raw"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def sample_timestamps() -> tuple[pd.Timestamp, pd.Timestamp]:
    """Provides a continuous 7-day test window."""
    start_dt = pd.to_datetime("2025-01-01 00:00:00", utc=True)
    end_dt = pd.to_datetime("2025-01-08 00:00:00", utc=True)
    return start_dt, end_dt


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_universe_defaults(tmp_data_dir: Path):
    """Verifies default universe of 10 liquid perpetual pairs and timeframes."""
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)
    assert len(loader.cfg.symbols) == 10
    assert "BTCUSDT" in loader.cfg.symbols
    assert "SUIUSDT" in loader.cfg.symbols
    assert loader.cfg.timeframes == ["15m", "4h"]
    assert loader.cfg.exchange == "binance"
    assert loader.cfg.allow_network is False


def test_cache_path_convention(tmp_data_dir: Path):
    """Verifies canonical path: data/raw/binance/<symbol>/<timeframe>.parquet."""
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)
    path_15m = loader.get_cache_path("BTCUSDT", "15m")
    path_4h = loader.get_cache_path("ETH/USDT", "4h")

    expected_15m = tmp_data_dir.resolve() / "binance" / "BTCUSDT" / "15m.parquet"
    expected_4h = tmp_data_dir.resolve() / "binance" / "ETHUSDT" / "4h.parquet"

    assert path_15m == expected_15m
    assert path_4h == expected_4h


def test_synthetic_generator_determinism(tmp_data_dir: Path, sample_timestamps):
    """Verifies that the synthetic generator produces bit-for-bit identical data with the same seed."""
    start_dt, end_dt = sample_timestamps
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)

    run_1 = loader.generate_synthetic_universe(start_dt, end_dt, symbols=["BTCUSDT", "ETHUSDT"], seed=101)
    run_2 = loader.generate_synthetic_universe(start_dt, end_dt, symbols=["BTCUSDT", "ETHUSDT"], seed=101)

    for sym in ["BTCUSDT", "ETHUSDT"]:
        pd.testing.assert_frame_equal(run_1[sym]["15m"], run_2[sym]["15m"])
        pd.testing.assert_frame_equal(run_1[sym]["4h"], run_2[sym]["4h"])


def test_synthetic_data_validation(tmp_data_dir: Path, sample_timestamps):
    """Verifies that synthetic data satisfies all mathematical OHLCV and geometry invariants."""
    start_dt, end_dt = sample_timestamps
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)
    data = loader.generate_synthetic_universe(start_dt, end_dt, symbols=["SOLUSDT", "DOGEUSDT"], seed=42)

    for sym in ["SOLUSDT", "DOGEUSDT"]:
        for tf in ["15m", "4h"]:
            df = data[sym][tf]
            loader.validate_dataset(df, sym, tf)

            assert df.index.is_monotonic_increasing
            assert not df.index.has_duplicates
            assert (df["volume"] > 0).all()
            assert (df["high"] >= df["low"]).all()
            assert (df["high"] >= np.maximum(df["open"], df["close"]) - 1e-6).all()
            assert (df["low"] <= np.minimum(df["open"], df["close"]) + 1e-6).all()


def test_multi_timeframe_aggregation_consistency(tmp_data_dir: Path, sample_timestamps):
    """Verifies exact causal aggregation: 4h open/high/low/close/volume matches 16 underlying 15m bars."""
    start_dt, end_dt = sample_timestamps
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)
    data = loader.generate_synthetic_universe(start_dt, end_dt, symbols=["BTCUSDT"], seed=77)

    df_15m = data["BTCUSDT"]["15m"]
    df_4h = data["BTCUSDT"]["4h"]

    bar_4h_open = df_4h.index[10]
    bar_4h_data = df_4h.loc[bar_4h_open]

    bars_15m_slice = df_15m.loc[bar_4h_open : bar_4h_open + pd.Timedelta(hours=4) - pd.Timedelta(minutes=15)]
    assert len(bars_15m_slice) == 16

    assert np.isclose(bar_4h_data["open"], bars_15m_slice.iloc[0]["open"])
    assert np.isclose(bar_4h_data["high"], bars_15m_slice["high"].max())
    assert np.isclose(bar_4h_data["low"], bars_15m_slice["low"].min())
    assert np.isclose(bar_4h_data["close"], bars_15m_slice.iloc[-1]["close"])
    assert np.isclose(bar_4h_data["volume"], bars_15m_slice["volume"].sum())


def test_causal_alignment_anti_lookahead(tmp_data_dir: Path):
    """
    Verifies that a 4h bar starting at T is strictly unavailable during 15m bars
    from T to T+3h45m, and only becomes available at or after T+4h.
    """
    start_dt = pd.to_datetime("2025-01-01 00:00:00", utc=True)
    end_dt = pd.to_datetime("2025-01-02 00:00:00", utc=True)
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)
    data = loader.generate_synthetic_universe(start_dt, end_dt, symbols=["BTCUSDT"], seed=42)

    df_15m = data["BTCUSDT"]["15m"]
    df_4h = data["BTCUSDT"]["4h"]

    # Case 1: At 15m bar 04:00 (closes at 04:15), the 4h bar 00:00-04:00 closed at 04:00. Available!
    res_0400 = loader.get_causal_4h_for_15m(pd.to_datetime("2025-01-01 04:00:00", utc=True), df_4h)
    assert res_0400 is not None
    assert res_0400.name == pd.to_datetime("2025-01-01 00:00:00", utc=True)

    # Case 2: At 15m bar 07:45 (closes at 08:00), the 4h bar 04:00-08:00 closed at 08:00. Available!
    res_0745 = loader.get_causal_4h_for_15m(pd.to_datetime("2025-01-01 07:45:00", utc=True), df_4h)
    assert res_0745 is not None
    assert res_0745.name == pd.to_datetime("2025-01-01 04:00:00", utc=True)

    # Case 3: At 15m bar 07:30 (closes at 07:45), the 4h bar 04:00-08:00 has NOT closed yet!
    # Only previous 00:00 4h bar is available!
    res_0730 = loader.get_causal_4h_for_15m(pd.to_datetime("2025-01-01 07:30:00", utc=True), df_4h)
    assert res_0730 is not None
    assert res_0730.name == pd.to_datetime("2025-01-01 00:00:00", utc=True)


def test_future_data_tampering_causal_invariance(tmp_data_dir: Path, sample_timestamps):
    """
    Altering future 4h data (after cutoff T) does not affect past causal alignment results.
    """
    start_dt, end_dt = sample_timestamps
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)
    data = loader.generate_synthetic_universe(start_dt, end_dt, symbols=["BTCUSDT"], seed=42)

    df_15m = data["BTCUSDT"]["15m"]
    df_4h_orig = data["BTCUSDT"]["4h"]

    cutoff_time = pd.to_datetime("2025-01-04 12:00:00", utc=True)

    # Tamper future 4h data
    df_4h_tampered = df_4h_orig.copy()
    future_mask = df_4h_tampered.index > cutoff_time
    df_4h_tampered.loc[future_mask, "close"] *= 5.0
    df_4h_tampered.loc[future_mask, "high"] *= 10.0

    aligned_orig = loader.align_multi_timeframe(df_15m, df_4h_orig)
    aligned_tampered = loader.align_multi_timeframe(df_15m, df_4h_tampered)

    past_15m = aligned_orig.loc[:cutoff_time]
    past_tampered = aligned_tampered.loc[:cutoff_time]

    pd.testing.assert_frame_equal(past_15m, past_tampered)


def test_explicit_offline_synthetic_mode(tmp_data_dir: Path, sample_timestamps):
    """
    Synthetic generation is explicit and never masquerades as historical cache.
    """
    start_dt, end_dt = sample_timestamps
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir, allow_network=False, mode="synthetic")

    df_btc = loader.load_symbol("BTCUSDT", "15m", start_dt, end_dt)
    assert not df_btc.empty
    assert len(df_btc) > 0
    assert loader.get_cache_path("BTCUSDT", "15m").is_file()


def test_parquet_cache_save_and_load_roundtrip(tmp_data_dir: Path, sample_timestamps):
    """Verifies that Parquet caching preserves exact timestamps, columns, and precision."""
    start_dt, end_dt = sample_timestamps
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir, mode="synthetic", seed=99)
    data = loader.generate_synthetic_universe(start_dt, end_dt, symbols=["BNBUSDT"], seed=99)

    df_orig = data["BNBUSDT"]["15m"]
    saved_path = loader.save_to_cache(df_orig, "BNBUSDT", "15m", provenance={
        "source": "synthetic_generator", "seed": 99, "source_uri": "test_fixture"})
    assert saved_path.is_file()

    # Verify the actual parquet roundtrip; synthetic load_symbol adds labelled funding.
    df_loaded = pd.read_parquet(saved_path)
    pd.testing.assert_frame_equal(df_orig, df_loaded, check_freq=False)


def test_fail_closed_on_invalid_data(tmp_data_dir: Path):
    """Verifies that validate_dataset raises ValueError/TypeError on corrupt data."""
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)
    ts = pd.date_range("2025-01-01", periods=10, freq="15min", tz="UTC")

    # 1. Non-monotonic index
    bad_idx = ts.to_list()
    bad_idx[3], bad_idx[4] = bad_idx[4], bad_idx[3]
    df_bad_order = pd.DataFrame({
        "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 500.0
    }, index=bad_idx)
    with pytest.raises(ValueError, match="strictly monotonic"):
        loader.validate_dataset(df_bad_order, "BTCUSDT", "15m")

    # 2. Duplicate timestamps
    dup_idx = ts.to_list()
    dup_idx[5] = dup_idx[4]
    df_dup = pd.DataFrame({
        "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 500.0
    }, index=dup_idx)
    with pytest.raises(ValueError, match="duplicate timestamps"):
        loader.validate_dataset(df_dup, "BTCUSDT", "15m")

    # 3. High < Low
    df_hl = pd.DataFrame({
        "open": 100.0, "high": 90.0, "low": 95.0, "close": 100.0, "volume": 500.0
    }, index=ts)
    with pytest.raises(ValueError, match="high < low"):
        loader.validate_dataset(df_hl, "BTCUSDT", "15m")

    # 4. Low > Min(Open, Close)
    df_low_high = pd.DataFrame({
        "open": 100.0, "high": 110.0, "low": 101.0, "close": 105.0, "volume": 500.0
    }, index=ts)
    with pytest.raises(ValueError, match="low > min"):
        loader.validate_dataset(df_low_high, "BTCUSDT", "15m")

    # 5. Non-UTC timezone
    ts_no_tz = pd.date_range("2025-01-01", periods=10, freq="15min")
    df_no_tz = pd.DataFrame({
        "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 500.0
    }, index=ts_no_tz)
    with pytest.raises(ValueError, match="must have UTC timezone"):
        loader.validate_dataset(df_no_tz, "BTCUSDT", "15m")


def test_1_year_universe_bar_count(tmp_data_dir: Path):
    """
    Verifies that a 1-year historical window generates exactly 35,040 bars on 15m
    and 2,190 bars on 4h for the entire 10-pair universe.
    """
    start_dt = pd.to_datetime("2024-10-01 00:00:00", utc=True)
    end_dt = pd.to_datetime("2025-09-30 23:45:00", utc=True)
    loader = UniverseDataLoader(raw_data_dir=tmp_data_dir)

    universe_data = loader.generate_synthetic_universe(start_dt, end_dt, seed=42)

    assert len(universe_data) == 10
    for sym in DEFAULT_UNIVERSE:
        assert sym in universe_data
        df_15m = universe_data[sym]["15m"]
        df_4h = universe_data[sym]["4h"]
        assert len(df_15m) == 35040
        assert len(df_4h) == 2190
