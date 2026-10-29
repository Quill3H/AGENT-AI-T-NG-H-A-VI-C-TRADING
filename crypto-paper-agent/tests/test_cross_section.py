"""Round-13 cross-sectional momentum (src/strategies/cross_section.py)."""
import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import cross_section as xs
from tests.test_indicator_suite import Broker, bars

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT
COINS = [f"C{i}USDT" for i in range(8)]


def _panel(tmp_path, n=300, start="2023-01-01"):
    """Coin i drifts by (i - 3.5) * 0.1% a bar: C7 strongest, C0 weakest."""
    for i, coin in enumerate(COINS):
        closes = 100.0 * np.exp(np.arange(n) * (i - 3.5) * 0.001)
        bars(closes, start=start).to_parquet(tmp_path / f"{coin}_perp_4h.parquet")
    return tmp_path


def _config(tmp_path, **rules):
    base = {"allow_short": True, "lookback_weeks": 3, "top_n": 3, "min_coins": 6, "absolute": False, "universe": COINS}
    return {"rules": {**base, **rules}, "default_conviction": "normal", "leverage": 2.0, "base_risk_percent": 0.02,
            "runtime": {"data_dir": str(tmp_path)}}


def _frame_at_rebalance(tmp_path, coin):
    frame = pd.read_parquet(tmp_path / f"{coin}_perp_4h.parquet")
    rebalance = [t for t in frame.index if xs.is_rebalance_bar(t) and t >= frame.index[200]][0]
    return frame.loc[:rebalance]


def held(direction, coin):
    broker = Broker(direction)
    broker.positions = {coin: broker.positions["BTCUSDT"]}
    return broker


def run(strategy, frame, broker=None):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("4h")}, frame, broker or Broker(None))


def test_rebalance_bar_is_sunday_20h():
    assert xs.is_rebalance_bar(pd.Timestamp("2023-01-08 20:00", tz="UTC"))  # a Sunday
    assert not xs.is_rebalance_bar(pd.Timestamp("2023-01-08 16:00", tz="UTC"))
    assert not xs.is_rebalance_bar(pd.Timestamp("2023-01-09 20:00", tz="UTC"))


def test_rank_scores_use_only_bars_up_to_the_decision():
    index = pd.date_range("2023-01-01", periods=10, freq="4h", tz="UTC")
    closes = pd.DataFrame({"A": np.arange(10.0) + 1, "B": 10.0 - np.arange(10.0)}, index=index)
    scores = xs.rank_scores(closes, index[5], 2)
    assert scores["A"] == pytest.approx(6 / 4 - 1) and scores["B"] == pytest.approx(5 / 7 - 1)
    future = closes.copy()
    future.iloc[6:] = 1e6
    assert xs.rank_scores(future, index[5], 2).equals(scores)


@pytest.mark.parametrize("coin,expected", [("C7USDT", LONG), ("C5USDT", LONG), ("C0USDT", SHORT), ("C3USDT", None)])
def test_top_three_long_bottom_three_short(tmp_path, coin, expected):
    _panel(tmp_path)
    order = run(xs.CrossSectionMomentum(_config(tmp_path), coin), _frame_at_rebalance(tmp_path, coin))
    assert (order.direction if order else None) == expected
    if order:
        assert (order.stop_loss_price < order.signal_price) == (expected == LONG)


def test_no_entry_between_rebalances(tmp_path):
    _panel(tmp_path)
    frame = _frame_at_rebalance(tmp_path, "C7USDT")
    full = pd.read_parquet(tmp_path / "C7USDT_perp_4h.parquet")
    later = full.loc[:frame.index[-1] + pd.Timedelta("4h")]
    assert run(xs.CrossSectionMomentum(_config(tmp_path), "C7USDT"), later) is None


def test_long_only_and_absolute_filters(tmp_path):
    _panel(tmp_path)
    frame = _frame_at_rebalance(tmp_path, "C0USDT")
    assert run(xs.CrossSectionMomentum(_config(tmp_path, allow_short=False), "C0USDT"), frame) is None
    # C4 is third from the top but its own drift is +0.05%/bar; C5..C7 positive too, so all longs pass
    frame4 = _frame_at_rebalance(tmp_path, "C5USDT")
    assert run(xs.CrossSectionMomentum(_config(tmp_path, absolute=True), "C5USDT"), frame4).direction == LONG


def test_absolute_blocks_a_top_coin_with_a_negative_return(tmp_path):
    _panel(tmp_path)
    for i, coin in enumerate(COINS):  # shift every coin down so that even the top three fall
        closes = 100.0 * np.exp(np.arange(300) * (i - 9.5) * 0.001)
        bars(closes, start="2023-01-01").to_parquet(tmp_path / f"{coin}_perp_4h.parquet")
    frame = _frame_at_rebalance(tmp_path, "C7USDT")
    assert run(xs.CrossSectionMomentum(_config(tmp_path), "C7USDT"), frame).direction == LONG
    assert run(xs.CrossSectionMomentum(_config(tmp_path, absolute=True), "C7USDT"), frame) is None


def test_exit_only_at_rebalance_when_the_coin_leaves_its_group(tmp_path):
    _panel(tmp_path)
    frame = _frame_at_rebalance(tmp_path, "C7USDT")
    broker = held(LONG, "C7USDT")
    run(xs.CrossSectionMomentum(_config(tmp_path), "C7USDT"), frame, broker)
    assert not broker.closed  # still top
    broker = held(SHORT, "C7USDT")
    run(xs.CrossSectionMomentum(_config(tmp_path), "C7USDT"), frame, broker)
    assert broker.closed  # a short in the top group must go
    broker = held(SHORT, "C7USDT")
    full = pd.read_parquet(tmp_path / "C7USDT_perp_4h.parquet")
    run(xs.CrossSectionMomentum(_config(tmp_path), "C7USDT"), full.loc[:frame.index[-1] + pd.Timedelta("4h")], broker)
    assert not broker.closed  # not a rebalance bar


def test_needs_enough_coins(tmp_path):
    _panel(tmp_path)
    frame = _frame_at_rebalance(tmp_path, "C7USDT")
    assert run(xs.CrossSectionMomentum(_config(tmp_path, min_coins=9), "C7USDT"), frame) is None


def test_absolute_blocks_a_bottom_coin_with_a_positive_return(tmp_path):
    for i, coin in enumerate(COINS):  # every coin rises, so even the bottom three gained
        closes = 100.0 * np.exp(np.arange(300) * (i + 1) * 0.001)
        bars(closes, start="2023-01-01").to_parquet(tmp_path / f"{coin}_perp_4h.parquet")
    frame = _frame_at_rebalance(tmp_path, "C0USDT")
    assert run(xs.CrossSectionMomentum(_config(tmp_path), "C0USDT"), frame).direction == SHORT
    assert run(xs.CrossSectionMomentum(_config(tmp_path, absolute=True), "C0USDT"), frame) is None
