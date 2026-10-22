"""Independent fixtures for causal formation and fixed-v1 signal rules."""
import importlib
import importlib.util

import numpy as np
import pandas as pd
import pytest


def api():
    name = "src.strategies.eth_btc_cointegration"
    assert importlib.util.find_spec(name), "cointegration strategy is not implemented"
    return importlib.import_module(name)


def history(seed=7):
    rng = np.random.default_rng(seed)
    when = pd.Timestamp("2026-06-01", tz="UTC")
    index = pd.date_range(end=when - pd.Timedelta(hours=4), periods=600, freq="4h")
    btc = 50000 + np.cumsum(rng.normal(0, 500, len(index)))
    residual = np.zeros(len(index))
    for i in range(1, len(index)):
        residual[i] = .9 * residual[i-1] + rng.normal(0, 2)
    return pd.DataFrame({"ETHUSDT": 500 + .05 * btc + residual,
                         "BTCUSDT": btc}, index=index), when


def test_fit_uses_exact_closed_90_days_and_recovers_positive_beta():
    frame, when = history()
    result = api().fit_week(frame, when)
    assert result["rows"] == 540
    assert result["model"].beta == pytest.approx(.05, abs=.001)
    assert 0 < result["model"].phi < 1
    assert result["model"].sigma > 0
    assert len(result["adf_pvalues"]) == 4


def test_future_prices_do_not_change_frozen_model():
    frame, when = history()
    past = api().fit_week(frame, when)
    future = pd.DataFrame({"ETHUSDT": [1e9], "BTCUSDT": [1.]}, index=[when])
    assert api().fit_week(pd.concat([frame, future]), when) == past


def test_timestamp_storage_precision_does_not_turn_complete_history_into_gap():
    frame,when=history()
    expected=api().fit_week(frame,when)
    frame.index=frame.index.as_unit('ms')
    assert api().fit_week(frame,when)==expected


def test_gap_or_short_formation_rejects_week():
    frame, when = history()
    for bad in [frame.drop(frame.index[-3]), frame.tail(539)]:
        assert api().fit_week(bad, when)["reason"] == "FORMATION_GAP"


def test_unrelated_random_walks_or_constant_series_do_not_trade():
    frame, when = history(21)
    frame["ETHUSDT"] = 3000 + np.cumsum(np.random.default_rng(9).normal(0, 20, len(frame)))
    assert not api().fit_week(frame, when)["eligible"]
    frame["ETHUSDT"] = 1000.
    assert not api().fit_week(frame, when)["eligible"]


@pytest.mark.parametrize("before,now,want", [(1.9,2.,-1),(-1.9,-2.,1),
    (2.1,2.2,0),(1.9,4.,0),(-1.9,-4.,0),(1.,1.5,0)])
def test_crossing_is_not_repeated_entry_or_four_sigma_fade(before, now, want):
    assert api().crossing(before, now) == want


def test_atr_is_simple_mean_not_exponential():
    frame = pd.DataFrame({"high": [102.] * 14 + [116.], "low": [98.] * 15,
                          "close": [100.] * 15})
    assert api().simple_atr(frame) == pytest.approx(5.)


def test_rejects_non_monday_formation_and_invalid_prices():
    frame, when = history()
    with pytest.raises(ValueError, match="Monday"):
        api().fit_week(frame, when + pd.Timedelta(days=1))
    frame.iloc[-1, 0] = np.inf
    assert not api().fit_week(frame, when)["eligible"]
