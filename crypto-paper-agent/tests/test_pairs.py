"""Round-14 distance pairs (src/strategies/pairs.py)."""
import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import pairs as p
from tests.test_indicator_suite import Broker, bars

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT


def _index(n, start="2020-09-01"):
    return pd.date_range(start, periods=n, freq="4h", tz="UTC")


def test_select_pairs_takes_the_closest_normalised_prices():
    index = _index(100)
    base = 100 * np.exp(np.linspace(0, 0.5, 100))
    closes = pd.DataFrame({"A": base, "B": base * 2 * (1 + 0.001 * np.sin(np.arange(100))),
                           "C": 50 * np.exp(np.linspace(0, -0.5, 100))}, index=index)
    chosen = p.select_pairs(closes, 1)
    assert [(a, b) for a, b, _ in chosen] == [("A", "B")]
    assert chosen[0][2] > 0
    closes.iloc[0, 2] = np.nan  # C lacks a full window, so it is left out
    assert all("C" not in (a, b) for a, b, _ in p.select_pairs(closes, 3))


def test_pair_path_opens_beyond_the_threshold_and_closes_at_the_crossing():
    index = _index(8)
    a = [100, 101, 103, 104, 101, 99, 97, 100]
    trading = pd.DataFrame({"A": a, "B": [100.0] * 8}, index=index)
    path = p.pair_path(trading, 100.0, 100.0, sigma=0.01, entry_sigma=2.0)
    # gap: 0, .01, .03, .04, .01, -.01, -.03, 0 -> open short-a at .03, close at the cross, reopen long-a at -.03
    assert list(path) == [0, 0, 1, 1, 1, 0, -1, 0]


def _panel(n=6 * 30 * 8):
    """A and B move together for 6 months, then A runs up while B stays flat."""
    index = _index(n)
    rng = np.random.default_rng(0)
    common = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    a, b = common.copy(), common * (1 + rng.normal(0, 0.0005, n))
    start = index.get_indexer([pd.Timestamp("2021-03-01", tz="UTC")])[0]
    a[start + 30:] *= 1.10
    c = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    return pd.DataFrame({"A": a, "B": b, "C": c}, index=index)


def test_coin_sides_short_the_leg_that_ran_up_and_buy_the_laggard():
    sides = p.coin_sides(_panel(), formation_months=6, trading_months=1, top_pairs=1, entry_sigma=2.0)
    at = pd.Timestamp("2021-03-01", tz="UTC") + pd.Timedelta(hours=4 * 31)
    assert sides.loc[at, "A"] == -1 and sides.loc[at, "B"] == 1 and sides.loc[at, "C"] == 0
    assert (sides.loc[:"2021-02-28"] == 0).all().all()  # the first 6 months only form pairs


def test_coin_sides_never_use_later_closes():
    closes = _panel()
    cut = pd.Timestamp("2021-03-10", tz="UTC")
    sides = p.coin_sides(closes, 6, 1, 1, 2.0)
    future = closes.copy()
    future.loc[future.index > cut] *= np.linspace(0.5, 3.0, int((future.index > cut).sum()))[:, None]
    assert sides.loc[:cut].equals(p.coin_sides(future, 6, 1, 1, 2.0).loc[:cut])


def test_window_starts_every_n_months_from_the_anchor():
    first, last = pd.Timestamp("2020-09-01", tz="UTC"), pd.Timestamp("2021-03-15", tz="UTC")
    assert [s.month for s in p.window_starts(first, last, 3)] == [12, 3]


def _strategy(sides):
    config = {"rules": {"allow_short": True, "universe": ["BTCUSDT"]}, "default_conviction": "normal",
              "leverage": 2.0, "base_risk_percent": 0.02}
    strategy = p.PairsDistance(config, "BTCUSDT")
    strategy.sides = sides
    return strategy


def run(strategy, frame, broker=None):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("4h")}, frame, broker or Broker(None))


def test_enters_only_when_the_side_changes_with_a_stop_on_the_right_side():
    frame = bars(np.linspace(100, 120, 200))
    sides = pd.Series(0, index=frame.index)
    sides.iloc[-1] = 1
    order = run(_strategy(sides), frame)
    assert order.direction == LONG and order.stop_loss_price < order.signal_price
    sides.iloc[-2:] = 1  # already long last bar: no new entry
    assert run(_strategy(sides), frame) is None
    sides.iloc[-2], sides.iloc[-1] = 0, -1
    order = run(_strategy(sides), frame)
    assert order.direction == SHORT and order.stop_loss_price > order.signal_price


def test_exits_when_the_side_moves_away():
    frame = bars(np.linspace(100, 120, 200))
    sides = pd.Series(1, index=frame.index)
    broker = Broker(LONG)
    run(_strategy(sides), frame, broker)
    assert not broker.closed
    sides.iloc[-1] = 0
    run(_strategy(sides), frame, broker)
    assert broker.closed


def test_without_peer_data_it_never_trades():
    frame = bars(np.linspace(100, 120, 200))
    assert run(_strategy(None), frame) is None
