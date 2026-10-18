"""Round-11 trader rules (src/strategies/trader_suite.py) and RuleStrategy scale-outs."""
import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import trader_suite as ts
from src.strategies.indicator_suite import ema, supertrend
from src.strategies.style_suite import SwingEmaPullback
from tests.test_indicator_suite import CONFIG, Broker, bars

LONG = OrderDirection.LONG


def run(strategy, frame, broker=None):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("4h")}, frame, broker or Broker())


def with_volume(frame, volume=100.0):
    frame = frame.copy()
    frame["volume"] = volume
    return frame


def test_obv_adds_volume_on_up_closes_and_subtracts_on_down_closes():
    frame = pd.DataFrame({"close": [10.0, 11.0, 11.0, 10.0, 12.0], "volume": [5.0, 2.0, 3.0, 4.0, 1.0]})
    assert list(ts.obv(frame)) == [0.0, 2.0, 2.0, -2.0, -1.0]


# ------------------------------------------------------------- swing + filter
def _swing_frame():
    closes = list(np.linspace(100, 200, 399))
    frame = with_volume(bars(closes + [closes[-1] * 1.004]))
    e20 = ema(frame["close"].iloc[-260:], 20)
    frame.iloc[-2, frame.columns.get_loc("low")] = e20.iloc[-2] * 0.99
    return frame


def test_sharks_takes_the_c1_signal_only_when_supertrends_and_obv_agree(monkeypatch):
    frame = _swing_frame()
    c1 = run(SwingEmaPullback({**CONFIG, "rules": {"allow_short": False}}), frame.iloc[-260:])
    monkeypatch.setattr(ts, "daily_supertrends_up", lambda f: True)
    monkeypatch.setattr(ts, "obv_rising", lambda f: True)
    order = run(ts.SwingEmaSharks(CONFIG), frame)
    assert c1 is not None and order.stop_loss_price == pytest.approx(c1.stop_loss_price)
    monkeypatch.setattr(ts, "obv_rising", lambda f: False)
    assert run(ts.SwingEmaSharks(CONFIG), frame) is None
    monkeypatch.setattr(ts, "obv_rising", lambda f: True)
    monkeypatch.setattr(ts, "daily_supertrends_up", lambda f: False)
    assert run(ts.SwingEmaSharks(CONFIG), frame) is None


def test_daily_supertrends_read_completed_days_only():
    up = with_volume(bars(np.linspace(100, 200, 400)))
    assert ts.daily_supertrends_up(up)
    down = with_volume(bars(np.linspace(200, 100, 400)))
    assert not ts.daily_supertrends_up(down)


@pytest.mark.parametrize("fast,slow,expected", [(1, 1, True), (-1, 1, False), (1, -1, False)])
def test_daily_filter_needs_both_supertrends(monkeypatch, fast, slow, expected):
    monkeypatch.setattr(ts, "supertrend", lambda days, bars, multiple: (None, [fast if multiple == 2.0 else slow]))
    assert ts.daily_supertrends_up(with_volume(bars(np.linspace(100, 200, 400)))) is expected


# ------------------------------------------------------------ supertrend obv
def test_supertrend_obv_enters_on_the_fast_flip_with_stop_on_the_slow_line():
    rng = np.random.default_rng(3)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.02, 600)))
    frame = with_volume(bars(closes))
    frame["volume"] = np.where(np.diff(np.r_[closes[0], closes]) > 0, 300.0, 100.0)
    hits = 0
    for end in range(200, 600):
        part = frame.iloc[end - 200:end]
        fast_line, fast = supertrend(part, 10, 2.0)
        slow_line, slow = supertrend(part, 10, 3.0)
        order = run(ts.SupertrendObv(CONFIG), part)
        wanted = fast[-2] < 0 < fast[-1] and slow[-1] > 0 and ts.obv_rising(part)
        assert (order is not None) == bool(wanted and slow_line[-1] < part["close"].iloc[-1])
        if order is not None:
            hits += 1
            assert order.stop_loss_price == pytest.approx(slow_line[-1])
    assert hits > 0


# ---------------------------------------------------------------- breakout
def _breakout(volume=400.0):
    closes = list(np.linspace(100, 150, 230)) + [150.0] * 29 + [153.0]
    frame = with_volume(bars(closes))
    frame.iloc[-1, frame.columns.get_loc("volume")] = volume
    return frame


def test_gooner_breakout_needs_volume_and_sets_a_2r_target():
    order = run(ts.GoonerBreakout(CONFIG), _breakout())
    assert order.direction == LONG
    close = 153.0
    assert order.take_profit_price == pytest.approx(close + 2.0 * (close - order.stop_loss_price))
    assert run(ts.GoonerBreakout(CONFIG), _breakout(volume=120.0)) is None


def test_gooner_breakout_needs_the_uptrend():
    frame = _breakout()
    falling = with_volume(bars(list(np.linspace(200, 150, 230)) + [150.0] * 29 + [153.0]))
    falling["volume"] = frame["volume"].to_numpy()
    assert run(ts.GoonerBreakout(CONFIG), falling) is None


# ------------------------------------------------------------------- cheds
def _cheds(closes):
    frame = bars(closes)
    e8 = ema(frame["close"], 8)
    frame.iloc[-2, frame.columns.get_loc("low")] = e8.iloc[-2] * 0.995
    return frame


def test_cheds_buys_a_dip_to_ema8_in_a_daily_uptrend():
    closes = list(np.linspace(100, 200, 399))
    order = run(ts.ChedsEmaPullback(CONFIG), _cheds(closes + [closes[-1] * 1.003]))
    assert order.direction == LONG


def test_cheds_skips_when_the_daily_trend_is_down():
    closes = list(np.linspace(200, 120, 380)) + list(np.linspace(120, 130, 19))
    assert run(ts.ChedsEmaPullback(CONFIG), _cheds(closes + [closes[-1] * 1.003])) is None


def test_cheds_exits_under_ema21():
    broker = Broker(LONG)
    frame = bars(list(np.linspace(100, 200, 390)) + list(np.linspace(199, 180, 10)))
    run(ts.ChedsEmaPullback(CONFIG), frame, broker)
    assert broker.closed


# --------------------------------------------------------------- scale-outs
def test_rules_partial_exits_reach_the_order():
    closes = list(np.linspace(100, 200, 399))
    frame = _cheds(closes + [closes[-1] * 1.003])
    config = {**CONFIG, "rules": {"partial_exits": [[1.0, 0.33], [2.0, 0.33]]}}
    assert run(ts.ChedsEmaPullback(config), frame).partial_exits == [[1.0, 0.33], [2.0, 0.33]]
    assert run(ts.ChedsEmaPullback(CONFIG), frame).partial_exits == []
