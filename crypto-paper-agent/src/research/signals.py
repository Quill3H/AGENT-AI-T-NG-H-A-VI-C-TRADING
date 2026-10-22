"""Daily signal generators for round 4 (docs/research/2026-10-16-new-directions.md).

All functions are causal: the value for day d (a daily bar that opens at d and
closes at d+1 00:00 UTC) uses only bars up to and including d.  The paper engine
then trades the signal at the next 15m open.  Models are plain numpy so the
project needs no new dependency.
"""
import numpy as np
import pandas as pd

from src.strategies.indicator_suite import ema, rsi

PRICE_FEATURES = ["ret_1", "ret_5", "ret_20", "vol_20", "dist_ema50", "rsi_14", "taker_buy_5", "volume_z20"]
METRIC_FEATURES = ["oi_chg_1", "oi_chg_5", "top_ls", "global_ls", "taker_ls"]


def daily_features(bars, metrics=None):
    """Feature table for one coin, indexed like its daily bars."""
    close = bars["close"]
    log_ret = np.log(close).diff()
    out = pd.DataFrame(index=bars.index)
    out["ret_1"] = close.pct_change(1)
    out["ret_5"] = close.pct_change(5)
    out["ret_20"] = close.pct_change(20)
    out["vol_20"] = log_ret.rolling(20).std()
    out["dist_ema50"] = close / ema(close, 50) - 1.0
    out["rsi_14"] = rsi(close, 14) / 100.0
    share = bars["taker_buy_base_volume"] / bars["volume"].replace(0.0, np.nan)
    out["taker_buy_5"] = share.rolling(5).mean() - 0.5
    volume = np.log(bars["volume"].replace(0.0, np.nan))
    out["volume_z20"] = (volume - volume.rolling(20).mean()) / volume.rolling(20).std()
    if metrics is not None:
        m = metrics.reindex(bars.index)
        out["oi_chg_1"] = m["oi_value_last"].pct_change(1, fill_method=None)
        out["oi_chg_5"] = m["oi_value_last"].pct_change(5, fill_method=None)
        out["top_ls"] = np.log(m["top_ls_mean"])
        out["global_ls"] = np.log(m["global_ls_mean"])
        out["taker_ls"] = np.log(m["taker_ratio_mean"])
    return out


def forward_sign(close, horizon):
    """+1/0 label: did the close rise over the next `horizon` days (NaN where unknown)."""
    future = close.shift(-horizon) / close - 1.0
    return (future > 0).astype(float).where(future.notna())


def fit_logistic(x, y, l2=1.0, iterations=50):
    """L2-regularised logistic regression by Newton's method; returns weights incl. bias as w[0]."""
    x = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(x.shape[1])
    penalty = np.full(x.shape[1], l2)
    penalty[0] = 0.0
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-np.clip(x @ w, -30, 30)))
        gradient = x.T @ (p - y) + penalty * w
        hessian = (x * (p * (1 - p))[:, None]).T @ x + np.diag(penalty) + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(hessian, gradient)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


def walk_forward_probabilities(panel, closes, features, horizon=5, retrain_days=30, min_history=365, l2=1.0):
    """Pooled walk-forward model; returns P(up over next `horizon` days) per day x coin.

    At a retrain day t the model sees only rows d with d + horizon <= t (their label
    is already known at t's close).  Predictions until the next retrain use that model.
    """
    days = sorted(set().union(*[f.index for f in panel.values()]))
    if not days:
        return pd.DataFrame()
    labels = {s: forward_sign(closes[s], horizon) for s in panel}
    first_day = days[0]
    probs = pd.DataFrame(np.nan, index=pd.DatetimeIndex(days), columns=list(panel))
    model, last_fit = None, None
    for t in days:
        if (t - first_day).days < min_history:
            continue
        if last_fit is None or (t - last_fit).days >= retrain_days:
            cutoff = t - pd.Timedelta(days=horizon)
            rows_x, rows_y = [], []
            for s, f in panel.items():
                block = f.loc[f.index <= cutoff, features]
                label = labels[s].reindex(block.index)
                keep = block.notna().all(axis=1) & label.notna()
                rows_x.append(block[keep].to_numpy())
                rows_y.append(label[keep].to_numpy())
            x, y = np.vstack(rows_x), np.concatenate(rows_y)
            if len(y) >= 200:
                mean, std = x.mean(axis=0), x.std(axis=0)
                std[std == 0] = 1.0
                model = (fit_logistic((x - mean) / std, y, l2), mean, std)
                last_fit = t
        if model is None:
            continue
        w, mean, std = model
        for s, f in panel.items():
            if t in f.index:
                row = f.loc[t, features].to_numpy(dtype=float)
                if np.isfinite(row).all():
                    z = np.concatenate([[1.0], (row - mean) / std])
                    probs.loc[t, s] = 1.0 / (1.0 + np.exp(-z @ w))
    return probs


def probability_positions(probs, enter=0.55, exit_level=0.5):
    """Hold state per coin: enter long above `enter`, short below 1-`enter`; leave when p crosses `exit_level`."""
    out = pd.DataFrame(0.0, index=probs.index, columns=probs.columns)
    for s in probs.columns:
        state = 0.0
        for t, p in probs[s].items():
            if not np.isfinite(p):
                state = 0.0
            elif state > 0 and p < exit_level:
                state = 0.0
            elif state < 0 and p > exit_level:
                state = 0.0
            if state == 0.0 and np.isfinite(p):
                state = 1.0 if p > enter else (-1.0 if p < 1.0 - enter else 0.0)
            out.loc[t, s] = state
    return out


def cross_sectional_positions(closes, lookback=30, rebalance_days=7):
    """Every `rebalance_days` rank coins by `lookback`-day return: top third long, bottom third short."""
    momentum = closes.pct_change(lookback, fill_method=None)
    out = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    current, last = pd.Series(0.0, index=closes.columns), None
    for t, row in momentum.iterrows():
        valid = row.dropna()
        if len(valid) >= 3 and (last is None or (t - last).days >= rebalance_days):
            ranked = valid.sort_values()
            third = len(ranked) // 3
            current = pd.Series(0.0, index=closes.columns)
            current[ranked.index[-third:]] = 1.0
            current[ranked.index[:third]] = -1.0
            last = t
        out.loc[t] = current
    return out
