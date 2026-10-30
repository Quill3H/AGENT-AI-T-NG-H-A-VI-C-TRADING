from datetime import datetime, timezone

import pytest

from src.paper.public_stream import parse_stream_event


UTC = timezone.utc


def event(symbol="BTCUSDT", interval="15m", opened=999_900_000, closed=False):
    duration = {"1m": 60_000, "15m": 900_000, "4h": 14_400_000}[interval]
    emitted = opened + duration if closed else opened + 1_000
    return {
        "stream": f"{symbol.lower()}@kline_{interval}",
        "data": {
            "e": "kline", "E": emitted, "s": symbol,
            "k": {
                "t": opened, "T": opened + duration - 1, "s": symbol, "i": interval,
                "o": "100", "h": "102", "l": "99", "c": "101",
                "v": "5", "x": closed,
            },
        },
    }


def test_stream_event_keeps_event_receipt_and_close_availability_separate():
    raw = event(closed=True)
    bar = parse_stream_event(raw, received_ms=raw["data"]["E"] + 250)
    assert bar["symbol"] == "BTCUSDT"
    assert bar["interval"] == "15m"
    assert bar["closed"] is True
    assert bar["open_time"] == datetime.fromtimestamp(999_900_000 / 1000, tz=UTC)
    assert bar["available_at"] > bar["close_time"]
    assert bar["event_time"] < bar["available_at"]
    assert bar["close"] == 101


@pytest.mark.parametrize("change", [
    lambda raw: raw.update(stream="ethusdt@kline_15m"),
    lambda raw: raw["data"]["k"].update(T=raw["data"]["k"]["T"] + 1),
    lambda raw: raw["data"]["k"].update(x=1),
    lambda raw: raw["data"]["k"].update(h="NaN"),
    lambda raw: raw["data"].update(E=raw["data"]["E"] + 40_000),
])
def test_stream_rejects_mismatch_malformed_and_stale(change):
    raw = event()
    change(raw)
    with pytest.raises(ValueError):
        parse_stream_event(raw, received_ms=999_901_100)


def test_provisional_stream_event_is_not_closed():
    raw = event(interval="1m")
    bar = parse_stream_event(raw, received_ms=raw["data"]["E"] + 100)
    assert bar["closed"] is False
    assert bar["event_time"] < bar["close_time"]
