"""Round-19 rules from the owner's r/Daytrading ICT post (src/strategies/ict_liquidity.py).
2023-07-05 is a Wednesday in US summer time: 09:30 ET = 13:30 UTC. Synthetic bars only."""
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import ict_liquidity as ict
from tests.test_indicator_suite import Broker

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT
COLS = ["open", "high", "low", "close"]


def config(*setups):
    return {"rules": {"allow_short": True, "setups": list(setups), "bar_minutes": 5, "window_bars": 240},
            "default_conviction": "normal", "leverage": 2.0, "base_risk_percent": 0.02}


def ts(at):
    return at if isinstance(at, pd.Timestamp) else pd.Timestamp(at, tz="UTC")


def put(frame, at, o, h, l, c):
    frame.loc[ts(at), COLS] = [o, h, l, c]


def span(frame, start, end, o, h, l, c):
    frame.loc[ts(start):ts(end), COLS] = [o, h, l, c]


def market(day="2023-07-05"):
    """A 1h bullish FVG [99.0, 99.8] two days before; on `day` Asia 99.8-101.5, London low 99.7
    (sweeps Asia), a 13:00 sweep to 99.5 (sweeps London, taps the FVG), a 13:05 displacement."""
    d = pd.Timestamp(day, tz="UTC")
    index = pd.date_range(d - pd.Timedelta(days=11), d + pd.Timedelta(hours=20), freq="5min")
    frame = pd.DataFrame({"open": 98.9, "high": 99.0, "low": 98.8, "close": 98.9}, index=index)
    gap_day = (d - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    span(frame, f"{gap_day} 11:00", f"{gap_day} 11:55", 99.3, 99.75, 99.05, 99.4)
    span(frame, f"{gap_day} 12:00", index[-1], 100.0, 100.2, 99.8, 100.0)
    span(frame, f"{day} 06:00", index[-1], 100.0, 100.1, 99.9, 100.0)
    put(frame, f"{day} 02:00", 100.0, 101.5, 99.9, 100.0)  # Asia high, the draw on liquidity
    put(frame, f"{day} 09:00", 100.0, 100.05, 99.7, 99.95)  # London takes the Asia low
    put(frame, f"{day} 13:00", 99.9, 99.95, 99.5, 99.6)  # takes the London low into the 1h FVG
    put(frame, f"{day} 13:05", 99.55, 100.08, 99.5, 100.05)  # displacement body 0.5 > ATR
    return frame


def run(strategy, frame, at):
    history = frame.loc[:pd.Timestamp(at, tz="UTC")]
    order = None
    for end in history.index[-24:]:  # walk the last bars so the day's state builds as in a run
        part = history.loc[:end]
        order = strategy.on_candle_close({"close_time": end + pd.Timedelta("5min")}, part, Broker()) or order
    return order


def orb_breakout(frame, day="2023-07-05"):
    put(frame, f"{day} 13:45", 99.95, 100.1, 99.9, 100.05)  # FVG bar 1
    put(frame, f"{day} 13:50", 100.1, 100.35, 100.05, 100.3)
    put(frame, f"{day} 13:55", 100.3, 100.4, 100.2, 100.35)  # bar 3 low > bar 1 high, close > OR high
    return frame


def mirror(frame):
    out = frame.copy()
    out["open"], out["close"] = 200 - frame["open"], 200 - frame["close"]
    out["high"], out["low"] = 200 - frame["low"], 200 - frame["high"]
    return out


def test_htf_zones_drop_a_gap_a_later_close_went_through():
    frame = market()
    day = pd.Timestamp("2023-07-05", tz="UTC")
    assert (pytest.approx(99.0), pytest.approx(99.8)) in [(b, t) for b, t in ict.live_htf_zones(frame, day, True)]
    span(frame, "2023-07-04 03:00", "2023-07-04 03:55", 100.0, 100.1, 98.5, 98.6)  # a 1h close below 99.0
    assert not [z for z in ict.live_htf_zones(frame, day, True) if z[0] == pytest.approx(99.0)]


def test_orb_fvg_long_after_both_lows_swept_targets_the_asia_high():
    frame = orb_breakout(market())
    order = run(ict.IctLiquidity(config("orb_fvg")), frame, "2023-07-05 13:55")
    assert order.direction == LONG
    assert order.stop_loss_price == pytest.approx(99.9) and order.take_profit_price == pytest.approx(101.5)


def test_orb_fvg_short_mirrors_the_long():
    frame = mirror(orb_breakout(market()))
    order = run(ict.IctLiquidity(config("orb_fvg")), frame, "2023-07-05 13:55")
    assert order.direction == SHORT
    assert order.stop_loss_price == pytest.approx(100.1) and order.take_profit_price == pytest.approx(98.5)


def test_no_trade_without_the_london_sweep_or_the_htf_gap_or_on_a_weekend():
    frame = orb_breakout(market())
    put(frame, "2023-07-05 13:00", 99.9, 99.95, 99.75, 99.8)  # stays above the London low 99.7
    assert run(ict.IctLiquidity(config("orb_fvg")), frame, "2023-07-05 13:55") is None
    frame = orb_breakout(market())
    span(frame, "2023-07-04 03:00", "2023-07-04 03:55", 100.0, 100.1, 98.5, 98.6)  # the 1h FVG fails
    assert run(ict.IctLiquidity(config("orb_fvg")), frame, "2023-07-05 13:55") is None
    frame = orb_breakout(market("2023-07-08"), "2023-07-08")  # Saturday
    assert run(ict.IctLiquidity(config("orb_fvg")), frame, "2023-07-08 13:55") is None


def test_orb_fvg_skips_when_the_asia_high_is_already_taken_or_too_close():
    frame = orb_breakout(market())
    put(frame, "2023-07-05 08:00", 100.0, 101.6, 99.9, 100.0)  # Asia high taken in London
    assert run(ict.IctLiquidity(config("orb_fvg")), frame, "2023-07-05 13:55") is None
    frame = orb_breakout(market())
    put(frame, "2023-07-05 02:00", 100.0, 100.8, 99.9, 100.0)  # target 0.45 away < 1.5 x 0.45 risk
    assert run(ict.IctLiquidity(config("orb_fvg")), frame, "2023-07-05 13:55") is None


def test_irl_erl_enters_on_the_first_tap_of_the_30m_gap_with_a_2r_target():
    frame = market()
    span(frame, "2023-07-05 13:30", "2023-07-05 13:55", 100.3, 100.8, 100.2, 100.7)
    span(frame, "2023-07-05 14:00", "2023-07-05 14:25", 100.7, 100.9, 100.5, 100.8)  # 30m low 100.5 > 100.1
    put(frame, "2023-07-05 14:30", 100.7, 100.75, 100.4, 100.6)  # first trade back into [100.1, 100.5]
    order = run(ict.IctLiquidity(config("irl_erl")), frame, "2023-07-05 14:30")
    assert order.direction == LONG and order.stop_loss_price == pytest.approx(99.5)
    assert order.take_profit_price == pytest.approx(100.6 + 2 * 1.1)
    put(frame, "2023-07-05 14:35", 100.6, 100.65, 100.3, 100.5)  # a second tap is not a new signal
    strategy = ict.IctLiquidity(config("irl_erl"))
    assert run(strategy, frame, "2023-07-05 14:35") is not None and strategy.entries_today == 1


def test_positions_are_closed_at_the_new_york_close():
    frame = market()
    strategy = ict.IctLiquidity(config("orb_fvg"))
    broker = Broker(direction=LONG)
    strategy.on_candle_close({"close_time": ts("2023-07-05 20:00")}, frame.loc[:ts("2023-07-05 19:55")], broker)
    assert broker.closed  # 19:55 bar closes 16:00 ET
