"""Round-17 rules from the r/Daytrading post (src/strategies/reddit_plan.py).
2023-07-03 is in US summer time: 06:00 ET = 10:00 UTC, 07:00 ET = 11:00 UTC, 09:30 ET = 13:30 UTC."""
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import reddit_plan as rp
from tests.test_indicator_suite import Broker

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT


def config(*setups):
    return {"rules": {"allow_short": True, "setups": list(setups)}, "default_conviction": "normal",
            "leverage": 2.0, "base_risk_percent": 0.02}


def run(strategy, frame, broker=None):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("5min")}, frame, broker or Broker())


def day(high=101.0, low=100.0):
    index = pd.date_range("2023-07-02 12:00", "2023-07-03 20:00", freq="5min", tz="UTC")
    return pd.DataFrame({"open": (high + low) / 2, "high": high, "low": low, "close": (high + low) / 2}, index=index)


def put(frame, at, o, h, l, c):
    frame.loc[pd.Timestamp(at, tz="UTC"), ["open", "high", "low", "close"]] = [o, h, l, c]


def upto(frame, at):
    return frame.loc[:pd.Timestamp(at, tz="UTC")]


def test_premarket_breakout_uses_the_far_side_of_the_range_as_stop():
    frame = day()
    put(frame, "2023-07-03 11:05", 100.5, 101.6, 100.4, 101.5)  # closes 07:10 ET
    order = run(rp.RedditPlan(config("premarket")), upto(frame, "2023-07-03 11:05"))
    assert order.direction == LONG and order.stop_loss_price == pytest.approx(100.0)
    assert order.take_profit_price == pytest.approx(101.5 + 2 * 1.5)
    put(frame, "2023-07-03 11:05", 100.5, 100.6, 99.4, 99.5)
    order = run(rp.RedditPlan(config("premarket")), upto(frame, "2023-07-03 11:05"))
    assert order.direction == SHORT and order.stop_loss_price == pytest.approx(101.0)


def test_premarket_breakout_only_first_break_inside_the_window():
    frame = day()
    put(frame, "2023-07-03 12:00", 100.5, 101.6, 100.4, 101.5)  # closes 08:05 ET, too late
    assert run(rp.RedditPlan(config("premarket")), upto(frame, "2023-07-03 12:00")) is None
    frame = day()
    put(frame, "2023-07-03 11:00", 100.5, 101.6, 100.4, 101.5)
    put(frame, "2023-07-03 11:10", 100.5, 101.6, 100.4, 101.5)
    assert run(rp.RedditPlan(config("premarket")), upto(frame, "2023-07-03 11:10")) is None  # not the first


def test_a_stop_too_close_for_the_costs_is_skipped():
    frame = day(high=100.1, low=100.0)
    put(frame, "2023-07-03 11:05", 100.05, 100.2, 100.0, 100.15)  # risk 0.15 < 0.3% of price
    assert run(rp.RedditPlan(config("premarket")), upto(frame, "2023-07-03 11:05")) is None


def _opening(up=True):
    frame = day()
    for i, t in enumerate(("13:30", "13:35", "13:40")):
        base = 100 + i if up else 100 - i
        put(frame, f"2023-07-03 {t}", base, base + 1.2, base - 0.2, base + 1 if up else base - 1)
    return frame


def test_open_reversal_fades_the_opening_move_with_a_reversal_candle():
    frame = _opening(up=True)
    put(frame, "2023-07-03 13:45", 103.0, 105.0, 102.9, 102.95)  # shooting star, closes 09:50 ET
    order = run(rp.RedditPlan(config("open_reversal")), upto(frame, "2023-07-03 13:45"))
    assert order.direction == SHORT and order.stop_loss_price == pytest.approx(105.0)
    assert order.take_profit_price == pytest.approx(102.95 - 2 * 2.05)
    frame = _opening(up=False)
    put(frame, "2023-07-03 13:45", 97.0, 97.05, 95.0, 96.95)  # hammer after a down open
    order = run(rp.RedditPlan(config("open_reversal")), upto(frame, "2023-07-03 13:45"))
    assert order.direction == LONG and order.stop_loss_price == pytest.approx(95.0)


