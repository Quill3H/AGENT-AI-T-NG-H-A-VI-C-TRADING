"""Round-7 strategies from the owner's video and published trader methods (src/strategies/session_suite.py)."""
import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import session_suite as ss
from tests.test_indicator_suite import CONFIG, Broker, bars

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT


def candle(frame):
    return {"close_time": frame.index[-1] + pd.Timedelta("5min"), "timestamp": frame.index[-1]}


def run(strategy, frame, broker=None):
    return strategy.on_candle_close(candle(frame), frame, broker or Broker())


def test_eastern_clock_follows_daylight_saving():
    summer, winter = pd.Timestamp("2023-07-03").date(), pd.Timestamp("2023-01-03").date()
    assert ss.eastern_at(summer, 3) == pd.Timestamp("2023-07-03 07:00", tz="UTC")
    assert ss.eastern_at(winter, 3) == pd.Timestamp("2023-01-03 08:00", tz="UTC")


def _london_day(break_at, price=101.5, before=None):
    """Flat 5m bars from 2023-07-02 (summer: London 07:00-12:00 UTC) with a break bar at break_at."""
    index = pd.date_range("2023-07-02 12:00", "2023-07-03 20:00", freq="5min", tz="UTC")
    frame = pd.DataFrame({"open": 100.5, "high": 101.0, "low": 100.0, "close": 100.5}, index=index)
    if before is not None:
        frame.loc[pd.Timestamp(before, tz="UTC"), ["high", "close"]] = [101.6, 101.4]
    t = pd.Timestamp(break_at, tz="UTC")
    frame.loc[t, ["open", "high", "low", "close"]] = [100.5, price + 0.1, 100.4, price]
    return frame.loc[:t]


def test_london_breakout_takes_the_first_close_outside_the_range():
    frame = _london_day("2023-07-03 12:30")
    order = run(ss.LondonBreakout(CONFIG), frame)
    assert order.direction == LONG and order.stop_loss_price == pytest.approx(100.4)
    assert order.take_profit_price == pytest.approx(101.5 + 2 * (101.5 - 100.4))


def test_london_breakout_skips_a_second_break_and_late_breaks():
    assert run(ss.LondonBreakout(CONFIG), _london_day("2023-07-03 13:00", before="2023-07-03 12:30")) is None
    assert run(ss.LondonBreakout(CONFIG), _london_day("2023-07-03 15:30")) is None  # after 11:00 ET
    strategy = ss.LondonBreakout(CONFIG)
    frame = _london_day("2023-07-03 12:30")
    assert run(strategy, frame) is not None and run(strategy, frame) is None  # one per day


def test_session_positions_close_at_new_york_close():
    frame = _london_day("2023-07-03 19:55")
    broker = Broker(LONG)
    run(ss.LondonBreakout(CONFIG), frame, broker)  # bar closes 20:00 UTC = 16:00 ET
    assert broker.closed
    broker = Broker(LONG)
    run(ss.LondonBreakout(CONFIG), frame.iloc[:-1], broker)
    assert not broker.closed


def test_heikin_ashi_matches_the_textbook_recursion():
    rng = np.random.default_rng(2)
    frame = bars(100 + np.cumsum(rng.normal(0, 1, 50)), freq="5min")
    ha = ss.heikin_ashi(frame)
    o = (frame["open"].iloc[0] + frame["close"].iloc[0]) / 2
    for i in range(len(frame)):
        c = frame.iloc[i][["open", "high", "low", "close"]].mean()
        if i:
            o = (o + prev_c) / 2
        assert ha["open"].iloc[i] == pytest.approx(o) and ha["close"].iloc[i] == pytest.approx(c)
        assert ha["high"].iloc[i] == pytest.approx(max(frame["high"].iloc[i], o, c))
        prev_c = c


def test_heikin_ashi_scalp_buys_a_doji_after_clean_red_bars_in_an_uptrend():
    closes = np.linspace(100, 130, 297)
    rows = [[x - 0.05, x + 0.1, x - 0.1, x] for x in closes]
    p = closes[-1]
    rows += [[p - 0.3, p - 0.3, p - 1.0, p - 0.9], [p - 0.9, p - 0.9, p - 1.8, p - 1.7]]  # red, no upper wick
    rows += [[p - 1.7, p + 0.6, p - 2.6, p - 1.65]]  # wide doji
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                         index=pd.date_range("2023-01-01", periods=len(rows), freq="5min", tz="UTC"))
    ha = ss.heikin_ashi(frame).iloc[-1]
    order = run(ss.HeikinAshiScalp(CONFIG), frame)
    assert order.direction == LONG and order.stop_loss_price == pytest.approx(ha["low"])
    assert order.take_profit_price == pytest.approx(2 * ha["high"] - ha["low"])
    wick = frame.copy()
    wick.iloc[-3] = [p, p, p - 1.0, p - 0.9]  # the first red bar now has an upper HA wick
    assert run(ss.HeikinAshiScalp(CONFIG), wick) is None
    below = frame.copy()
    below[["open", "high", "low", "close"]] = below[["open", "high", "low", "close"]].iloc[::-1].to_numpy()[::-1] - np.r_[np.zeros(297), [40.0] * 3][:, None]
    assert run(ss.HeikinAshiScalp(CONFIG), below) is None  # under EMA(100)


