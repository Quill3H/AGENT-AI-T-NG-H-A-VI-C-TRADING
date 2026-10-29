"""A download that fails part-way must raise, never return a silently truncated dataset."""
import ccxt
import pandas as pd
import pytest

from src.data_layer import fetcher
from src.data_layer.fetcher import FetchError


class _AlwaysDown:
    """Fake exchange: first OHLCV chunk succeeds, every later call raises a network error."""

    def __init__(self, first_chunk=None, error=ccxt.NetworkError):
        self.calls = 0
        self.first_chunk = first_chunk
        self.error = error

    def fetch_ohlcv(self, symbol, timeframe, since, limit):
        self.calls += 1
        if self.calls == 1 and self.first_chunk is not None:
            return self.first_chunk
        raise self.error("down")

    def fetch_funding_rate_history(self, **kwargs):
        raise self.error("down")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(fetcher.time, "sleep", lambda s: None)


def _full_chunk(start_ms, step_ms=900_000):
    return [[start_ms + i * step_ms, 1, 2, 0.5, 1.5, 10] for i in range(fetcher.MAX_CANDLES_PER_REQUEST)]


@pytest.mark.parametrize("error", [ccxt.NetworkError, ccxt.RateLimitExceeded, ccxt.ExchangeError])
def test_ohlcv_chunk_raises_after_retries(error):
    with pytest.raises(FetchError):
        fetcher._fetch_ohlcv_chunk(_AlwaysDown(error=error), "BTC/USDT", "15m", 0)


def test_ohlcv_partial_download_raises_instead_of_truncating(monkeypatch):
    since = pd.Timestamp("2024-01-01", tz="UTC")
    exchange = _AlwaysDown(first_chunk=_full_chunk(int(since.timestamp() * 1000)))
    monkeypatch.setattr(fetcher, "_get_exchange", lambda: exchange)
    with pytest.raises(FetchError):
        fetcher.fetch_ohlcv("BTC/USDT", "15m", since, since + pd.Timedelta(days=60), {})


def test_funding_chunk_raises_after_retries():
    with pytest.raises(FetchError):
        fetcher._fetch_funding_chunk(_AlwaysDown(), "BTC/USDT:USDT", 0, 1)
