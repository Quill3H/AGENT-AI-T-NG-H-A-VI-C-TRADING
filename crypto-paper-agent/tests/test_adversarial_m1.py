"""
tests/test_adversarial_m1.py
============================
Adversarial Stress Test Suite for Milestone 1:
- SynthesizedStrategy (src/strategies/synthesized.py)
- UniverseDataLoader (src/data_layer/universe_loader.py)

Designed and executed by empirical challenger (teamwork_challenger_m1_1).
"""
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import (
    OrderDirection,
    OrderRequest,
    OrderType,
    Position,
)
from src.execution.paper_broker import PaperBroker
from src.data_layer.universe_loader import UniverseDataLoader
from src.strategies.synthesized import (
    SynthesizedStrategy,
    MarketRegime,
    SetupType,
    ConvictionTier,
)


def _create_synthetic_history_15m(n_bars: int = 100, base_price: float = 100.0) -> pd.DataFrame:
    """Helper to generate clean 15m OHLCV dataframe."""
    start = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    idx = pd.date_range(start, periods=n_bars, freq="15min", tz="UTC")
    closes = np.linspace(base_price, base_price * 1.05, n_bars)
    opens = np.roll(closes, 1)
    opens[0] = base_price
    highs = np.maximum(opens, closes) * 1.002
    lows = np.minimum(opens, closes) * 0.998
    volume = np.full(n_bars, 1000.0)
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volume},
        index=idx,
    )
    df.index.name = "timestamp"
    return df


def _create_synthetic_history_4h(n_bars: int = 300, base_price: float = 100.0) -> pd.DataFrame:
    """Helper to generate clean 4h OHLCV dataframe with indicators."""
    start = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    idx = pd.date_range(start, periods=n_bars, freq="4h", tz="UTC")
    closes = np.linspace(base_price, base_price * 1.20, n_bars)
    opens = np.roll(closes, 1)
    opens[0] = base_price
    highs = np.maximum(opens, closes) * 1.005
    lows = np.minimum(opens, closes) * 0.995
    volume = np.full(n_bars, 50000.0)
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volume},
        index=idx,
    )
    df.index.name = "timestamp"
    return df


# ===========================================================================
# ADVERSARIAL SUITE 1: Causal Strictness & Future 4h Tampering
# ===========================================================================

def test_adv_future_4h_tampering_zero_impact_on_15m():
    """
    Adversarial Challenge: Future 4h data tampering must not leak into 15m decisions.
    We inject a massive 10x price spike and extreme ADX into future 4h candles,
    and verify that all 15m decisions prior to the 4h close remain 100% bit-identical.
    """
    loader = UniverseDataLoader()
    start_dt = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    end_dt = pd.Timestamp("2024-01-05 00:00:00", tz="UTC")
    data = loader.generate_synthetic_universe(start_dt, end_dt, symbols=["BTCUSDT"])
    df_15m = data["BTCUSDT"]["15m"]
    df_4h_clean = data["BTCUSDT"]["4h"]

    # Tamper future 4h bars after 2024-01-02 00:00:00
    tamper_cutoff = pd.Timestamp("2024-01-02 00:00:00", tz="UTC")
    df_4h_tampered = df_4h_clean.copy()
    future_mask = df_4h_tampered.index >= tamper_cutoff
    df_4h_tampered.loc[future_mask, "close"] *= 10.0
    df_4h_tampered.loc[future_mask, "high"] *= 10.0

    # Probe 15m bar at 2024-01-01 23:45:00 (closes at 2024-01-02 00:00:00)
    probe_ts = pd.Timestamp("2024-01-01 23:45:00", tz="UTC")
    causal_clean = loader.get_causal_4h_for_15m(probe_ts, df_4h_clean)
    causal_tampered = loader.get_causal_4h_for_15m(probe_ts, df_4h_tampered)

    assert causal_clean is not None
    assert causal_tampered is not None
    # Must be identical
    pd.testing.assert_series_equal(causal_clean, causal_tampered)

    # Strategy outputs must be identical
    cfg = {"synthesized": {}}
    strat_clean = SynthesizedStrategy(cfg, "BTCUSDT")
    strat_tampered = SynthesizedStrategy(cfg, "BTCUSDT")

    candle_15m = dict(df_15m.loc[probe_ts])
    candle_15m["close_time"] = probe_ts + pd.Timedelta(minutes=15)
    hist_15m = df_15m.loc[:probe_ts]

    res_clean = strat_clean.on_candle_close(
        candle_15m, hist_15m,
        dict(causal_clean), df_4h_clean.loc[:causal_clean.name],
    )
    res_tampered = strat_tampered.on_candle_close(
        candle_15m, hist_15m,
        dict(causal_tampered), df_4h_tampered.loc[:causal_tampered.name],
    )

    assert strat_clean.current_regime == strat_tampered.current_regime
    if res_clean is None:
        assert res_tampered is None
    else:
        assert res_tampered is not None
        assert res_clean.direction == res_tampered.direction
        assert res_clean.signal_price == res_tampered.signal_price


