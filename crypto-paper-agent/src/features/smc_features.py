"""Causal Smart Money Concepts feature extraction."""
from typing import Any

import numpy as np
import pandas as pd


def compute_smc_features(frame: pd.DataFrame, swing_n: int = 3, min_bos_pct: float = 0.001) -> pd.DataFrame:
    """Compute confirmed swings, sweeps, structure breaks and FVGs without backdating."""
    if swing_n < 1:
        raise ValueError("swing_n must be positive")
    required = {"high", "low", "close", "open"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"SMC features require columns: {sorted(missing)}")
    out = frame.copy()
    for name in ("swing_high_confirmed", "swing_low_confirmed", "liquidity_sweep_bullish", "liquidity_sweep_bearish", "bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish"):
        out[name] = False
    for name in ("swing_high_price", "swing_low_price", "fvg_low", "fvg_high", "fvg_mid"):
        out[name] = np.nan
    out["fvg_direction"] = None
    confirmed_high = []
    confirmed_low = []
    prior_trend = None
    for i in range(len(out)):
        pivot = i - swing_n
        if pivot >= swing_n:
            left = out.iloc[pivot - swing_n:pivot]
            right = out.iloc[pivot + 1:i + 1]
            if float(out.iloc[pivot]["high"]) > float(left["high"].max()) and float(out.iloc[pivot]["high"]) > float(right["high"].max()):
                price = float(out.iloc[pivot]["high"])
                out.iat[i, out.columns.get_loc("swing_high_confirmed")] = True
                out.iat[i, out.columns.get_loc("swing_high_price")] = price
                confirmed_high.append(price)
            if float(out.iloc[pivot]["low"]) < float(left["low"].min()) and float(out.iloc[pivot]["low"]) < float(right["low"].min()):
                price = float(out.iloc[pivot]["low"])
                out.iat[i, out.columns.get_loc("swing_low_confirmed")] = True
                out.iat[i, out.columns.get_loc("swing_low_price")] = price
                confirmed_low.append(price)
        if i >= 2:
            a, c = out.iloc[i - 2], out.iloc[i]
            if float(a["high"]) < float(c["low"]):
                lo, hi = float(a["high"]), float(c["low"])
                out.iat[i, out.columns.get_loc("fvg_low")] = lo
                out.iat[i, out.columns.get_loc("fvg_high")] = hi
                out.iat[i, out.columns.get_loc("fvg_mid")] = (lo + hi) / 2.0
                out.iat[i, out.columns.get_loc("fvg_direction")] = "BULLISH"
            elif float(a["low"]) > float(c["high"]):
                lo, hi = float(c["high"]), float(a["low"])
                out.iat[i, out.columns.get_loc("fvg_low")] = lo
                out.iat[i, out.columns.get_loc("fvg_high")] = hi
                out.iat[i, out.columns.get_loc("fvg_mid")] = (lo + hi) / 2.0
                out.iat[i, out.columns.get_loc("fvg_direction")] = "BEARISH"
        latest_high = confirmed_high[-1] if confirmed_high else None
        latest_low = confirmed_low[-1] if confirmed_low else None
        close = float(out.iloc[i]["close"])
        if latest_high is not None and close > latest_high * (1.0 + min_bos_pct):
            out.iat[i, out.columns.get_loc("bos_bullish")] = True
            out.iat[i, out.columns.get_loc("choch_bullish")] = prior_trend == "BEARISH"
            prior_trend = "BULLISH"
        if latest_low is not None and close < latest_low * (1.0 - min_bos_pct):
            out.iat[i, out.columns.get_loc("bos_bearish")] = True
            out.iat[i, out.columns.get_loc("choch_bearish")] = prior_trend == "BULLISH"
            prior_trend = "BEARISH"
        if latest_low is not None and float(out.iloc[i]["low"]) < latest_low and close >= latest_low:
            out.iat[i, out.columns.get_loc("liquidity_sweep_bullish")] = True
        if latest_high is not None and float(out.iloc[i]["high"]) > latest_high and close <= latest_high:
            out.iat[i, out.columns.get_loc("liquidity_sweep_bearish")] = True
    return out
