"""
tests/test_synthesized_strategy.py
==================================
Comprehensive Unit Test Suite for SynthesizedStrategy (Milestone 1).

Covers:
  T1.  Initialization, inheritance from BaseStrategy, and config parsing.
  T2.  Macro 4h Regime Classification: TREND_BULL.
  T3.  Macro 4h Regime Classification: TREND_BEAR.
  T4.  Macro 4h Regime Classification: CHOP_RANGING (ADX < threshold or chop band).
  T5.  Macro Regime Causal Persistence across 15m bars.
  T6.  Micro 15m Trend Pullback Long execution.
  T7.  Micro 15m Trend Pullback Short execution.
  T8.  Micro 15m Breakout-Retest Long execution.
  T9.  Micro 15m SMC Liquidity Sweep Long execution in Chop regime.
  T10. Counter-trend setup suppression.
  T11. Funding Rate Sentiment Filter veto logic.
  T12. Conviction Arbiter risk scaling & circuit breaker veto.
  T13. Multi-Target Exit metadata & partial exit parameters.
  T14. Trailing stop breakeven move on partials_done == 1.
  T15. Trailing stop EMA runner move on partials_done >= 2 (tightening only).
  T16. Strict concurrency and active position gating.
  T17. Event time monotonicity & reversal fail-closed behavior.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.execution.order_models import (
    ExitReason,
    OrderDirection,
    OrderRequest,
    OrderType,
    Position,
)
from src.features.indicators import _ema_presma
from src.strategies.base_strategy import BaseStrategy
from src.strategies.synthesized import (
    ConvictionTier,
    MarketRegime,
    SetupState,
    SetupType,
    SynthesizedStrategy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_config() -> Dict[str, Any]:
    return {
        "strategy": {
            "name": "SynthesizedStrategy",
            "timeframe_signal": "4h",
            "timeframe_execution": "15m",
        },
        "data": {
            "futures_symbol": "BTCUSDT",
        },
        "synthesized": {
            "macro_regime": {
                "ema_fast": 50,
                "ema_slow": 200,
                "adx_period": 14,
                "adx_threshold": 20.0,
                "chop_band_pct": 0.015,
            },
            "pullback": {
                "ema_fast": 20,
                "ema_slow": 50,
                "rsi_period": 14,
                "rsi_bull_threshold": 50.0,
                "rsi_bear_threshold": 50.0,
                "max_setup_age_bars": 8,
                "swing_lookback_bars": 5,
            },
            "breakout": {
                "lookback_bars": 20,
                "volume_multiplier": 1.3,
                "retest_volume_max": 1.1,
                "max_setup_age_bars": 8,
                "level_tolerance_pct": 0.0015,
                "stop_buffer_pct": 0.002,
            },
            "smc": {
                "swing_n": 3,
                "min_bos_pct": 0.001,
                "displacement_min_atr": 0.4,
                "fvg_min_size_atr": 0.25,
                "ob_max_distance_atr": 1.2,
                "buffer_pct": 0.001,
                "max_setup_age_bars": 10,
            },
            "funding_filter": {
                "enabled": True,
                "max_long_funding_rate": 0.0005,
                "min_short_funding_rate": -0.0005,
            },
            "conviction_arbiter": {
                "mode": "heuristic",
                "risk_low": 0.01,
                "risk_normal": 0.02,
                "risk_high": 0.05,
            },
            "exit_logic": {
                "partial_exits": [
                    [1.5, 0.50],
                    [3.0, 0.25],
                ],
                "move_sl_to_be_after_tp1": True,
                "trailing_runner_ema": 20,
            },
        },
        "leverage": 2.0,
        "base_risk_percent": 0.02,
    }


def make_history_df(prices: List[float], vols: Optional[List[float]] = None) -> pd.DataFrame:
    """Creates a basic valid OHLCV DataFrame."""
    n = len(prices)
    ts = pd.date_range("2025-01-01 00:00:00", periods=n, freq="15min", tz="UTC")
    closes = np.array(prices, dtype=float)
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    highs = np.maximum(opens, closes) * 1.002
    lows = np.minimum(opens, closes) * 0.998
    if vols is None:
        volumes = np.full(n, 100.0)
    else:
        volumes = np.array(vols, dtype=float)

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }, index=ts)


# ---------------------------------------------------------------------------
# Unit Tests (T1 - T17)
# ---------------------------------------------------------------------------

def test_synthesized_strategy_initialization(default_config):
    """T1: Verifies inheritance from BaseStrategy, parameter defaults, and idle setup state."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    assert isinstance(strategy, BaseStrategy)
    assert strategy.symbol == "BTCUSDT"
    assert strategy.current_regime == MarketRegime.CHOP_RANGING
    assert strategy.setup.phase == "IDLE"
    assert strategy.setup.setup_type is None
    assert strategy.leverage == 2.0
    assert strategy.partial_exits == [[1.5, 0.50], [3.0, 0.25]]
    assert strategy.risk_tier_map[ConvictionTier.LOW] == 0.01
    assert strategy.risk_tier_map[ConvictionTier.NORMAL] == 0.02
    assert strategy.risk_tier_map[ConvictionTier.HIGH] == 0.05