def test_last_swing_needs_bars_on_both_sides():
    assert ss.last_swing(np.array([1, 2, 5, 2, 1, 3, 4.0]), 2, True) == 5.0
    assert ss.last_swing(np.array([1, 2, 3, 2, 6.0]), 2, True) is None


def test_zone_swing_break_finds_a_support_zone_and_respects_the_morning_window():
    index = pd.date_range("2023-07-01", periods=2900, freq="5min", tz="UTC")
    base = 100 + 0.2 * np.sin(np.arange(2900) / 12.0)
    frame = pd.DataFrame({"open": base, "high": base + 0.1, "low": base - 0.1, "close": base}, index=index)
    dip = slice(1200, 1212)
    frame.iloc[dip, frame.columns.get_loc("low")] -= 3.0  # one hour with a deep low
    frame.iloc[1212:1290, [0, 1, 2, 3]] += np.linspace(0, 4, 78)[:, None]  # strong move away
    strategy = ss.ZoneSwingBreak(CONFIG)
    strategy.refresh_zones(frame)
    supports, _ = strategy.zones
    assert any(bottom == pytest.approx(frame["low"].iloc[dip].min()) for bottom, _ in supports)
    late = frame.loc[:"2023-07-10 20:00"]  # 16:00 ET
    assert run(ss.ZoneSwingBreak(CONFIG), late) is None


def _two_days(second):
    index = pd.date_range("2023-02-28", periods=576 + len(second), freq="5min", tz="UTC")
    first = [[100.0, 101.0, 99.0, 100.0]] * 576  # yesterday's range = 2
    return pd.DataFrame(first + second, columns=["open", "high", "low", "close"], index=index)


def test_volatility_breakout_enters_on_open_plus_six_tenths_of_the_range():
    frame = _two_days([[100.0, 100.5, 99.9, 100.2], [100.2, 101.4, 100.1, 101.3]])
    order = run(ss.VolatilityBreakout(CONFIG), frame)
    assert order.direction == LONG and order.stop_loss_price == pytest.approx(101.3 - 1.0)
    short_of = _two_days([[100.0, 100.5, 99.9, 100.2], [100.2, 101.1, 100.1, 101.0]])
    assert run(ss.VolatilityBreakout(CONFIG), short_of) is None  # 101.0 < 100 + 0.6 x 2
    late = _two_days([[100.0, 101.4, 99.9, 101.3], [101.3, 101.6, 101.2, 101.5]])
    assert run(ss.VolatilityBreakout(CONFIG), late) is None  # the first break already happened
    broker = Broker(LONG)
    end = _two_days([[100.0, 100.5, 99.9, 100.2]] * 288)
    run(ss.VolatilityBreakout(CONFIG), end, broker)
    assert broker.closed


def test_nr7_breakout_uses_the_narrow_bar():
    rows = [[100, 103, 97, 100]] * 28 + [[100, 100.5, 99.5, 100], [100, 101.2, 99.8, 101.0]]
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float,
                         index=pd.date_range("2023-01-01", periods=30, freq="4h", tz="UTC"))
    order = ss.NarrowRangeBreakout(CONFIG).on_candle_close(candle(frame), frame, Broker())
    assert order.direction == LONG and order.stop_loss_price == pytest.approx(99.5)
    wide = frame.copy()
    wide.iloc[-2] = [100, 103.4, 96.6, 100]  # wider than the six before
    wide.iloc[-1] = [100, 103.6, 99.8, 103.5]
    assert ss.NarrowRangeBreakout(CONFIG).on_candle_close(candle(wide), wide, Broker()) is None


def test_holy_grail_needs_a_strong_trend():
    rng = np.random.default_rng(5)
    flat = bars(100 + rng.normal(0, 0.2, 120), freq="1h")
    assert ss.HolyGrail(CONFIG).on_candle_close(candle(flat), flat, Broker()) is None
    closes = list(np.linspace(100, 160, 112)) + [158.0, 156.5, 155.5, 155.0, 155.2, 155.4, 155.6, 157.0]
    trend = bars(closes, freq="1h")
    trend.iloc[-2, trend.columns.get_loc("low")] = float(ss.ema(trend["close"], 20).iloc[-1]) - 0.1
    order = ss.HolyGrail(CONFIG).on_candle_close(candle(trend), trend, Broker())
    assert order is not None and order.direction == LONG
    assert order.take_profit_price == pytest.approx(trend["high"].iloc[-21:-1].max())


@pytest.mark.parametrize("name,tf", [("london_breakout", "5m"), ("london_breakout_trend", "5m"), ("heikin_ashi_scalp", "5m"),
                                     ("zone_swing_break", "5m"), ("swing_ema_pullback_1h", "1h"), ("holy_grail", "1h"),
                                     ("volatility_breakout", "5m"), ("nr7_breakout", "4h")])
def test_round7_registered(name, tf):
    from scripts.run_vision_backtest import load_config
    from src.strategies.registry import directional_strategy
    assert load_config(name, [])["strategy"]["timeframe_signal"] == tf
    assert directional_strategy(name, CONFIG).name
