"""Round-12 adaptive rules (src/strategies/adaptive_suite.py)."""
import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import OrderDirection
from src.strategies import adaptive_suite as ad
from src.strategies.indicator_suite import ema
from src.strategies.style_suite import SwingEmaPullback
from tests.test_indicator_suite import CONFIG, Broker, bars

LONG = OrderDirection.LONG


def run(strategy, frame, broker=None):
    return strategy.on_candle_close({"close_time": frame.index[-1] + pd.Timedelta("4h")}, frame, broker or Broker())


def with_flow(frame, buy_share=0.6):
    frame = frame.copy()
    frame["volume"] = 100.0
    frame["taker_buy_base_volume"] = 100.0 * buy_share
    return frame


def _swing(n=400):
    closes = list(np.linspace(100, 200, n - 1))
    frame = bars(closes + [closes[-1] * 1.004])
    e20 = ema(frame["close"].iloc[-260:], 20)
    frame.iloc[-2, frame.columns.get_loc("low")] = e20.iloc[-2] * 0.99
    return with_flow(frame)


# ---------------------------------------------------------------- KAMA
def test_efficiency_ratio_is_one_for_a_straight_line_and_low_for_noise():
    line = pd.Series(np.linspace(100, 110, 30))
    assert ad.efficiency_ratio(line).iloc[-1] == pytest.approx(1.0)
    noise = pd.Series(np.where(np.arange(30) % 2, 101.0, 100.0))
    assert ad.efficiency_ratio(noise).iloc[-1] < 0.2


def test_kama_is_causal():
    close = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, 120))))
    assert ad.kama(close.iloc[:80]).equals(ad.kama(close).iloc[:80])


def test_kama_trend_signals_match_the_rule_on_a_random_walk():
    rng = np.random.default_rng(7)
    frame = bars(100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, 500))))
    hits = 0
    for end in range(200, 500):
        part = frame.iloc[end - 200:end]
        close, line = part["close"], ad.kama(part["close"])
        wanted = (close.iloc[-2] <= line.iloc[-2] and close.iloc[-1] > line.iloc[-1]
                  and line.iloc[-1] > line.iloc[-4] and ad.efficiency_ratio(close).iloc[-1] > 0.3)
        order = run(ad.KamaTrend(CONFIG), part)
        assert (order is not None) == bool(wanted)
        hits += order is not None
    assert hits > 0


# ---------------------------------------------------------------- C1 based
def test_c1_based_rules_keep_c1_entries():
    frame = _swing()
    c1 = run(SwingEmaPullback({**CONFIG, "rules": {"allow_short": False}}), frame.iloc[-260:])
    for cls in (ad.SwingEmaAdaptiveExit, ad.SwingEmaChandelier, ad.SwingEmaOrderFlow):
        order = run(cls(CONFIG), frame)
        assert order.stop_loss_price == pytest.approx(c1.stop_loss_price)


def test_order_flow_filter_needs_net_taker_buying():
    assert run(ad.SwingEmaOrderFlow(CONFIG), with_flow(_swing(), 0.45)) is None


def test_vol_expansion_filter_needs_atr_ratio_above_its_median(monkeypatch):
    frame = _swing()
    rising = pd.Series(np.linspace(1.0, 2.0, len(frame)), index=frame.index)
    monkeypatch.setattr(ad, "atr", lambda f, n: rising.loc[f.index] * f["close"])
    assert run(ad.SwingEmaVolExpansion(CONFIG), frame) is not None
    monkeypatch.setattr(ad, "atr", lambda f, n: rising.loc[f.index][::-1].to_numpy() * f["close"])
    assert run(ad.SwingEmaVolExpansion(CONFIG), frame) is None


def test_adaptive_exit_uses_ema20_in_a_weak_trend(monkeypatch):
    frame = bars(list(np.linspace(100, 200, 300)) + [195.0])
    close = frame["close"]
    assert ema(close, 50).iloc[-1] < close.iloc[-1] < ema(close, 20).iloc[-1]
    monkeypatch.setattr(ad, "adx", lambda f, n: pd.Series([10.0]))
    broker = Broker(LONG)
    run(ad.SwingEmaAdaptiveExit(CONFIG), frame, broker)
    assert broker.closed
    monkeypatch.setattr(ad, "adx", lambda f, n: pd.Series([40.0]))
    broker = Broker(LONG)
    run(ad.SwingEmaAdaptiveExit(CONFIG), frame, broker)
    assert not broker.closed


def test_chandelier_trail_is_22_bar_high_minus_3_atr():
    frame = bars(np.linspace(100, 200, 260))
    expected = frame["high"].iloc[-22:].max() - 3.0 * ad.atr(frame, 22).iloc[-1]
    assert ad.SwingEmaChandelier(CONFIG).trail(frame, LONG) == pytest.approx(expected)


# ---------------------------------------------------------------- regime
def test_regime_uses_bands_when_the_daily_trend_is_weak(monkeypatch):
    closes = list(np.where(np.arange(399) % 2, 101.0, 99.0)) + [99.5]
    frame = bars(closes)
    frame.iloc[-2, frame.columns.get_loc("close")] = 95.0
    frame.iloc[-2, frame.columns.get_loc("low")] = 94.5
    monkeypatch.setattr(ad, "adx", lambda f, n: pd.Series([12.0]))
    strategy = ad.RegimeSwingBands(CONFIG)
    order = run(strategy, frame)
    assert order is not None and strategy.mode == "range"
    assert order.take_profit_price == pytest.approx(frame["close"].iloc[-20:].mean())
    strategy.held_bars = 12
    assert strategy.should_exit(frame, LONG)
    monkeypatch.setattr(ad, "adx", lambda f, n: pd.Series([30.0]))
    assert run(ad.RegimeSwingBands(CONFIG), frame) is None  # trending mode: no C1 signal here


def test_regime_uses_c1_when_the_daily_trend_is_strong(monkeypatch):
    monkeypatch.setattr(ad, "adx", lambda f, n: pd.Series([30.0]))
    strategy = ad.RegimeSwingBands(CONFIG)
    assert run(strategy, _swing()) is not None and strategy.mode == "trend"
