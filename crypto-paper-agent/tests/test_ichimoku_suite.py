"""Round-9 Ichimoku rules (src/strategies/ichimoku_suite.py)."""
import numpy as np
import pandas as pd

from src.execution.order_models import OrderDirection
from src.strategies.ichimoku_suite import IchimokuKumoBreakout, IchimokuTkCross, ichimoku
from tests.test_indicator_suite import CONFIG, Broker

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT


def _flat(n=140):
    index = pd.date_range("2023-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=index)


def _mirror(frame):
    out = 200.0 - frame
    out["high"], out["low"] = 200.0 - frame["low"], 200.0 - frame["high"]
    return out


def _tk_cross_up():
    frame = _flat()
    frame.iloc[-20] = [100.0, 106.0, 95.0, 100.0]  # keeps Kijun above Tenkan on the previous bar
    frame.iloc[-1] = [100.0, 110.0, 99.5, 109.0]
    return frame


def run(strategy, frame):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("4h")}, frame, Broker())


def test_cloud_uses_only_past_bars():
    rng = np.random.default_rng(3)
    frame = _flat(200)
    frame["close"] = 100 + rng.normal(0, 1, 200).cumsum()
    frame["high"], frame["low"] = frame["close"] + 1, frame["close"] - 1
    cut = ichimoku(frame.iloc[:150])
    full = ichimoku(frame)
    for key in cut:
        assert np.allclose(cut[key].dropna(), full[key].iloc[:150].dropna())


def test_tk_cross_above_cloud_goes_long_with_stop_under_kijun():
    order = run(IchimokuTkCross(CONFIG), _tk_cross_up())
    assert order.direction == LONG
    assert order.stop_loss_price < 102.5


def test_tk_cross_mirror_goes_short_unless_shorts_are_off():
    frame = _mirror(_tk_cross_up())
    assert run(IchimokuTkCross(CONFIG), frame).direction == SHORT
    assert run(IchimokuTkCross({**CONFIG, "rules": {"allow_short": False}}), frame) is None


def test_tk_cross_needs_chikou_confirmation():
    frame = _tk_cross_up()
    frame.iloc[-27, frame.columns.get_loc("close")] = 120.0  # close 26 bars ago above today's
    assert run(IchimokuTkCross(CONFIG), frame) is None


def test_no_cross_no_trade():
    assert run(IchimokuTkCross(CONFIG), _flat()) is None


def _kumo_break_up():
    """Price rises slowly for a while (bullish projected cloud, Tenkan > Kijun) then a close
    clears the cloud drawn from 26 bars ago."""
    frame = _flat()
    ramp = np.linspace(100.0, 104.0, 30)
    for i, c in enumerate(ramp):
        frame.iloc[-31 + i] = [c, c + 1.0, c - 1.0, c]
    frame.iloc[-2] = [100.3, 100.6, 99.8, 100.1]  # just under the cloud top
    frame.iloc[-1] = [101.0, 106.0, 100.8, 105.5]
    return frame


def test_kumo_breakout_long_and_mirror_short():
    frame = _kumo_break_up()
    ich = ichimoku(frame)
    assert frame["close"].iloc[-2] <= max(ich["cloud_a"].iloc[-2], ich["cloud_b"].iloc[-2])
    order = run(IchimokuKumoBreakout(CONFIG), frame)
    assert order.direction == LONG
    assert order.stop_loss_price < min(ich["cloud_a"].iloc[-1], ich["cloud_b"].iloc[-1])
    assert run(IchimokuKumoBreakout(CONFIG), _mirror(frame)).direction == SHORT


def test_exit_when_close_crosses_kijun():
    strategy = IchimokuTkCross(CONFIG)
    frame = _tk_cross_up()
    assert not strategy.should_exit(frame, LONG)
    frame.iloc[-1, frame.columns.get_loc("close")] = 100.0
    assert strategy.should_exit(frame, LONG)


def test_cloud_is_displaced_26_bars():
    rng = np.random.default_rng(5)
    frame = _flat(200)
    frame["close"] = 100 + rng.normal(0, 1, 200).cumsum()
    frame["high"], frame["low"] = frame["close"] + 1, frame["close"] - 1
    ich = ichimoku(frame)
    assert ich["cloud_a"].iloc[-1] == (ich["tenkan"].iloc[-27] + ich["kijun"].iloc[-27]) / 2.0
    assert ich["cloud_b"].iloc[-1] == ich["future_b"].iloc[-27]


def test_tk_cross_under_the_cloud_is_skipped():
    frame = _tk_cross_up()
    frame.iloc[-80:-28] = [120.0, 121.0, 119.0, 120.0]  # the cloud over today comes from these bars
    assert run(IchimokuTkCross(CONFIG), frame) is None


def test_kumo_breakout_needs_a_bullish_projection():
    frame = _kumo_break_up()
    frame.iloc[-20, frame.columns.get_loc("high")] = 150.0  # projected span B and Kijun jump above
    assert run(IchimokuKumoBreakout(CONFIG), frame) is None
