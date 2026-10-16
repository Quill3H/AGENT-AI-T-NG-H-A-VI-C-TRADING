"""Complete-cache claims must match the frames actually admitted to research."""
import pandas as pd
import pytest

from src.data_layer.cache_manager import get_cache_path, has_complete_cache, load_from_cache, save_to_cache
from src.data_layer import fetcher


@pytest.mark.parametrize("missing_count", [1, 50])
@pytest.mark.parametrize("data_type,timeframe", [("ohlcv", "15m"), ("open_interest", "4h"), ("funding_rate", "8h")])
def test_cache_with_retained_endpoints_and_middle_gap_is_not_complete(tmp_path, missing_count, data_type, timeframe):
    idx = pd.date_range("2024-01-01", periods=200, freq="15min" if timeframe == "15m" else timeframe, tz="UTC")
    frame = pd.DataFrame({"close": 100.0}, index=idx).drop(idx[50:50 + missing_count])
    save_to_cache(frame, str(tmp_path), "binance", "BTCUSDT", timeframe, data_type)
    args = (str(tmp_path), "binance", "BTCUSDT", timeframe, data_type, idx[0], idx[-1])
    assert has_complete_cache(*args) is False
    assert load_from_cache(*args) is None


@pytest.mark.parametrize("index_name", [None, "timestamp", "open_time"])
def test_complete_cache_named_index_and_partial_final_interval(tmp_path, index_name):
    idx = pd.date_range("2024-01-01", periods=200, freq="15min", tz="UTC", name=index_name)
    frame = pd.DataFrame({"close": 100.0}, index=idx)
    save_to_cache(frame, str(tmp_path), "binance", "BTCUSDT", "15m", "ohlcv")
    for until in (idx[-1], idx[-1] + pd.Timedelta(minutes=14)):
        args = (str(tmp_path), "binance", "BTCUSDT", "15m", "ohlcv", idx[0], until)
        assert has_complete_cache(*args) is True
        loaded = load_from_cache(*args)
        assert loaded is not None
        pd.testing.assert_frame_equal(loaded, frame, check_freq=False)


@pytest.mark.parametrize("damage", ["duplicate", "off_grid", "missing_first", "missing_last", "out_of_order", "nat"])
def test_cached_bad_cadence_or_boundaries_is_rejected(tmp_path, damage):
    idx = pd.date_range("2024-01-01", periods=200, freq="15min", tz="UTC")
    frame = pd.DataFrame({"close": 100.0}, index=idx)
    if damage == "duplicate":
        frame = pd.concat([frame, frame.iloc[[50]]]).sort_index()
    elif damage == "off_grid":
        shifted = list(idx)
        shifted[50] += pd.Timedelta(minutes=1)
        frame.index = pd.DatetimeIndex(shifted)
    elif damage == "missing_first":
        frame = frame.iloc[1:]
    elif damage == "missing_last":
        frame = frame.iloc[:-1]
    elif damage == "out_of_order":
        frame = pd.concat([frame.iloc[1:2], frame.iloc[0:1], frame.iloc[2:]])
    else:
        frame.index = pd.DatetimeIndex([*idx[:-1], pd.NaT])
    # Bypass the writer to reproduce pre-existing or externally damaged cache.
    path = get_cache_path(str(tmp_path), "binance", "BTCUSDT", "15m", "ohlcv")
    path.parent.mkdir(parents=True)
    frame.to_parquet(path)
    args = (str(tmp_path), "binance", "BTCUSDT", "15m", "ohlcv", idx[0], idx[-1])
    assert has_complete_cache(*args) is False
    assert load_from_cache(*args) is None


@pytest.mark.parametrize("missing_type", ["ohlcv", "open_interest", "funding_rate"])
def test_fetch_all_handles_actual_cache_miss_without_len_none(tmp_path, monkeypatch, missing_type):
    since = pd.Timestamp("2024-01-01", tz="UTC")
    until = since + pd.Timedelta(hours=16)
    idx = pd.date_range(since, until, freq="4h")
    frames = {
        "ohlcv": pd.DataFrame({"open": 100., "high": 101., "low": 99., "close": 100., "volume": 5.}, index=idx),
        "open_interest": pd.DataFrame({"open_interest": 1000.}, index=idx),
        "funding_rate": pd.DataFrame({"funding_rate": 0.0001}, index=pd.date_range(since, until, freq="8h")),
    }
    for data_type, frame in frames.items():
        tf = "8h" if data_type == "funding_rate" else "4h"
        save_to_cache(frame, str(tmp_path), "binance", "BTCUSDT", tf, data_type)
    original_load = fetcher.load_from_cache
    # Model a stale metadata hit / file disappearing between check and load.
    monkeypatch.setattr(fetcher, "load_from_cache", lambda *args: None if args[4] == missing_type else original_load(*args))
    def fetch_ohlcv(*args):
        assert missing_type == "ohlcv"
        return frames["ohlcv"]
    def fetch_oi(*args):
        assert missing_type == "open_interest"
        return frames["open_interest"]
    def fetch_funding(*args):
        assert missing_type == "funding_rate"
        return frames["funding_rate"]
    monkeypatch.setattr(fetcher, "fetch_ohlcv", fetch_ohlcv)
    monkeypatch.setattr(fetcher, "fetch_open_interest", fetch_oi)
    monkeypatch.setattr(fetcher, "fetch_funding_rate", fetch_funding)
    result = fetcher.fetch_all("BTCUSDT", ["4h"], since, until, {"data": {"raw_data_dir": str(tmp_path)}})
    assert list(result) == ["4h"]
    assert result["4h"].index.equals(idx)
    assert result["4h"]["volume"].tolist() == [5.] * 5
    assert result["4h"]["funding_rate"].tolist() == [0.0001] * 5
    assert result["4h"]["open_interest"].tolist() == [1000.] * 5


def test_incomplete_fetched_ohlcv_is_not_admitted_as_complete(tmp_path, monkeypatch):
    idx = pd.date_range("2024-01-01", periods=200, freq="15min", tz="UTC")
    frame = pd.DataFrame({"open": 100., "high": 101., "low": 99., "close": 100., "volume": 5.}, index=idx).drop(idx[50])
    monkeypatch.setattr(fetcher, "fetch_ohlcv", lambda *args: frame)
    monkeypatch.setattr(fetcher, "fetch_open_interest", lambda *args: pd.DataFrame())
    monkeypatch.setattr(fetcher, "fetch_funding_rate", lambda *args: pd.DataFrame())
    with pytest.raises(ValueError, match="OHLCV.*incomplete"):
        fetcher.fetch_all("BTCUSDT", ["15m"], idx[0], idx[-1], {"data": {"raw_data_dir": str(tmp_path)}})
