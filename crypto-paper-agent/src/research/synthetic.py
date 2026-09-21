"""Explicitly synthetic fixtures for deterministic research pipeline smoke."""

import pandas as pd


def smc_frames(short=False):
    rows = [
        (100, 102, 99, 101),
        (100, 101, 97, 100),
        (100, 103, 99, 102),
        (102, 106, 101, 104),
        (104, 105, 100, 102),
        (102, 103, 96, 100),
        (100, 109, 99, 108),
        (108, 111, 105, 110),
        (110, 111, 103, 105),
        (105, 120, 104, 119),
        (119, 133, 118, 131),
        (131, 134, 125, 130),
        (130, 131, 110, 112),
    ]
    if short:
        rows = [(220 - o, 220 - l, 220 - h, 220 - c) for o, h, l, c in rows]
    signal = pd.DataFrame(
        rows,
        columns=["open", "high", "low", "close"],
        index=pd.date_range("2024-01-01T01:00:00Z", periods=len(rows), freq="5min"),
    )
    signal["volume"] = 50.0
    signal = signal.astype(float)
    execution = []
    times = []
    for ts, row in signal.iterrows():
        path = (
            [row.open, row.high, row.low, row.close, row.close, row.close]
            if short
            else [row.open, row.low, row.high, row.close, row.close, row.close]
        )
        for minute in range(5):
            a, b = path[minute : minute + 2]
            execution.append((a, max(a, b), min(a, b), b, 10.0))
            times.append(ts + pd.Timedelta(minutes=minute))
    fast = pd.DataFrame(
        execution,
        index=pd.DatetimeIndex(times),
        columns=["open", "high", "low", "close", "volume"],
    )
    return signal, fast


def smc_config():
    return {
        "account": {"initial_equity_usd": 10000},
        "fees": {"taker_pct": 0.0005, "slippage_pct": 0},
        "strategy": {
            "name": "SMC_LIQUIDITY_SWEEP",
            "timeframe_signal": "5m",
            "timeframe_execution": "1m",
        },
        "smc": {"swing_n": 1, "displacement_min_atr": 0.5, "fvg_min_size_atr": 0.3},
        "entry": {"require_order_block_confluence": True},
        "base_risk_percent": 0.02,
        "leverage": 2.0,
    }


def comparison_datasets(days=3):
    import numpy as np

    idx = pd.date_range("2024-01-01", periods=days * 1440, freq="min", tz="UTC")
    close = 100 + 2 * np.sin(np.arange(len(idx)) / 200)
    fast = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.05,
            "low": close - 0.05,
            "close": close,
            "volume": 10.0,
        },
        index=idx,
    )
    fast["funding_time"] = fast.index.floor("8h")
    fast["funding_rate"] = 0.0002
    fast["funding_readiness"] = True
    frames = {"1m": fast}
    for tf in ("5m", "15m", "4h"):
        freq = tf.replace("m", "min") if tf.endswith("m") else tf
        frame = fast.resample(freq).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "funding_rate": "last",
                "funding_time": "last",
                "funding_readiness": "last",
            }
        )
        frames[tf] = frame
    basket_idx = pd.date_range(idx[0], idx[-1], freq="8h")
    frames["basket"] = pd.DataFrame(
        {
            "spot_close": 100.0,
            "perp_close": 100.1,
            "observed_funding_rate": 0.0002,
            "observed_funding_time": basket_idx,
            "funding_rate": 0.0002,
            "funding_time": basket_idx,
            "funding_readiness": True,
        },
        index=basket_idx,
    )
    return frames


def breakout_frames(short=False):
    values = [100, 100, 100, 100, 104, 102, 112, 112]
    rows = [(v, v + 1, v - 1, v) for v in values]
    rows[5] = (102, 103, 98, 102)
    rows[6] = (102, 113, 102, 112)
    if short:
        rows = [(220 - o, 220 - l, 220 - h, 220 - c) for o, h, l, c in rows]
    signal = pd.DataFrame(
        rows,
        columns=["open", "high", "low", "close"],
        index=pd.date_range("2024-01-01", periods=8, freq="4h", tz="UTC"),
    ).astype(float)
    signal["volume"] = [10, 10, 10, 10, 20, 5, 10, 10]
    rec = []
    times = []
    for ts, row in signal.iterrows():
        path = (
            [row.open, row.high, row.low, row.close]
            if short
            else [row.open, row.low, row.high, row.close]
        ) + [row.close] * 13
        for i in range(16):
            a, b = path[i : i + 2]
            rec.append((a, max(a, b), min(a, b), b, row.volume / 16))
            times.append(ts + pd.Timedelta(minutes=i * 15))
    fast = pd.DataFrame(
        rec,
        index=pd.DatetimeIndex(times),
        columns=["open", "high", "low", "close", "volume"],
    )
    fast["funding_time"] = fast.index.floor("8h")
    fast["funding_rate"] = 0.0002
    fast["funding_readiness"] = True
    return signal, fast
