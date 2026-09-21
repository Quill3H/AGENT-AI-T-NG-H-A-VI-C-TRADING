"""Causal Breakout & Retest strategy (Stage 7)."""
from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any, Dict, Optional

import pandas as pd

from src.execution.order_models import OrderDirection, OrderRequest, _ensure_utc
from src.strategies.base_strategy import BaseStrategy


@dataclass
class BreakoutSetup:
    direction: Optional[OrderDirection] = None
    level: Optional[float] = None
    age: int = 0

    def reset(self) -> None:
        self.direction = None
        self.level = None
        self.age = 0


class BreakoutRetestStrategy(BaseStrategy):
    """Breakout must close beyond a prior range, then retest on a later candle."""

    def __init__(self, config: Dict[str, Any], symbol: str = "BTCUSDT"):
        super().__init__(config, symbol)
        strategy_cfg = config.get("strategy", {})
        rules = config.get("breakout", {})
        self.timeframe_signal = strategy_cfg.get("timeframe_signal", "4h")
        self.timeframe_execution = strategy_cfg.get("timeframe_execution", "15m")
        self.lookback = int(rules.get("lookback_bars", 20))
        self.volume_multiplier = float(rules.get("volume_multiplier", 1.5))
        self.retest_volume_max = float(rules.get("retest_volume_max", 1.0))
        self.max_setup_age_bars = int(rules.get("max_setup_age_bars", 6))
        self.level_tolerance_pct = float(rules.get("level_tolerance_pct", 0.001))
        self.rrr = float(rules.get("rrr", 2.0))
        self.stop_buffer_pct = float(rules.get("stop_buffer_pct", 0.002))
        for name in ("lookback_bars", "max_setup_age_bars"):
            value = rules.get(name, 20 if name == "lookback_bars" else 6)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name, value in (("rrr", self.rrr), ("volume_multiplier", self.volume_multiplier),
                            ("retest_volume_max", self.retest_volume_max), ("stop_buffer_pct", self.stop_buffer_pct)):
            if type(rules.get(name)) is bool or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not 0 <= self.level_tolerance_pct < 1 or not self.stop_buffer_pct < 1:
            raise ValueError("tolerance/buffer must be fractions below one")
        self.leverage = float(config.get("leverage", 2.0))
        self.base_risk_percent = float(config.get("base_risk_percent", 0.02))
        self.default_conviction = str(config.get("default_conviction", "normal"))
        self.setup = BreakoutSetup()
        self.setup_count = 0
        self.candidate_count = 0
        self._last_event = None

    def reset_state(self) -> None:
        self.setup.reset()
        self.setup_count = 0
        self.candidate_count = 0
        self._last_event = None

    @staticmethod
    def _finite(value: Any) -> Optional[float]:
        if type(value) is bool:
            return None
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) else None

    def _has_active_position(self, broker: Any) -> bool:
        positions = getattr(broker, "positions", {})
        return bool(positions) or bool(getattr(broker, "pending_orders", []))

    def on_candle_close(self, candle_4h: Dict[str, Any], history_4h: pd.DataFrame, broker_state: Any) -> Optional[OrderRequest]:
        current_time = _ensure_utc(candle_4h.get("close_time") or candle_4h.get("timestamp"))
        if self._last_event is not None:
            if current_time < self._last_event:
                raise ValueError("strategy event time reversal")
            if current_time == self._last_event:
                return None
        self._last_event = current_time
        if history_4h is None or len(history_4h) < self.lookback + 1:
            return None
        current = history_4h.iloc[-1]
        prior = history_4h.iloc[-(self.lookback + 1):-1]
        # Reject an incomplete baseline; pandas mean/max would silently skip NaN.
        for column in ("high", "low", "volume"):
            if any(self._finite(v) is None or float(v) <= 0 for v in prior[column]):
                return None
        close = self._finite(current.get("close"))
        high = self._finite(current.get("high"))
        low = self._finite(current.get("low"))
        volume = self._finite(current.get("volume"))
        prior_high = self._finite(prior["high"].max())
        prior_low = self._finite(prior["low"].min())
        avg_volume = self._finite(prior["volume"].mean())
        if None in (close, high, low, volume, prior_high, prior_low, avg_volume) or avg_volume <= 0:
            return None

        if self.setup.direction is not None:
            self.setup.age += 1
            direction = self.setup.direction
            level = float(self.setup.level)
            if self.setup.age > self.max_setup_age_bars:
                self.setup.reset()
            else:
                invalidated = (direction == OrderDirection.LONG and close < level * (1 - self.level_tolerance_pct)) or (
                    direction == OrderDirection.SHORT and close > level * (1 + self.level_tolerance_pct)
                )
                retest_volume = volume <= avg_volume * self.retest_volume_max
                if invalidated:
                    self.setup.reset()
                elif retest_volume and not self._has_active_position(broker_state):
                    if direction == OrderDirection.LONG:
                        retest = low <= level * (1 + self.level_tolerance_pct) and close > level
                        stop = min(low, level * (1 - self.stop_buffer_pct))
                    else:
                        retest = high >= level * (1 - self.level_tolerance_pct) and close < level
                        stop = max(high, level * (1 + self.stop_buffer_pct))
                    risk_distance = abs(close - stop)
                    if retest and risk_distance > 0 and math.isfinite(risk_distance):
                        take_profit = close + self.rrr * risk_distance if direction == OrderDirection.LONG else close - self.rrr * risk_distance
                        self.candidate_count += 1
                        request = OrderRequest(
                            symbol=self.symbol,
                            direction=direction,
                            signal_price=close,
                            stop_loss_price=stop,
                            take_profit_price=take_profit,
                            signal_time=current_time,
                            conviction_tier=self.default_conviction,
                            leverage=self.leverage,
                            base_risk_percent=self.base_risk_percent,
                            metadata={"strategy": "BREAKOUT_RETEST", "breakout_level": level, "setup_age_bars": self.setup.age, "rrr": self.rrr},
                        )
                        self.setup.reset()
                        return request

        if self.setup.direction is None and volume >= avg_volume * self.volume_multiplier:
            if close > prior_high:
                self.setup.direction = OrderDirection.LONG
                self.setup.level = prior_high
                self.setup.age = 0
                self.setup_count += 1
            elif close < prior_low:
                self.setup.direction = OrderDirection.SHORT
                self.setup.level = prior_low
                self.setup.age = 0
                self.setup_count += 1
        return None

    def update_trailing_stop(self, candle_4h: Dict[str, Any], broker: Any) -> None:
        return None