def test_adv_rejects_future_4h_candle_in_on_candle_close():
    """
    Adversarial Challenge: Does on_candle_close detect when a caller passes
    a 4h candle whose timestamp/close_time is strictly in the FUTURE relative to 15m?
    """
    cfg = {"synthesized": {}}
    strat = SynthesizedStrategy(cfg, "BTCUSDT")

    t_15m = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    candle_15m = {
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0,
        "close_time": t_15m + pd.Timedelta(minutes=15),
    }
    hist_15m = _create_synthetic_history_15m(50, 100.0)

    # Malicious future 4h candle: closes 4 hours AFTER the 15m candle!
    future_4h_time = t_15m + pd.Timedelta(hours=4)
    candle_4h_future = {
        "open": 100.0, "high": 150.0, "low": 90.0, "close": 140.0, "volume": 50000.0,
        "close_time": future_4h_time,
        "timestamp": future_4h_time,
    }
    hist_4h = _create_synthetic_history_4h(250, 100.0)

    # Let's check what happens:
    # If the strategy accepts this future 4h candle without validation,
    # it silently classifies the macro regime based on future data!
    strat.on_candle_close(
        candle_15m, hist_15m,
        candle_4h_future, hist_4h,
    )
    # Observe whether strat.last_4h_close_time was updated to the future time:
    future_accepted = (strat.last_4h_close_time > candle_15m["close_time"])
    # Record empirical finding:
    assert future_accepted, "Observed that future 4h candle is accepted without temporal guard"


# ===========================================================================
# ADVERSARIAL SUITE 2: Trailing Stop Ratchet Invariants & Erratic Swings
# ===========================================================================

def test_adv_trailing_stop_never_loosens_under_wild_oscillations():
    """
    Adversarial Challenge: Under violent price oscillations, verify that
    trailing stop strictly obeys the ratchet rule:
    - For LONG: Stop can ONLY increase. Never decrease, never exceed mark price.
    - For SHORT: Stop can ONLY decrease. Never increase, never drop below mark price.
    """
    broker = PaperBroker(config={}, initial_balance=10000.0)
    strat = SynthesizedStrategy({}, "BTCUSDT")

    # Setup a mock LONG position with partials_done = 2
    pos = Position(
        position_id="POS_BTC_001",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=0.25,
        entry_price=100.0,
        initial_margin=12.5,
        isolated_collateral=12.5,
        leverage=2.0,
        stop_loss_price=95.0,
        liquidation_price=50.0,
        take_profit_price=120.0,
        opened_at=datetime.now(timezone.utc),
        metadata={"partials_done": 2},
    )
    broker.positions["BTCUSDT"] = pos

    # Simulate erratic EMA oscillations
    ema_sequence = [102.0, 104.0, 108.0, 103.0, 109.0, 107.0, 112.0, 95.0, 115.0]
    mark_sequence = [105.0, 107.0, 110.0, 106.0, 111.0, 109.0, 114.0, 108.0, 118.0]

    sl_history = [pos.stop_loss_price]

    for ema, mark in zip(ema_sequence, mark_sequence):
        candle = {"close": mark, "ema_20": ema}
        broker.last_mark_prices["BTCUSDT"] = mark
        strat.update_trailing_stop(candle, broker)
        sl_history.append(pos.stop_loss_price)

        # Invariants:
        # 1. Stop loss must be monotonically non-decreasing (ratchet invariant: NEVER LOOSENS)
        assert sl_history[-1] >= sl_history[-2], f"SL loosened from {sl_history[-2]} to {sl_history[-1]}"
        # 2. When updated, new stop loss must not have exceeded the mark price AT TIME OF UPDATE
        if sl_history[-1] > sl_history[-2]:
            assert sl_history[-1] < mark, f"New SL {sl_history[-1]} exceeded update mark price {mark}"

    # Verify SL ratcheted up to the maximum valid EMA (115.0)
    assert pos.stop_loss_price == 115.0


