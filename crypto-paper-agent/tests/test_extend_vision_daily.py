"""Forward-data extension keeps base rows and builds whole days only (scripts/extend_vision_daily.py)."""
import pandas as pd

from scripts.extend_vision_daily import daily_from_hourly, extend


def _bars(start, periods, freq, price):
    index = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    return pd.DataFrame({c: price for c in ("open", "high", "low", "close", "volume", "quote_volume", "trades",
                                            "taker_buy_base_volume", "taker_buy_quote")}, index=index)


def test_extend_keeps_base_rows_on_overlap():
    base, new = _bars("2026-09-30", 24, "1h", 1.0), _bars("2026-09-30 20:00", 10, "1h", 2.0)
    out = extend(base, new)
    assert (out.loc[:base.index[-1], "close"] == 1.0).all()
    assert len(out) == 24 + 6 and out.index.is_monotonic_increasing


def test_daily_bars_need_all_24_hours():
    hourly = _bars("2026-10-01", 47, "1h", 3.0)
    days = daily_from_hourly(hourly)
    assert list(days.index) == [pd.Timestamp("2026-10-01", tz="UTC")]
    assert days["volume"].iloc[0] == 72.0


def test_funding_from_api_reads_saved_rest_rows(tmp_path):
    import json
    from scripts.extend_vision_daily import funding_from_api
    path = tmp_path / "BTCUSDT_funding_api.json"
    path.write_text(json.dumps({"rows": [{"fundingTime": 1790812800001, "fundingRate": "0.0001"}]}))
    frame = funding_from_api(path)
    assert frame["funding_rate"].iloc[0] == 0.0001 and frame.index[0].year == 2026
