"""Nison candlestick patterns (src/strategies/candles.py) and the round-6 strategies."""
import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import candles as c
from src.strategies import style_suite as st
from tests.test_indicator_suite import CONFIG, Broker

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT
UNIT = 1.0


def bar(o, h, l, cl):
    return pd.Series({"open": o, "high": h, "low": l, "close": cl})


def frame_of(rows, freq="4h"):
    index = pd.date_range("2021-01-01", periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index, dtype=float)


def test_doji_and_hammer_follow_the_book():
    assert c.doji(bar(10.0, 10.5, 9.5, 10.05))
    assert not c.doji(bar(10.0, 10.5, 9.5, 10.3))
    assert c.hammer_shape(bar(10.0, 10.21, 9.0, 10.2))      # lower shadow 5x body, no upper shadow
    assert not c.hammer_shape(bar(10.0, 10.8, 9.0, 10.2))   # long upper shadow
    assert c.star_shape(bar(10.2, 11.2, 9.99, 10.0))


def test_harami_needs_a_long_body_then_a_small_one_inside():
    long_black = bar(12.0, 12.1, 10.9, 11.0)
    assert c.harami(long_black, bar(11.3, 11.6, 11.2, 11.5), UNIT, bullish=True)
    assert not c.harami(long_black, bar(11.3, 12.5, 11.2, 12.4), UNIT, bullish=True)   # not inside
    assert not c.harami(bar(11.2, 11.3, 10.9, 11.0), bar(11.05, 11.2, 11.0, 11.1), UNIT, bullish=True)  # first body too small


def test_piercing_line_and_dark_cloud():
    assert c.piercing(bar(12.0, 12.1, 10.9, 11.0), bar(11.0, 11.8, 10.8, 11.7), UNIT, bullish=True)
    assert not c.piercing(bar(12.0, 12.1, 10.9, 11.0), bar(11.0, 11.4, 10.8, 11.3), UNIT, bullish=True)  # below midpoint
    assert c.piercing(bar(11.0, 12.1, 10.9, 12.0), bar(12.0, 12.2, 11.2, 11.3), UNIT, bullish=False)


def test_morning_and_evening_star():
    first, middle = bar(12.0, 12.1, 10.9, 11.0), bar(11.0, 11.1, 10.7, 10.9)
    assert c.star(first, middle, bar(10.9, 11.8, 10.85, 11.7), UNIT, bullish=True)
    assert not c.star(first, middle, bar(10.9, 11.3, 10.85, 11.2), UNIT, bullish=True)
    assert c.star(bar(11.0, 12.1, 10.9, 12.0), bar(12.0, 12.3, 11.95, 12.1), bar(12.1, 12.15, 11.2, 11.3), UNIT, bullish=False)


def test_three_soldiers_and_three_methods():
    soldiers = frame_of([[10.0, 11.05, 9.95, 11.0], [10.5, 12.05, 10.4, 12.0], [11.5, 13.1, 11.4, 13.0]])
    assert c.three_soldiers(soldiers, UNIT, bullish=True)
    broken = soldiers.copy()
    broken.iloc[2] = [11.5, 14.5, 11.4, 13.0]  # long upper shadow
    assert not c.three_soldiers(broken, UNIT, bullish=True)
    methods = frame_of([[10.0, 12.1, 9.9, 12.0], [12.0, 12.05, 11.5, 11.6], [11.6, 11.8, 11.3, 11.4],
                        [11.4, 11.6, 11.1, 11.2], [11.2, 12.9, 11.1, 12.8]])
    assert c.three_methods(methods, UNIT, bullish=True)
    escaped = methods.copy()
    escaped.iloc[2] = [11.6, 12.5, 11.3, 11.4]  # a small bar leaves the first range
    assert not c.three_methods(escaped, UNIT, bullish=True)


