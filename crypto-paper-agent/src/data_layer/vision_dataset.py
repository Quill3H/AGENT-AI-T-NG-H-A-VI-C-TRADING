"""Load the verified Binance Vision BTCUSDT archive (see scripts/download_vision_history.py).

Binance computes each 8-hour funding event a few milliseconds after the
settlement boundary (observed 0-47 ms, 2020-09..2026-09).  The cashflow is
settled at the boundary, so an event within `tolerance` after it is assigned
to the boundary; the original source time is kept in `funding_source_time`.
Anything further away is an integrity error, not a settlement.
"""
from pathlib import Path

import pandas as pd

from src.data_layer.fetcher import funding_readiness

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume", "taker_buy_base_volume"]


def load_bars(data_dir, timeframe, market="perp", symbol="BTCUSDT"):
    frame = pd.read_parquet(Path(data_dir) / f"{symbol}_{market}_{timeframe}.parquet")
    return frame[OHLCV_COLUMNS]


def load_funding(data_dir, symbol="BTCUSDT"):
    return snap_funding_to_settlement(pd.read_parquet(Path(data_dir) / f"{symbol}_perp_funding.parquet"))


def snap_funding_to_settlement(funding, tolerance=pd.Timedelta(seconds=1)):
    boundary = funding.index.floor("h")
    delay = funding.index - boundary
    if (delay > tolerance).any():
        late = funding.index[delay > tolerance][0]
        raise ValueError(f"funding event {late} is not within {tolerance} after a settlement boundary")
    snapped = funding[["funding_rate"]].copy()
    snapped["funding_source_time"] = funding.index
    snapped.index = pd.DatetimeIndex(boundary, name="timestamp")
    if snapped.index.has_duplicates:
        raise ValueError("two funding events map to the same settlement boundary")
    return snapped


def attach_funding(bars, funding):
    events = funding[["funding_rate"]].copy()
    events["funding_time"] = events.index
    merged = pd.merge_asof(bars, events, left_index=True, right_index=True, direction="backward")
    merged["funding_readiness"] = funding_readiness(merged)
    return merged


def basket_frame(data_dir, timeframe="1h", symbol="BTCUSDT"):
    """Synchronized spot/perpetual quotes for the carry basket.

    Quotes are bar opens (known at the bar's timestamp).  The decision signal is
    the last funding rate settled strictly before the bar; the settlement columns
    carry the bar's own event.  Spot bars missing during exchange maintenance are
    forward-filled from the previous quote (19 of 53,304 hourly bars, 2020-09..2026-09).
    """
    perp = load_bars(data_dir, timeframe, "perp", symbol)
    spot = load_bars(data_dir, timeframe, "spot", symbol).reindex(perp.index).ffill()
    funding = load_funding(data_dir, symbol)
    events = funding[["funding_rate"]].copy()
    events["funding_time"] = events.index
    settled = pd.merge_asof(perp.iloc[:, :0], events, left_index=True, right_index=True, direction="backward")
    observed = pd.merge_asof(
        perp.iloc[:, :0], events, left_index=True, right_index=True, direction="backward", allow_exact_matches=False
    )
    frame = pd.DataFrame(
        {
            "spot_close": spot["open"],
            "perp_close": perp["open"],
            "observed_funding_rate": observed["funding_rate"],
            "observed_funding_time": observed["funding_time"],
            "funding_rate": settled["funding_rate"],
            "funding_time": settled["funding_time"],
        },
        index=perp.index,
    )
    frame["funding_readiness"] = funding_readiness(frame)
    return frame.dropna(subset=["spot_close", "observed_funding_rate"])
