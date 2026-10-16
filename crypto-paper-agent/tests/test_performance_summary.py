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