def test_adv_trailing_stop_boolean_type_confusion():
    """
    Adversarial Challenge: In candle_15m, what if ema_20 is passed as boolean True?
    In Python, isinstance(True, int) is True, and float(True) == 1.0.
    Does update_trailing_stop handle boolean values without corrupting state or crashing?
    """
    broker = PaperBroker(config={}, initial_balance=10000.0)
    strat = SynthesizedStrategy({}, "BTCUSDT")

    pos = Position(
        position_id="POS_BTC_002",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=0.25,
        entry_price=100.0,
        initial_margin=12.5,
        isolated_collateral=12.5,
        leverage=2.0,
        stop_loss_price=0.5,  # Very low stop loss
        liquidation_price=0.1,
        take_profit_price=120.0,
        opened_at=datetime.now(timezone.utc),
        metadata={"partials_done": 2},
    )
    broker.positions["BTCUSDT"] = pos
    broker.last_mark_prices["BTCUSDT"] = 105.0

    # Pass boolean True as ema_20
    candle_corrupt = {"close": 105.0, "ema_20": True}

    strat.update_trailing_stop(candle_corrupt, broker)
    # Check if stop loss was updated to 1.0 due to float(True) == 1.0 > 0.5
    # If it was updated to 1.0, it demonstrates a type-coercion vulnerability!
    type_coerced = (pos.stop_loss_price == 1.0)
    print(f"Boolean type coercion result: pos.stop_loss_price={pos.stop_loss_price}")


# ===========================================================================
# ADVERSARIAL SUITE 3: Invalid Order Generation Under Extreme Conditions
# ===========================================================================

def test_adv_smc_setup_crash_on_inverted_stop_loss():
    """
    Adversarial Probe: In _evaluate_smc_setup, lines 533-556, does the code verify
    that stop < c for LONG, and stop > c for SHORT, before constructing OrderRequest?
    If price flash-crashed during FVG so c <= stop, does OrderRequest crash with ValueError?
    """
    cfg = {"synthesized": {}}
    strat = SynthesizedStrategy(cfg, "BTCUSDT")

    # Manually arm an SMC setup for LONG
    strat.setup.setup_type = SetupType.SMC_SWEEP
    strat.setup.direction = OrderDirection.LONG
    strat.setup.phase = "WAIT_FVG"
    strat.setup.sweep_extreme = 100.0  # extreme was 100.0
    strat.setup.metadata["ob_low"] = 100.5
    strat.setup.age = 1

    # Now mock SMC tracker to return a BULLISH FVG
    hist_15m = _create_synthetic_history_15m(50, 100.0)
    # In history, last bar has close = 95.0 (flash dump below sweep extreme 100.0!)
    candle_15m = {
        "open": 98.0, "high": 99.0, "low": 94.0, "close": 95.0, "volume": 5000.0,
        "close_time": datetime.now(timezone.utc),
    }

    # Monkeypatch tracker.step to simulate FVG
    strat.smc_tracker.step = lambda df: {
        "fvg_direction": "BULLISH",
        "fvg_high": 99.0,
        "fvg_low": 96.0,
        "fvg_mid": 97.5,
    }

    # Now run on_candle_close:
    # extreme = 100.0, base_ref = 100.0 -> stop = 100.0 * 0.999 = 99.9
    # signal_price = c = 95.0
    # Stop loss (99.9) > signal price (95.0) for a LONG!
    # Does OrderRequest crash with ValueError?
    crashed = False
    try:
        strat.on_candle_close(candle_15m, hist_15m)
    except ValueError as exc:
        crashed = True
        err_msg = str(exc)
        print(f"Empirically caught crash: {err_msg}")
        assert "LONG stop_loss_price" in err_msg or "signal_price" in err_msg

    assert not crashed, "CRITICAL: SynthesizedStrategy crashed on invalid SMC stop loss!"


def test_adv_smc_setup_crash_on_short_inverted_stop_loss():
    """
    Adversarial Probe: Same check for SHORT SMC setup.
    If price rallies during FVG so c >= stop, does OrderRequest crash?
    """
    cfg = {"synthesized": {}}
    strat = SynthesizedStrategy(cfg, "BTCUSDT")

    strat.setup.setup_type = SetupType.SMC_SWEEP
    strat.setup.direction = OrderDirection.SHORT
    strat.setup.phase = "WAIT_FVG"
    strat.setup.sweep_extreme = 100.0
    strat.setup.metadata["ob_high"] = 99.5
    strat.setup.age = 1

    hist_15m = _create_synthetic_history_15m(50, 100.0)
    # Close rallies to 105.0 (above sweep extreme 100.0)
    candle_15m = {
        "open": 101.0, "high": 106.0, "low": 100.0, "close": 105.0, "volume": 5000.0,
        "close_time": datetime.now(timezone.utc),
    }

    strat.smc_tracker.step = lambda df: {
        "fvg_direction": "BEARISH",
        "fvg_high": 104.0,
        "fvg_low": 102.0,
        "fvg_mid": 103.0,
    }

    crashed = False
    try:
        strat.on_candle_close(candle_15m, hist_15m)
    except ValueError as exc:
        crashed = True
        err_msg = str(exc)
        print(f"Empirically caught SHORT crash: {err_msg}")
        assert "SHORT stop_loss_price" in err_msg or "signal_price" in err_msg

    assert not crashed, "CRITICAL: SynthesizedStrategy crashed on invalid SHORT SMC stop loss!"


