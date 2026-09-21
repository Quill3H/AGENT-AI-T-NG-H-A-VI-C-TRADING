"""Causal SMC liquidity sweep strategy for paper backtests."""
from datetime import datetime
from typing import Any, Dict, Optional
import math
import pandas as pd

from src.execution.order_models import OrderDirection, OrderRequest, _ensure_utc
from src.features.smc_features import compute_smc_features
from src.strategies.base_strategy import BaseStrategy


class SMCLiquiditySweepStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any], symbol: str = "BTCUSDT"):
        super().__init__(config, symbol)
        smc = config.get("smc", {})
        self.swing_n = int(smc.get("swing_n", 3))
        self.min_bos_pct = float(smc.get("min_bos_pct", 0.001))
        entry = config.get("entry", {})
        self.rrr_min = float(config.get("take_profit", {}).get("rrr_min", 2.0))
        self.buffer_pct = float(config.get("stop_loss", {}).get("buffer_pct", 0.002))
        self.leverage = float(config.get("leverage", 2.0))
        self.base_risk_percent = float(config.get("base_risk_percent", 0.02))
        self.conviction = str(config.get("default_conviction", "high"))
        self.require_ob = bool(entry.get("require_order_block_confluence", False))
        self._last_signal_time: Optional[datetime] = None
        self.setup_count = 0
        self.candidate_count = 0

    def on_candle_close(self, candle_4h: Dict[str, Any], history_4h: pd.DataFrame, broker_state: Any) -> Optional[OrderRequest]:
        if history_4h is None or len(history_4h) < self.swing_n * 2 + 3:
            return None
        features = compute_smc_features(history_4h, self.swing_n, self.min_bos_pct)
        row = features.iloc[-1]
        ts = _ensure_utc(candle_4h.get("close_time") or candle_4h.get("timestamp"))
        if self._last_signal_time == ts or bool(getattr(broker_state, "positions", {})):
            return None
        direction = None
        level = None
        if bool(row.get("liquidity_sweep_bullish")) and bool(row.get("fvg_direction") == "BULLISH"):
            direction, level = OrderDirection.LONG, float(row["fvg_mid"])
        elif bool(row.get("liquidity_sweep_bearish")) and bool(row.get("fvg_direction") == "BEARISH"):
            direction, level = OrderDirection.SHORT, float(row["fvg_mid"])
        if direction is None or not math.isfinite(level):
            return None
        close = float(row["close"])
        low, high = float(row["low"]), float(row["high"])
        if direction == OrderDirection.LONG and not (low <= level <= close):
            return None
        if direction == OrderDirection.SHORT and not (close <= level <= high):
            return None
        stop = low * (1 - self.buffer_pct) if direction == OrderDirection.LONG else high * (1 + self.buffer_pct)
        risk = abs(close - stop)
        if risk <= 0 or not math.isfinite(risk):
            return None
        tp = close + self.rrr_min * risk if direction == OrderDirection.LONG else close - self.rrr_min * risk
        self._last_signal_time = ts
        self.setup_count += 1
        self.candidate_count += 1
        return OrderRequest(symbol=self.symbol, direction=direction, signal_price=close,
            stop_loss_price=stop, take_profit_price=tp, signal_time=ts,
            conviction_tier=self.conviction, leverage=self.leverage,
            base_risk_percent=self.base_risk_percent,
            metadata={"strategy": "SMC_LIQUIDITY_SWEEP", "fvg_mid": level,
                      "partial_exit": {"fraction": 0.5, "rr_multiple": 1.0},
                      "causal_features": True})

    def update_trailing_stop(self, candle_4h: Dict[str, Any], broker: Any) -> None:
        return None
