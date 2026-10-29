"""
src/research/ml/walkforward.py
==============================
Purged walk-forward runner and the market-neutral book used to score it (design §5/§6).

The book is a research measure, not the engine: at each rebalance time it holds half of equity
long the top `quantile` of coins by model score and half short the bottom `quantile`, closes at
the label's exit, and pays the round-trip cost on the whole notional. Any candidate that passes
gate D must be re-run through the project engine and risk state (round 18 lesson) before forward.
"""
import numpy as np
import pandas as pd

from src.research.ml import labels, models, splits as splitlib


def run(panel, feature_cols, spec, first_test, last_test, train_days=730, test_days=30,
        embargo=pd.Timedelta(days=1), label_col="label", weight_col=None):
    """OOS predictions for every test row: panel columns time, symbol, fill_time, exit_time, ret,
    the label and features. Returns the test rows with p, score, abstain and split_start."""
    panel = panel.reset_index(drop=True)
    x = panel[feature_cols].to_numpy(dtype=float)
    if not np.isfinite(x).all():
        raise ValueError("features contain NaN/inf; drop warm-up rows before the walk-forward")
    y = panel[label_col].to_numpy(dtype=int)
    w = panel[weight_col].to_numpy(dtype=float) if weight_col else np.ones(len(panel))
    t, t1 = pd.DatetimeIndex(panel["time"]), pd.DatetimeIndex(panel["exit_time"])
    out = []
    for train, test, start, _ in splitlib.purged_walk_forward(t, t1, first_test, last_test, train_days, test_days, embargo):
        fit, cal = splitlib.inner_split(t, t1, train, embargo=embargo)
        if len(fit) < 50 or len(cal) < 20 or len(np.unique(y[fit])) < 2 or len(np.unique(y[cal])) < 2:
            continue
        p, score, abstain = models.fit_predict(spec, x[fit], y[fit], w[fit], x[cal], y[cal], x[test])
        part = panel.iloc[test][["time", "symbol", "exit_time", "ret", label_col]].copy()
        part["p"], part["score"], part["abstain"], part["split_start"] = p, score, abstain, start
        out.append(part)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def long_short_book(preds, quantile=0.3, cost=labels.ROUND_TRIP, score_col="score"):
    """Per rebalance time: 0.5 * mean ret of the top quantile - 0.5 * mean ret of the bottom
    quantile - cost (whole notional opened and closed once). Also returns per-symbol P&L.
    preds columns: time, symbol, ret, score, abstain."""
    rows, pnl = [], {}
    for time, g in preds[~preds["abstain"]].groupby("time"):
        n = int(np.floor(len(g) * quantile))
        if n < 1:
            continue
        g = g.sort_values(score_col)
        short, long_ = g.iloc[:n], g.iloc[-n:]
        r = 0.5 * long_["ret"].mean() - 0.5 * short["ret"].mean() - cost
        rows.append((time, r))
        for sym, rr in zip(long_["symbol"], long_["ret"]):
            pnl[sym] = pnl.get(sym, 0.0) + 0.5 * rr / n
        for sym, rr in zip(short["symbol"], short["ret"]):
            pnl[sym] = pnl.get(sym, 0.0) - 0.5 * rr / n
    series = pd.Series(dict(rows), dtype=float).sort_index()
    return series, pnl


def daily(series):
    """Per-period book returns summed into UTC calendar days (compounding inside a day ignored),
    with flat days as zero so Sharpe and drawdown see every calendar day."""
    if series.empty:
        return series
    idx = pd.DatetimeIndex(series.index)
    out = series.groupby(idx.floor("D")).sum()
    return out.reindex(pd.date_range(out.index.min(), out.index.max(), freq="D"), fill_value=0.0)


def cross_sectional_demean(panel, cols):
    """Each feature minus its mean across the symbols present at the same time: a market-neutral
    label needs features without the common market move."""
    out = panel.copy()
    out[cols] = panel[cols] - panel.groupby("time")[cols].transform("mean")
    return out


def permutation_null(panel, feature_cols, spec, first_test, last_test, reps, seed=0, label_col="label",
                     quantile=0.3, **kw):
    """Sharpe of the daily book when labels are block-permuted within each symbol (30-day blocks),
    re-running the whole walk-forward each time."""
    from src.research.ml import stats

    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        shuffled = panel.copy()
        shuffled[label_col] = stats.block_permute(panel[label_col].to_numpy(), panel["time"], panel["symbol"], rng=rng)
        preds = run(shuffled, feature_cols, spec, first_test, last_test, label_col=label_col, **kw)
        # Score the permuted model on the true returns.
        book, _ = long_short_book(preds, quantile)
        out.append(stats.sharpe(daily(book)))
    return np.asarray(out)
