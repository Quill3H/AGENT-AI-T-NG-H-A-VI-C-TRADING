"""Confirmed swing -> sweep -> displacement/BOS -> FVG -> resting limit.

A limit is submitted only after the FVG creation candle closes. The broker alone
observes subsequent 1m candles to fill it. All timeout values are signal bars.
"""

from dataclasses import dataclass
import math
import pandas as pd
from src.execution.order_models import (
    OrderDirection,
    OrderRequest,
    OrderType,
    _ensure_utc,
)
from src.features.smc_features import SMCFeatureTracker
from src.strategies.base_strategy import BaseStrategy
from src.research.validation import positive_int, number
from src.data_layer.cache_manager import timeframe_to_timedelta


@dataclass
class SMCSetup:
    direction: object = None
    phase: str = "IDLE"
    age: int = 0
    sweep_extreme: float = 0.0
    ob_low: object = None
    ob_high: object = None


class SMCLiquiditySweepStrategy(BaseStrategy):
    def __init__(self, config, symbol="BTCUSDT"):
        super().__init__(config, symbol)
        smc = config.get("smc", {})
        entry = config.get("entry", {})
        self.swing_n = positive_int(smc.get("swing_n", 3), "swing_n")
        self.min_bos_pct = number(
            smc.get("min_bos_pct", 0.001), "min_bos_pct", maximum=1
        )
        self.max_age = positive_int(
            smc.get("max_setup_age_bars", 12), "max_setup_age_bars"
        )
        self.displacement_atr = number(
            smc.get("displacement_min_atr", 0.5), "displacement_min_atr"
        )
        self.fvg_min_atr = number(smc.get("fvg_min_size_atr", 0.3), "fvg_min_size_atr")
        self.ob_distance_atr = number(
            smc.get("ob_max_distance_atr", 1.0), "ob_max_distance_atr"
        )
        self.require_ob = entry.get("require_order_block_confluence", True)
        if type(self.require_ob) is not bool:
            raise TypeError("require_order_block_confluence must be boolean")
        self.buffer_pct = number(
            config.get("stop_loss", {}).get("buffer_pct", 0.002),
            "buffer_pct",
            maximum=1,
        )
        self.partial_exits = config.get("take_profit", {}).get(
            "partial_exits", [[1.5, 0.4], [3.0, 0.3]]
        )
        self.leverage = config.get("leverage", 2.0)
        self.base_risk_percent = config.get("base_risk_percent", 0.02)
        self.conviction = config.get("default_conviction", "normal")
        self.signal_duration = timeframe_to_timedelta(
            config.get("strategy", {}).get("timeframe_signal", "5m")
        )
        self.reset_state()

    def reset_state(self):
        self.tracker = SMCFeatureTracker(self.swing_n, self.min_bos_pct)
        self.setup = SMCSetup()
        self.last_ts = None
        self.setup_count = 0
        self.candidate_count = 0
        self.last_features = None

    def prime(self, history):
        """Warm confirmed levels only; no orders or setup state crosses a fold."""
        for i in range(len(history)):
            self.tracker.step(history.iloc[: i + 1])

    def on_candle_close(self, candle_4h, history_4h, broker_state):
        ts = _ensure_utc(candle_4h.get("close_time") or candle_4h.get("timestamp"))
        if self.last_ts == ts:
            return None
        if self.last_ts and ts < self.last_ts:
            raise ValueError("SMC event time reversal")
        self.last_ts = ts
        if history_4h is None or history_4h.empty:
            return None
        e = self.tracker.step(history_4h)
        self.last_features = e
        row = history_4h.iloc[-1]
        close = float(row.close)
        if getattr(broker_state, "positions", {}) or getattr(
            broker_state, "pending_orders", []
        ):
            self.setup = SMCSetup()
            return None
        s = self.setup
        if s.direction is not None:
            s.age += 1
            invalid = (
                close < s.sweep_extreme
                if s.direction == OrderDirection.LONG
                else close > s.sweep_extreme
            )
            if invalid or s.age > self.max_age:
                self.setup = SMCSetup()
                return None
            direction = "BULLISH" if s.direction == OrderDirection.LONG else "BEARISH"
            suffix = direction.lower()
            # ATR estimate uses closed bars only; no scaler or fitted data.
            atr = float((history_4h.high - history_4h.low).iloc[-14:].mean())
            if s.phase == "WAIT_BOS" and (e["bos_" + suffix] or e["choch_" + suffix]):
                if abs(float(row.close - row.open)) >= self.displacement_atr * atr:
                    s.phase = "WAIT_FVG"
                    if e["order_block_direction"] == direction:
                        s.ob_low = e["order_block_low"]
                        s.ob_high = e["order_block_high"]
            if s.phase == "WAIT_FVG" and e["fvg_direction"] == direction:
                if e["fvg_high"] - e["fvg_low"] < self.fvg_min_atr * atr:
                    return None
                mid = float(e["fvg_mid"])
                # Confluence = known directional OB body within configured ATR
                # distance of the FVG, on the protective side of the limit.
                ob_ok = s.ob_low is not None and (
                    s.ob_low < mid
                    if s.direction == OrderDirection.LONG
                    else s.ob_high > mid
                )
                if ob_ok:
                    separation = max(
                        0.0, e["fvg_low"] - s.ob_high, s.ob_low - e["fvg_high"]
                    )
                    ob_ok = separation <= self.ob_distance_atr * atr
                if self.require_ob and not ob_ok:
                    return None
                if s.direction == OrderDirection.LONG:
                    stop = min(
                        s.sweep_extreme, s.ob_low if ob_ok else s.sweep_extreme
                    ) * (1 - self.buffer_pct)
                else:
                    stop = max(
                        s.sweep_extreme, s.ob_high if ob_ok else s.sweep_extreme
                    ) * (1 + self.buffer_pct)
                req = OrderRequest(
                    symbol=self.symbol,
                    direction=s.direction,
                    signal_price=mid,
                    stop_loss_price=stop,
                    signal_time=ts,
                    conviction_tier=self.conviction,
                    leverage=self.leverage,
                    base_risk_percent=self.base_risk_percent,
                    order_type=OrderType.LIMIT_ENTRY,
                    expires_at=ts + self.signal_duration * (self.max_age - s.age + 1),
                    partial_exits=self.partial_exits,
                    metadata={
                        "strategy": "SMC_LIQUIDITY_SWEEP",
                        "fvg_mid": mid,
                        "order_block_confluence": bool(ob_ok),
                        "order_block_body": [s.ob_low, s.ob_high],
                        "causal_features": True,
                    },
                )
                self.candidate_count += 1
                self.setup = SMCSetup()
                return req
        elif e["liquidity_sweep_bullish"] or e["liquidity_sweep_bearish"]:
            long = e["liquidity_sweep_bullish"]
            self.setup = SMCSetup(
                OrderDirection.LONG if long else OrderDirection.SHORT,
                "WAIT_BOS",
                sweep_extreme=float(row.low if long else row.high),
            )
            self.setup_count += 1
        return None

    def update_trailing_stop(self, candle_4h, broker):
        pos = getattr(broker, "positions", {}).get(self.symbol)
        if pos is None or pos.metadata.get("partials_done", 0) < 2:
            return
        candidate = (
            float(candle_4h["low"]) * (1 - self.buffer_pct)
            if pos.direction == OrderDirection.LONG
            else float(candle_4h["high"]) * (1 + self.buffer_pct)
        )
        broker.update_stop_loss(self.symbol, candidate)