def _trend_with_pullback(last_rows):
    """An up-trend of 300 4h bars, a 6-bar pullback, then the given pattern bars."""
    closes = np.linspace(100, 160, 300)
    rows = [[x - 0.5, x + 0.3, x - 0.8, x] for x in closes]
    level = closes[-1]
    for i in range(6):
        level -= 1.2
        rows.append([level + 1.2, level + 1.4, level - 0.2, level])
    return frame_of(rows + last_rows(level))


def test_candle_pullback_buys_a_bullish_engulfing_after_a_dip_in_an_uptrend():
    frame = _trend_with_pullback(lambda p: [[p + 0.1, p + 0.2, p - 1.2, p - 1.0], [p - 1.1, p + 0.8, p - 1.3, p + 0.6]])
    order = st.CandlePullback(CONFIG).on_candle_close({"close_time": frame.index[-1], "timestamp": frame.index[-1]}, frame, Broker())
    assert order is not None and order.direction == LONG
    assert order.stop_loss_price < frame["low"].iloc[-2:].min()


def test_candle_pullback_ignores_the_pattern_without_a_prior_decline():
    closes = np.linspace(100, 160, 300)
    rows = [[x - 0.5, x + 0.3, x - 0.8, x] for x in closes]
    p = closes[-1]
    rows += [[p + 0.1, p + 0.2, p - 1.2, p - 1.0], [p - 1.1, p + 0.8, p - 1.3, p + 0.6]]
    frame = frame_of(rows)
    assert st.CandlePullback(CONFIG).on_candle_close({"close_time": frame.index[-1], "timestamp": frame.index[-1]}, frame, Broker()) is None


def test_candle_reversal_needs_the_20_day_low():
    closes = list(np.linspace(130, 100, 70))
    rows = [[x + 0.5, x + 0.8, x - 0.3, x] for x in closes]
    p = closes[-1]
    rows += [[p + 0.1, p + 0.2, p - 1.5, p - 1.0], [p - 1.1, p + 1.0, p - 1.6, p + 0.8]]
    frame = frame_of(rows, freq="1D")
    order = st.CandleReversal(CONFIG).on_candle_close({"close_time": frame.index[-1], "timestamp": frame.index[-1]}, frame, Broker())
    assert order.direction == LONG and order.take_profit_price > order.signal_price > order.stop_loss_price
    high = frame.copy()
    high[["open", "high", "low", "close"]] += np.r_[np.zeros(len(high) - 2), [5.0, 5.0]][:, None]  # pattern far above the low
    assert st.CandleReversal(CONFIG).on_candle_close({"close_time": high.index[-1], "timestamp": high.index[-1]}, high, Broker()) is None


def test_patterns_only_read_the_bars_they_are_given():
    frame = _trend_with_pullback(lambda p: [[p + 0.1, p + 0.2, p - 1.2, p - 1.0], [p - 1.1, p + 0.8, p - 1.3, p + 0.6]])
    assert c.reversal_signal(frame, True) == c.reversal_signal(pd.concat([frame, frame.iloc[-1:].shift(1, freq="4h")]).iloc[:-1], True)


@pytest.mark.parametrize("name,tf", [("candle_pullback", "4h"), ("candle_reversal", "1d"), ("candle_continuation", "4h"), ("candle_pullback_1h", "1h")])
def test_round6_registered(name, tf):
    from scripts.run_vision_backtest import load_config
    from src.strategies.registry import directional_strategy
    assert load_config(name, [])["strategy"]["timeframe_signal"] == tf
    assert directional_strategy(name, CONFIG).name


def _engulfing_frame():
    return _trend_with_pullback(lambda p: [[p + 0.1, p + 0.2, p - 1.2, p - 1.0], [p - 1.1, p + 0.8, p - 1.3, p + 0.6]])


def _order(mode, frame=None):
    frame = _engulfing_frame() if frame is None else frame
    strategy = st.CandlePullback({**CONFIG, "rules": {"exit_mode": mode}})
    return strategy, strategy.on_candle_close({"close_time": frame.index[-1], "timestamp": frame.index[-1]}, frame, Broker())


