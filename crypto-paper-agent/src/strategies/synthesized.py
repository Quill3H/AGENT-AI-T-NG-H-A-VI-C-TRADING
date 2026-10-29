"""
src/strategies/synthesized.py
=============================
Synthesized Multi-Regime Quantitative Trading Strategy (Milestone 1).

Architecture:
  1. 4h Macro Regime Classification:
     - TREND_BULL: 4h close > EMA200, EMA50 > EMA200, ADX >= threshold
     - TREND_BEAR: 4h close < EMA200, EMA50 < EMA200, ADX >= threshold
     - CHOP_RANGING: ADX < threshold OR price within chop band around EMA200
  2. 15m Micro-Setup Execution:
     - Micro-Trend Pullback Continuation (EMA 20/50 band retest + RSI confirmation)
     - Dynamic Breakout-Retest (20-bar Donchian channel breakout with low-volume retest)
     - SMC Liquidity Sweeps (Swing pivot sweeps + MSS/BOS + FVG entry)
  3. Funding Rate Sentiment Filter:
     - Vetoes Long entries during crowded positive funding (+0.05% per 8h)
     - Vetoes Short entries during crowded negative funding (-0.05% per 8h)
  4. PPO / Heuristic Conviction Arbiter:
     - Maps setup quality & market conditions to ConvictionTier (VETO, LOW 1%, NORMAL 2%, HIGH 5%)
  5. Multi-Target Exit & Trailing Runner:
     - 1.5R: 50% partial exit, immediately moving stop loss to Breakeven
     - 3.0R: 25% partial exit
     - Runner: remaining 25% balance trailed along 15m EMA20

Strictly causal, zero lookahead bias, paper-only execution.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from loguru import logger

from src.execution.order_models import (
    ExitReason,
    OrderDirection,
    OrderRequest,
    OrderType,
    Position,
    _ensure_utc,
)
from src.features.indicators import (
    calculate_atr,
    calculate_ema,
    calculate_rsi,
    _ema_presma,
)
from src.features.smc_features import SMCFeatureTracker
from src.strategies.base_strategy import BaseStrategy


# ---------------------------------------------------------------------------
# Enums & Data Containers
# ---------------------------------------------------------------------------

class MarketRegime(str, Enum):
    TREND_BULL = "TREND_BULL"
    TREND_BEAR = "TREND_BEAR"
    CHOP_RANGING = "CHOP_RANGING"


class SetupType(str, Enum):
    PULLBACK = "PULLBACK"
    BREAKOUT = "BREAKOUT"
    SMC_SWEEP = "SMC_SWEEP"


class ConvictionTier(str, Enum):
    VETO = "veto"          # 0: Vetoed (No trade)
    LOW = "low"            # 1: 1% risk
    NORMAL = "normal"      # 2: 2% risk
    HIGH = "high"          # 3: 5% risk


@dataclass
class SetupState:
    setup_type: Optional[SetupType] = None
    direction: Optional[OrderDirection] = None
    level: Optional[float] = None
    sweep_extreme: Optional[float] = None
    phase: str = "IDLE"  # "IDLE", "ARMED", "WAIT_BOS", "WAIT_FVG"
    age: int = 0
    trigger_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def reset(self) -> None:
        self.setup_type = None
        self.direction = None
        self.level = None
        self.sweep_extreme = None
        self.phase = "IDLE"
        self.age = 0
        self.trigger_time = None
        self.metadata.clear()


# ---------------------------------------------------------------------------
# SynthesizedStrategy Class
# ---------------------------------------------------------------------------

class SynthesizedStrategy(BaseStrategy):
    """
    Synthesized Multi-Regime Trading Strategy inheriting from BaseStrategy.
    """

    def __init__(self, config: Dict[str, Any], symbol: str = "BTCUSDT"):
        super().__init__(config, symbol)
        self.symbol = str(symbol).strip().upper()

        # Configuration sections
        synth_cfg = config.get("synthesized", {})
        macro_cfg = synth_cfg.get("macro_regime", {})
        pullback_cfg = synth_cfg.get("pullback", {})
        breakout_cfg = synth_cfg.get("breakout", {})
        smc_cfg = synth_cfg.get("smc", {})
        funding_cfg = synth_cfg.get("funding_filter", {})
        arbiter_cfg = synth_cfg.get("conviction_arbiter", {})
        exit_cfg = synth_cfg.get("exit_logic", {})
        risk_cfg = config.get("risk", {})

        # Risk & Stop-Loss Floor Parameters
        self.min_stop_distance_pct = float(risk_cfg.get("min_stop_distance_pct", 0.008))
        self.atr_stop_mult = float(risk_cfg.get("atr_stop_multiplier", 1.2))
        mr_cfg = synth_cfg.get("mean_reversion", {})
        self.mean_reversion_enabled = bool(mr_cfg.get("enabled", False))

        # 1. Macro Regime Parameters (4h)
        self.macro_ema_fast = int(macro_cfg.get("ema_fast", 50))
        self.macro_ema_slow = int(macro_cfg.get("ema_slow", 200))
        self.macro_adx_period = int(macro_cfg.get("adx_period", 14))
        self.macro_adx_threshold = float(macro_cfg.get("adx_threshold", 20.0))
        self.macro_chop_band_pct = float(macro_cfg.get("chop_band_pct", 0.015))  # 1.5%

        # 2. Micro 15m Pullback Parameters
        self.pb_ema_fast = int(pullback_cfg.get("ema_fast", 20))
        self.pb_ema_slow = int(pullback_cfg.get("ema_slow", 50))
        self.pb_rsi_period = int(pullback_cfg.get("rsi_period", 14))
        self.pb_rsi_bull = float(pullback_cfg.get("rsi_bull_threshold", 52.0))
        self.pb_rsi_bear = float(pullback_cfg.get("rsi_bear_threshold", 48.0))
        self.pb_max_age = int(pullback_cfg.get("max_setup_age_bars", 8))
        self.pb_swing_bars = int(pullback_cfg.get("swing_lookback_bars", 5))

        # 3. Micro 15m Breakout Parameters
        self.bo_lookback = int(breakout_cfg.get("lookback_bars", 24))
        self.bo_vol_multiplier = float(breakout_cfg.get("volume_multiplier", 1.25))
        self.bo_retest_vol_max = float(breakout_cfg.get("retest_volume_max", 1.15))
        self.bo_max_age = int(breakout_cfg.get("max_setup_age_bars", 12))
        self.bo_tolerance_pct = float(breakout_cfg.get("level_tolerance_pct", 0.0025))
        self.bo_buffer_pct = float(breakout_cfg.get("stop_buffer_pct", 0.004))

        # 4. Micro 15m SMC Parameters
        self.smc_swing_n = int(smc_cfg.get("swing_n", 3))
        self.smc_min_bos_pct = float(smc_cfg.get("min_bos_pct", 0.001))
        self.smc_displacement_atr = float(smc_cfg.get("displacement_min_atr", 0.32))
        self.smc_fvg_min_atr = float(smc_cfg.get("fvg_min_size_atr", 0.20))
        self.smc_ob_max_distance_atr = float(smc_cfg.get("ob_max_distance_atr", 1.5))
        self.smc_buffer_pct = float(smc_cfg.get("buffer_pct", 0.002))
        self.smc_max_age = int(smc_cfg.get("max_setup_age_bars", 14))
        self.smc_tracker = SMCFeatureTracker(
            swing_n=self.smc_swing_n,
            min_bos_pct=self.smc_min_bos_pct,
        )

        # 5. Funding Filter Parameters
        self.funding_filter_enabled = bool(funding_cfg.get("enabled", True))
        self.funding_max_long = float(funding_cfg.get("max_long_funding_rate", 0.0005))   # +0.05% per 8h
        self.funding_min_short = float(funding_cfg.get("min_short_funding_rate", -0.0005)) # -0.05% per 8h

        # 6. Conviction Arbiter Parameters
        self.arbiter_mode = str(arbiter_cfg.get("mode", "heuristic")).lower()  # "heuristic" or "ppo"
        self.risk_tier_map = {
            ConvictionTier.VETO: 0.0,
            ConvictionTier.LOW: float(arbiter_cfg.get("risk_low", 0.008)),
            ConvictionTier.NORMAL: float(arbiter_cfg.get("risk_normal", 0.012)),
            ConvictionTier.HIGH: float(arbiter_cfg.get("risk_high", 0.015)),
        }
        self.leverage = float(config.get("leverage", 2.0))
        self.base_risk_percent = float(config.get("base_risk_percent", 0.012))

        # 7. Multi-Target Exit Parameters
        self.partial_exits = [
            [float(r), float(f)]
            for r, f in exit_cfg.get("partial_exits", [[1.5, 0.50], [3.0, 0.25]])
        ]
        self.be_after_partial_1 = bool(exit_cfg.get("move_sl_to_be_after_tp1", True))
        self.trailing_ema_period = int(exit_cfg.get("trailing_runner_ema", 20))

        # Internal State Management
        self.current_regime: MarketRegime = MarketRegime.CHOP_RANGING
        self.last_4h_close_time: Optional[datetime] = None
        self.setup: SetupState = SetupState()
        self.setup_count: int = 0
        self.candidate_count: int = 0
        self._last_event_time: Optional[datetime] = None

    # -----------------------------------------------------------------------
    # Core Mathematical Indicators
    # -----------------------------------------------------------------------

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculates standard Wilder Average Directional Index (ADX).
        Causal, zero lookahead bias, pure pandas/numpy with TA-Lib matching smoothing.
        """
        if len(df) < period * 2:
            return pd.Series(np.nan, index=df.index)

        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)
        prev_high = high.shift(1)
        prev_low = low.shift(1)

        tr0 = high - low
        tr1 = (high - prev_close).abs()
        tr2 = (low - prev_close).abs()
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)

        up_move = high - prev_high
        down_move = prev_low - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # Wilder's Smoothing alpha = 1 / period
        alpha = 1.0 / period
        atr = tr.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
        smoothed_plus_dm = pd.Series(plus_dm, index=df.index).ewm(
            alpha=alpha, adjust=False, min_periods=period
        ).mean()
        smoothed_minus_dm = pd.Series(minus_dm, index=df.index).ewm(
            alpha=alpha, adjust=False, min_periods=period
        ).mean()

        plus_di = 100.0 * (smoothed_plus_dm / atr.replace(0.0, np.nan))
        minus_di = 100.0 * (smoothed_minus_dm / atr.replace(0.0, np.nan))

        dx_denom = plus_di + minus_di
        dx = 100.0 * ((plus_di - minus_di).abs() / dx_denom.replace(0.0, np.nan))
        adx = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
        return adx.fillna(0.0)

    # -----------------------------------------------------------------------
    # 4h Macro Regime Classifier
    # -----------------------------------------------------------------------

    def classify_macro_regime(
        self,
        candle_4h: Dict[str, Any],
        history_4h: pd.DataFrame,
    ) -> MarketRegime:
        """
        Classifies macro market regime on 4h closed bars:
        - TREND_BULL: close > EMA200, EMA50 > EMA200, ADX >= threshold
        - TREND_BEAR: close < EMA200, EMA50 < EMA200, ADX >= threshold
        - CHOP_RANGING: ADX < threshold OR price within chop band around EMA200
        """
        if history_4h is None or len(history_4h) < max(self.macro_ema_slow, self.macro_adx_period * 2):
            return MarketRegime.CHOP_RANGING

        close_4h = float(candle_4h.get("close", history_4h.iloc[-1]["close"]))

        # Extract or compute EMAs
        ema_fast_col = f"ema_{self.macro_ema_fast}"
        ema_slow_col = f"ema_{self.macro_ema_slow}"

        if ema_fast_col in history_4h.columns and not pd.isna(history_4h[ema_fast_col].iloc[-1]):
            ema50 = float(history_4h[ema_fast_col].iloc[-1])
        else:
            ema50 = float(_ema_presma(history_4h["close"], self.macro_ema_fast).iloc[-1])

        if ema_slow_col in history_4h.columns and not pd.isna(history_4h[ema_slow_col].iloc[-1]):
            ema200 = float(history_4h[ema_slow_col].iloc[-1])
        else:
            ema200 = float(_ema_presma(history_4h["close"], self.macro_ema_slow).iloc[-1])

        # ADX computation
        if "adx" in candle_4h and not pd.isna(candle_4h["adx"]):
            adx_val = float(candle_4h["adx"])
        else:
            adx_series = self.calculate_adx(history_4h, period=self.macro_adx_period)
            adx_val = float(adx_series.iloc[-1]) if not adx_series.empty else 0.0

        # Chop band check: within +/- chop_band_pct of EMA200
        dist_to_ema200 = abs(close_4h - ema200) / ema200
        is_in_chop_band = dist_to_ema200 < self.macro_chop_band_pct

        if is_in_chop_band or adx_val < self.macro_adx_threshold:
            return MarketRegime.CHOP_RANGING

        if close_4h > ema200 and ema50 > ema200:
            return MarketRegime.TREND_BULL
        elif close_4h < ema200 and ema50 < ema200:
            return MarketRegime.TREND_BEAR
        else:
            return MarketRegime.CHOP_RANGING

    # -----------------------------------------------------------------------
    # Micro-Setup Engines (15m Timeframe)
    # -----------------------------------------------------------------------

    def _evaluate_pullback_setup(
        self,
        current_15m: Dict[str, Any],
        history_15m: pd.DataFrame,
        regime: MarketRegime,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates 15m Micro-Trend Pullback against EMA20/EMA50 band.
        Active in TREND_BULL (Longs) and TREND_BEAR (Shorts).
        """
        if regime == MarketRegime.CHOP_RANGING:
            return None
        if len(history_15m) < max(self.pb_ema_slow, self.pb_swing_bars) + 2:
            return None

        row = history_15m.iloc[-1]
        c = float(current_15m.get("close", row["close"]))
        h = float(current_15m.get("high", row["high"]))
        l = float(current_15m.get("low", row["low"]))

        ema_f_key = f"ema_{self.pb_ema_fast}"
        ema_s_key = f"ema_{self.pb_ema_slow}"
        rsi_key = f"rsi_{self.pb_rsi_period}"
        if ema_f_key in current_15m and ema_s_key in current_15m and rsi_key in current_15m:
            ema20 = float(current_15m[ema_f_key])
            ema50 = float(current_15m[ema_s_key])
            rsi = float(current_15m[rsi_key])
        else:
            close_series = history_15m["close"]
            ema20 = float(_ema_presma(close_series, self.pb_ema_fast).iloc[-1])
            ema50 = float(_ema_presma(close_series, self.pb_ema_slow).iloc[-1])

            # RSI 14
            delta = close_series.diff()
            gain = delta.clip(lower=0.0).ewm(alpha=1.0 / self.pb_rsi_period, adjust=False).mean()
            loss = (-delta).clip(lower=0.0).ewm(alpha=1.0 / self.pb_rsi_period, adjust=False).mean()
            rs = gain / loss.replace(0.0, np.nan)
            rsi = float((100.0 - (100.0 / (1.0 + rs))).iloc[-1])

        if "atr_14" in current_15m and pd.notna(current_15m["atr_14"]):
            atr = float(current_15m["atr_14"])
        else:
            atr = float((history_15m["high"] - history_15m["low"]).iloc[-14:].mean())
        if atr <= 0.0 or not math.isfinite(atr):
            atr = c * 0.005

        min_sl_dist = max(self.atr_stop_mult * atr, self.min_stop_distance_pct * c)

        if regime == MarketRegime.TREND_BULL:
            if not (c > ema50 and ema20 > ema50):
                return None
            band_touch = (l <= ema20) and (h >= ema50)
            close_confirmed = (c >= ema20)
            rsi_confirmed = rsi > self.pb_rsi_bull
            if band_touch and close_confirmed and rsi_confirmed:
                swing_low = float(history_15m["low"].iloc[-self.pb_swing_bars:].min())
                delta_structure = c - min(l, swing_low)
                sl_dist = max(delta_structure, min_sl_dist)
                stop_loss = c - sl_dist
                if stop_loss < c:
                    return {
                        "setup_type": SetupType.PULLBACK,
                        "direction": OrderDirection.LONG,
                        "signal_price": c,
                        "stop_loss_price": stop_loss,
                        "metadata": {
                            "strategy": "SYNTHESIZED_PULLBACK",
                            "ema20": ema20,
                            "ema50": ema50,
                            "rsi": rsi,
                            "regime": regime.value,
                        },
                    }

        elif regime == MarketRegime.TREND_BEAR:
            if not (c < ema50 and ema20 < ema50):
                return None
            band_touch = (h >= ema20) and (l <= ema50)
            close_confirmed = (c <= ema20)
            rsi_confirmed = rsi < self.pb_rsi_bear
            if band_touch and close_confirmed and rsi_confirmed:
                swing_high = float(history_15m["high"].iloc[-self.pb_swing_bars:].max())
                delta_structure = max(h, swing_high) - c
                sl_dist = max(delta_structure, min_sl_dist)
                stop_loss = c + sl_dist
                if stop_loss > c:
                    return {
                        "setup_type": SetupType.PULLBACK,
                        "direction": OrderDirection.SHORT,
                        "signal_price": c,
                        "stop_loss_price": stop_loss,
                        "metadata": {
                            "strategy": "SYNTHESIZED_PULLBACK",
                            "ema20": ema20,
                            "ema50": ema50,
                            "rsi": rsi,
                            "regime": regime.value,
                        },
                    }
        return None

    def _evaluate_breakout_setup(
        self,
        current_15m: Dict[str, Any],
        history_15m: pd.DataFrame,
        regime: MarketRegime,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates 15m Breakout of prior 20-bar Donchian channel with low-volume retest.
        Active in TREND_BULL (Longs) and TREND_BEAR (Shorts).
        """
        if regime == MarketRegime.CHOP_RANGING:
            return None
        if len(history_15m) < self.bo_lookback + 2:
            return None

        current = history_15m.iloc[-1]
        prior = history_15m.iloc[-(self.bo_lookback + 1):-1]
        prior_high = float(prior["high"].max())
        prior_low = float(prior["low"].min())
        avg_volume = float(prior["volume"].mean())

        c = float(current["close"])
        h = float(current["high"])
        l = float(current["low"])
        vol = float(current["volume"])

        if "atr_14" in current_15m and pd.notna(current_15m["atr_14"]):
            atr = float(current_15m["atr_14"])
        else:
            atr = float((history_15m["high"] - history_15m["low"]).iloc[-14:].mean())
        if atr <= 0.0 or not math.isfinite(atr):
            atr = c * 0.005
        min_sl_dist = max(self.atr_stop_mult * atr, self.min_stop_distance_pct * c)

        # Check existing armed breakout setup
        if self.setup.setup_type == SetupType.BREAKOUT and self.setup.direction is not None:
            self.setup.age += 1
            if self.setup.age > self.bo_max_age:
                self.setup.reset()
            elif (self.setup.direction in (OrderDirection.LONG, getattr(OrderDirection, "BUY", "BUY")) or str(self.setup.direction) in ("LONG", "BUY")) and regime == MarketRegime.TREND_BEAR:
                self.setup.reset()
            elif (self.setup.direction in (OrderDirection.SHORT, getattr(OrderDirection, "SELL", "SELL")) or str(self.setup.direction) in ("SHORT", "SELL")) and regime == MarketRegime.TREND_BULL:
                self.setup.reset()
            else:
                direction = self.setup.direction
                level = float(self.setup.level)
                retest_vol_ok = vol <= avg_volume * self.bo_retest_vol_max

                if direction == OrderDirection.LONG:
                    invalid = c < level * (1.0 - self.bo_tolerance_pct)
                    retest = l <= level * (1.0 + self.bo_tolerance_pct) and c > level
                    if invalid:
                        self.setup.reset()
                    elif retest and retest_vol_ok and regime == MarketRegime.TREND_BULL:
                        delta_structure = c - min(l, level * (1.0 - self.bo_buffer_pct))
                        sl_dist = max(delta_structure, min_sl_dist)
                        stop = c - sl_dist
                        if stop < c:
                            res = {
                                "setup_type": SetupType.BREAKOUT,
                                "direction": OrderDirection.LONG,
                                "signal_price": c,
                                "stop_loss_price": stop,
                                "metadata": {
                                    "strategy": "SYNTHESIZED_BREAKOUT",
                                    "breakout_level": level,
                                    "setup_age": self.setup.age,
                                    "regime": regime.value,
                                },
                            }
                            self.setup.reset()
                            return res
                else:  # SHORT
                    invalid = c > level * (1.0 + self.bo_tolerance_pct)
                    retest = h >= level * (1.0 - self.bo_tolerance_pct) and c < level
                    if invalid:
                        self.setup.reset()
                    elif retest and retest_vol_ok and regime == MarketRegime.TREND_BEAR:
                        delta_structure = max(h, level * (1.0 + self.bo_buffer_pct)) - c
                        sl_dist = max(delta_structure, min_sl_dist)
                        stop = c + sl_dist
                        if stop > c:
                            res = {
                                "setup_type": SetupType.BREAKOUT,
                                "direction": OrderDirection.SHORT,
                                "signal_price": c,
                                "stop_loss_price": stop,
                                "metadata": {
                                    "strategy": "SYNTHESIZED_BREAKOUT",
                                    "breakout_level": level,
                                    "setup_age": self.setup.age,
                                    "regime": regime.value,
                                },
                            }
                            self.setup.reset()
                            return res

        # Arming new breakout if volume surge
        if self.setup.setup_type is None and vol >= avg_volume * self.bo_vol_multiplier:
            if c > prior_high and regime == MarketRegime.TREND_BULL:
                self.setup.setup_type = SetupType.BREAKOUT
                self.setup.direction = OrderDirection.LONG
                self.setup.level = prior_high
                self.setup.age = 0
                self.setup_count += 1
            elif c < prior_low and regime == MarketRegime.TREND_BEAR:
                self.setup.setup_type = SetupType.BREAKOUT
                self.setup.direction = OrderDirection.SHORT
                self.setup.level = prior_low
                self.setup.age = 0
                self.setup_count += 1

        return None

    def _evaluate_smc_setup(
        self,
        current_15m: Dict[str, Any],
        history_15m: pd.DataFrame,
        regime: MarketRegime,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates 15m SMC Liquidity Sweeps (hunting swing highs/lows + MSS + FVG).
        Active primarily in CHOP_RANGING regimes (Mean Reversion), or pro-trend discount sweeps.
        """
        if len(history_15m) < (2 * self.smc_swing_n + 1):
            return None

        e = self.smc_tracker.step(history_15m)
        row = history_15m.iloc[-1]
        c = float(current_15m.get("close", row["close"]))
        o = float(current_15m.get("open", row["open"]))
        h = float(current_15m.get("high", row["high"]))
        l = float(current_15m.get("low", row["low"]))
        if "atr_14" in current_15m and pd.notna(current_15m["atr_14"]):
            atr = float(current_15m["atr_14"])
        else:
            atr = float((history_15m["high"] - history_15m["low"]).iloc[-14:].mean())
        if atr <= 0.0 or not math.isfinite(atr):
            atr = c * 0.005

        # Check existing SMC state
        if self.setup.setup_type == SetupType.SMC_SWEEP and self.setup.direction is not None:
            self.setup.age += 1
            if self.setup.age > self.smc_max_age:
                self.setup.reset()
                return None

            s = self.setup
            if s.direction == OrderDirection.LONG and regime not in (MarketRegime.CHOP_RANGING, MarketRegime.TREND_BULL):
                self.setup.reset()
                return None
            if s.direction == OrderDirection.SHORT and regime not in (MarketRegime.CHOP_RANGING, MarketRegime.TREND_BEAR):
                self.setup.reset()
                return None

            # Phase 1 -> Phase 2: WAIT_BOS displacement
            if s.phase == "WAIT_BOS":
                bos_col = "bos_bullish" if s.direction == OrderDirection.LONG else "bos_bearish"
                if e.get(bos_col, False):
                    body = abs(c - o)
                    if body >= self.smc_displacement_atr * atr:
                        s.phase = "WAIT_FVG"
                        s.metadata["ob_low"] = e.get("order_block_low")
                        s.metadata["ob_high"] = e.get("order_block_high")

            # Phase 2 -> Phase 3: FVG Confluence Entry
            if s.phase == "WAIT_FVG":
                fvg_dir = "BULLISH" if s.direction == OrderDirection.LONG else "BEARISH"
                if e.get("fvg_direction") == fvg_dir:
                    fvg_high = float(e.get("fvg_high", 0.0))
                    fvg_low = float(e.get("fvg_low", 0.0))
                    fvg_size = fvg_high - fvg_low
                    if fvg_size >= self.smc_fvg_min_atr * atr:
                        mid = float(e.get("fvg_mid", (fvg_high + fvg_low) / 2.0))
                        ob_low = s.metadata.get("ob_low")
                        ob_high = s.metadata.get("ob_high")

                        min_sl_dist = max(self.atr_stop_mult * atr, self.min_stop_distance_pct * c)
                        if s.direction == OrderDirection.LONG:
                            extreme = s.sweep_extreme if s.sweep_extreme is not None else l
                            base_ref = ob_low if ob_low is not None and not np.isnan(ob_low) else extreme
                            delta_structure = c - min(extreme, base_ref) * (1.0 - self.smc_buffer_pct)
                            sl_dist = max(delta_structure, min_sl_dist)
                            stop = c - sl_dist
                            if stop >= c or stop <= 0.0:
                                self.setup.reset()
                                return None
                        else:
                            extreme = s.sweep_extreme if s.sweep_extreme is not None else h
                            base_ref = ob_high if ob_high is not None and not np.isnan(ob_high) else extreme
                            delta_structure = max(extreme, base_ref) * (1.0 + self.smc_buffer_pct) - c
                            sl_dist = max(delta_structure, min_sl_dist)
                            stop = c + sl_dist
                            if stop <= c or c <= 0.0:
                                self.setup.reset()
                                return None

                        res = {
                            "setup_type": SetupType.SMC_SWEEP,
                            "direction": s.direction,
                            "signal_price": c,
                            "stop_loss_price": stop,
                            "order_type": OrderType.MARKET_ENTRY,
                            "metadata": {
                                "strategy": "SYNTHESIZED_SMC",
                                "fvg_mid": mid,
                                "sweep_extreme": s.sweep_extreme,
                                "regime": regime.value,
                            },
                        }
                        self.setup.reset()
                        return res

        # Sweep Detection to Arm SMC Setup
        if e.get("liquidity_sweep_bullish", False) and regime in (MarketRegime.CHOP_RANGING, MarketRegime.TREND_BULL):
            self.setup.setup_type = SetupType.SMC_SWEEP
            self.setup.direction = OrderDirection.LONG
            self.setup.phase = "WAIT_BOS"
            self.setup.sweep_extreme = l
            self.setup.age = 0
            self.setup_count += 1
        elif e.get("liquidity_sweep_bearish", False) and regime in (MarketRegime.CHOP_RANGING, MarketRegime.TREND_BEAR):
            self.setup.setup_type = SetupType.SMC_SWEEP
            self.setup.direction = OrderDirection.SHORT
            self.setup.phase = "WAIT_BOS"
            self.setup.sweep_extreme = h
            self.setup.age = 0
            self.setup_count += 1

        return None

    def _evaluate_mean_reversion_setup(
        self,
        current_15m: Dict[str, Any],
        history_15m: pd.DataFrame,
        regime: MarketRegime,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates 15m Mean Reversion in CHOP_RANGING regimes.
        Buys oversold dips at lower 20-bar channel, sells overbought rallies at upper 20-bar channel.
        """
        if not self.mean_reversion_enabled:
            return None
        if regime != MarketRegime.CHOP_RANGING:
            return None
        if len(history_15m) < 25:
            return None

        row = history_15m.iloc[-1]
        c = float(current_15m.get("close", row["close"]))
        h = float(current_15m.get("high", row["high"]))
        l = float(current_15m.get("low", row["low"]))

        if "atr_14" in current_15m and pd.notna(current_15m["atr_14"]):
            atr = float(current_15m["atr_14"])
        else:
            atr = float((history_15m["high"] - history_15m["low"]).iloc[-14:].mean())
        if atr <= 0.0 or not math.isfinite(atr):
            atr = c * 0.005

        rsi_val = float(current_15m.get("rsi_14", 50.0))
        recent_20 = history_15m.iloc[-21:-1]
        range_high = float(recent_20["high"].max())
        range_low = float(recent_20["low"].min())
        min_sl_dist = max(1.5 * atr, 0.012 * c)

        # Long: RSI < 30 (deep oversold) and low swept range_low
        if rsi_val < 30.0 and l <= range_low * 1.001 and c > range_low * 0.995:
            delta_structure = max(c - l * 0.998, min_sl_dist)
            stop = c - delta_structure
            if stop < c:
                return {
                    "setup_type": SetupType.PULLBACK,
                    "direction": OrderDirection.LONG,
                    "signal_price": c,
                    "stop_loss_price": stop,
                    "partial_exits": [[1.2, 0.60], [2.5, 0.25]],
                    "metadata": {
                        "strategy": "SYNTHESIZED_RANGE_MEAN_REV",
                        "rsi": rsi_val,
                        "regime": regime.value,
                    },
                }

        # Short: RSI > 70 (deep overbought) and high swept range_high
        elif rsi_val > 70.0 and h >= range_high * 0.999 and c < range_high * 1.005:
            delta_structure = max(h * 1.002 - c, min_sl_dist)
            stop = c + delta_structure
            if stop > c:
                return {
                    "setup_type": SetupType.PULLBACK,
                    "direction": OrderDirection.SHORT,
                    "signal_price": c,
                    "stop_loss_price": stop,
                    "partial_exits": [[1.2, 0.60], [2.5, 0.25]],
                    "metadata": {
                        "strategy": "SYNTHESIZED_RANGE_MEAN_REV",
                        "rsi": rsi_val,
                        "regime": regime.value,
                    },
                }

        return None

    # -----------------------------------------------------------------------
    # Funding Sentiment Filter & Conviction Arbiter
    # -----------------------------------------------------------------------

    def _apply_funding_filter(
        self,
        direction: OrderDirection,
        candle_15m: Dict[str, Any],
    ) -> bool:
        """
        Funding Rate Sentiment Filter:
        Returns True if signal is approved; False if vetoed due to crowded positioning.
        - LONG vetoed if funding_rate > funding_max_long (+0.05%)
        - SHORT vetoed if funding_rate < funding_min_short (-0.05%)
        """
        if not self.funding_filter_enabled:
            return True

        raw_fr = candle_15m.get("funding_rate")
        if raw_fr is None or type(raw_fr) is bool or not isinstance(raw_fr, (int, float)):
            return True  # Fallback: pass through if funding rate not available

        funding_rate = float(raw_fr)
        if not math.isfinite(funding_rate):
            return True

        if direction == OrderDirection.LONG and funding_rate > self.funding_max_long:
            logger.debug(f"[{self.symbol}] Long VETOED by Funding Filter: {funding_rate:.6f} > {self.funding_max_long}")
            return False

        if direction == OrderDirection.SHORT and funding_rate < self.funding_min_short:
            logger.debug(f"[{self.symbol}] Short VETOED by Funding Filter: {funding_rate:.6f} < {self.funding_min_short}")
            return False

        return True

    def _evaluate_conviction(
        self,
        setup: Dict[str, Any],
        candle_15m: Dict[str, Any],
        history_15m: pd.DataFrame,
        regime: MarketRegime,
        broker_state: Optional[Any],
    ) -> Tuple[ConvictionTier, float]:
        """
        Evaluates setup conviction to determine risk sizing:
        ConvictionTier:
          - VETO (0): Trade rejected (returns 0.0 risk)
          - LOW (1): 1% risk
          - NORMAL (2): 2% risk
          - HIGH (3): 5% risk
        Returns: (ConvictionTier, base_risk_percent)
        """
        # Circuit Breaker & Drawdown state check
        cb = getattr(broker_state, "circuit_breaker", None)
        if cb is not None:
            if getattr(cb, "is_locked", False):
                return (ConvictionTier.VETO, 0.0)
            if getattr(cb, "risk_multiplier", 1.0) < 1.0:
                return (ConvictionTier.LOW, self.risk_tier_map[ConvictionTier.LOW])

        # Heuristic Conviction Confluence Engine
        score = 0
        direction = setup["direction"]
        setup_type = setup["setup_type"]

        # Confluence 1: Trend Alignment
        if (direction == OrderDirection.LONG and regime == MarketRegime.TREND_BULL) or \
           (direction == OrderDirection.SHORT and regime == MarketRegime.TREND_BEAR):
            score += 1

        # Confluence 2: Setup Specific Quality
        if setup_type == SetupType.SMC_SWEEP:
            score += 1
        elif setup_type == SetupType.BREAKOUT:
            score += 1

        # Score mapping:
        # score <= 0 -> LOW (1%)
        # score == 1 -> NORMAL (2%)
        # score >= 2 -> HIGH (5%)
        if score >= 2:
            tier = ConvictionTier.HIGH
        elif score == 1:
            tier = ConvictionTier.NORMAL
        else:
            tier = ConvictionTier.LOW

        risk_pct = self.risk_tier_map[tier]
        return (tier, risk_pct)

    # -----------------------------------------------------------------------
    # Signal Ingestion & Trailing Stop Updates
    # -----------------------------------------------------------------------

    def on_candle_close(
        self,
        candle_15m: Dict[str, Any],
        history_15m: pd.DataFrame,
        candle_4h: Optional[Union[Dict[str, Any], Any]] = None,
        history_4h: Optional[pd.DataFrame] = None,
        broker_state: Optional[Any] = None,
        **kwargs: Any,
    ) -> Optional[OrderRequest]:
        """
        Main execution hook called at each 15m closed candle.
        Supports 3-arg legacy call signature and 5-arg multi-timeframe call signature.
        """
        # Argument normalization for legacy 3-arg calls: on_candle_close(candle, history, broker)
        if candle_4h is not None and not isinstance(candle_4h, dict) and broker_state is None:
            broker_state = candle_4h
            candle_4h = None
            history_4h = None

        raw_ts = candle_15m.get("close_time") or candle_15m.get("timestamp") or candle_15m.get("open_time")
        if raw_ts is None:
            raw_ts = datetime.now(timezone.utc)
        current_time = _ensure_utc(raw_ts)

        # Time monotonicity verification
        if self._last_event_time is not None:
            if current_time < self._last_event_time:
                raise ValueError(f"Event time reversal: {current_time} < {self._last_event_time}")
            if current_time == self._last_event_time:
                return None
        self._last_event_time = current_time

        # Update 4h Macro Regime only when new 4h candle arrives
        if candle_4h is not None and history_4h is not None:
            raw_4h_ts = candle_4h.get("close_time") or candle_4h.get("timestamp")
            current_4h_close = _ensure_utc(raw_4h_ts) if raw_4h_ts is not None else None
            if current_4h_close is None or current_4h_close != self.last_4h_close_time:
                self.current_regime = self.classify_macro_regime(candle_4h, history_4h)
                self.last_4h_close_time = current_4h_close

        # Strict Concurrency Check: maximum 1 concurrent position or pending order per symbol
        if broker_state is not None:
            positions = getattr(broker_state, "positions", {})
            pending = getattr(broker_state, "pending_orders", [])
            has_pos = False
            if isinstance(positions, dict):
                has_pos = self.symbol in positions
            elif isinstance(positions, (list, tuple, set)):
                has_pos = any(getattr(p, "symbol", p) == self.symbol for p in positions)

            has_pending = False
            if isinstance(pending, dict):
                has_pending = self.symbol in pending
            elif isinstance(pending, (list, tuple, set)):
                has_pending = any(getattr(req, "symbol", req) == self.symbol for req in pending)

            if has_pos or has_pending:
                return None

        # Multi-Setup Evaluation
        candidate: Optional[Dict[str, Any]] = None

        # 1. Check SMC Liquidity Sweep (Chop or pro-trend)
        candidate = self._evaluate_smc_setup(candle_15m, history_15m, self.current_regime)

        # 2. Check Breakout-Retest (Trending regimes)
        if candidate is None:
            candidate = self._evaluate_breakout_setup(candle_15m, history_15m, self.current_regime)

        # 3. Check Micro-Trend Pullback (Trending regimes)
        if candidate is None:
            candidate = self._evaluate_pullback_setup(candle_15m, history_15m, self.current_regime)

        # 4. Check Range Mean Reversion (Chop / Ranging regimes)
        if candidate is None:
            candidate = self._evaluate_mean_reversion_setup(candle_15m, history_15m, self.current_regime)

        if candidate is None:
            return None

        # Funding Rate Sentiment Filter
        if not self._apply_funding_filter(candidate["direction"], candle_15m):
            return None

        # Conviction Arbiter
        conviction_tier, risk_pct = self._evaluate_conviction(
            setup=candidate,
            candle_15m=candle_15m,
            history_15m=history_15m,
            regime=self.current_regime,
            broker_state=broker_state,
        )

        if conviction_tier == ConvictionTier.VETO or risk_pct <= 0.0:
            return None

        # Construct and return validated OrderRequest
        self.candidate_count += 1
        req = OrderRequest(
            symbol=self.symbol,
            direction=candidate["direction"],
            signal_price=candidate["signal_price"],
            stop_loss_price=candidate["stop_loss_price"],
            signal_time=current_time,
            conviction_tier=conviction_tier.value,
            leverage=self.leverage,
            base_risk_percent=risk_pct,
            order_type=candidate.get("order_type", OrderType.MARKET_ENTRY),
            partial_exits=candidate.get("partial_exits", self.partial_exits),
            metadata={
                **candidate.get("metadata", {}),
                "regime": self.current_regime.value,
                "conviction_tier": conviction_tier.value,
                "strategy": "SYNTHESIZED",
            },
        )
        return req

    def update_trailing_stop(self, candle_15m: Dict[str, Any], broker: Any) -> None:
        """
        Manages Multi-Target Exits and Trailing Stops:
        1. When partials_done == 1 (1.5R reached): moves SL to Breakeven (pos.entry_price).
        2. When partials_done >= 2 (3.0R reached): trails remaining 25% balance along 15m EMA20.
        Tightening-only invariant enforced via broker.update_stop_loss.
        """
        if broker is None or not hasattr(broker, "positions") or not hasattr(broker, "update_stop_loss"):
            return

        pos: Optional[Position] = None
        if isinstance(broker.positions, dict):
            pos = broker.positions.get(self.symbol)
        elif isinstance(broker.positions, list):
            for p in broker.positions:
                if getattr(p, "symbol", None) == self.symbol:
                    pos = p
                    break

        if pos is None:
            return

        partials_done = pos.metadata.get("partials_done", 0)
        mark_price = float(candle_15m.get("close", getattr(broker, "last_mark_prices", {}).get(self.symbol, pos.entry_price)))

        # Step 1: Move SL to Breakeven after First Partial Exit (1.5R)
        if partials_done == 1 and self.be_after_partial_1:
            be_price = pos.entry_price
            if pos.direction == OrderDirection.LONG:
                if be_price > pos.stop_loss_price and be_price < mark_price:
                    broker.update_stop_loss(self.symbol, be_price)
            else:  # SHORT
                if be_price < pos.stop_loss_price and be_price > mark_price:
                    broker.update_stop_loss(self.symbol, be_price)

        # Step 2: Trail Remaining Balance (Runner) along EMA20 after Second Partial Exit (3.0R)
        elif partials_done >= 2:
            raw_ema = candle_15m.get(f"ema_{self.trailing_ema_period}")
            if raw_ema is not None and type(raw_ema) is not bool and isinstance(raw_ema, (int, float)) and math.isfinite(float(raw_ema)):
                candidate_stop = float(raw_ema)
                if pos.direction == OrderDirection.LONG:
                    if candidate_stop > pos.stop_loss_price and candidate_stop < mark_price:
                        broker.update_stop_loss(self.symbol, candidate_stop)
                else:  # SHORT
                    if candidate_stop < pos.stop_loss_price and candidate_stop > mark_price:
                        broker.update_stop_loss(self.symbol, candidate_stop)
