"""
src/research/ml/features.py
===========================
Multi-timeframe features (FreqAI idea: include_timeframes, corr pairs, shifted candles), built
so that the row for base bar i uses only information available at that bar's close, plus the
three leak checks the design requires before any dev run (§6): truncation, future shuffle and
warm-up stability.

Frames are OHLCV indexed by bar OPEN time (UTC), as in the Binance Vision parquet files. A bar is
known at open + duration, so a higher timeframe is joined by its CLOSE time; joining by open time
would let a 4h bar stamped 08:00 leak 08:00-12:00 into an 09:00 1h row.
"""
import numpy as np
import pandas as pd

DURATION = {"15m": pd.Timedelta(minutes=15), "1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4),
            "1d": pd.Timedelta(days=1)}
# Days of history a feature row needs before it no longer depends on where the series starts
# (the slowest recursion is the 1d EMA50: about 3e-6 ATR left after 365 days, so warmup_check
# uses a 1e-5 tolerance). Rows in the first WARMUP_DAYS of a coin are dropped from any dataset.
WARMUP_DAYS = 365


def resample(frame_15m, timeframe):
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    rule = {"1h": "1h", "4h": "4h", "1d": "1D"}[timeframe]
    return frame_15m.resample(rule, label="left", closed="left").agg(agg).dropna()


def bar_features(frame, prefix):
    """Features of one series, each computed from bars up to and including the row's bar."""
    c, h, l, v = frame["close"], frame["high"], frame["low"], frame["volume"]
    r = np.log(c).diff()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    ema20, ema50 = c.ewm(span=20, adjust=False).mean(), c.ewm(span=50, adjust=False).mean()
    gain, loss = r.clip(lower=0), (-r).clip(lower=0)
    rs = gain.ewm(alpha=1 / 14, adjust=False).mean() / loss.ewm(alpha=1 / 14, adjust=False).mean()
    out = pd.DataFrame({
        "ret1": r, "ret5": np.log(c / c.shift(5)), "ret20": np.log(c / c.shift(20)),
        "vol20": r.rolling(20).std(), "atr_pct": atr / c,
        "dist_ema20": (c - ema20) / atr, "dist_ema50": (c - ema50) / atr,
        "rsi14": 100 - 100 / (1 + rs),
        "range_pos20": (c - l.rolling(20).min()) / (h.rolling(20).max() - l.rolling(20).min()),
        "vol_z20": (np.log(v + 1) - np.log(v + 1).rolling(20).mean()) / np.log(v + 1).rolling(20).std(),
    }, index=frame.index)
    return out.add_prefix(prefix)


def join_closed(base_index, base_tf, higher, higher_tf):
    """Rows of `higher` (indexed by open time) aligned to base bars: for base bar i, the last
    higher bar whose close time <= base bar i's close time."""
    close_times = higher.index + DURATION[higher_tf]
    pos = close_times.searchsorted(base_index + DURATION[base_tf], side="right") - 1
    values = higher.to_numpy(dtype=float)[np.clip(pos, 0, None)]
    values[pos < 0] = np.nan
    return pd.DataFrame(values, index=base_index, columns=higher.columns)


