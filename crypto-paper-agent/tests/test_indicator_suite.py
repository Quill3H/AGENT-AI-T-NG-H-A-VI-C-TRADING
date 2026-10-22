from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import indicator_suite as s
from src.strategies.registry import directional_strategy

CONFIG = {"rules": {}, "default_conviction": "normal", "leverage": 2.0, "base_risk_percent": 0.02}


def bars(closes, freq="4h", start="2021-01-01"):
    closes = np.asarray(closes, dtype=float)
    index = pd.date_range(start, periods=len(closes), freq=freq, tz="UTC")
    opens = np.concatenate([[closes[0]], closes[:-1]])
    high, low = np.maximum(opens, closes) * 1.0005, np.minimum(opens, closes) * 0.9995
    return pd.DataFrame({"open": opens, "high": high, "low": low, "close": closes}, index=index)


def candle(frame):
    return {"close_time": frame.index[-1] + pd.Timedelta("4h"), "timestamp": frame.index[-1]}


class Broker:
    def __init__(self, direction=None):
        self.positions = {"BTCUSDT": SimpleNamespace(direction=direction, stop_loss_price=1.0)} if direction else {}
        self.pending_orders = []
        self.closed, self.stops = [], []

    def request_close(self, symbol, when):
        self.closed.append((symbol, when))

    def update_stop_loss(self, symbol, price):
        self.stops.append(price)
        return True


def test_rsi_is_100_on_a_rising_series_and_0_on_a_falling_one():
    assert s.rsi(pd.Series(np.arange(1.0, 30.0)), 2).iloc[-1] == pytest.approx(100.0)
    assert s.rsi(pd.Series(np.arange(30.0, 1.0, -1.0)), 2).iloc[-1] == pytest.approx(0.0)


def test_completed_daily_drops_the_day_that_has_not_closed():
    frame = bars(np.linspace(100, 110, 6 * 3 + 2))  # 3 full days + 2 bars of the 4th
    assert len(s.completed_daily(frame)) == 3
    assert len(s.completed_daily(frame.iloc[:18])) == 3


def test_tsmom_goes_long_in_an_uptrend_with_stop_below_price():
    frame = bars(np.linspace(100, 200, 100), freq="1D")
    order = s.TimeSeriesMomentum(CONFIG).on_candle_close(candle(frame), frame, Broker())
    assert order.direction == OrderDirection.LONG and order.stop_loss_price < 200


def test_tsmom_goes_short_in_a_downtrend_and_exits_when_momentum_flips():
    down = bars(np.linspace(200, 100, 100), freq="1D")
    order = s.TimeSeriesMomentum(CONFIG).on_candle_close(candle(down), down, Broker())
    assert order.direction == OrderDirection.SHORT and order.stop_loss_price > 100
    up = bars(np.linspace(100, 200, 100), freq="1D")
    broker = Broker(OrderDirection.SHORT)
    assert s.TimeSeriesMomentum(CONFIG).on_candle_close(candle(up), up, broker) is None
    assert broker.closed


def test_rsi2_buys_a_sharp_dip_above_the_200_bar_average():
    closes = list(np.linspace(100, 200, 258)) + [190.0, 180.0]
    frame = bars(closes)
    order = s.RSI2Reversion(CONFIG).on_candle_close(candle(frame), frame, Broker())
    assert order.direction == OrderDirection.LONG


def test_rsi2_does_not_buy_a_dip_below_the_200_bar_average():
    closes = list(np.linspace(200, 100, 258)) + [95.0, 90.0]
    frame = bars(closes)
    order = s.RSI2Reversion(CONFIG).on_candle_close(candle(frame), frame, Broker())
    assert order is None or order.direction == OrderDirection.SHORT


