"""
src/research/ml/labels.py
=========================
Leak-free labels for the ML study (docs/reports-vi/thiet-ke-bang-chung-hoc-may-2026-10-23.md, §6).

Timing contract shared by every label here: a signal is formed at the close of bar i (open time
index[i]), the fill is bar i+1's open, and the label interval [fill, exit] is what the purge in
splits.py removes from training. Costs are the project's taker fee + slippage per side on notional;
funding is every settlement in (fill time, exit time], including off-schedule events (round 17).
"""
import numpy as np
import pandas as pd

COST_PER_SIDE = 0.0005 + 0.0003  # config/default_config.yaml taker_pct + slippage_pct
ROUND_TRIP = 2 * COST_PER_SIDE


def atr(frame, n=14):
    prev = frame["close"].shift()
    tr = pd.concat([frame["high"] - frame["low"], (frame["high"] - prev).abs(), (frame["low"] - prev).abs()],
                   axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def cusum_events(close, span=100):
    """Bar positions where a symmetric CUSUM of log returns crosses the past EWM std."""
    r = np.log(close).diff()
    h = r.ewm(span=span, adjust=False).std().shift()
    events, s_pos, s_neg = [], 0.0, 0.0
    for i, (ri, hi) in enumerate(zip(r.to_numpy(), h.to_numpy())):
        if not (np.isfinite(ri) and np.isfinite(hi)):
            continue
        s_pos, s_neg = max(0.0, s_pos + ri), min(0.0, s_neg + ri)
        if s_pos > hi or s_neg < -hi:
            events.append(i)
            s_pos = s_neg = 0.0
    return np.asarray(events, dtype=int)


def funding_between(funding, start, end):
    """Sum of funding rates settled in (start, end] for each pair of times (vectorised)."""
    cum = np.concatenate([[0.0], np.cumsum(funding["funding_rate"].to_numpy())])
    a = funding.index.searchsorted(start, side="right")
    b = funding.index.searchsorted(end, side="right")
    return cum[b] - cum[a]


def triple_barrier(frame, funding, events, k, horizon, side, cost=ROUND_TRIP):
    """One row per event for a long (side=+1) or short (side=-1) position.

    Stop and target sit k * ATR14 (known at bar i's close) from the fill. A bar touching both
    counts as the stop; a gap through the stop exits at the worse open, a gap through the target
    exits at the target (no gap bonus). Otherwise the position closes at the close of bar i+horizon.
    """
    if side not in (1, -1):
        raise ValueError("side must be +1 or -1")
    o, hi, lo, c = (frame[col].to_numpy() for col in ("open", "high", "low", "close"))
    a = atr(frame).to_numpy()
    idx, n = frame.index, len(frame)
    step = idx[1] - idx[0]
    rows = []
    for i in events:
        if i + 1 >= n or not np.isfinite(a[i]):
            continue
        fill = o[i + 1]
        dist = k * a[i] / c[i] * fill
        stop, target = fill - side * dist, fill + side * dist
        last = min(i + horizon, n - 1)
        exit_price, exit_j, kind = c[last], last, "vertical"
        for j in range(i + 1, last + 1):
            stop_hit = lo[j] <= stop if side == 1 else hi[j] >= stop
            target_hit = hi[j] >= target if side == 1 else lo[j] <= target
            if stop_hit:
                gap = (o[j] < stop) if side == 1 else (o[j] > stop)
                exit_price, exit_j, kind = (o[j] if gap and j > i + 1 else stop), j, "stop"
                break
            if target_hit:
                exit_price, exit_j, kind = target, j, "target"
                break
        rows.append({"bar": i, "start": i + 1, "end": exit_j, "signal_time": idx[i], "fill_time": idx[i + 1],
                     "exit_time": idx[exit_j] + step, "kind": kind, "gross": side * (exit_price / fill - 1)})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    fund = funding_between(funding, out["fill_time"], out["exit_time"])
    out["funding"] = -side * fund  # a long pays positive funding, a short receives it
    out["net"] = out["gross"] - cost + out["funding"]
    out["label"] = (out["net"] > 0).astype(int)
    return out


def forward_returns(frame, funding, horizon, side=1):
    """Per bar i: side-signed return from bar i+1's open to bar i+horizon's close, plus funding
    in that interval (no costs; the portfolio simulation charges them). NaN where incomplete."""
    o, c, idx = frame["open"].to_numpy(), frame["close"].to_numpy(), frame.index
    n, step = len(frame), idx[1] - idx[0]
    ret = np.full(n, np.nan)
    fill_t = np.array([idx[min(i + 1, n - 1)] for i in range(n)])
    exit_t = np.array([idx[min(i + horizon, n - 1)] + step for i in range(n)])
    ok = np.arange(n) + horizon < n
    ret[ok] = side * (c[np.arange(n)[ok] + horizon] / o[np.arange(n)[ok] + 1] - 1)
    fund = np.zeros(n)
    fund[ok] = funding_between(funding, pd.DatetimeIndex(fill_t[ok]), pd.DatetimeIndex(exit_t[ok]))
    return pd.DataFrame({"ret": ret - side * fund, "fill_time": fill_t, "exit_time": exit_t}, index=idx).where(
        pd.Series(ok, index=idx), np.nan)


def market_neutral_labels(frames, fundings, horizon, every=None):
    """Long-format panel of relative labels (the recommended primary label).

    At every `every`-th bar (default: horizon, so labels of one coin do not overlap), each coin's
    funding-adjusted forward return minus the equal-weight mean of the coins present that bar.
    label = 1 when the coin beats the basket. Columns: time, symbol, fill_time, exit_time, ret,
    rel_ret, label. Costs are not in the label: both legs of a long/short book pay them.
    """
    every = every or horizon
    parts = []
    for symbol, frame in frames.items():
        fr = forward_returns(frame, fundings[symbol], horizon)
        fr = fr.iloc[::every].dropna(subset=["ret"])
        fr = fr.assign(symbol=symbol)
        parts.append(fr)
    panel = pd.concat(parts).rename_axis("time").reset_index()
    panel["rel_ret"] = panel["ret"] - panel.groupby("time")["ret"].transform("mean")
    counts = panel.groupby("time")["symbol"].transform("count")
    panel = panel[counts >= 2].copy()
    panel["label"] = (panel["rel_ret"] > 0).astype(int)
    return panel.sort_values(["time", "symbol"]).reset_index(drop=True)


def uniqueness(start, end, n):
    """Average uniqueness of each label (Lopez de Prado 2018, ch. 4): mean over its bars of
    1 / number of concurrent labels. start/end are inclusive bar positions in one series."""
    start, end = np.asarray(start, dtype=int), np.asarray(end, dtype=int)
    if len(start) == 0:
        return np.array([])
    conc = np.zeros(n + 1)
    np.add.at(conc, start, 1)
    np.add.at(conc, end + 1, -1)
    conc = np.cumsum(conc)[:n]
    inv = np.concatenate([[0.0], np.cumsum(1.0 / np.where(conc > 0, conc, np.inf))])
    return (inv[end + 1] - inv[start]) / (end - start + 1)