def test_macro_regime_classification_bull(default_config):
    """T2: 4h close > EMA200, EMA50 > EMA200, ADX >= 20.0 -> TREND_BULL."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    n = 250
    # Create trending up series
    base_price = np.linspace(50000, 70000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    df_4h = pd.DataFrame({
        "open": base_price - 100,
        "high": base_price + 300,
        "low": base_price - 200,
        "close": base_price,
        "volume": 500.0,
    }, index=ts)

    candle_4h = {"close": 70000.0, "adx": 28.0}
    regime = strategy.classify_macro_regime(candle_4h, df_4h)
    assert regime == MarketRegime.TREND_BULL


def test_macro_regime_classification_bear(default_config):
    """T3: 4h close < EMA200, EMA50 < EMA200, ADX >= 20.0 -> TREND_BEAR."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    n = 250
    # Create trending down series
    base_price = np.linspace(70000, 50000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    df_4h = pd.DataFrame({
        "open": base_price + 100,
        "high": base_price + 200,
        "low": base_price - 300,
        "close": base_price,
        "volume": 500.0,
    }, index=ts)

    candle_4h = {"close": 50000.0, "adx": 30.0}
    regime = strategy.classify_macro_regime(candle_4h, df_4h)
    assert regime == MarketRegime.TREND_BEAR


def test_macro_regime_classification_chop(default_config):
    """T4: ADX < 20.0 or price within 1.5% chop band of EMA200 -> CHOP_RANGING."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    n = 250
    # Flat oscillating series
    base_price = 60000.0 + 100.0 * np.sin(np.linspace(0, 10 * np.pi, n))
    ts = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    df_4h = pd.DataFrame({
        "open": base_price,
        "high": base_price + 50,
        "low": base_price - 50,
        "close": base_price,
        "volume": 500.0,
    }, index=ts)

    # Case A: Low ADX (14.0 < 20.0)
    candle_low_adx = {"close": 60000.0, "adx": 14.0}
    assert strategy.classify_macro_regime(candle_low_adx, df_4h) == MarketRegime.CHOP_RANGING

    # Case B: Close right on EMA200 (within 1.5% band) even with ADX = 25.0
    candle_at_ema = {"close": 60000.0, "adx": 25.0}
    assert strategy.classify_macro_regime(candle_at_ema, df_4h) == MarketRegime.CHOP_RANGING


def test_macro_regime_causal_persistence(default_config):
    """T5: Macro regime set by 4h bar persists across intervening 15m bars."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    n = 250
    base_price = np.linspace(50000, 70000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    df_4h = pd.DataFrame({
        "open": base_price - 50,
        "high": base_price + 100,
        "low": base_price - 100,
        "close": base_price,
        "volume": 500.0,
    }, index=ts)

    candle_4h = {"close": 70000.0, "adx": 26.0, "timestamp": ts[-1]}
    history_15m = make_history_df([69000.0] * 60)

    # Initial 4h bar sets regime to TREND_BULL
    candle_15m_1 = {"close": 69000.0, "timestamp": pd.to_datetime("2025-01-02 04:00:00", utc=True)}
    strategy.on_candle_close(candle_15m_1, history_15m, candle_4h, df_4h)
    assert strategy.current_regime == MarketRegime.TREND_BULL

    # Next 15m bars without 4h update maintain TREND_BULL
    candle_15m_2 = {"close": 69050.0, "timestamp": pd.to_datetime("2025-01-02 04:15:00", utc=True)}
    strategy.on_candle_close(candle_15m_2, history_15m)
    assert strategy.current_regime == MarketRegime.TREND_BULL

    candle_15m_3 = {"close": 69100.0, "timestamp": pd.to_datetime("2025-01-02 04:30:00", utc=True)}
    strategy.on_candle_close(candle_15m_3, history_15m)
    assert strategy.current_regime == MarketRegime.TREND_BULL


def test_micro_trend_pullback_long_trigger(default_config):
    """T6: In TREND_BULL, price dips into EMA 20/50 band and regains EMA 20 with RSI > 50 -> OrderRequest(LONG)."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")
    strategy.current_regime = MarketRegime.TREND_BULL

    # Construct 15m price sequence: uptrend, then dip to EMA20/50, then regain EMA20
    prices = [60000.0 + i * 20.0 for i in range(80)]
    prices[-3] = prices[-4] - 150.0
    prices[-2] = prices[-4] - 250.0
    prices[-1] = prices[-4] + 20.0
    history = make_history_df(prices)
    ema20 = float(_ema_presma(history["close"], 20).iloc[-1])

    current_candle = {
        "open": prices[-2],
        "high": prices[-1] + 20.0,
        "low": ema20 - 20.0,
        "close": prices[-1],
        "volume": 200.0,
        "timestamp": history.index[-1],
    }

    req = strategy.on_candle_close(current_candle, history)
    assert req is not None
    assert req.direction == OrderDirection.LONG
    assert req.signal_price == current_candle["close"]
    assert req.stop_loss_price < req.signal_price
    assert req.metadata["strategy"] == "SYNTHESIZED"


def test_micro_trend_pullback_short_trigger(default_config):
    """T7: In TREND_BEAR, price bounces into EMA 20/50 band and rejects below EMA 20 with RSI < 50 -> OrderRequest(SHORT)."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")
    strategy.current_regime = MarketRegime.TREND_BEAR

    # Construct 15m downtrend sequence
    prices = [60000.0 - i * 20.0 for i in range(80)]
    prices[-3] = prices[-4] + 150.0
    prices[-2] = prices[-4] + 250.0
    prices[-1] = prices[-4] - 20.0
    history = make_history_df(prices)
    ema20 = float(_ema_presma(history["close"], 20).iloc[-1])

    current_candle = {
        "open": prices[-2],
        "high": ema20 + 20.0,
        "low": prices[-1] - 20.0,
        "close": prices[-1],
        "volume": 200.0,
        "timestamp": history.index[-1],
    }

    req = strategy.on_candle_close(current_candle, history)
    assert req is not None
    assert req.direction == OrderDirection.SHORT
    assert req.signal_price == current_candle["close"]
    assert req.stop_loss_price > req.signal_price


def test_breakout_retest_long_trigger(default_config):
    """T8: In TREND_BULL, 20-bar Donchian breakout on volume >= 1.3x followed by low-vol retest -> OrderRequest(LONG)."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")
    strategy.current_regime = MarketRegime.TREND_BULL

    # 30 bars range bound between 59000 and 60000
    prices = [59500.0 + 200.0 * np.sin(i) for i in range(30)]
    vols = [100.0] * 30
    history = make_history_df(prices, vols)

    # Bar 1: Breakout above prior high (60000) with volume surge (250.0 >= 100 * 1.3)
    bo_close = 60500.0
    candle_bo = {
        "open": 59800.0,
        "high": 60600.0,
        "low": 59700.0,
        "close": bo_close,
        "volume": 250.0,
        "timestamp": pd.to_datetime("2025-01-01 12:00:00", utc=True),
    }
    history_bo = pd.concat([history, pd.DataFrame([{
        "open": 59800.0, "high": 60600.0, "low": 59700.0, "close": bo_close, "volume": 250.0
    }], index=[candle_bo["timestamp"]])])

    req_bo = strategy.on_candle_close(candle_bo, history_bo)
    # Breakout is armed, no entry yet
    assert req_bo is None
    assert strategy.setup.setup_type == SetupType.BREAKOUT
    assert strategy.setup.direction == OrderDirection.LONG

    # Bar 2: Retest of breakout level with low volume (80.0 <= 100 * 1.1)
    retest_close = 60100.0
    candle_retest = {
        "open": 60400.0,
        "high": 60450.0,
        "low": 59800.0,  # Dips to retest level
        "close": retest_close,
        "volume": 80.0,
        "timestamp": pd.to_datetime("2025-01-01 12:15:00", utc=True),
    }
    history_retest = pd.concat([history_bo, pd.DataFrame([{
        "open": 60400.0, "high": 60450.0, "low": 59800.0, "close": retest_close, "volume": 80.0
    }], index=[candle_retest["timestamp"]])])

    req_entry = strategy.on_candle_close(candle_retest, history_retest)
    assert req_entry is not None
    assert req_entry.direction == OrderDirection.LONG
    assert req_entry.signal_price == retest_close
    assert req_entry.stop_loss_price < retest_close
    assert strategy.setup.setup_type is None  # Reset after entry


def test_smc_liquidity_sweep_chop_trigger(default_config):
    """T9: In CHOP_RANGING, bullish sweep of swing low -> WAIT_BOS -> WAIT_FVG -> OrderRequest(LONG)."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")
    strategy.current_regime = MarketRegime.CHOP_RANGING

    # Step 1: Arm via sweep detection
    strategy.setup.setup_type = SetupType.SMC_SWEEP
    strategy.setup.direction = OrderDirection.LONG
    strategy.setup.phase = "WAIT_BOS"
    strategy.setup.sweep_extreme = 58000.0
    strategy.setup.age = 1

    # Mock SMC feature tracker step
    strategy.smc_tracker.step = MagicMock(return_value={
        "bos_bullish": True,
        "fvg_direction": "BULLISH",
        "fvg_high": 58600.0,
        "fvg_low": 58300.0,
        "fvg_mid": 58450.0,
        "order_block_low": 58050.0,
        "order_block_high": 58200.0,
    })

    prices = [58200.0] * 20
    history = make_history_df(prices)
    candle = {
        "open": 58200.0,
        "high": 58700.0,
        "low": 58150.0,
        "close": 58650.0,
        "volume": 150.0,
        "timestamp": history.index[-1],
    }

    req = strategy.on_candle_close(candle, history)
    assert req is not None
    assert req.direction == OrderDirection.LONG
    assert req.signal_price == 58650.0
    assert req.stop_loss_price < 58650.0
    assert req.order_type == OrderType.MARKET_ENTRY


