"""Pure diagnostics for recovery time, concentration, placebo and regime dependence."""

import math
from numbers import Real

import numpy as np
import pandas as pd


def _finite_number(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _series(values, name, *, returns=False):
    if not isinstance(values, pd.Series):
        raise TypeError(f"{name} must be a pandas Series")
    if values.empty and not isinstance(values.index, pd.DatetimeIndex):
        return pd.Series(index=pd.DatetimeIndex([], tz="UTC"), dtype=float)
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError(f"{name} must use a DatetimeIndex")
    if values.index.has_duplicates or not values.index.is_monotonic_increasing:
        raise ValueError(f"{name} timestamps must be sorted and unique")
    if values.index.tz is None or any(ts.utcoffset().total_seconds() != 0 for ts in values.index):
        raise ValueError(f"{name} timestamps must use UTC")
    parsed = pd.Series(
        [_finite_number(value, f"{name} value") for value in values],
        index=values.index,
        dtype=float,
    )
    if returns and (parsed < -1.0).any():
        raise ValueError(f"{name} returns must not be below -100%")
    if not returns and (parsed < 0.0).any():
        raise ValueError(f"{name} equity must be non-negative")
    return parsed


def _iso(timestamp):
    return pd.Timestamp(timestamp).isoformat() if timestamp is not None else None


def _days(start, end):
    return round(float((pd.Timestamp(end) - pd.Timestamp(start)).total_seconds() / 86400.0), 6)


def drawdown_diagnostics(equity, start_equity, start=None):
    """Describe the deepest and longest peak-to-recovery episodes on an equity curve."""
    equity = _series(equity, "equity")
    start_equity = _finite_number(start_equity, "start_equity")
    if start_equity <= 0:
        raise ValueError("start_equity must be positive")
    if equity.empty:
        return {
            "max_drawdown_pct": 0.0,
            "worst_peak_at": None,
            "worst_trough_at": None,
            "worst_recovered_at": None,
            "worst_decline_days": 0.0,
            "worst_recovery_days": 0.0,
            "worst_underwater_days": 0.0,
            "worst_recovered": True,
            "longest_underwater_days": 0.0,
            "longest_underwater_start_at": None,
            "longest_underwater_end_at": None,
            "longest_underwater_recovered": True,
        }

    first_at = equity.index[0]
    peak_at = pd.Timestamp(start) if start is not None else first_at
    if peak_at.tzinfo is None or peak_at.utcoffset().total_seconds() != 0:
        raise ValueError("start must use UTC")
    if peak_at > first_at:
        raise ValueError("start must not be after the first equity observation")

    peak_value = start_equity
    in_drawdown = False
    episode_peak_at = None
    episodes = []
    max_dd = 0.0
    worst_peak_at = None
    worst_peak_value = None
    worst_trough_at = None

    for timestamp, value in equity.items():
        if value >= peak_value:
            if in_drawdown:
                episodes.append((episode_peak_at, timestamp, True))
                in_drawdown = False
            peak_value = float(value)
            peak_at = timestamp
            continue

        if not in_drawdown:
            in_drawdown = True
            episode_peak_at = peak_at
        drawdown = (peak_value - float(value)) / peak_value * 100.0
        if drawdown > max_dd:
            max_dd = drawdown
            worst_peak_at = peak_at
            worst_peak_value = peak_value
            worst_trough_at = timestamp

    if in_drawdown:
        episodes.append((episode_peak_at, equity.index[-1], False))

    if max_dd == 0.0:
        longest = (None, None, True)
        longest_days = 0.0
        recovered_at = None
    else:
        post_trough = equity.loc[equity.index > worst_trough_at]
        recovered = post_trough[post_trough >= worst_peak_value]
        recovered_at = recovered.index[0] if len(recovered) else None
        longest = max(episodes, key=lambda episode: _days(episode[0], episode[1]))
        longest_days = _days(longest[0], longest[1])

    worst_end = recovered_at if recovered_at is not None else equity.index[-1]
    return {
        "max_drawdown_pct": round(max_dd, 6),
        "worst_peak_at": _iso(worst_peak_at),
        "worst_trough_at": _iso(worst_trough_at),
        "worst_recovered_at": _iso(recovered_at),
        "worst_decline_days": _days(worst_peak_at, worst_trough_at) if worst_peak_at is not None else 0.0,
        "worst_recovery_days": _days(worst_trough_at, recovered_at) if recovered_at is not None else None,
        "worst_underwater_days": _days(worst_peak_at, worst_end) if worst_peak_at is not None else 0.0,
        "worst_recovered": recovered_at is not None or max_dd == 0.0,
        "longest_underwater_days": longest_days,
        "longest_underwater_start_at": _iso(longest[0]),
        "longest_underwater_end_at": _iso(longest[1]),
        "longest_underwater_recovered": longest[2],
    }


def _period_concentration(equity, start_equity, frequency):
    period_index = equity.index.tz_convert(None).to_period(frequency)
    closes = equity.groupby(period_index).last()
    if closes.empty:
        return {
            "periods": 0, "positive_periods": 0, "period_pnl": {},
            "gross_positive_change": 0.0, "gross_negative_change": 0.0,
            "top_1_positive_share_pct": None, "top_3_positive_share_pct": None,
            "top_positive_periods": [],
        }
    closes = closes.reindex(pd.period_range(closes.index[0], closes.index[-1], freq=frequency)).ffill()
    opening = closes.shift(1).fillna(start_equity)
    pnl = closes - opening
    positive = pnl[pnl > 0].sort_values(ascending=False)
    gross_positive = float(positive.sum())
    gross_negative = float(-pnl[pnl < 0].sum())

    def share(count):
        return round(float(positive.iloc[:count].sum() / gross_positive * 100.0), 2) if gross_positive else None

    return {
        "periods": int(len(pnl)),
        "positive_periods": int((pnl > 0).sum()),
        "period_pnl": {str(period): round(float(value), 2) for period, value in pnl.items()},
        "gross_positive_change": round(gross_positive, 2),
        "gross_negative_change": round(gross_negative, 2),
        "top_1_positive_share_pct": share(1),
        "top_3_positive_share_pct": share(3),
        "top_positive_periods": [str(period) for period in positive.index[:3]],
    }


def profit_concentration(equity, start_equity):
    """Measure how much gross positive equity change came from the best months and years."""
    equity = _series(equity, "equity")
    start_equity = _finite_number(start_equity, "start_equity")
    if start_equity <= 0:
        raise ValueError("start_equity must be positive")
    return {
        "monthly": _period_concentration(equity, start_equity, "M"),
        "yearly": _period_concentration(equity, start_equity, "Y"),
    }


def placebo_comparison(candidate_value, placebo_values, *, higher_is_better):
    """Rank one candidate metric against all preregistered placebo-run values."""
    if not isinstance(higher_is_better, bool):
        raise TypeError("higher_is_better must be boolean")
    candidate = _finite_number(candidate_value, "candidate_value")
    placebos = [_finite_number(value, "placebo value") for value in placebo_values]
    if not placebos:
        raise ValueError("placebo_values must not be empty")
    values = np.asarray(placebos, dtype=float)
    beaten = int(np.sum(values < candidate)) if higher_is_better else int(np.sum(values > candidate))
    ties = int(np.sum(values == candidate))
    at_least_as_good = int(np.sum(values >= candidate)) if higher_is_better else int(np.sum(values <= candidate))
    percentile = (beaten + 0.5 * ties) / len(values) * 100.0
    return {
        "candidate_value": candidate,
        "higher_is_better": higher_is_better,
        "placebo_runs": len(placebos),
        "placebo_mean": round(float(values.mean()), 6),
        "placebo_median": round(float(np.median(values)), 6),
        "placebo_5th_percentile": round(float(np.percentile(values, 5)), 6),
        "placebo_95th_percentile": round(float(np.percentile(values, 95)), 6),
        "candidate_percentile_pct": round(percentile, 6),
        "one_sided_exceedance_probability": round((1 + at_least_as_good) / (len(values) + 1), 6),
        "beats_all_placebos": bool(
            candidate > float(values.max()) if higher_is_better else candidate < float(values.min())
        ),
        "interpretation": "DIAGNOSTIC_ONLY",
    }


def _compounded_pct(returns):
    return round(float(((1.0 + returns).prod() - 1.0) * 100.0), 6) if len(returns) else None


def benchmark_dependence(strategy_returns, benchmark_returns):
    """Describe strategy behavior when the supplied benchmark rises and falls."""
    strategy = _series(strategy_returns, "strategy_returns", returns=True)
    benchmark = _series(benchmark_returns, "benchmark_returns", returns=True)
    if not strategy.index.equals(benchmark.index):
        raise ValueError("strategy_returns and benchmark_returns must have the same index")
    if strategy.empty:
        raise ValueError("return series must not be empty")
    variance = float(benchmark.var()) if len(benchmark) > 1 else 0.0
    beta = float(strategy.cov(benchmark) / variance) if variance > 0 else None
    correlation = float(strategy.corr(benchmark)) if variance > 0 and float(strategy.var()) > 0 else None
    up = benchmark > 0
    down = benchmark < 0
    flat = benchmark == 0
    return {
        "observations": int(len(strategy)),
        "beta": round(beta, 6) if beta is not None else None,
        "correlation": round(correlation, 6) if correlation is not None else None,
        "benchmark_up_observations": int(up.sum()),
        "benchmark_down_observations": int(down.sum()),
        "benchmark_flat_observations": int(flat.sum()),
        "strategy_return_in_benchmark_up_pct": _compounded_pct(strategy[up]),
        "strategy_return_in_benchmark_down_pct": _compounded_pct(strategy[down]),
        "strategy_return_in_benchmark_flat_pct": _compounded_pct(strategy[flat]),
        "benchmark_return_in_up_periods_pct": _compounded_pct(benchmark[up]),
        "benchmark_return_in_down_periods_pct": _compounded_pct(benchmark[down]),
        "benchmark_return_in_flat_periods_pct": _compounded_pct(benchmark[flat]),
    }


def regime_stability(strategy_returns, regimes):
    """Aggregate periodic strategy returns by caller-supplied causal regime labels."""
    returns = _series(strategy_returns, "strategy_returns", returns=True)
    if not isinstance(regimes, pd.Series):
        raise TypeError("regimes must be a pandas Series")
    if not returns.index.equals(regimes.index):
        raise ValueError("strategy_returns and regimes must have the same index")
    if returns.empty:
        raise ValueError("strategy_returns must not be empty")
    if regimes.isna().any() or any(not isinstance(value, str) or not value.strip() for value in regimes):
        raise ValueError("regimes must contain non-empty labels")
    result = {}
    for label in dict.fromkeys(regimes.tolist()):
        values = returns[regimes == label]
        result[label] = {
            "observations": int(len(values)),
            "compounded_return_pct": _compounded_pct(values),
            "mean_return_pct": round(float(values.mean() * 100.0), 6),
            "win_rate_pct": round(float((values > 0).mean() * 100.0), 6),
        }
    compounded = [stats["compounded_return_pct"] for stats in result.values()]
    return {
        "regime_count": len(result),
        "profitable_regimes": sum(value > 0 for value in compounded),
        "best_regime_return_pct": max(compounded),
        "worst_regime_return_pct": min(compounded),
        "regimes": result,
    }
