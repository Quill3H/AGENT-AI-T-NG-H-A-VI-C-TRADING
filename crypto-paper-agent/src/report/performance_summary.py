"""Owner-facing summary of one paper run: yearly equity path, bootstrap uncertainty and the success verdict.

Success rule agreed with the owner (2026-10-16): starting from 10,000 USDT, the
run must end more than 20% up and grow steadily over time, which we measure as
at least 4 of 5 calendar years profitable and no single year losing more than
10%.  Anything else counts as "try a new method".
"""
import numpy as np
import pandas as pd

from src.report.lifecycles import completed_lifecycles
from src.research.robustness import drawdown_diagnostics, profit_concentration

SUCCESS_MIN_RETURN_PCT = 20.0
SUCCESS_MIN_PROFITABLE_YEAR_SHARE = 0.8
SUCCESS_WORST_YEAR_PCT = -10.0


def equity_series(snapshots):
    if not snapshots:
        return pd.Series(dtype=float)
    series = pd.Series(
        [s.equity for s in snapshots],
        index=pd.DatetimeIndex([pd.Timestamp(s.timestamp) for s in snapshots]),
    )
    return series[~series.index.duplicated(keep="last")].sort_index()


def yearly_returns(equity, start_equity):
    year_end = equity.groupby(equity.index.year).last()
    opening = year_end.shift(1).fillna(start_equity)
    return {int(year): round(float((close / open_ - 1.0) * 100.0), 2) for year, close, open_ in zip(year_end.index, year_end, opening)}


MONTHLY_TARGET_PCT = 20.0


def monthly_stats(equity, start_equity):
    """Month-by-month view the owner asked for: how many months hit +20%, how many lost, and ruin risk."""
    utc_index = equity.index.tz_convert(None) if equity.index.tz is not None else equity.index
    month_end = equity.groupby(utc_index.to_period("M")).last()
    month_end = month_end.reindex(pd.period_range(month_end.index[0], month_end.index[-1], freq="M")).ffill()
    opening = month_end.shift(1).fillna(start_equity)
    returns = ((month_end / opening - 1.0) * 100.0).round(2)
    months = len(returns)
    growth = float(month_end.iloc[-1]) / float(start_equity)
    return {
        "months": months,
        "monthly_return_pct": {str(period): float(value) for period, value in returns.items()},
        "average_month_pct": round((growth ** (1.0 / months) - 1.0) * 100.0, 2) if growth > 0 else -100.0,
        "median_month_pct": round(float(returns.median()), 2),
        "best_month_pct": round(float(returns.max()), 2),
        "worst_month_pct": round(float(returns.min()), 2),
        "months_at_or_above_20pct": int((returns >= MONTHLY_TARGET_PCT).sum()),
        "losing_months": int((returns < 0).sum()),
        "lowest_equity_usd": round(float(min(equity.min(), start_equity)), 2),
        "lost_half_of_start": bool(equity.min() <= 0.5 * start_equity),
    }


def bootstrap_mean_ci(values, samples=5000, seed=7):
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(samples, len(values)), replace=True).mean(axis=1)
    return [round(float(np.percentile(means, 2.5)), 2), round(float(np.percentile(means, 97.5)), 2)]


def verdict(total_return_pct, years):
    if not years:
        return "FAIL"
    profitable = sum(1 for r in years.values() if r > 0) / len(years)
    steady = profitable >= SUCCESS_MIN_PROFITABLE_YEAR_SHARE and min(years.values()) >= SUCCESS_WORST_YEAR_PCT
    return "SUCCESS" if total_return_pct > SUCCESS_MIN_RETURN_PCT and steady else "FAIL"


def max_drawdown_pct(equity):
    peak = equity.cummax()
    return round(float(((peak - equity) / peak).max() * 100.0), 2) if len(equity) else 0.0


def curve_summary(equity, start_equity, start, end, trade_pnl):
    """Summary for runs that produce an equity curve and per-trade P&L outside the broker."""
    if equity.empty and not isinstance(equity.index, pd.DatetimeIndex):
        equity = pd.Series(index=pd.DatetimeIndex([], tz="UTC"), dtype=float)
    equity = equity[equity.index < end]
    final = float(equity.iloc[-1]) if len(equity) else float(start_equity)
    total_return = (final / start_equity - 1.0) * 100.0
    years = yearly_returns(equity, start_equity) if len(equity) else {}
    drawdown = drawdown_diagnostics(equity, start_equity, start=start)
    return {
        "window": [str(start.date()), str((end - pd.Timedelta(days=1)).date())],
        "start_equity_usd": float(start_equity),
        "final_equity_usd": round(final, 2),
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(drawdown["max_drawdown_pct"], 2),
        "yearly_return_pct": years,
        "completed_trades": len(trade_pnl),
        "win_rate_pct": round(100.0 * sum(p > 0 for p in trade_pnl) / len(trade_pnl), 1) if trade_pnl else None,
        "mean_trade_usd": round(float(np.mean(trade_pnl)), 2) if trade_pnl else None,
        "mean_trade_usd_95ci": bootstrap_mean_ci(trade_pnl),
        "monthly": monthly_stats(equity, start_equity) if len(equity) else None,
        "drawdown_diagnostics": drawdown,
        "profit_concentration": profit_concentration(equity, start_equity),
        "verdict": verdict(total_return, years),
    }


def summarize_run(broker, metrics, start, end):
    start_equity = float(broker.initial_balance)
    full_equity = equity_series(broker.account_snapshots)
    diagnostic_equity = full_equity[full_equity.index <= end].copy()
    diagnostic_equity.loc[end] = float(broker.equity)
    diagnostic_equity = diagnostic_equity.sort_index()
    # The final settlement snapshot is stamped at the window end (next year's first instant).
    equity = full_equity[full_equity.index < end].copy()
    if len(equity):
        equity.iloc[-1] = float(broker.equity)
    years = yearly_returns(equity, start_equity) if len(equity) else {}
    trades = completed_lifecycles(broker.trade_history)
    pnl = [float(t["net_pnl"] if isinstance(t, dict) else t.net_pnl) for t in trades]
    total_return = float(metrics["total_return_pct"])
    drawdown = drawdown_diagnostics(diagnostic_equity, start_equity, start=start)
    return {
        "window": [str(start.date()), str((end - pd.Timedelta(days=1)).date())],
        "start_equity_usd": start_equity,
        "final_equity_usd": round(float(broker.equity), 2),
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(drawdown["max_drawdown_pct"], 2),
        "yearly_return_pct": years,
        "completed_trades": len(pnl),
        "win_rate_pct": round(100.0 * sum(p > 0 for p in pnl) / len(pnl), 1) if pnl else None,
        "mean_trade_usd": round(float(np.mean(pnl)), 2) if pnl else None,
        "mean_trade_usd_95ci": bootstrap_mean_ci(pnl),
        "profit_factor": metrics.get("profit_factor"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "rejection_reasons": metrics.get("rejection_reasons"),
        "monthly": monthly_stats(equity, start_equity) if len(equity) else None,
        "drawdown_diagnostics": drawdown,
        "profit_concentration": profit_concentration(equity, start_equity),
        "verdict": verdict(total_return, years),
    }
