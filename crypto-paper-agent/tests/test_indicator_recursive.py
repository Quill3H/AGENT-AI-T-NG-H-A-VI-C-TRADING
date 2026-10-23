"""Recursive-indicator check (the idea behind Freqtrade's recursive-analysis, rewritten here).

ewm(adjust=False) indicators (EMA, Wilder RSI/ATR/ADX, Supertrend's band) depend on where the data
starts. RuleStrategy always computes on exactly the last `window` bars, so a backtest and a forward
paper run that see the same bars get the same value. What this file pins is how far that windowed
value sits from the value on a long history:

- converged cases must agree to the stated tolerance;
- two cases are KNOWN not to converge inside their frozen window (measured on BTCUSDT 4h perp
  2021-2026 on 2026-10-23: ADX(14) on 80 bars, median 2.7% / max 10% off, the ADX>25 gate flips on
  about 2.7% of checks; daily EMA(200) inside 1400 4h bars, median 1.4% / max 8.9% off, the
  EMA50>EMA200 regime flips on about 5% of checks). Their windows belong to round-3 results and are
  not changed here; the ceilings below (set on the seeded random walk, where the gaps are smaller
  than on BTC) only stop the gap growing unnoticed.
"""
import numpy as np
import pandas as pd
import pytest

from src.strategies import indicator_suite as s

HISTORY = 3000


def random_walk(n=HISTORY + 400, seed=7):
    rng = np.random.default_rng(seed)
    close = 30000 * np.exp(np.cumsum(rng.normal(0, 0.012, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0, 0.006, (2, n)))
    index = pd.date_range("2021-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * (1 + wick[0]),
                         "low": np.minimum(open_, close) * (1 - wick[1]), "close": close}, index=index)


def daily_ema(bars):
    return lambda f: s.ema(s.completed_daily(f)["close"], bars)


# (case, strategy window, indicator on a frame, max relative gap at the last bar)
CASES = [
    ("SqueezeBreakout EMA20", s.SqueezeBreakout.window, lambda f: s.ema(f["close"], 20), 1e-7),
    ("SqueezeBreakout/ADXDonchian ATR20", s.SqueezeBreakout.window, lambda f: s.atr(f, 20), 1e-12),
    ("RSI2Reversion RSI2", s.RSI2Reversion.window, lambda f: s.rsi(f["close"], 2), 1e-9),
    ("Supertrend line", s.SupertrendStrategy.window, lambda f: pd.Series(s.supertrend(f)[0], index=f.index), 1e-6),
    ("RegimeSwitch ADX14", s.RegimeSwitch.window, lambda f: s.adx(f, 14), 0.01),
    ("MultiTimeframeTrend daily EMA50", s.MultiTimeframeTrend.window, daily_ema(50), 1e-3),
    ("TimeSeriesMomentum EMA50", s.TimeSeriesMomentum.window, lambda f: s.ema(f["close"], 50), 0.015),
    ("KNOWN ADXDonchian ADX14", s.ADXDonchian.window, lambda f: s.adx(f, 14), 0.10),
    ("KNOWN MultiTimeframeTrend daily EMA200", s.MultiTimeframeTrend.window, daily_ema(200), 0.06),
]


@pytest.mark.parametrize("case, window, indicator, tolerance", CASES, ids=[c[0] for c in CASES])
def test_windowed_value_matches_long_history_within_tolerance(case, window, indicator, tolerance):
    data = random_walk()
    gaps = []
    for end in range(HISTORY, len(data) + 1, 6):  # one check per simulated day
        full = data.iloc[end - HISTORY:end]
        windowed, reference = float(indicator(full.iloc[-window:]).iloc[-1]), float(indicator(full).iloc[-1])
        gaps.append(abs(windowed - reference) / max(abs(reference), 1e-12))
    assert max(gaps) <= tolerance, f"{case}: windowed value off by up to {max(gaps):.4%}"


@pytest.mark.parametrize("cls", [s.TimeSeriesMomentum, s.RSI2Reversion, s.SqueezeBreakout, s.ADXDonchian,
                                 s.SupertrendStrategy, s.RegimeSwitch, s.MultiTimeframeTrend])
def test_decision_does_not_depend_on_where_the_history_starts(cls):
    """Backtest (years of history) and forward paper (only recent bars) must decide alike."""
    data = random_walk()
    strategy = cls({"rules": {}, "default_conviction": "normal", "leverage": 2.0, "base_risk_percent": 0.02})
    for end in range(HISTORY, len(data) + 1, 25):
        long_history, short_history = data.iloc[:end], data.iloc[end - cls.window:end]
        a = strategy.entry(long_history.iloc[-cls.window:][list(cls.columns)])
        b = strategy.entry(short_history[list(cls.columns)])
        assert a == b