@pytest.mark.parametrize("mode,multiple", [("rr1", 1.0), ("rr2", 2.0)])
def test_fixed_reward_to_risk_targets(mode, multiple):
    _, order = _order(mode)
    risk = order.signal_price - order.stop_loss_price
    assert order.take_profit_price == pytest.approx(order.signal_price + multiple * risk)


def test_percent_and_resistance_targets():
    _, pct = _order("pct")
    assert pct.take_profit_price == pytest.approx(pct.signal_price * 1.01)
    frame = _engulfing_frame()
    _, sr = _order("sr", frame)
    assert sr.take_profit_price == pytest.approx(frame["high"].iloc[-21:-1].max())


def test_base_and_trail_have_no_take_profit_and_trail_tightens_from_recent_highs():
    _, base = _order("base")
    assert base.take_profit_price is None
    strategy, trail = _order("trail")
    assert trail.take_profit_price is None
    frame = _engulfing_frame()
    broker = Broker(LONG)
    strategy.on_candle_close({"close_time": frame.index[-1], "timestamp": frame.index[-1]}, frame, broker)
    expected = frame["high"].iloc[-10:].max() - 2.0 * float(st.atr(frame, 14).iloc[-1])
    assert broker.stops and broker.stops[-1] == pytest.approx(expected)


def test_indicator_exit_leaves_on_overbought_rsi():
    frame = frame_of([[x - 0.5, x + 0.3, x - 0.8, x] for x in np.linspace(100, 160, 300)])
    broker = Broker(LONG)
    st.CandlePullback({**CONFIG, "rules": {"exit_mode": "indicator"}}).on_candle_close(
        {"close_time": frame.index[-1], "timestamp": frame.index[-1]}, frame, broker)
    assert broker.closed


def test_take_profit_modes_time_out():
    strategy = st.CandlePullback({**CONFIG, "rules": {"exit_mode": "rr2"}})
    frame, broker = _engulfing_frame(), Broker(LONG)
    for _ in range(st.TIME_EXIT_BARS):
        strategy.on_candle_close({"close_time": frame.index[-1], "timestamp": frame.index[-1]}, frame, broker)
    assert len(broker.closed) == 1


def test_unknown_exit_mode_is_refused():
    with pytest.raises(ValueError):
        st.CandlePullback({**CONFIG, "rules": {"exit_mode": "moon"}})


WHATIF = "config/research/candles_2026_10_18/whatif_leverage_x20.yaml"


def test_leverage_whatif_is_per_symbol_and_capped_by_risk_config():
    from scripts.run_vision_backtest import load_config
    from src.strategies.registry import directional_strategy
    plain = load_config("candle_pullback", [])
    assert directional_strategy("candle_pullback", plain, "BTCUSDT").leverage == 2.0
    whatif = load_config("candle_pullback", [WHATIF])
    assert directional_strategy("candle_pullback", whatif, "BTCUSDT").leverage == 20.0
    assert directional_strategy("candle_pullback", whatif, "ETHUSDT").leverage == 20.0
    assert directional_strategy("candle_pullback", whatif, "SOLUSDT").leverage == 5.0
    capped = {**whatif, "risk": {**whatif["risk"], "max_leverage": 5}}
    assert directional_strategy("candle_pullback", capped, "BTCUSDT").leverage == 5.0
    assert st.CandlePullback({**CONFIG, "leverage": 50.0}).leverage == 5.0  # no risk config: old 5x ceiling


def test_x20_still_needs_the_stop_before_liquidation():
    from scripts.run_vision_backtest import load_config
    from src.risk.invariant_checks import calculate_estimated_liquidation_price
    whatif = load_config("candle_pullback", [WHATIF])
    liq = calculate_estimated_liquidation_price(direction="LONG", entry_price=100.0, position_size_usd=5000.0,
                                                leverage=20.0, symbol="BTCUSDT", leverage_brackets=whatif["leverage_brackets"])
    assert 94.0 < liq < 96.0  # about 5% under entry at x20, so a 6% stop cannot be used
