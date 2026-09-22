"""Explicitly synthetic fixtures for deterministic research pipeline smoke."""

import pandas as pd


def trend_config():
    return {
        "account": {"initial_equity_usd": 10000},
        "fees": {"taker_pct": 0.0005, "slippage_pct": 0},
        "strategy": {
            "name": "TREND_FOLLOWING",
            "timeframe_signal": "4h",
            "timeframe_execution": "15m",
        },
        "rules": {
            "crossover_fast_ema": 20,
            "crossover_slow_ema": 50,
            "regime_ema": 200,
            "rsi_period": 14,
            "rsi_threshold": 50.0,
            "max_setup_age_bars": 12,
            "swing_lookback_bars": 5,
        },
        "oi_confluence": {
            "mode": "optional",
            "fallback_when_nan": True,
            "nan_log_note": "OI_BYPASSED_SYNTHETIC",
        },
        "base_risk_percent": 0.02,
        "leverage": 2.0,
    }


def trend_frames(short=False):
    closes = [100.0, 100.5, 101.0, 101.5, 102.0, 104.0, 104.0, 110.0]
    fast = [100.0, 100.1, 100.2, 100.4, 101.0, 103.0, 103.5, 106.0]
    slow = [101.0, 101.0, 101.1, 101.2, 101.5, 102.0, 102.5, 103.0]
    rows = []
    for index, close in enumerate(closes):
        low = close - 1.0
        high = close + 1.0
        if index == 6:
            low, high = 102.0, 105.0
        rows.append(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": 50.0,
                "ema_20": fast[index],
                "ema_50": slow[index],
                "ema_200": 90.0,
                "rsi_14": 60.0,
                "oi_delta_pct": 1.0,
            }
        )
    signal = pd.DataFrame(
        rows,
        index=pd.date_range("2024-01-01", periods=len(rows), freq="4h", tz="UTC"),
    )
    if short:
        for column in ("open", "close", "ema_20", "ema_50", "ema_200"):
            signal[column] = 220.0 - signal[column]
        old_high = signal["high"].copy()
        signal["high"] = 220.0 - signal["low"]
        signal["low"] = 220.0 - old_high
        signal["rsi_14"] = 40.0

    records = []
    times = []
    for timestamp, row in signal.iterrows():
        path = [row.open, row.low, row.high, row.close] + [row.close] * 14
        if short:
            path = [row.open, row.high, row.low, row.close] + [row.close] * 14
        for minute in range(16):
            start, end = path[minute : minute + 2]
            records.append((start, max(start, end), min(start, end), end, 10.0))
            times.append(timestamp + pd.Timedelta(minutes=15 * minute))
    execution = pd.DataFrame(
        records,
        index=pd.DatetimeIndex(times),
        columns=["open", "high", "low", "close", "volume"],
    )
    execution["funding_time"] = execution.index.floor("8h")
    execution["funding_rate"] = 0.0002
    execution["funding_readiness"] = True
    return signal, execution


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
