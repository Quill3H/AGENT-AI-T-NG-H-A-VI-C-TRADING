"""
src/strategies/donchian_trend.py
================================
Daily Donchian channel trend following (the classic "Turtle" rulebook, Dennis/Faith).

Rules, all evaluated on closed signal bars and filled at the next execution open:
1. LONG when the close breaks above the highest high of the previous `entry_bars`
   bars; SHORT when it breaks below the lowest low (SHORT can be disabled).
2. Initial stop: entry ± `stop_atr_multiple` × ATR(`atr_bars`).
3. Exit: trailing stop at the lowest low (LONG) / highest high (SHORT) of the
   previous `exit_bars` bars, moved only in the risk-reducing direction.
No take-profit. Parameters come from the published rulebook, not from fitting.
"""
import math
from typing import Any, Dict, Optional

import pandas as pd

from src.execution.order_models import OrderDirection, OrderRequest, _ensure_utc
from src.strategies.base_strategy import BaseStrategy


def average_true_range(history: pd.DataFrame, bars: int) -> float:
    prev_close = history["close"].shift(1)
    true_range = pd.concat(
        [history["high"] - history["low"], (history["high"] - prev_close).abs(), (history["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return float(true_range.iloc[-bars:].mean())


class DonchianTrendStrategy(BaseStrategy):
    """Breakout of an N-bar channel, ATR initial stop, M-bar channel trailing exit."""

    def __init__(self, config: Dict[str, Any], symbol: str = "BTCUSDT"):
        super().__init__(config, symbol)
        rules = config.get("rules", {})
        self.entry_bars = int(rules.get("entry_bars", 20))
        self.exit_bars = int(rules.get("exit_bars", 10))
        self.atr_bars = int(rules.get("atr_bars", 20))
        self.stop_atr_multiple = float(rules.get("stop_atr_multiple", 2.0))
        self.allow_short = bool(rules.get("allow_short", True))
        self.default_conviction = config.get("default_conviction", "normal")
        self.leverage = min(float(config.get("leverage", 2.0)), 5.0)
        self.base_risk_percent = float(config.get("base_risk_percent", 0.02))
        self.setup_count = 0
        self.candidate_count = 0

    def on_candle_close(self, candle_4h: Dict[str, Any], history_4h: pd.DataFrame, broker_state: Any) -> Optional[OrderRequest]:
        needed = max(self.entry_bars, self.atr_bars) + 1
        if history_4h is None or len(history_4h) < needed:
            return None
        self._trail_exit_channel(candle_4h, history_4h, broker_state)
        if self._broker_has_active_or_pending(broker_state):
            return None
        close = float(candle_4h["close"])
        previous = history_4h.iloc[-(self.entry_bars + 1):-1]
        channel_high = float(previous["high"].max())
        channel_low = float(previous["low"].min())
        atr = average_true_range(history_4h, self.atr_bars)
        if not math.isfinite(atr) or atr <= 0:
            return None

        if close > channel_high:
            direction, stop = OrderDirection.LONG, close - self.stop_atr_multiple * atr
        elif close < channel_low and self.allow_short:
            direction, stop = OrderDirection.SHORT, close + self.stop_atr_multiple * atr
        else:
            return None
        if stop <= 0:
            return None

        self.setup_count += 1
        self.candidate_count += 1
        return OrderRequest(
            symbol=self.symbol,
            direction=direction,
            signal_price=close,
            stop_loss_price=stop,
            signal_time=_ensure_utc(candle_4h.get("close_time") or candle_4h.get("timestamp")),
            conviction_tier=self.default_conviction,
            take_profit_price=None,
            leverage=self.leverage,
            base_risk_percent=self.base_risk_percent,
            metadata={
                "strategy": "DONCHIAN_TREND",
                "channel_high": channel_high,
                "channel_low": channel_low,
                "atr": atr,
            },
        )

    def update_trailing_stop(self, candle_4h: Dict[str, Any], broker: Any) -> None:
        """The exit channel needs bar history, so trailing happens in on_candle_close."""

    def _trail_exit_channel(self, candle_4h: Dict[str, Any], history_4h: pd.DataFrame, broker: Any) -> None:
        if broker is None or len(history_4h) < self.exit_bars:
            return
        position = getattr(broker, "positions", {}).get(self.symbol)
        if position is None:
            return
        window = history_4h.iloc[-self.exit_bars:]
        mark = float(candle_4h["close"])
        if position.direction == OrderDirection.LONG:
            candidate = float(window["low"].min())
            if position.stop_loss_price < candidate < mark:
                broker.update_stop_loss(self.symbol, candidate)
        else:
            candidate = float(window["high"].max())
            if mark < candidate < position.stop_loss_price:
                broker.update_stop_loss(self.symbol, candidate)

    def _broker_has_active_or_pending(self, broker_state: Any) -> bool:
        if broker_state is None:
            return False
        if self.symbol in getattr(broker_state, "positions", {}):
            return True
        return any(getattr(order, "symbol", None) == self.symbol for order in getattr(broker_state, "pending_orders", []))
