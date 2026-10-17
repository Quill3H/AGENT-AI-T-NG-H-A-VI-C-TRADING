"""Round-5 trading-style strategies (src/strategies/style_suite.py)."""
import numpy as np
import pandas as pd
import pytest

from scripts.run_vision_backtest import load_config
from src.backtest.engine import BacktestEngine
from src.data_layer.vision_dataset import attach_funding, snap_funding_to_settlement
from src.execution.order_models import OrderDirection
from src.execution.paper_broker import PaperBroker
from src.strategies import style_suite as st
from src.strategies.registry import directional_strategy
from tests.test_indicator_suite import CONFIG, Broker, bars

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT


def bar(o, h, l, c):
    return pd.Series({"open": o, "high": h, "low": l, "close": c})


def candle(frame, freq):
    return {"close_time": frame.index[-1] + pd.Timedelta(freq), "timestamp": frame.index[-1]}


def with_volume(frame, volume=1.0):
    frame = frame.copy()
    frame["volume"] = volume
    return frame


# ------------------------------------------------------------ candle patterns
def test_engulfing_patterns():
    assert st.bullish_engulfing(bar(10, 10.2, 9, 9.2), bar(9.1, 10.5, 9.0, 10.3))
    assert not st.bullish_engulfing(bar(10, 10.2, 9, 9.2), bar(9.1, 9.8, 9.0, 9.7))  # body too small
    assert st.bearish_engulfing(bar(9.2, 10.2, 9, 10), bar(10.1, 10.2, 8.9, 9.0))
    assert not st.bearish_engulfing(bar(9.2, 10.2, 9, 10), bar(10.1, 10.2, 8.9, 9.5))


def test_hammer_and_shooting_star():
    assert st.hammer(bar(10.0, 10.05, 9.0, 10.04))
    assert not st.hammer(bar(10.0, 10.6, 9.0, 10.04))  # long upper shadow
    assert st.shooting_star(bar(10.0, 11.0, 9.96, 9.98))
    assert not st.shooting_star(bar(10.0, 11.0, 9.4, 9.98))


# ------------------------------------------------------------------- vwap
def test_session_vwap_restarts_each_day_and_ignores_later_bars():
    frame = with_volume(bars(np.linspace(100, 120, 192), freq="15min"))
    vwap = st.session_vwap(frame)
    day2 = frame.index[96]
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    assert vwap.loc[day2] == pytest.approx(typical.loc[day2])
    assert st.session_vwap(frame.iloc[:120]).equals(vwap.iloc[:120])


# ------------------------------------------------------------------- swing
def test_swing_pullback_buys_a_dip_to_ema20_in_an_uptrend():
    closes = list(np.linspace(100, 200, 299))
    frame = bars(closes + [closes[-1] * 1.004], freq="4h")
    e20 = st.ema(frame["close"], 20)
    frame.iloc[-2, frame.columns.get_loc("low")] = e20.iloc[-2] * 0.99
    order = st.SwingEmaPullback(CONFIG).on_candle_close(candle(frame, "4h"), frame, Broker())
    assert order.direction == LONG and order.stop_loss_price < frame["low"].iloc[-5:].min()


def test_swing_pullback_exits_below_ema50():
    frame = bars(list(np.linspace(100, 200, 250)) + list(np.linspace(199, 150, 12)), freq="4h")
    broker = Broker(LONG)
    st.SwingEmaPullback(CONFIG).on_candle_close(candle(frame, "4h"), frame, broker)
    assert broker.closed


def test_support_candle_long_has_take_profit_at_resistance():
    closes = list(np.linspace(130, 100, 69)) + [99.0]
    frame = bars(closes, freq="1D")
    frame.iloc[-2] = [101.0, 101.2, 99.5, 99.6]
    frame.iloc[-1] = [99.4, 101.8, 99.0, 101.7]  # bullish engulfing at the 30-day low
    order = st.SupportResistanceCandles(CONFIG).on_candle_close(candle(frame, "1D"), frame, Broker())
    resistance = frame["high"].iloc[-31:-1].max()
    assert order.direction == LONG and order.take_profit_price == pytest.approx(resistance)
    assert order.stop_loss_price < 99.0