def funding_known(base_index, base_tf, funding):
    """Last funding rate settled strictly before the base bar's close (the source event lands a
    few ms after the boundary, so an equal timestamp is not yet known)."""
    left = pd.DataFrame({"t": base_index + DURATION[base_tf]})
    right = funding[["funding_rate"]].rename_axis("t").reset_index()
    merged = pd.merge_asof(left, right, on="t", direction="backward", allow_exact_matches=False)
    rate = pd.Series(merged["funding_rate"].to_numpy(), index=base_index)
    return pd.DataFrame({"funding_last": rate, "funding_mean21": rate.rolling(21 * 8 // 4, min_periods=1).mean()},
                        index=base_index)


def build(inputs, base_tf="4h", higher=("1d",), lags=(1, 2, 3), context=("BTCUSDT",)):
    """Feature frame for one symbol.

    inputs: {"bars": {tf: frame}, "funding": frame, "context": {symbol: {tf: frame}}} where every
    frame covers only data the caller may use. Returns a frame on the base bars' index.
    """
    base = inputs["bars"][base_tf]
    parts = [bar_features(base, f"{base_tf}_")]
    for tf in higher:
        parts.append(join_closed(base.index, base_tf, bar_features(inputs["bars"][tf], f"{tf}_"), tf))
    own = parts[0]
    for k in lags:  # FreqAI include_shifted_candles
        parts.append(own[[f"{base_tf}_ret1", f"{base_tf}_vol20"]].shift(k).add_suffix(f"_lag{k}"))
    if inputs.get("funding") is not None:
        parts.append(funding_known(base.index, base_tf, inputs["funding"]))
    for symbol in context:
        ctx = inputs.get("context", {}).get(symbol)
        if ctx is None:
            continue
        f = bar_features(ctx[base_tf], f"{symbol}_{base_tf}_")[[f"{symbol}_{base_tf}_ret1", f"{symbol}_{base_tf}_ret20",
                                                                 f"{symbol}_{base_tf}_vol20"]]
        parts.append(join_closed(base.index, base_tf, f, base_tf))
    return pd.concat(parts, axis=1)


# ------------------------------------------------------------------ leak checks
def _truncate(inputs, cutoff, base_tf):
    """Inputs as they were at the close of the base bar opening at `cutoff`."""
    known = cutoff + DURATION[base_tf]

    def cut(frame, tf):
        return frame[frame.index + DURATION[tf] <= known]

    out = {"bars": {tf: cut(f, tf) for tf, f in inputs["bars"].items()},
           "context": {s: {tf: cut(f, tf) for tf, f in d.items()} for s, d in inputs.get("context", {}).items()}}
    if inputs.get("funding") is not None:
        out["funding"] = inputs["funding"][inputs["funding"].index < known]
    return out


def _same(a, b, tol):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    both_nan = np.isnan(a) & np.isnan(b)
    close = np.abs(a - b) <= tol * np.maximum(1.0, np.abs(b))
    return bool(np.all(both_nan | close))


def truncation_check(builder, inputs, times, base_tf="4h", tol=1e-9):
    """Row t from the full build equals row t built from data known at t. Returns failing times."""
    full = builder(inputs)
    bad = []
    for t in times:
        part = builder(_truncate(inputs, t, base_tf))
        if t not in part.index or not _same(full.loc[t].to_numpy(), part.loc[t].to_numpy(), tol):
            bad.append(t)
    return bad


def future_shuffle_check(builder, inputs, times, base_tf="4h", seed=0, tol=1e-9):
    """Scrambling every bar after t (prices scaled by random factors) leaves rows <= t unchanged."""
    full = builder(inputs)
    rng = np.random.default_rng(seed)
    bad = []
    for t in times:
        known = t + DURATION[base_tf]

        def scramble(frame, tf):
            f = frame.copy()
            late = f.index + DURATION[tf] > known
            f.loc[late, ["open", "high", "low", "close"]] *= rng.uniform(0.5, 1.5, size=(int(late.sum()), 1))
            f.loc[late, "volume"] *= rng.uniform(0.1, 10.0, size=int(late.sum()))
            return f

        shuffled = {"bars": {tf: scramble(f, tf) for tf, f in inputs["bars"].items()},
                    "context": {s: {tf: scramble(f, tf) for tf, f in d.items()} for s, d in inputs.get("context", {}).items()},
                    "funding": inputs.get("funding")}
        if shuffled["funding"] is not None:
            fu = shuffled["funding"].copy()
            fu.loc[fu.index >= known, "funding_rate"] = rng.normal(0, 0.001, size=int((fu.index >= known).sum()))
            shuffled["funding"] = fu
        other = builder(shuffled)
        rows = full.index[full.index <= t]
        if not _same(full.loc[rows].to_numpy(), other.loc[rows].to_numpy(), tol):
            bad.append(t)
    return bad


def warmup_check(builder, inputs, offsets_days=(0, 50, 100), warmup_days=WARMUP_DAYS, base_tf="4h", tol=1e-5):
    """Features built from series starting later agree, after `warmup_days`, with the full build
    (recursive-analysis idea). Returns {offset: number of mismatching rows}."""
    full = builder(inputs)
    out = {}
    for days in offsets_days:
        start = inputs["bars"][base_tf].index[0] + pd.Timedelta(days=days)

        def late(frame):
            return frame[frame.index >= start]

        sub = {"bars": {tf: late(f) for tf, f in inputs["bars"].items()},
               "context": {s: {tf: late(f) for tf, f in d.items()} for s, d in inputs.get("context", {}).items()},
               "funding": None if inputs.get("funding") is None else late(inputs["funding"])}
        part = builder(sub)
        rows = part.index[part.index >= start + pd.Timedelta(days=warmup_days)]
        a, b = full.loc[rows].to_numpy(dtype=float), part.loc[rows].to_numpy(dtype=float)
        ok = (np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= tol * np.maximum(1.0, np.abs(a)))
        out[days] = int((~ok.all(axis=1)).sum())
    return out