def test_squeeze_breakout_needs_a_quiet_market_first():
    rng = np.random.default_rng(1)
    noisy = 100 + np.cumsum(rng.normal(0, 3, 159))
    frame = bars(list(noisy) + [noisy[-1] + 40.0])
    close, band = frame["close"], s.atr(frame, 20).iloc[-1]
    assert close.iloc[-1] > s.ema(close, 20).iloc[-1] + 1.5 * band  # a real breakout, but no squeeze before it
    assert s.SqueezeBreakout(CONFIG).on_candle_close(candle(frame), frame, Broker()) is None
    quiet = list(100 + np.cumsum(rng.normal(0, 3, 120))) + [100.0 + 0.01 * i for i in range(39)]
    frame = bars(quiet + [110.0])
    order = s.SqueezeBreakout(CONFIG).on_candle_close(candle(frame), frame, Broker())
    assert order is not None and order.direction == OrderDirection.LONG


def test_mtf_trend_only_trades_with_the_daily_regime():
    rising = bars(np.linspace(100, 1000, 1400))
    order = s.MultiTimeframeTrend(CONFIG).on_candle_close(candle(rising), rising, Broker())
    assert order is not None and order.direction == OrderDirection.LONG
    falling = bars(np.linspace(1000, 100, 1400))
    order = s.MultiTimeframeTrend(CONFIG).on_candle_close(candle(falling), falling, Broker())
    assert order is not None and order.direction == OrderDirection.SHORT


def test_mtf_trend_does_not_trade_against_the_daily_regime():
    rising_then_crash = bars(list(np.linspace(100, 1000, 1399)) + [800.0])
    assert s.MultiTimeframeTrend(CONFIG).on_candle_close(candle(rising_then_crash), rising_then_crash, Broker()) is None
    falling_then_spike = bars(list(np.linspace(1000, 100, 1399)) + [130.0])
    assert s.MultiTimeframeTrend(CONFIG).on_candle_close(candle(falling_then_spike), falling_then_spike, Broker()) is None


def test_adx_filter_blocks_breakouts_in_a_trendless_market():
    flat = bars(list(100.0 + 5.0 * np.sin(np.arange(79) * 0.9)) + [106.0], freq="1D")
    assert s.ADXDonchian(CONFIG).on_candle_close(candle(flat), flat, Broker()) is None
    trend = bars(np.linspace(100, 200, 80), freq="1D")
    assert s.ADXDonchian(CONFIG).on_candle_close(candle(trend), trend, Broker()).direction == OrderDirection.LONG


def test_supertrend_enters_only_on_the_flip_bar():
    closes = list(np.linspace(200, 100, 150)) + list(np.linspace(100, 160, 50))
    frame = bars(closes)
    _, direction = s.supertrend(frame)
    flip = int(np.argmax(direction[150:] > 0)) + 150
    at_flip = frame.iloc[: flip + 1]
    padded = pd.concat([bars(np.full(200, 200.0), start="2020-01-01"), at_flip]).iloc[-200:]
    order = s.SupertrendStrategy(CONFIG).on_candle_close(candle(padded), padded, Broker())
    assert order is not None and order.direction == OrderDirection.LONG
    after = pd.concat([bars(np.full(200, 200.0), start="2020-01-01"), frame.iloc[: flip + 5]]).iloc[-200:]
    assert s.SupertrendStrategy(CONFIG).on_candle_close(candle(after), after, Broker()) is None


def test_held_position_gets_trailing_stop_not_a_new_entry():
    frame = bars(np.linspace(100, 300, 1400))
    broker = Broker(OrderDirection.LONG)
    assert s.MultiTimeframeTrend(CONFIG).on_candle_close(candle(frame), frame, broker) is None
    assert broker.stops and broker.stops[-1] < 300


@pytest.mark.parametrize("name", ["tsmom", "rsi2_reversion", "squeeze_breakout", "mtf_trend", "adx_donchian", "supertrend"])
def test_registry_builds_each_round3_strategy(name):
    assert directional_strategy(name, CONFIG, "ETHUSDT").symbol == "ETHUSDT"