def test_wyckoff_spring_needs_a_volume_spike():
    rng = np.random.default_rng(1)
    closes = 100 + rng.normal(0, 0.3, 79)
    frame = with_volume(bars(np.append(closes, 100.0), freq="4h"))
    low = frame["low"].iloc[-41:-1].min()
    frame.iloc[-1, frame.columns.get_loc("low")] = low - 0.5
    quiet = st.WyckoffSpring(CONFIG).on_candle_close(candle(frame, "4h"), frame, Broker())
    frame.iloc[-1, frame.columns.get_loc("volume")] = 3.0
    spring = st.WyckoffSpring(CONFIG).on_candle_close(candle(frame, "4h"), frame, Broker())
    assert quiet is None
    assert spring.direction == LONG and spring.take_profit_price == pytest.approx(frame["high"].iloc[-41:-1].max())


# -------------------------------------------------------------- day trading
def _orb_frame(break_hour):
    """Ten flat days, then a day whose first four hours set a range and price breaks up later."""
    closes = np.full(24 * 13, 100.0) + np.linspace(0, 1, 24 * 13)
    frame = bars(closes, freq="1h")
    day = frame.index[-24]
    for i in range(24):
        t = day + pd.Timedelta(hours=i)
        frame.loc[t, ["open", "high", "low", "close"]] = [101.0, 101.3, 100.8, 101.0]
    t = day + pd.Timedelta(hours=break_hour)
    frame.loc[t, ["open", "high", "low", "close"]] = [101.0, 101.9, 101.0, 101.8]
    return frame.loc[:t]


def test_opening_range_breakout_waits_for_the_range_and_trades_once_a_day():
    early = _orb_frame(2)
    assert st.DayOpeningRange(CONFIG).on_candle_close(candle(early, "1h"), early, Broker()) is None
    frame = _orb_frame(6)
    strategy = st.DayOpeningRange(CONFIG)
    order = strategy.on_candle_close(candle(frame, "1h"), frame, Broker())
    assert order.direction == LONG and order.stop_loss_price == pytest.approx(100.8)
    assert order.take_profit_price == pytest.approx(101.8 + 2 * (101.8 - 100.8))
    assert strategy.on_candle_close(candle(frame, "1h"), frame, Broker()) is None


def test_day_strategies_close_on_the_bar_that_ends_the_day():
    frame = bars(np.linspace(100, 110, 24 * 13), freq="1h")
    last_bar = frame.loc[: frame.index[-1].normalize() + pd.Timedelta(hours=23)]
    broker = Broker(LONG)
    st.DayOpeningRange(CONFIG).on_candle_close(candle(last_bar, "1h"), last_bar, broker)
    assert broker.closed
    broker = Broker(LONG)
    st.DayOpeningRange(CONFIG).on_candle_close(candle(last_bar.iloc[:-1], "1h"), last_bar.iloc[:-1], broker)
    assert not broker.closed


def test_day_trades_never_stay_open_past_midnight_in_the_engine():
    rng = np.random.default_rng(7)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, 96 * 40)))
    exec_15m = bars(closes, freq="15min")
    exec_15m["volume"] = 1.0
    funding = pd.DataFrame({"funding_rate": 0.0001}, index=pd.date_range(exec_15m.index[0], exec_15m.index[-1], freq="8h"))
    exec_15m = attach_funding(exec_15m, snap_funding_to_settlement(funding))
    signal_1h = exec_15m[["open", "high", "low", "close", "volume"]].resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    full = load_config("day_orb", [])
    full["account"]["initial_equity_usd"] = 10000.0
    engine = BacktestEngine(config=full, data_4h=signal_1h, data_15m=exec_15m,
                            strategy=directional_strategy("day_orb", full), broker=PaperBroker(config=full))
    engine.run(force_close=True)
    trades = engine.broker.trade_history
    assert trades, "the synthetic walk should produce at least one breakout"
    for trade in trades:
        exit_limit = pd.Timestamp(trade.entry_time).normalize() + pd.Timedelta(days=1)
        assert pd.Timestamp(trade.exit_time) <= exit_limit


