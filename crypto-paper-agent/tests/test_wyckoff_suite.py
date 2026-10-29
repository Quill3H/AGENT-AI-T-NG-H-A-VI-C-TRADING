"""Round-10 Wyckoff rules and Ichimoku variants (src/strategies/wyckoff_suite.py, ichimoku_suite.py)."""
import numpy as np
import pandas as pd

from src.execution.order_models import OrderDirection
from src.strategies.ichimoku_suite import IchimokuTkDaily, IchimokuTkTrail, daily_cloud_side
from src.strategies.wyckoff_suite import WyckoffSosLps, WyckoffSpringRun
from tests.test_indicator_suite import CONFIG, Broker

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT


def _range(n=140):
    index = pd.date_range("2023-01-01", periods=n, freq="4h", tz="UTC")
    close = np.where(np.arange(n) % 2, 100.4, 99.6)
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": close, "volume": 100.0}, index=index)


def run(strategy, frame):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("4h")}, frame, Broker())


def _sos_lps(volume=500.0):
    frame = _range()
    frame.iloc[-4] = [100.0, 103.5, 99.8, 103.0, volume]  # sign of strength
    frame.iloc[-3] = [103.0, 104.5, 102.5, 104.0, 100.0]
    frame.iloc[-2] = [104.0, 104.2, 102.4, 103.5, 100.0]
    frame.iloc[-1] = [103.5, 103.6, 101.3, 102.6, 100.0]  # back near the range high, closes above it
    return frame


def _mirror(frame):
    out = frame.copy()
    for c in ("open", "close"):
        out[c] = 200.0 - frame[c]
    out["high"], out["low"] = 200.0 - frame["low"], 200.0 - frame["high"]
    return out


def test_sos_then_lps_goes_long_and_mirror_short():
    order = run(WyckoffSosLps(CONFIG), _sos_lps())
    assert order.direction == LONG and order.stop_loss_price < 101.3
    assert run(WyckoffSosLps(CONFIG), _mirror(_sos_lps())).direction == SHORT


def test_sos_needs_volume():
    assert run(WyckoffSosLps(CONFIG), _sos_lps(volume=120.0)) is None


def test_lps_is_void_once_a_close_falls_back_into_the_range():
    frame = _sos_lps()
    frame.iloc[-2, frame.columns.get_loc("close")] = 100.5
    assert run(WyckoffSosLps(CONFIG), frame) is None


def test_no_pullback_no_lps():
    frame = _sos_lps()
    frame.iloc[-1] = [104.0, 105.5, 103.8, 105.0, 100.0]
    assert run(WyckoffSosLps(CONFIG), frame) is None


def test_spring_run_has_no_fixed_target_and_exits_on_ema50():
    frame = _range()
    frame.iloc[-1] = [99.5, 100.2, 97.5, 99.9, 500.0]
    strategy = WyckoffSpringRun(CONFIG)
    order = run(strategy, frame)
    assert order.direction == LONG and order.take_profit_price is None
    frame.iloc[-1, frame.columns.get_loc("close")] = 95.0
    assert strategy.should_exit(frame, LONG)


def _trend(n=560, step=0.2):
    index = pd.date_range("2023-01-01", periods=n, freq="4h", tz="UTC")
    close = pd.Series(100.0 + step * np.arange(n), index=index)
    return pd.DataFrame({"open": close - 0.05, "high": close + 1.0, "low": close - 1.0, "close": close})


def test_daily_cloud_side_reads_finished_days_only():
    up = _trend()
    assert daily_cloud_side(up) == 1
    assert daily_cloud_side(_trend(step=-0.1)) == -1
    # a wild last bar of an unfinished day does not change the daily answer
    partial = up.iloc[:-1].copy()  # ends at 16:00 or earlier, day not finished
    if partial.index[-1].hour != 20:
        moved = partial.copy()
        moved.iloc[-1, moved.columns.get_loc("close")] = 1.0
        assert daily_cloud_side(moved) == daily_cloud_side(partial)


def test_daily_filter_blocks_a_long_under_the_daily_cloud(monkeypatch):
    from src.strategies import ichimoku_suite
    strategy = IchimokuTkDaily(CONFIG)
    frame = _trend()
    monkeypatch.setattr(ichimoku_suite.IchimokuTkCross, "entry", lambda self, f: (LONG, 1.0))
    monkeypatch.setattr(ichimoku_suite, "daily_cloud_side", lambda f: -1)
    assert strategy.entry(frame) is None
    monkeypatch.setattr(ichimoku_suite, "daily_cloud_side", lambda f: 1)
    assert strategy.entry(frame) == (LONG, 1.0)


def test_trail_follows_the_kijun():
    frame = _trend(200)
    stop = IchimokuTkTrail(CONFIG).trail(frame, LONG)
    kijun = (frame["high"].iloc[-26:].max() + frame["low"].iloc[-26:].min()) / 2
    assert stop < kijun and stop > kijun - 2.0
