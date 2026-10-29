"""Input fidelity regressions extracted from ffbc14b; broker/RL remain separate."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd
import pytest
from src.data_layer.fetcher import _candles_to_dataframe, merge_ohlcv_with_oi_and_funding
from src.features.cvd import calculate_cvd
T = datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)

def frame(index):
    return pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0,
         "close": 100.0, "volume": 10.0},
        index=pd.DatetimeIndex(index, tz="UTC"),
    )

def test_oi_source_time_and_freshness_are_preserved():
    ohlcv = frame([T, T + timedelta(minutes=15), T + timedelta(days=30)])
    oi = pd.DataFrame({"open_interest": [123.0]}, index=pd.DatetimeIndex([T]))
    merged = merge_ohlcv_with_oi_and_funding(ohlcv, oi, pd.DataFrame(), "15m", {})
    assert merged["open_interest"].iloc[0] == 123.0
    assert merged["oi_source_time"].iloc[0] == pd.Timestamp(T)
    assert bool(merged["oi_available"].iloc[0]) is True
    assert np.isnan(merged["open_interest"].iloc[-1])
    assert bool(merged["oi_available"].iloc[-1]) is False
    assert pd.isna(merged["oi_source_time"].iloc[-1])

def test_missing_taker_volume_never_looks_like_observed_cvd():
    raw = [
        [int(pd.Timestamp(T).timestamp() * 1000), 100, 101, 99, 100, 10],
        [int(pd.Timestamp(T + timedelta(minutes=1)).timestamp() * 1000), 100, 101, 99, 100, 10],
    ]
    observed = _candles_to_dataframe(raw)
    assert observed["taker_buy_base_volume"].isna().all()
    features = calculate_cvd(observed)
    assert features["cvd"].isna().all()

def test_cvd_after_missing_delta_remains_unobserved():
    inputs = pd.DataFrame({"volume": [10.0, 10.0, 10.0],
                           "taker_buy_base_volume": [6.0, np.nan, 7.0]})
    result = calculate_cvd(inputs)
    assert result["cvd"].iloc[0] == 2.0
    assert result["cvd"].iloc[1:].isna().all()

def test_funding_cli_rejects_explicit_dates_it_does_not_apply(tmp_path):
    idx = pd.date_range("2024-01-01", periods=5, freq="8h", tz="UTC")
    basket = pd.DataFrame({
        "spot_close": [100, 100, 100.5, 101, 101],
        "perp_close": [100, 100, 100.6, 101.1, 101.2],
        "observed_funding_rate": [0.0002] * 5,
        "observed_funding_time": idx,
        "funding_rate": [0.0002, 0.0002, 0.0002, -0.0001, -0.0001],
        "funding_time": idx,
        "funding_readiness": True,
    }, index=idx)
    source = tmp_path / "basket.parquet"
    basket.to_parquet(source)
    output = tmp_path / "out"
    result = subprocess.run([
        sys.executable, str(Path(__file__).resolve().parents[1] / "run_backtest.py"),
        "--strategy", "funding_arbitrage", "--basket-input", str(source),
        "--start", "2030-01-01", "--end", "2030-01-02",
        "--output-dir", str(output),
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "UNSUPPORTED_DATE_RANGE" in result.stderr
    assert not output.exists()

def test_comparison_cli_rejects_explicit_dates_before_loading_files(tmp_path):
    result = subprocess.run([
        sys.executable, str(Path(__file__).resolve().parents[1] / "run_backtest.py"),
        "--strategy", "all", "--comparison-data-dir", str(tmp_path),
        "--start", "2030-01-01", "--end", "2030-01-02",
        "--output-dir", str(tmp_path / "out"),
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "UNSUPPORTED_DATE_RANGE" in result.stderr
    assert not (tmp_path / "out").exists()