def test_counter_trend_suppression(default_config):
    """T10: In TREND_BULL, counter-trend pullbacks and breakouts are suppressed."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")
    strategy.current_regime = MarketRegime.TREND_BULL

    # Bearish pullback candidate should return None in TREND_BULL
    history = make_history_df([60000.0 - i * 10 for i in range(80)])
    current_candle = {
        "open": 59200.0,
        "high": 59300.0,
        "low": 59100.0,
        "close": 59150.0,
        "volume": 100.0,
        "timestamp": history.index[-1],
    }
    candidate = strategy._evaluate_pullback_setup(current_candle, history, strategy.current_regime)
    assert candidate is None


def test_funding_rate_sentiment_filter_veto(default_config):
    """T11: High funding rate (+0.08% > +0.05%) vetoes LONG; low funding (-0.08% < -0.05%) vetoes SHORT."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    # Long with high positive funding -> VETO
    candle_crowded_long = {"funding_rate": 0.0008}
    assert strategy._apply_funding_filter(OrderDirection.LONG, candle_crowded_long) is False

    # Short with deeply negative funding -> VETO
    candle_crowded_short = {"funding_rate": -0.0008}
    assert strategy._apply_funding_filter(OrderDirection.SHORT, candle_crowded_short) is False

    # Normal funding -> PASS
    candle_normal = {"funding_rate": 0.0001}
    assert strategy._apply_funding_filter(OrderDirection.LONG, candle_normal) is True
    assert strategy._apply_funding_filter(OrderDirection.SHORT, candle_normal) is True


