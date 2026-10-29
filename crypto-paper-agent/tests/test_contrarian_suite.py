"""Round-8 contrarian rules (src/strategies/contrarian_suite.py)."""
import pandas as pd

from src.execution.order_models import OrderDirection
from src.strategies.contrarian_suite import ExtremeFade
from tests.test_indicator_suite import CONFIG, Broker

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT


def _frame(spike, last_open, last_close):
    """59 quiet 4h bars, then one bar that closes `spike` away from 100, then the trigger bar."""
    index = pd.date_range("2023-01-01", periods=61, freq="4h", tz="UTC")
    frame = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=index)
    frame.iloc[::2, frame.columns.get_loc("close")] = 100.4
    peak = 100.0 + spike
    frame.iloc[-2] = [100.0, max(100.0, peak) + 0.5, min(100.0, peak) - 0.5, peak]
    frame.iloc[-1] = [last_open, max(last_open, last_close) + 0.2, min(last_open, last_close) - 0.2, last_close]
    return frame


def run(strategy, frame):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("4h")}, frame, Broker())


def test_blowoff_then_red_bar_goes_short_with_stop_above_the_high():
    frame = _frame(12.0, 112.0, 110.0)
    order = run(ExtremeFade(CONFIG), frame)
    assert order.direction == SHORT
    assert order.stop_loss_price > frame["high"].iloc[-3:].max()


def test_blowoff_without_a_red_bar_waits():
    assert run(ExtremeFade(CONFIG), _frame(12.0, 112.0, 113.0)) is None


def test_small_move_is_not_a_blowoff():
    assert run(ExtremeFade(CONFIG), _frame(1.5, 101.5, 101.0)) is None


def test_flush_then_green_bar_goes_long_unless_long_is_off():
    frame = _frame(-12.0, 88.0, 90.0)
    assert run(ExtremeFade(CONFIG), frame).direction == LONG
    assert run(ExtremeFade({**CONFIG, "rules": {"allow_long": False}}), frame) is None


def test_short_off_skips_the_blowoff():
    assert run(ExtremeFade({**CONFIG, "rules": {"allow_short": False}}), _frame(12.0, 112.0, 110.0)) is None


def test_exit_at_ema_or_after_twelve_bars():
    strategy = ExtremeFade(CONFIG)
    frame = _frame(12.0, 112.0, 110.0)
    assert not strategy.should_exit(frame, SHORT)
    strategy.held_bars = 12
    assert strategy.should_exit(frame, SHORT)
    strategy.held_bars = 0
    assert strategy.should_exit(_frame(0.0, 100.0, 99.0), SHORT)


def test_steady_climb_with_high_rsi_is_not_stretched_enough():
    index = pd.date_range("2023-01-01", periods=61, freq="4h", tz="UTC")
    close = pd.Series([100.0 + 0.1 * i for i in range(61)], index=index)
    frame = pd.DataFrame({"open": close - 0.05, "high": close + 1.0, "low": close - 1.0, "close": close})
    frame.iloc[-1, frame.columns.get_loc("open")] = frame["close"].iloc[-1] + 0.3
    assert run(ExtremeFade(CONFIG), frame) is None
