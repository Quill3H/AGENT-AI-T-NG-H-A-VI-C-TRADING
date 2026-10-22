import pandas as pd

from scripts.run_vision_portfolio import combine_curves


def _s(points):
    return pd.Series([v for _, v in points], index=pd.DatetimeIndex([pd.Timestamp(t, tz="UTC") for t, _ in points]))


def test_combine_curves_sums_sleeves_and_carries_each_forward():
    a = _s([("2021-01-01 00:00", 3000.0), ("2021-01-01 02:00", 3300.0)])
    b = _s([("2021-01-01 01:00", 2900.0)])
    total = combine_curves([a, b], [3000.0, 3000.0])
    assert list(total.values) == [6000.0, 5900.0, 6200.0]


def test_combine_curves_uses_starting_capital_before_first_point():
    a = _s([("2021-01-02", 4000.0)])
    b = _s([("2021-01-01", 1000.0)])
    total = combine_curves([a, b], [5000.0, 5000.0])
    assert list(total.values) == [6000.0, 5000.0]