def test_conviction_arbiter_risk_scaling(default_config):
    """T12: ConvictionTier maps to base_risk_percent (LOW 1%, NORMAL 2%, HIGH 5%); circuit breaker locks veto."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    history = make_history_df([60000.0] * 30)
    candle = {"close": 60000.0}
    setup_long = {"direction": OrderDirection.LONG, "setup_type": SetupType.PULLBACK}

    # Case A: Low conviction (counter trend or low score)
    tier, risk = strategy._evaluate_conviction(setup_long, candle, history, MarketRegime.CHOP_RANGING, None)
    assert tier == ConvictionTier.LOW
    assert risk == 0.01

    # Case B: High conviction (Trend Bull + Breakout)
    setup_bo = {"direction": OrderDirection.LONG, "setup_type": SetupType.BREAKOUT}
    tier_hi, risk_hi = strategy._evaluate_conviction(setup_bo, candle, history, MarketRegime.TREND_BULL, None)
    assert tier_hi == ConvictionTier.HIGH
    assert risk_hi == 0.05

    # Case C: Circuit breaker locked -> VETO
    class MockCircuitBreaker:
        is_locked = True
        risk_multiplier = 0.0

    class MockBroker:
        circuit_breaker = MockCircuitBreaker()

    tier_cb, risk_cb = strategy._evaluate_conviction(setup_bo, candle, history, MarketRegime.TREND_BULL, MockBroker())
    assert tier_cb == ConvictionTier.VETO
    assert risk_cb == 0.0


def test_multi_target_partial_exits_metadata(default_config):
    """T13: Returned OrderRequest contains partial_exits = [[1.5, 0.50], [3.0, 0.25]] and valid risk."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")
    strategy.current_regime = MarketRegime.TREND_BULL

    prices = [60000.0 + i * 20.0 for i in range(80)]
    prices[-3] = prices[-4] - 150.0
    prices[-2] = prices[-4] - 250.0
    prices[-1] = prices[-4] + 20.0
    history = make_history_df(prices)
    ema20 = float(_ema_presma(history["close"], 20).iloc[-1])

    candle = {
        "open": prices[-2],
        "high": prices[-1] + 20.0,
        "low": ema20 - 20.0,
        "close": prices[-1],
        "volume": 200.0,
        "timestamp": history.index[-1],
    }

    req = strategy.on_candle_close(candle, history)
    assert req is not None
    assert req.partial_exits == [[1.5, 0.50], [3.0, 0.25]]
    assert req.leverage == 2.0
    assert req.base_risk_percent in (0.01, 0.02, 0.05)