# ----------------------------------------------------------------- scalping
def test_scalp_ema_cross_sets_stop_and_target_and_times_out():
    closes = list(np.linspace(100, 110, 260)) + list(np.linspace(110, 109, 12)) + [109.2, 109.4, 109.55, 109.7, 109.8]
    frame = bars(closes, freq="5min")
    strategy = st.ScalpEmaCross(CONFIG)
    order = None
    for end in range(262, len(frame) + 1):
        order = order or strategy.on_candle_close(candle(frame.iloc[:end], "5min"), frame.iloc[:end], Broker())
    assert order is not None and order.direction == LONG
    assert order.stop_loss_price < order.signal_price < order.take_profit_price
    broker = Broker(LONG)
    for _ in range(24):
        strategy.on_candle_close(candle(frame, "5min"), frame, broker)
    assert len(broker.closed) == 1


def test_scalp_bollinger_fades_a_stretch_in_a_quiet_market():
    rng = np.random.default_rng(3)
    closes = list(100 + rng.normal(0, 0.05, 119)) + [99.0]
    frame = bars(closes, freq="5min")
    order = st.ScalpBollingerRevert(CONFIG).on_candle_close(candle(frame, "5min"), frame, Broker())
    assert order.direction == LONG
    assert order.take_profit_price == pytest.approx(frame["close"].iloc[-20:].mean())


def test_invalid_take_profit_is_refused():
    class Bad(st.RuleStrategy):
        window = 5

        def entry(self, frame):
            last = float(frame["close"].iloc[-1])
            return LONG, last - 1.0, last - 0.5

    frame = bars(np.linspace(100, 101, 10), freq="5min")
    assert Bad(CONFIG).on_candle_close(candle(frame, "5min"), frame, Broker()) is None


@pytest.mark.parametrize("name", ["swing_ema_pullback", "sr_candles", "wyckoff_spring", "day_orb", "day_vwap", "scalp_ema", "scalp_bb"])
def test_registered(name):
    assert directional_strategy(name, CONFIG).name


def test_rsi_pullback_takes_a_quick_profit_with_a_wider_stop():
    closes = list(np.linspace(100, 130, 258)) + [128.0, 126.0]
    frame = bars(closes, freq="15min")
    order = st.ScalpRsiPullback(CONFIG).on_candle_close(candle(frame, "15min"), frame, Broker())
    assert order.direction == LONG
    assert order.take_profit_price - order.signal_price < order.signal_price - order.stop_loss_price
    broker = Broker(LONG)
    strategy = st.ScalpRsiPullback(CONFIG)
    for _ in range(8):
        strategy.on_candle_close(candle(frame, "15min"), frame, broker)
    assert len(broker.closed) == 1


def test_rsi_pullback_does_not_buy_below_the_trend():
    closes = list(np.linspace(130, 100, 258)) + [98.0, 96.0]
    frame = bars(closes, freq="15min")
    order = st.ScalpRsiPullback(CONFIG).on_candle_close(candle(frame, "15min"), frame, Broker())
    assert order is None


@pytest.mark.parametrize("name,tf", [("scalp_bb_15m", "15m"), ("scalp_bb_1h", "1h"), ("scalp_rsi_15m", "15m"), ("scalp_rsi_1h", "1h")])
def test_short_timeframe_scalps_use_their_own_signal_bars(name, tf):
    assert load_config(name, [])["strategy"]["timeframe_signal"] == tf
