"""Round-15 funding rules (src/strategies/funding_signals.py)."""
import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import cross_section as xs
from src.strategies import funding_signals as fs
from tests.test_indicator_suite import Broker, bars

LONG, SHORT = OrderDirection.LONG, OrderDirection.SHORT
COINS = [f"C{i}USDT" for i in range(8)]


def _events(start, n, rate):
    index = pd.date_range(start, periods=n, freq="8h", tz="UTC")
    return pd.Series(rate if np.ndim(rate) else [rate] * n, index=index, dtype=float)


def test_mean_funding_uses_events_up_to_and_including_the_decision_time():
    series = _events("2023-01-01", 10, np.arange(10.0))
    until = series.index[5]
    assert fs.mean_funding(series, until, 1) == pytest.approx(np.mean([3.0, 4.0, 5.0]))
    later = series.copy()
    later.iloc[6:] = 1e6
    assert fs.mean_funding(later, until, 1) == fs.mean_funding(series, until, 1)


def test_crowded_compares_the_week_with_its_own_history():
    calm = _events("2023-01-01", 3 * 200, 0.0001)
    until = calm.index[-1]
    assert not fs.crowded(calm, until)
    hot = calm.copy()
    hot.iloc[-21:] = 0.001  # the last 7 days pay 10x
    assert fs.crowded(hot, until)
    assert not fs.crowded(hot.iloc[-100:], until)  # too little history


def _panel(tmp_path, rates, start="2023-01-01", n=300):
    for coin, rate in zip(COINS, rates):
        bars(100 + np.arange(n) * 0.1, start=start).to_parquet(tmp_path / f"{coin}_perp_4h.parquet")
        frame = pd.DataFrame({"funding_rate": _events(start, n, rate), "funding_interval_hours": 8})
        frame.to_parquet(tmp_path / f"{coin}_perp_funding.parquet")
    return tmp_path


def _config(tmp_path, **rules):
    base = {"allow_short": True, "side": "both", "lookback_days": 7, "top_n": 3, "min_coins": 6, "universe": COINS}
    return {"rules": {**base, **rules}, "default_conviction": "normal", "leverage": 2.0, "base_risk_percent": 0.02,
            "runtime": {"data_dir": str(tmp_path)}}


def _frame(tmp_path, coin):
    frame = pd.read_parquet(tmp_path / f"{coin}_perp_4h.parquet")
    rebalance = [t for t in frame.index if xs.is_rebalance_bar(t) and t >= frame.index[200]][0]
    return frame.loc[:rebalance]


def run(strategy, frame, broker=None):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("4h")}, frame, broker or Broker(None))


RATES = [-0.0003, -0.0002, -0.0001, 0.0, 0.0001, 0.0002, 0.0003, 0.0004]  # C0 lowest .. C7 highest


@pytest.mark.parametrize("coin,expected", [("C0USDT", LONG), ("C2USDT", LONG), ("C3USDT", None), ("C7USDT", SHORT), ("C5USDT", SHORT)])
def test_carry_buys_the_lowest_funding_and_sells_the_highest(tmp_path, coin, expected):
    _panel(tmp_path, RATES)
    order = run(fs.FundingCarry(_config(tmp_path), coin), _frame(tmp_path, coin))
    assert (order.direction if order else None) == expected
    if order:
        assert (order.stop_loss_price < order.signal_price) == (expected == LONG)


def test_short_side_only_and_only_when_funding_is_positive(tmp_path):
    _panel(tmp_path, RATES)
    assert run(fs.FundingCarry(_config(tmp_path, side="short"), "C0USDT"), _frame(tmp_path, "C0USDT")) is None
    assert run(fs.FundingCarry(_config(tmp_path, side="short"), "C7USDT"), _frame(tmp_path, "C7USDT")).direction == SHORT
    _panel(tmp_path, [r - 0.001 for r in RATES])  # everything negative: no crowded long anywhere
    assert run(fs.FundingCarry(_config(tmp_path, side="short"), "C7USDT"), _frame(tmp_path, "C7USDT")) is None
    assert run(fs.FundingCarry(_config(tmp_path), "C7USDT"), _frame(tmp_path, "C7USDT")).direction == SHORT


def test_carry_trades_only_at_the_weekly_bar_and_needs_enough_coins(tmp_path):
    _panel(tmp_path, RATES)
    frame = _frame(tmp_path, "C7USDT")
    full = pd.read_parquet(tmp_path / "C7USDT_perp_4h.parquet")
    assert run(fs.FundingCarry(_config(tmp_path), "C7USDT"), full.loc[:frame.index[-1] + pd.Timedelta("4h")]) is None
    assert run(fs.FundingCarry(_config(tmp_path, min_coins=9), "C7USDT"), frame) is None


def test_carry_exits_when_the_coin_leaves_its_group(tmp_path):
    _panel(tmp_path, RATES)
    frame = _frame(tmp_path, "C7USDT")
    strategy = fs.FundingCarry(_config(tmp_path), "C7USDT")
    broker = Broker(SHORT)
    broker.positions = {"C7USDT": broker.positions["BTCUSDT"]}
    run(strategy, frame, broker)
    assert not broker.closed
    broker = Broker(LONG)
    broker.positions = {"C7USDT": broker.positions["BTCUSDT"]}
    run(strategy, frame, broker)
    assert broker.closed


def test_c1_filter_blocks_longs_only_while_funding_is_crowded(monkeypatch):
    config = {"rules": {"allow_short": False}, "default_conviction": "normal", "leverage": 2.0, "base_risk_percent": 0.02}
    strategy = fs.C1FundingFilter(config, "BTCUSDT")
    frame = bars(np.linspace(100, 120, 300))
    monkeypatch.setattr(fs.C1FundingFilter, "c1_entry", lambda self, f: (LONG, float(f["close"].iloc[-1]) * 0.95))
    seen = []
    monkeypatch.setattr(fs, "crowded", lambda series, until: seen.append(until) or True)
    strategy.funding = pd.Series([0.0001])
    assert run(strategy, frame) is None
    assert seen == [frame.index[-1] + pd.Timedelta("4h")]  # decided at the bar's close
    monkeypatch.setattr(fs, "crowded", lambda series, until: False)
    assert run(strategy, frame).direction == LONG