def test_open_reversal_needs_a_candle_against_the_move_after_0945():
    frame = _opening(up=True)
    put(frame, "2023-07-03 13:45", 103.0, 103.05, 101.0, 102.95)  # hammer: with the move, not against
    assert run(rp.RedditPlan(config("open_reversal")), upto(frame, "2023-07-03 13:45")) is None
    frame = _opening(up=True)
    put(frame, "2023-07-03 13:40", 102.0, 105.0, 101.9, 101.95)  # star on the 09:40 bar, before 09:45
    assert run(rp.RedditPlan(config("open_reversal")), upto(frame, "2023-07-03 13:40")) is None


def test_engulfing_candles_count_as_reversals():
    prev = {"open": 100.0, "high": 101.2, "low": 99.9, "close": 101.0}
    bear = {"open": 101.1, "high": 101.2, "low": 99.7, "close": 99.8}
    assert rp.reversal(prev, bear, bullish=False) and not rp.reversal(prev, bear, bullish=True)
    prev = {"open": 101.0, "high": 101.1, "low": 99.8, "close": 100.0}
    bull = {"open": 99.9, "high": 101.3, "low": 99.8, "close": 101.2}
    assert rp.reversal(prev, bull, bullish=True) and not rp.reversal(prev, bull, bullish=False)


def test_the_plan_takes_each_setup_once_then_stops():
    frame = _opening(up=True)
    put(frame, "2023-07-03 11:05", 100.5, 101.6, 100.4, 101.5)
    put(frame, "2023-07-03 13:45", 103.0, 105.0, 102.9, 102.95)
    put(frame, "2023-07-03 13:50", 103.0, 105.0, 102.9, 102.95)
    strategy = rp.RedditPlan(config("premarket", "open_reversal"))
    assert run(strategy, upto(frame, "2023-07-03 11:05")).direction == LONG
    assert run(strategy, upto(frame, "2023-07-03 13:45")).direction == SHORT
    assert run(strategy, upto(frame, "2023-07-03 13:50")) is None  # both setups used
    only_premarket = rp.RedditPlan(config("premarket"))
    assert run(only_premarket, upto(frame, "2023-07-03 13:45")) is None


def test_positions_are_flat_by_the_new_york_close():
    frame = day()
    broker = Broker(LONG)
    run(rp.RedditPlan(config("premarket")), upto(frame, "2023-07-03 19:55"), broker)
    assert broker.closed


def test_a_wick_shorter_than_twice_the_body_is_not_a_hammer_or_star():
    flat = {"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0}
    near_hammer = {"open": 97.0, "high": 97.0, "low": 94.4, "close": 96.0}  # lower wick 1.6 < 2 x body 1
    near_star = {"open": 96.0, "high": 98.6, "low": 96.0, "close": 97.0}
    assert not rp.reversal(flat, near_hammer, bullish=True)
    assert not rp.reversal(flat, near_star, bullish=False)


def test_a_down_bar_inside_the_previous_up_bar_is_not_engulfing():
    prev = {"open": 100.0, "high": 101.1, "low": 99.9, "close": 101.0}
    inside = {"open": 100.9, "high": 100.95, "low": 100.4, "close": 100.5}
    assert not rp.reversal(prev, inside, bullish=False)


def test_each_setup_fires_once_a_day_even_with_budget_left():
    frame = _opening(up=True)
    put(frame, "2023-07-03 13:45", 103.0, 105.0, 102.9, 102.95)
    put(frame, "2023-07-03 13:50", 103.0, 105.0, 102.9, 102.95)
    strategy = rp.RedditPlan(config("open_reversal"))
    assert run(strategy, upto(frame, "2023-07-03 13:45")) is not None
    assert run(strategy, upto(frame, "2023-07-03 13:50")) is None