# ===========================================================================
# ADVERSARIAL SUITE 4: Rapid Regime Flipping & Setup Invalidation
# ===========================================================================

def test_adv_smc_setup_counter_trend_execution_after_regime_flip():
    """
    Adversarial Challenge:
    1. Bullish SMC setup arms in CHOP_RANGING.
    2. Macro regime flips to TREND_BEAR.
    3. FVG triggers: Does the strategy execute a counter-trend LONG directly into TREND_BEAR?
    """
    cfg = {"synthesized": {}}
    strat = SynthesizedStrategy(cfg, "BTCUSDT")

    # Step 1: Arm in CHOP_RANGING
    strat.current_regime = MarketRegime.CHOP_RANGING
    strat.setup.setup_type = SetupType.SMC_SWEEP
    strat.setup.direction = OrderDirection.LONG
    strat.setup.phase = "WAIT_FVG"
    strat.setup.sweep_extreme = 90.0
    strat.setup.age = 1

    # Step 2: Regime flips to TREND_BEAR
    strat.current_regime = MarketRegime.TREND_BEAR

    # Step 3: Trigger FVG
    hist_15m = _create_synthetic_history_15m(50, 100.0)
    candle_15m = {
        "open": 99.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 5000.0,
        "close_time": datetime.now(timezone.utc),
    }
    strat.smc_tracker.step = lambda df: {
        "fvg_direction": "BULLISH",
        "fvg_high": 101.0,
        "fvg_low": 99.0,
        "fvg_mid": 100.0,
    }

    order = strat.on_candle_close(candle_15m, hist_15m)

    # Invariant: Counter-trend LONG order must NOT execute in TREND_BEAR
    assert order is None, "Counter-trend LONG order should be suppressed/reset after regime flip to TREND_BEAR"


def test_adv_breakout_zombie_setup_blocks_new_setups_on_regime_flip():
    """
    Adversarial Challenge:
    When Breakout arms in TREND_BULL, then regime flips to TREND_BEAR,
    does the un-invalidated long setup linger and block any short breakout from arming?
    """
    cfg = {"synthesized": {}}
    strat = SynthesizedStrategy(cfg, "BTCUSDT")

    # Arm a bullish breakout in TREND_BULL
    strat.current_regime = MarketRegime.TREND_BULL
    strat.setup.setup_type = SetupType.BREAKOUT
    strat.setup.direction = OrderDirection.LONG
    strat.setup.level = 100.0
    strat.setup.age = 1

    # Regime flips to TREND_BEAR
    strat.current_regime = MarketRegime.TREND_BEAR

    # A massive bear breakdown occurs with 3x volume
    hist_15m = _create_synthetic_history_15m(50, 100.0)
    # Price breaks down to 90.0 (prior low was 98.0) with massive volume
    candle_15m = {
        "open": 95.0, "high": 96.0, "low": 89.0, "close": 90.0, "volume": 50000.0,
        "close_time": datetime.now(timezone.utc),
    }

    # Evaluate breakout setup
    strat._evaluate_breakout_setup(candle_15m, hist_15m, strat.current_regime)

    # Check if a BEAR breakout was able to arm:
    # If setup_type is still LONG BREAKOUT (or was not armed), it was blocked!
    blocked = (strat.setup.direction == OrderDirection.LONG or strat.setup.setup_type is None)
    print(f"Breakout state after flip: type={strat.setup.setup_type}, dir={strat.setup.direction}, age={strat.setup.age}")
    assert blocked


# ===========================================================================
# ADVERSARIAL SUITE 5: UniverseLoader Data Corruption Permutations
# ===========================================================================

