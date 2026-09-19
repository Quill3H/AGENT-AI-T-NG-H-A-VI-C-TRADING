"""
src/strategies/trend_following.py
=================================
Triển khai chiến lược Trend Following (Giai đoạn 5) trên khung thời gian 4h.
Tuân thủ nghiêm ngặt ANTIGRAVITY_STAGE_05_TASK.md:
1. Signal/regime trên nến 4h đã đóng, thực thi tại open nến 15m kế tiếp.
2. Crossover EMA20/EMA50 kích hoạt trạng thái ARMED (không vào lệnh tại nến crossover).
3. Retest/pullback hợp lệ vào vùng EMA20/EMA50 trên nến 4h sau trigger:
   - LONG: low <= ema20, high >= ema50, close >= ema20.
   - SHORT: high >= ema20, low <= ema50, close <= ema20.
4. Macro regime: close > ema200 (LONG), close < ema200 (SHORT).
5. Momentum: RSI14 > 50 (LONG), RSI14 < 50 (SHORT).
6. OI confluence (ADR 0005): oi_delta_pct > 0; mode strict/optional/disabled; fallback_when_nan có note OI_BYPASSED_HISTORICAL.
7. Causal swing stop loss: min(low) / max(high) của 5 nến 4h đã đóng gần nhất.
8. Trailing stop bám EMA50 nến 4h đã đóng theo hướng thắt chặt rủi ro (tightening-only) qua broker.update_stop_loss.
9. take_profit_price = None (không fixed TP, không partial TP).
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from typing import Any, Dict, Optional
from loguru import logger
import numpy as np
import pandas as pd

from src.execution.order_models import (
    OrderDirection,
    OrderRequest,
    _ensure_utc,
    _validate_finite_positive,
)
from src.strategies.base_strategy import BaseStrategy


class SetupState(str, Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"


@dataclass
class SetupContext:
    state: SetupState = SetupState.IDLE
    direction: Optional[OrderDirection] = None
    trigger_time: Optional[datetime] = None
    setup_age_bars: int = 0

    def reset(self) -> None:
        self.state = SetupState.IDLE
        self.direction = None
        self.trigger_time = None
        self.setup_age_bars = 0


class TrendFollowingStrategy(BaseStrategy):
    """
    Chiến lược giao dịch bám đuổi xu hướng (Trend Following) khung 4h.
    """

    def __init__(self, config: Dict[str, Any], symbol: str = "BTCUSDT"):
        super().__init__(config, symbol)
        
        # Đọc cấu hình chiến lược
        strat_cfg = config.get("strategy", {})
        rules_cfg = config.get("rules", {})
        oi_cfg = config.get("oi_confluence", {})
        stop_cfg = config.get("stop_loss", {})
        
        self.timeframe_signal = strat_cfg.get("timeframe_signal", "4h")
        self.timeframe_execution = strat_cfg.get("timeframe_execution", "15m")
        
        # Conviction & Sizing
        self.default_conviction = config.get("default_conviction", "normal")
        self.leverage = min(float(config.get("leverage", 2.0)), 5.0)
        self.base_risk_percent = float(config.get("base_risk_percent", 0.02))
        
        # Rules
        self.crossover_fast_ema = int(rules_cfg.get("crossover_fast_ema", 20))
        self.crossover_slow_ema = int(rules_cfg.get("crossover_slow_ema", 50))
        self.regime_ema = int(rules_cfg.get("regime_ema", 200))
        self.rsi_period = int(rules_cfg.get("rsi_period", 14))
        self.rsi_threshold = float(rules_cfg.get("rsi_threshold", 50.0))
        self.max_setup_age_bars = int(rules_cfg.get("max_setup_age_bars", 12))
        self.swing_lookback_bars = int(rules_cfg.get("swing_lookback_bars", 5))
        
        # OI Confluence
        self.oi_mode = str(oi_cfg.get("mode", "optional")).lower()
        self.oi_fallback_when_nan = bool(oi_cfg.get("fallback_when_nan", True))
        self.oi_nan_log_note = str(oi_cfg.get("nan_log_note", "OI_BYPASSED_HISTORICAL"))
        
        # State machine context per symbol
        self.setup = SetupContext()
        self.setup_count: int = 0
        self.candidate_count: int = 0

    def reset_state(self) -> None:
        """Reset state machine về trạng thái IDLE."""
        self.setup.reset()
        self.setup_count = 0
        self.candidate_count = 0

    def on_candle_close(
        self,
        candle_4h: Dict[str, Any],
        history_4h: pd.DataFrame,
        broker_state: Any,
    ) -> Optional[OrderRequest]:
        """
        Được gọi mỗi khi một nến 4h đóng cửa hoàn toàn.
        
        Quy trình xử lý:
        1. Kiểm tra warm-up của các indicators (EMA20, EMA50, EMA200, RSI14).
        2. Nếu đang IDLE: kiểm tra tín hiệu Crossover EMA20/EMA50 + Macro Regime để ARM setup.
        3. Nếu đang ARMED:
           - Tăng setup_age_bars += 1.
           - Kiểm tra invalidation (tuổi vượt max_setup_age_bars, đảo chiều regime hoặc crossover).
           - Nếu hợp lệ: kiểm tra Pullback/Retest vào vùng EMA20/EMA50, Momentum RSI, OI Confluence.
           - Nếu mọi điều kiện đạt: tính Causal Swing Stop Loss, tạo OrderRequest và reset về IDLE.
        """
        # Kiểm tra history có đủ nến để xác định nến t và t-1
        if history_4h is None or len(history_4h) < 2:
            return None

        # Trích xuất các giá trị indicator cần thiết tại nến hiện tại (t)
        curr_close = candle_4h.get("close")
        curr_high = candle_4h.get("high")
        curr_low = candle_4h.get("low")
        curr_ema_fast = candle_4h.get(f"ema_{self.crossover_fast_ema}")
        curr_ema_slow = candle_4h.get(f"ema_{self.crossover_slow_ema}")
        curr_ema_regime = candle_4h.get(f"ema_{self.regime_ema}")
        curr_rsi = candle_4h.get(f"rsi_{self.rsi_period}")
        curr_time = candle_4h.get("close_time") or candle_4h.get("timestamp")

        # Kiểm tra giá trị hợp lệ cơ bản
        if any(
            v is None or type(v) is bool or not isinstance(v, (int, float)) or not math.isfinite(float(v))
            for v in (curr_close, curr_high, curr_low, curr_ema_fast, curr_ema_slow, curr_ema_regime)
        ):
            # Thiếu indicator cơ bản hoặc đang trong giai đoạn warm-up
            return None

        curr_close = float(curr_close)
        curr_high = float(curr_high)
        curr_low = float(curr_low)
        curr_ema_fast = float(curr_ema_fast)
        curr_ema_slow = float(curr_ema_slow)
        curr_ema_regime = float(curr_ema_regime)
        curr_time = _ensure_utc(curr_time)

        # Trích xuất nến trước đó (t-1) từ history_4h
        prev_bar = history_4h.iloc[-2]
        prev_ema_fast = prev_bar.get(f"ema_{self.crossover_fast_ema}")
        prev_ema_slow = prev_bar.get(f"ema_{self.crossover_slow_ema}")

        prev_has_emas = (
            prev_ema_fast is not None
            and prev_ema_slow is not None
            and not (type(prev_ema_fast) is bool or type(prev_ema_slow) is bool)
            and isinstance(prev_ema_fast, (int, float))
            and isinstance(prev_ema_slow, (int, float))
            and math.isfinite(float(prev_ema_fast))
            and math.isfinite(float(prev_ema_slow))
        )

        # -------------------------------------------------------------
        # XỬ LÝ KHI TRẠNG THÁI ĐANG ARMED
        # -------------------------------------------------------------
        if self.setup.state == SetupState.ARMED:
            self.setup.setup_age_bars += 1
            direction = self.setup.direction

            # Kiểm tra 1: Hết hạn setup (expiry)
            if self.setup.setup_age_bars > self.max_setup_age_bars:
                logger.debug(
                    f"[{self.symbol}] Setup {direction.value} expired: age {self.setup.setup_age_bars} > {self.max_setup_age_bars} bars."
                )
                self.setup.reset()
                # Có thể nến này là crossover mới, tiếp tục chạy kiểm tra trigger bên dưới
            else:
                # Kiểm tra 2: Invalidation do đảo chiều Regime hoặc Crossover
                invalidated = False
                if direction == OrderDirection.LONG:
                    if curr_close <= curr_ema_regime:
                        invalidated = True
                        logger.debug(f"[{self.symbol}] Setup LONG invalidated: close {curr_close} <= ema200 {curr_ema_regime}")
                    elif curr_ema_fast < curr_ema_slow:
                        invalidated = True
                        logger.debug(f"[{self.symbol}] Setup LONG invalidated: ema20 {curr_ema_fast} < ema50 {curr_ema_slow}")
                else:  # SHORT
                    if curr_close >= curr_ema_regime:
                        invalidated = True
                        logger.debug(f"[{self.symbol}] Setup SHORT invalidated: close {curr_close} >= ema200 {curr_ema_regime}")
                    elif curr_ema_fast > curr_ema_slow:
                        invalidated = True
                        logger.debug(f"[{self.symbol}] Setup SHORT invalidated: ema20 {curr_ema_fast} > ema50 {curr_ema_slow}")

                if invalidated:
                    self.setup.reset()
                else:
                    # Kiểm tra 3: Thỏa mãn điều kiện Retest/Pullback + Confirmation
                    # Đã qua ít nhất 1 nến sau trigger (setup_age_bars >= 1)
                    retest_valid = False
                    if direction == OrderDirection.LONG:
                        # Vùng EMA20/EMA50: [curr_ema_slow, curr_ema_fast] vì ema_fast > ema_slow
                        # Biên nến giao với vùng giữa EMA20 và EMA50:
                        band_intersect = (curr_low <= curr_ema_fast) and (curr_high >= curr_ema_slow)
                        close_regained = (curr_close >= curr_ema_fast)
                        retest_valid = band_intersect and close_regained
                    else:  # SHORT
                        # Vùng EMA20/EMA50: [curr_ema_fast, curr_ema_slow] vì ema_fast < ema_slow
                        band_intersect = (curr_high >= curr_ema_fast) and (curr_low <= curr_ema_slow)
                        close_regained = (curr_close <= curr_ema_fast)
                        retest_valid = band_intersect and close_regained

                    if retest_valid:
                        # Kiểm tra 4: Momentum RSI
                        if curr_rsi is None or type(curr_rsi) is bool or not isinstance(curr_rsi, (int, float)) or not math.isfinite(float(curr_rsi)):
                            # RSI không hợp lệ -> không tạo lệnh
                            rsi_valid = False
                        else:
                            curr_rsi_val = float(curr_rsi)
                            if direction == OrderDirection.LONG:
                                rsi_valid = curr_rsi_val > self.rsi_threshold  # Nghiêm ngặt > 50
                            else:
                                rsi_valid = curr_rsi_val < self.rsi_threshold  # Nghiêm ngặt < 50

                        if rsi_valid:
                            # Kiểm tra 5: OI Confluence (ADR 0005)
                            oi_valid, oi_note = self._check_oi_confluence(candle_4h)

                            if oi_valid:
                                # Kiểm tra 6: Causal Swing Stop Loss
                                stop_loss_price = self._calculate_swing_stop(
                                    direction=direction,
                                    history_4h=history_4h,
                                    signal_price=curr_close,
                                )

                                if stop_loss_price is not None:
                                    # Kiểm tra 7: Vị thế hoặc pending order đã tồn tại trong broker
                                    if not self._broker_has_active_or_pending(broker_state):
                                        metadata = {
                                            "strategy": "TREND_FOLLOWING",
                                            "trigger_time": self.setup.trigger_time.isoformat() if self.setup.trigger_time else None,
                                            "setup_age_bars": self.setup.setup_age_bars,
                                            "ema_fast": curr_ema_fast,
                                            "ema_slow": curr_ema_slow,
                                            "ema_regime": curr_ema_regime,
                                            "rsi": float(curr_rsi),
                                        }
                                        if oi_note:
                                            metadata["oi_note"] = oi_note

                                        order_req = OrderRequest(
                                            symbol=self.symbol,
                                            direction=direction,
                                            signal_price=curr_close,
                                            stop_loss_price=stop_loss_price,
                                            signal_time=curr_time,
                                            conviction_tier=self.default_conviction,
                                            take_profit_price=None,  # Section 4.3: Không fixed TP / partial TP
                                            leverage=self.leverage,
                                            base_risk_percent=self.base_risk_percent,
                                            metadata=metadata,
                                        )

                                        # One-shot: đã phát lệnh xong thì reset setup về IDLE
                                        self.candidate_count += 1
                                        self.setup.reset()
                                        return order_req

        # -------------------------------------------------------------
        # KIỂM TRA TÍN HIỆU TRIGGER MỚI (CROSSOVER EMA20 / EMA50)
        # -------------------------------------------------------------
        # Chỉ kiểm tra nếu hiện tại đang IDLE và nến t-1 có đủ EMA
        if self.setup.state == SetupState.IDLE and prev_has_emas:
            p_fast = float(prev_ema_fast)
            p_slow = float(prev_ema_slow)

            # LONG Trigger:
            # 1. Macro Regime: close > EMA200
            # 2. Crossover: ema20[t-1] <= ema50[t-1] and ema20[t] > ema50[t]
            if curr_close > curr_ema_regime and p_fast <= p_slow and curr_ema_fast > curr_ema_slow:
                self.setup.state = SetupState.ARMED
                self.setup.direction = OrderDirection.LONG
                self.setup.trigger_time = curr_time
                self.setup.setup_age_bars = 0
                self.setup_count += 1
                logger.debug(
                    f"[{self.symbol}] LONG setup ARMED at {curr_time.isoformat()}: "
                    f"Crossover EMA20({curr_ema_fast:.2f}) > EMA50({curr_ema_slow:.2f}), Close > EMA200."
                )
                # Tuyệt đối không vào lệnh tại nến crossover!
                return None

            # SHORT Trigger:
            # 1. Macro Regime: close < EMA200
            # 2. Crossover: ema20[t-1] >= ema50[t-1] and ema20[t] < ema50[t]
            if curr_close < curr_ema_regime and p_fast >= p_slow and curr_ema_fast < curr_ema_slow:
                self.setup.state = SetupState.ARMED
                self.setup.direction = OrderDirection.SHORT
                self.setup.trigger_time = curr_time
                self.setup.setup_age_bars = 0
                self.setup_count += 1
                logger.debug(
                    f"[{self.symbol}] SHORT setup ARMED at {curr_time.isoformat()}: "
                    f"Crossover EMA20({curr_ema_fast:.2f}) < EMA50({curr_ema_slow:.2f}), Close < EMA200."
                )
                # Tuyệt đối không vào lệnh tại nến crossover!
                return None

        return None

    def _check_oi_confluence(self, candle_4h: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Kiểm tra hợp lưu Open Interest (ADR 0005).
        Returns
        -------
        (is_valid: bool, note: Optional[str])
        """
        if self.oi_mode == "disabled":
            return True, None

        raw_oi_delta = candle_4h.get("oi_delta_pct")

        # Kiểm tra kiểu dữ liệu bất thường: bool, string, object không hợp lệ -> fail-closed (Section 6, Test 5)
        if raw_oi_delta is not None and (type(raw_oi_delta) is bool or isinstance(raw_oi_delta, str)):
            logger.warning(f"[{self.symbol}] OI confluence fail-closed: invalid type {type(raw_oi_delta).__name__}")
            return False, None

        # Kiểm tra missing / NaN
        if raw_oi_delta is None or (isinstance(raw_oi_delta, (int, float)) and math.isnan(float(raw_oi_delta))):
            if self.oi_mode == "strict":
                logger.debug(f"[{self.symbol}] OI confluence strict: blocked due to missing/NaN OI delta.")
                return False, None
            elif self.oi_mode == "optional":
                if self.oi_fallback_when_nan:
                    return True, self.oi_nan_log_note
                return False, None
            return False, None

        # raw_oi_delta là số thực: phải hữu hạn (không chấp nhận Inf / -Inf)
        if not isinstance(raw_oi_delta, (int, float)):
            return False, None

        val = float(raw_oi_delta)
        if not math.isfinite(val):
            logger.warning(f"[{self.symbol}] OI confluence fail-closed: non-finite value {val}")
            return False, None

        # Giá trị số hữu hạn: yêu cầu oi_delta_pct > 0
        if val > 0.0:
            return True, None
        else:
            logger.debug(f"[{self.symbol}] OI confluence: rejected oi_delta_pct={val} <= 0")
            return False, None

    def _calculate_swing_stop(
        self,
        direction: OrderDirection,
        history_4h: pd.DataFrame,
        signal_price: float,
    ) -> Optional[float]:
        """
        Tính stop ban đầu là đáy swing gần nhất (LONG) hoặc đỉnh swing gần nhất (SHORT)
        dựa trên swing_lookback_bars nến 4h đã đóng gần nhất (Section 4.3).
        """
        if len(history_4h) < self.swing_lookback_bars:
            logger.warning(f"[{self.symbol}] Not enough history for swing stop: {len(history_4h)} < {self.swing_lookback_bars}")
            return None

        window = history_4h.iloc[-self.swing_lookback_bars:]

        if direction == OrderDirection.LONG:
            if "low" not in window.columns:
                return None
            lows = window["low"]
            if lows.isna().any():
                return None
            stop = float(lows.min())
            if not math.isfinite(stop) or stop <= 0:
                return None
            # Đảm bảo stop < signal_price
            if stop >= signal_price:
                logger.warning(f"[{self.symbol}] Swing stop invalid for LONG: stop {stop} >= signal {signal_price}")
                return None
            return stop
        else:  # SHORT
            if "high" not in window.columns:
                return None
            highs = window["high"]
            if highs.isna().any():
                return None
            stop = float(highs.max())
            if not math.isfinite(stop) or stop <= 0:
                return None
            # Đảm bảo stop > signal_price
            if stop <= signal_price:
                logger.warning(f"[{self.symbol}] Swing stop invalid for SHORT: stop {stop} <= signal {signal_price}")
                return None
            return stop

    def _broker_has_active_or_pending(self, broker_state: Any) -> bool:
        """Kiểm tra broker đã có vị thế mở hoặc lệnh pending cho symbol hay chưa."""
        if broker_state is None:
            return False

        # Kiểm tra positions
        positions = getattr(broker_state, "positions", {})
        if self.symbol in positions:
            return True

        # Kiểm tra pending_orders
        pending_orders = getattr(broker_state, "pending_orders", [])
        for order in pending_orders:
            if getattr(order, "symbol", None) == self.symbol:
                return True

        return False

    def update_trailing_stop(
        self,
        candle_4h: Dict[str, Any],
        broker: Any,
    ) -> None:
        """
        Cập nhật trailing stop loss cho các vị thế đang mở sau mỗi nến 4h đóng.
        Bám EMA50 nến 4h đã đóng theo hướng thắt chặt rủi ro (tightening-only).
        Tuyệt đối không nới stop loss và không sửa trực tiếp Position.
        """
        if broker is None or not hasattr(broker, "positions") or not hasattr(broker, "update_stop_loss"):
            return

        pos = broker.positions.get(self.symbol)
        if pos is None:
            return

        raw_ema50 = candle_4h.get(f"ema_{self.crossover_slow_ema}")
        if raw_ema50 is None or type(raw_ema50) is bool or not isinstance(raw_ema50, (int, float)):
            return

        candidate_stop = float(raw_ema50)
        if not math.isfinite(candidate_stop) or candidate_stop <= 0:
            return

        # Xác định mark price hiện tại
        mark_price = candle_4h.get("close")
        if mark_price is None or not isinstance(mark_price, (int, float)):
            mark_price = getattr(broker, "last_mark_prices", {}).get(self.symbol, pos.entry_price)
        mark_price = float(mark_price)

        # Kiểm tra điều kiện tightening-only trước khi gọi broker
        if pos.direction == OrderDirection.LONG:
            if candidate_stop > pos.stop_loss_price and candidate_stop < mark_price:
                updated = broker.update_stop_loss(self.symbol, candidate_stop)
                if updated:
                    logger.debug(f"[{self.symbol}] Trailing stop updated (LONG): {pos.stop_loss_price:.2f} -> {candidate_stop:.2f}")
        else:  # SHORT
            if candidate_stop < pos.stop_loss_price and candidate_stop > mark_price:
                updated = broker.update_stop_loss(self.symbol, candidate_stop)
                if updated:
                    logger.debug(f"[{self.symbol}] Trailing stop updated (SHORT): {pos.stop_loss_price:.2f} -> {candidate_stop:.2f}")