def test_update_trailing_stop_breakeven_move(default_config):
    """T14: Position with partials_done == 1 moves stop loss to Breakeven (entry_price)."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    # Mock Broker with active position
    mock_pos = Position(
        position_id="POS_1",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        entry_price=60000.0,
        quantity=0.1,
        initial_margin=3000.0,
        isolated_collateral=3000.0,
        leverage=2.0,
        stop_loss_price=59000.0,
        liquidation_price=30000.0,
        opened_at=datetime.now(timezone.utc),
        metadata={"partials_done": 1},
    )

    mock_broker = MagicMock()
    mock_broker.positions = {"BTCUSDT": mock_pos}
    mock_broker.update_stop_loss = MagicMock()

    candle = {"close": 61500.0}
    strategy.update_trailing_stop(candle, mock_broker)

    # Should call broker.update_stop_loss("BTCUSDT", 60000.0)
    mock_broker.update_stop_loss.assert_called_once_with("BTCUSDT", 60000.0)


def test_update_trailing_stop_runner_ema(default_config):
    """T15: Position with partials_done == 2 trails runner stop loss along 15m EMA20 (tightening-only)."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")

    mock_pos = Position(
        position_id="POS_2",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        entry_price=60000.0,
        quantity=0.025,
        initial_margin=750.0,
        isolated_collateral=750.0,
        leverage=2.0,
        stop_loss_price=60000.0,  # Already at BE
        liquidation_price=30000.0,
        opened_at=datetime.now(timezone.utc),
        metadata={"partials_done": 2},
    )

    mock_broker = MagicMock()
    mock_broker.positions = {"BTCUSDT": mock_pos}
    mock_broker.update_stop_loss = MagicMock()

    # Case A: EMA20 is 61000.0 (> 60000.0, < 62000.0 mark price) -> Updates SL
    candle_a = {"close": 62000.0, "ema_20": 61000.0}
    strategy.update_trailing_stop(candle_a, mock_broker)
    mock_broker.update_stop_loss.assert_called_once_with("BTCUSDT", 61000.0)

    # Case B: EMA20 is 59500.0 (< current SL 60000.0) -> Does NOT loosen stop
    mock_broker.reset_mock()
    candle_b = {"close": 62000.0, "ema_20": 59500.0}
    strategy.update_trailing_stop(candle_b, mock_broker)
    mock_broker.update_stop_loss.assert_not_called()