@pytest.mark.parametrize("corruption_type", [
    "non_monotonic",
    "duplicates",
    "naive_tz",
    "wrong_tz",
    "missing_column",
    "nan_price",
    "inf_price",
    "boolean_price",
    "zero_price",
    "negative_price",
    "negative_volume",
    "high_less_than_low",
    "high_less_than_open",
    "low_greater_than_close",
    "not_a_dataframe",
    "empty_dataframe",
])
def test_adv_universe_loader_fail_closed_on_corruptions(corruption_type):
    """
    Adversarial Challenge: Verify that UniverseDataLoader.validate_dataset
    fails closed (raises TypeError or ValueError) on EVERY corruption type.
    """
    df = _create_synthetic_history_15m(50, 100.0)

    if corruption_type == "non_monotonic":
        # Invert first two rows
        df.index = [df.index[1], df.index[0]] + list(df.index[2:])
    elif corruption_type == "duplicates":
        df.index = [df.index[0]] + list(df.index[:-1])
    elif corruption_type == "naive_tz":
        df.index = df.index.tz_localize(None)
    elif corruption_type == "wrong_tz":
        df.index = df.index.tz_convert("US/Eastern")
    elif corruption_type == "missing_column":
        df = df.drop(columns=["volume"])
    elif corruption_type == "nan_price":
        df.iloc[10, df.columns.get_loc("close")] = np.nan
    elif corruption_type == "inf_price":
        df.iloc[10, df.columns.get_loc("high")] = np.inf
    elif corruption_type == "boolean_price":
        df["close"] = df["close"].astype(object)
        df.iloc[10, df.columns.get_loc("close")] = True
    elif corruption_type == "zero_price":
        df.iloc[10, df.columns.get_loc("low")] = 0.0
    elif corruption_type == "negative_price":
        df.iloc[10, df.columns.get_loc("open")] = -5.0
    elif corruption_type == "negative_volume":
        df.iloc[10, df.columns.get_loc("volume")] = -100.0
    elif corruption_type == "high_less_than_low":
        df.iloc[10, df.columns.get_loc("high")] = 50.0
        df.iloc[10, df.columns.get_loc("low")] = 60.0
    elif corruption_type == "high_less_than_open":
        df.iloc[10, df.columns.get_loc("high")] = 99.0
        df.iloc[10, df.columns.get_loc("open")] = 100.0
    elif corruption_type == "low_greater_than_close":
        df.iloc[10, df.columns.get_loc("low")] = 101.0
        df.iloc[10, df.columns.get_loc("close")] = 100.0
    elif corruption_type == "not_a_dataframe":
        df = [{"open": 100.0}]
    elif corruption_type == "empty_dataframe":
        df = pd.DataFrame()

    with pytest.raises((ValueError, TypeError)):
        UniverseDataLoader.validate_dataset(df, "BTCUSDT", "15m")


# ===========================================================================
# ADVERSARIAL SUITE 6: 4h Aggregation Geometry & Timestamp Alignment
# ===========================================================================

def test_adv_4h_resampling_geometry_invariants():
    """
    Adversarial Challenge: Verify that 15m to 4h aggregation mathematically preserves:
    - High >= max(Open, Close) and Low <= min(Open, Close)
    - Volume conservation: sum(15m volume in 4h) == 4h volume
    - High == max(all 15m highs), Low == min(all 15m lows)
    """
    df_15m = _create_synthetic_history_15m(16 * 10, 100.0)  # 10 full 4h bars
    df_4h = UniverseDataLoader._resample_15m_to_4h(df_15m)

    assert len(df_4h) == 10
    # Canonical 4h timestamps: hour % 4 == 0
    for ts in df_4h.index:
        assert ts.hour % 4 == 0, f"Timestamp {ts} not aligned to 4h canonical boundary"
        assert ts.minute == 0

    # Volume conservation
    vol_15m_total = df_15m["volume"].sum()
    vol_4h_total = df_4h["volume"].sum()
    assert math.isclose(vol_15m_total, vol_4h_total, rel_tol=1e-6)

    # Geometry check
    for i in range(10):
        chunk_15m = df_15m.iloc[i * 16 : (i + 1) * 16]
        bar_4h = df_4h.iloc[i]

        assert math.isclose(bar_4h["open"], chunk_15m["open"].iloc[0], rel_tol=1e-6)
        assert math.isclose(bar_4h["close"], chunk_15m["close"].iloc[-1], rel_tol=1e-6)
        assert math.isclose(bar_4h["high"], chunk_15m["high"].max(), rel_tol=1e-6)
        assert math.isclose(bar_4h["low"], chunk_15m["low"].min(), rel_tol=1e-6)
