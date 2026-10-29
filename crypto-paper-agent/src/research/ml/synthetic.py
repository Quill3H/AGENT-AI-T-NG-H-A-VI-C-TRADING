"""
src/research/ml/synthetic.py
============================
Synthetic multi-coin 4h/1d panels for testing the ML framework itself (design §6 check 5): with
edge=0 nothing should pass; with a planted idiosyncratic-momentum edge the gates should pass.
No market data is read.
"""
import numpy as np
import pandas as pd


def panel(n_coins=6, days=1100, edge=0.0, seed=0, start="2021-01-01"):
    """Returns (frames, fundings): frames[symbol] = {"4h": df, "1d": df}; coin 0 is "BTCUSDT".

    Each 4h log return = market shock + idiosyncratic shock; with edge > 0 the idiosyncratic mean
    is edge * clip(z, -2, 2), z = the coin's last-20-bar idiosyncratic sum in standard units.
    """
    rng = np.random.default_rng(seed)
    n = days * 6
    idx = pd.date_range(start, periods=n, freq="4h", tz="UTC")
    market = rng.normal(0, 0.008, n)
    frames, fundings = {}, {}
    for c in range(n_coins):
        sym = "BTCUSDT" if c == 0 else f"C{c}USDT"
        shocks = rng.normal(0, 0.01, n)
        idio = np.zeros(n)
        for t in range(n):
            z = idio[max(0, t - 20):t].sum() / (0.01 * np.sqrt(20)) if t else 0.0
            idio[t] = shocks[t] + edge * np.clip(z, -2, 2)
        r = market + idio
        close = 100 * np.exp(np.cumsum(r))
        open_ = np.concatenate([[100.0], close[:-1]])
        wiggle = np.abs(rng.normal(0, 0.003, (2, n)))
        frame = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * (1 + wiggle[0]),
                              "low": np.minimum(open_, close) * (1 - wiggle[1]), "close": close,
                              "volume": rng.lognormal(10, 0.5, n)}, index=idx)
        daily = frame.resample("1D", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        frames[sym] = {"4h": frame, "1d": daily}
        f_idx = pd.date_range(start, periods=days * 3, freq="8h", tz="UTC")
        fundings[sym] = pd.DataFrame({"funding_rate": rng.normal(0.0001, 0.00005, len(f_idx))}, index=f_idx)
    return frames, fundings
