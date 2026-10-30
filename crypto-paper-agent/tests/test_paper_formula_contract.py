"""Independent arithmetic oracles for the frozen pandas-fallback-v1 convention."""
import math

import pandas as pd
import pytest

from src.features.indicators import calculate_ema, calculate_rsi, calculate_atr, calculate_macd


def ema(values, period):
    result = [float('nan')] * (period - 1)
    current = sum(values[:period]) / period
    result.append(current)
    alpha = 2 / (period + 1)
    for value in values[period:]:
        current = alpha * value + (1 - alpha) * current
        result.append(current)
    return result


def test_ema_and_macd_use_explicit_sma_seed_and_scalar_recursion():
    values = [100., 102., 99., 103., 105., 107., 101., 110.]
    frame = pd.DataFrame({'close': values})
    result = calculate_ema(frame, periods=[3], use_fallback=True)
    assert result.ema_3.tolist() == pytest.approx(ema(values, 3), nan_ok=True)
    fast, slow = ema(values, 2), ema(values, 4)
    lines = [a - b for a, b in zip(fast, slow)]
    valid = [v for v in lines if math.isfinite(v)]
    signals = [float('nan')] * 3 + ema(valid, 2)
    macd = calculate_macd(frame, fast=2, slow=4, signal=2, use_fallback=True)
    assert macd.macd.tolist() == pytest.approx(lines, nan_ok=True)
    assert macd.macd_signal.tolist() == pytest.approx(signals, nan_ok=True)
    assert macd.macd_hist.tolist() == pytest.approx([a - b for a, b in zip(lines, signals)], nan_ok=True)


def test_rsi_seed_is_first_delta_not_sma_and_zero_cases_are_explicit():
    # +2,-1,+3: first-delta seed, then Wilder alpha 1/3; gains 17/9, losses 2/9.
    result = calculate_rsi(pd.DataFrame({'close': [100., 102., 101., 104.]}), period=3, use_fallback=True)
    assert result.rsi_3.iloc[:3].isna().all()
    assert result.rsi_3.iloc[3] == pytest.approx(100 - 100 / (1 + 17 / 2))
    for values, expected in [([100.] * 5, 50), ([100.,101.,102.,103.,104.], 100), ([100.,99.,98.,97.,96.], 0)]:
        assert calculate_rsi(pd.DataFrame({'close': values}), period=3, use_fallback=True).rsi_3.iloc[-1] == expected


def test_atr_first_high_low_seed_and_gap_true_range_have_hand_oracle():
    frame = pd.DataFrame({'high': [101., 106., 105., 112.], 'low': [99., 104., 102., 109.],
                          'close': [100., 105., 103., 110.]})
    # TR = 2,6,3,9; RMA starts at first TR, not the first-window SMA.
    expected = [float('nan'), float('nan'), 29 / 9, 139 / 27]
    assert calculate_atr(frame, period=3, use_fallback=True).atr_3.tolist() == pytest.approx(expected, nan_ok=True)
