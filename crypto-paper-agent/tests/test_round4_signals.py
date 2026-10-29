"""Round-4 signal generators must be causal: truncating the future cannot change the past."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.research import signals as sig
from src.strategies.indicator_suite import RegimeSwitch, SignalSeries


def coin(seed, days=700):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.03, days)))
    index = pd.date_range("2020-09-01", periods=days, freq="1D", tz="UTC")
    volume = rng.uniform(1000, 2000, days)
    return pd.DataFrame({"open": close, "high": close * 1.02, "low": close * 0.98, "close": close,
                         "volume": volume, "taker_buy_base_volume": volume * rng.uniform(0.4, 0.6, days)}, index=index)


def metrics_for(bars, seed):
    rng = np.random.default_rng(seed)
    n = len(bars)
    return pd.DataFrame({"oi_value_last": 1e9 * np.exp(np.cumsum(rng.normal(0, 0.02, n))),
                         "top_ls_mean": rng.uniform(0.8, 1.5, n), "global_ls_mean": rng.uniform(0.8, 1.5, n),
                         "taker_ratio_mean": rng.uniform(0.8, 1.2, n)}, index=bars.index)


@pytest.fixture(scope="module")
def universe():
    bars = {s: coin(i) for i, s in enumerate(["AAA", "BBB", "CCC"])}
    return bars


def test_daily_features_do_not_change_when_future_bars_are_removed(universe):
    bars = universe["AAA"]
    full = sig.daily_features(bars, metrics_for(bars, 1))
    cut = sig.daily_features(bars.iloc[:400], metrics_for(bars, 1).iloc[:400])
    pd.testing.assert_frame_equal(full.iloc[:400], cut)


@pytest.mark.parametrize("cut", [455, 515, 520])  # 455 and 515 are retrain days
def test_walk_forward_probabilities_are_causal(universe, cut):
    panel = {s: sig.daily_features(b) for s, b in universe.items()}
    closes = {s: b["close"] for s, b in universe.items()}
    full = sig.walk_forward_probabilities(panel, closes, sig.PRICE_FEATURES)
    cut_day = full.index[cut]
    panel_cut = {s: f.loc[:cut_day] for s, f in panel.items()}
    closes_cut = {s: c.loc[:cut_day] for s, c in closes.items()}
    cut = sig.walk_forward_probabilities(panel_cut, closes_cut, sig.PRICE_FEATURES)
    assert full.loc[:cut_day].notna().sum().sum() > 100
    pd.testing.assert_frame_equal(full.loc[:cut_day], cut)


def test_no_prediction_before_a_year_of_history(universe):
    panel = {s: sig.daily_features(b) for s, b in universe.items()}
    probs = sig.walk_forward_probabilities(panel, {s: b["close"] for s, b in universe.items()}, sig.PRICE_FEATURES)
    assert probs.loc[: probs.index[0] + pd.Timedelta(days=364)].isna().all().all()


def test_logistic_learns_an_obvious_rule():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(500, 1))
    y = (x[:, 0] > 0).astype(float)
    w = sig.fit_logistic(x, y, l2=0.1)
    assert w[1] > 2.0


def test_probability_positions_use_entry_band_and_midline_exit():
    probs = pd.DataFrame({"AAA": [0.5, 0.56, 0.52, 0.49, 0.44, 0.47, 0.51]})
    assert list(sig.probability_positions(probs)["AAA"]) == [0, 1, 1, 0, -1, -1, 0]


def test_cross_sectional_positions_are_causal_and_rebalance_weekly(universe):
    closes = pd.DataFrame({s: b["close"] for s, b in universe.items()})
    full = sig.cross_sectional_positions(closes)
    cut = sig.cross_sectional_positions(closes.iloc[:300])
    pd.testing.assert_frame_equal(full.iloc[:300], cut)
    changes = full.diff().abs().sum(axis=1)
    changed_days = full.index[changes > 0]
    assert all((b - a).days >= 7 for a, b in zip(changed_days[:-1], changed_days[1:]))
    assert (full.iloc[40:].abs().sum(axis=1) == 2).all()  # one long and one short of three coins


def _candle(frame):
    return {"close_time": frame.index[-1] + pd.Timedelta("1D")}


class Broker:
    def __init__(self, direction=None, symbol="AAA"):
        self.positions = {symbol: SimpleNamespace(direction=direction, stop_loss_price=1.0)} if direction else {}
        self.pending_orders, self.closed = [], []

    def request_close(self, symbol, when):
        self.closed.append(symbol)

    def update_stop_loss(self, symbol, price):
        return True


def test_signal_series_enters_and_exits_on_the_table(tmp_path, universe):
    bars = universe["AAA"].iloc[:60][["open", "high", "low", "close"]]
    table = pd.DataFrame({"AAA": 0.0}, index=bars.index)
    table.iloc[-1] = 1.0
    path = tmp_path / "s.parquet"
    table.to_parquet(path)
    config = {"rules": {"signal_path": str(path)}, "leverage": 2.0}
    order = SignalSeries(config, "AAA").on_candle_close(_candle(bars), bars, Broker())
    assert order.direction == OrderDirection.LONG and order.stop_loss_price < bars["close"].iloc[-1]
    table.iloc[-1] = -1.0
    table.to_parquet(path)
    broker = Broker(OrderDirection.LONG)
    assert SignalSeries(config, "AAA").on_candle_close(_candle(bars), bars, broker) is None
    assert broker.closed == ["AAA"]


def test_regime_switch_waits_in_the_middle_band(universe):
    bars = universe["BBB"].iloc[:200][["open", "high", "low", "close"]]
    strategy = RegimeSwitch({"rules": {}, "leverage": 2.0}, "BBB")
    from src.strategies.indicator_suite import adx
    strengths = adx(bars, 14)
    for end in range(140, 200):
        frame = bars.iloc[:end]
        order = strategy.on_candle_close(_candle(frame), frame, Broker(symbol="BBB"))
        if 20 <= strengths.iloc[end - 1] <= 25:
            assert order is None
