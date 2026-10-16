"""Donchian trend rulebook: entries use only closed bars; exits only tighten."""
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies.donchian_trend import DonchianTrendStrategy

CONFIG = {"rules": {"entry_bars": 5, "exit_bars": 3, "atr_bars": 5, "stop_atr_multiple": 2.0}}


def _history(closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="1D", tz="UTC")
    closes = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": closes, "high": closes + 1, "low": closes - 1, "close": closes, "volume": 1.0})


def _candle(history):
    row = history.iloc[-1].to_dict()
    row["close_time"] = history.index[-1] + pd.Timedelta(days=1)
    return row


class _Broker:
    def __init__(self, position=None):
        self.positions = {"BTCUSDT": position} if position else {}
        self.pending_orders = []
        self.stop_updates = []

    def update_stop_loss(self, symbol, price):
        self.stop_updates.append(price)
        return True


def test_breakout_above_previous_highs_goes_long_with_atr_stop():
    history = _history([100, 101, 100, 102, 101, 103, 110])
    order = DonchianTrendStrategy(CONFIG).on_candle_close(_candle(history), history, _Broker())
    assert order.direction == OrderDirection.LONG
    assert order.stop_loss_price < 110


def test_no_signal_inside_channel():
    history = _history([100, 104, 100, 102, 101, 103, 102])
    assert DonchianTrendStrategy(CONFIG).on_candle_close(_candle(history), history, _Broker()) is None


def test_short_disabled_blocks_breakdown():
    history = _history([100, 101, 100, 102, 101, 103, 90])
    config = {"rules": {**CONFIG["rules"], "allow_short": False}}
    assert DonchianTrendStrategy(config).on_candle_close(_candle(history), history, _Broker()) is None
    assert DonchianTrendStrategy(CONFIG).on_candle_close(_candle(history), history, _Broker()).direction == OrderDirection.SHORT


def test_signal_is_unchanged_by_future_bars():
    history = _history([100, 101, 100, 102, 101, 103, 110, 50, 200])
    upto = history.iloc[:7]
    first = DonchianTrendStrategy(CONFIG).on_candle_close(_candle(upto), upto, _Broker())
    again = DonchianTrendStrategy(CONFIG).on_candle_close(_candle(upto), history.iloc[:7].copy(), _Broker())
    assert (first.direction, first.stop_loss_price) == (again.direction, again.stop_loss_price)


@pytest.mark.parametrize("stop, expected_updates", [(90.0, [104.0]), (106.0, [])])
def test_long_exit_channel_only_tightens(stop, expected_updates):
    class Position:
        direction = OrderDirection.LONG
        stop_loss_price = stop

    history = _history([100, 101, 100, 102, 101, 105, 106, 107])
    broker = _Broker(Position())
    DonchianTrendStrategy(CONFIG).on_candle_close(_candle(history), history, broker)
    assert broker.stop_updates == expected_updates
