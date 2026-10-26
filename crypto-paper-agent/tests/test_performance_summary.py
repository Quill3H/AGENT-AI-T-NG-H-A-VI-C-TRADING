import pandas as pd
import pytest

from src.report.performance_summary import curve_summary, monthly_stats


def _curve(points):
    index = pd.DatetimeIndex([pd.Timestamp(t, tz="UTC") for t, _ in points])
    return pd.Series([v for _, v in points], index=index)


def test_monthly_stats_counts_target_and_losing_months():
    equity = _curve([
        ("2021-01-15", 11000.0), ("2021-01-31", 12500.0),   # Jan +25%
        ("2021-02-28", 11250.0),                            # Feb -10%
        ("2021-03-31", 11475.0),                            # Mar +2%
    ])
    stats = monthly_stats(equity, 10000.0)
    assert stats["monthly_return_pct"] == {"2021-01": 25.0, "2021-02": -10.0, "2021-03": 2.0}
    assert stats["months"] == 3
    assert stats["months_at_or_above_20pct"] == 1
    assert stats["losing_months"] == 1
    assert stats["worst_month_pct"] == -10.0
    assert stats["best_month_pct"] == 25.0
    assert stats["median_month_pct"] == 2.0


def test_monthly_stats_flags_half_account_loss_as_ruin():
    equity = _curve([("2021-01-31", 9000.0), ("2021-02-15", 4900.0), ("2021-02-28", 6000.0)])
    stats = monthly_stats(equity, 10000.0)
    assert stats["lost_half_of_start"] is True
    assert stats["lowest_equity_usd"] == 4900.0


def test_monthly_stats_months_without_points_carry_equity_forward():
    equity = _curve([("2021-01-31", 11000.0), ("2021-03-31", 12100.0)])
    stats = monthly_stats(equity, 10000.0)
    assert stats["monthly_return_pct"] == {"2021-01": 10.0, "2021-02": 0.0, "2021-03": 10.0}


def test_curve_summary_includes_monthly_block():
    equity = _curve([("2021-01-31", 10500.0), ("2021-12-31", 13000.0)])
    start, end = pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC")
    summary = curve_summary(equity, 10000.0, start, end, [])
    assert summary["monthly"]["months"] == 12
    assert summary["monthly"]["lost_half_of_start"] is False
    assert summary["monthly"]["average_month_pct"] == pytest.approx((1.3 ** (1 / 12) - 1) * 100, abs=0.01)
    assert summary["drawdown_diagnostics"]["longest_underwater_days"] == 0.0
    assert summary["profit_concentration"]["yearly"]["top_1_positive_share_pct"] == 100.0


def test_curve_summary_reports_recovery_time_and_open_underwater_duration():
    equity = _curve([
        ("2021-01-01", 10000.0),
        ("2021-01-02", 12000.0),
        ("2021-01-03", 9000.0),
        ("2021-01-05", 12000.0),
        ("2021-01-06", 13000.0),
        ("2021-01-10", 11000.0),
    ])
    start, end = pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2021-01-11", tz="UTC")

    summary = curve_summary(equity, 10000.0, start, end, [])

    assert summary["drawdown_diagnostics"]["worst_recovery_days"] == 2.0
    assert summary["drawdown_diagnostics"]["longest_underwater_days"] == 4.0
    assert summary["drawdown_diagnostics"]["longest_underwater_recovered"] is False


def test_curve_summary_keeps_empty_runs_reportable():
    start, end = pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC")

    summary = curve_summary(pd.Series(dtype=float), 10000.0, start, end, [])

    assert summary["drawdown_diagnostics"]["max_drawdown_pct"] == 0.0
    assert summary["profit_concentration"]["yearly"]["periods"] == 0


def test_curve_summary_headline_drawdown_includes_loss_from_initial_capital():
    equity = _curve([("2021-01-02", 9000.0), ("2021-01-03", 9500.0)])
    start, end = pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2021-01-04", tz="UTC")

    summary = curve_summary(equity, 10000.0, start, end, [])

    assert summary["max_drawdown_pct"] == 10.0
    assert summary["max_drawdown_pct"] == summary["drawdown_diagnostics"]["max_drawdown_pct"]
