import math

import pandas as pd
import pytest

from src.research.robustness import (
    benchmark_dependence,
    drawdown_diagnostics,
    placebo_comparison,
    profit_concentration,
    regime_stability,
)


def _series(values, dates):
    return pd.Series(values, index=pd.DatetimeIndex(dates, tz="UTC"), dtype=float)


def test_drawdown_reports_depth_recovery_and_longest_open_underwater_period():
    equity = _series(
        [100.0, 120.0, 90.0, 120.0, 130.0, 100.0, 110.0],
        ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-05",
         "2026-01-06", "2026-01-07", "2026-01-10"],
    )

    result = drawdown_diagnostics(equity, start_equity=100.0)

    assert result["max_drawdown_pct"] == 25.0
    assert result["worst_peak_at"].startswith("2026-01-02")
    assert result["worst_trough_at"].startswith("2026-01-03")
    assert result["worst_recovered_at"].startswith("2026-01-05")
    assert result["worst_decline_days"] == 1.0
    assert result["worst_recovery_days"] == 2.0
    assert result["worst_underwater_days"] == 3.0
    assert result["longest_underwater_days"] == 4.0
    assert result["longest_underwater_recovered"] is False


def test_unrecovered_worst_drawdown_is_measured_to_the_last_observation():
    equity = _series([100.0, 120.0, 80.0], ["2026-01-01", "2026-01-02", "2026-01-04"])

    result = drawdown_diagnostics(equity, start_equity=100.0)

    assert result["max_drawdown_pct"] == pytest.approx(33.333333)
    assert result["worst_recovered"] is False
    assert result["worst_recovered_at"] is None
    assert result["worst_recovery_days"] is None
    assert result["worst_underwater_days"] == 2.0


def test_profit_concentration_uses_additive_equity_changes_by_period():
    equity = _series(
        [110.0, 150.0, 140.0, 150.0],
        ["2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31"],
    )

    result = profit_concentration(equity, start_equity=100.0)

    assert result["yearly"]["period_pnl"] == {
        "2021": 10.0, "2022": 40.0, "2023": -10.0, "2024": 10.0,
    }
    assert result["yearly"]["top_1_positive_share_pct"] == pytest.approx(66.67, abs=0.01)
    assert result["yearly"]["top_3_positive_share_pct"] == 100.0
    assert result["yearly"]["top_positive_periods"][0] == "2022"


def test_placebo_comparison_reports_empirical_rank_without_claiming_significance():
    result = placebo_comparison(12.0, [1.0, 5.0, 10.0, 15.0], higher_is_better=True)

    assert result["placebo_runs"] == 4
    assert result["candidate_percentile_pct"] == 75.0
    assert result["one_sided_exceedance_probability"] == 0.4
    assert result["placebo_median"] == 7.5
    assert result["beats_all_placebos"] is False
    assert result["higher_is_better"] is True
    assert result["interpretation"] == "DIAGNOSTIC_ONLY"


def test_placebo_comparison_reverses_rank_for_lower_is_better_metrics():
    result = placebo_comparison(10.0, [20.0, 30.0], higher_is_better=False)

    assert result["candidate_percentile_pct"] == 100.0
    assert result["one_sided_exceedance_probability"] == pytest.approx(1 / 3, abs=1e-6)
    assert result["beats_all_placebos"] is True
    assert result["higher_is_better"] is False


def test_benchmark_dependence_separates_up_and_down_periods():
    strategy = _series([0.02, -0.01, 0.03, -0.02], pd.date_range("2026-01-01", periods=4))
    benchmark = _series([0.01, -0.01, 0.02, -0.02], pd.date_range("2026-01-01", periods=4))

    result = benchmark_dependence(strategy, benchmark)

    assert result["observations"] == 4
    assert result["benchmark_up_observations"] == 2
    assert result["benchmark_down_observations"] == 2
    assert result["strategy_return_in_benchmark_up_pct"] == pytest.approx(5.06, abs=0.01)
    assert result["strategy_return_in_benchmark_down_pct"] == pytest.approx(-2.98, abs=0.01)
    expected_beta = float(strategy.cov(benchmark) / benchmark.var())
    assert result["beta"] == pytest.approx(expected_beta)
    assert math.isfinite(result["correlation"])


def test_benchmark_dependence_reports_flat_periods_in_the_decomposition():
    strategy = _series([0.10, 0.50, -0.10], pd.date_range("2026-01-01", periods=3))
    benchmark = _series([0.01, 0.0, -0.01], pd.date_range("2026-01-01", periods=3))

    result = benchmark_dependence(strategy, benchmark)

    assert result["benchmark_flat_observations"] == 1
    assert result["strategy_return_in_benchmark_flat_pct"] == 50.0
    assert result["benchmark_return_in_flat_periods_pct"] == 0.0


def test_regime_stability_reports_each_caller_supplied_regime():
    returns = _series([0.10, -0.05, 0.02, 0.03], pd.date_range("2026-01-01", periods=4))
    regimes = pd.Series(["bull", "bull", "bear", "bear"], index=returns.index)

    result = regime_stability(returns, regimes)

    assert result["regime_count"] == 2
    assert result["profitable_regimes"] == 2
    assert result["regimes"]["bull"]["compounded_return_pct"] == pytest.approx(4.5)
    assert result["regimes"]["bear"]["compounded_return_pct"] == pytest.approx(5.06)
    assert result["regimes"]["bull"]["win_rate_pct"] == 50.0


def test_robustness_diagnostics_fail_closed_on_misaligned_or_invalid_inputs():
    returns = _series([0.01, 0.02], ["2026-01-01", "2026-01-02"])
    shifted = _series([0.01, 0.02], ["2026-01-02", "2026-01-03"])

    with pytest.raises(ValueError, match="same index"):
        benchmark_dependence(returns, shifted)
    with pytest.raises(ValueError, match="same index"):
        regime_stability(returns, pd.Series(["bull", "bear"], index=shifted.index))
    with pytest.raises(ValueError, match="finite"):
        placebo_comparison(1.0, [float("nan")], higher_is_better=True)
    with pytest.raises(TypeError, match="higher_is_better"):
        placebo_comparison(1.0, [0.0], higher_is_better=1)
    with pytest.raises(ValueError, match="sorted"):
        drawdown_diagnostics(returns.sort_index(ascending=False), 100.0)