def test_concurrency_and_active_position_gate(default_config):
    """T16: If broker already holds active position or pending order for symbol, on_candle_close returns None."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")
    strategy.current_regime = MarketRegime.TREND_BULL

    prices = [60000.0 + i * 20.0 for i in range(80)]
    prices[-3] = prices[-4] - 80.0
    prices[-2] = prices[-3] - 20.0
    prices[-1] = prices[-4] + 10.0
    history = make_history_df(prices)
    candle = {
        "open": prices[-2],
        "high": prices[-1] + 10.0,
        "low": prices[-2] - 10.0,
        "close": prices[-1],
        "volume": 200.0,
        "timestamp": history.index[-1],
    }

    # Case 1: Active position exists
    broker_with_pos = MagicMock()
    broker_with_pos.positions = {"BTCUSDT": MagicMock()}
    broker_with_pos.pending_orders = []

    res1 = strategy.on_candle_close(candle, history, broker_state=broker_with_pos)
    assert res1 is None

    # Case 2: Pending order exists
    pending_req = MagicMock()
    pending_req.symbol = "BTCUSDT"
    broker_with_pending = MagicMock()
    broker_with_pending.positions = {}
    broker_with_pending.pending_orders = [pending_req]

    candle_next = {**candle, "timestamp": candle["timestamp"] + pd.Timedelta(minutes=15)}
    res2 = strategy.on_candle_close(candle_next, history, broker_state=broker_with_pending)
    assert res2 is None


def test_time_reversal_raises_value_error(default_config):
    """T17: Time reversal in incoming closed candles raises ValueError fail-closed."""
    strategy = SynthesizedStrategy(default_config, symbol="BTCUSDT")
    history = make_history_df([60000.0] * 30)

    t1 = pd.to_datetime("2025-01-01 12:00:00", utc=True)
    candle_1 = {"close": 60000.0, "timestamp": t1}
    strategy.on_candle_close(candle_1, history)

    # Time reversal: T < previous event time
    t_past = pd.to_datetime("2025-01-01 11:45:00", utc=True)
    candle_past = {"close": 59900.0, "timestamp": t_past}

    with pytest.raises(ValueError, match="Event time reversal"):
        strategy.on_candle_close(candle_past, history)
