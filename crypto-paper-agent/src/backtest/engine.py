"""
src/backtest/engine.py
======================
Cỗ máy Backtest tối thiểu cho Giai đoạn 5 (Trend Following).
Tuân thủ nghiêm ngặt ANTIGRAVITY_STAGE_05_TASK.md:
1. Nhận config, data_4h, data_15m, strategy và PaperBroker qua dependency injection.
2. Validate schema, index UTC, thứ tự tăng đơn điệu, không duplicate timestamp và OHLC hữu hạn/hợp lệ.
3. Tính feature trên từng timeframe bằng pipeline hiện có (add_all_features), không dùng logic riêng.
4. Hợp nhất đa khung causal: tại thời điểm quyết định chỉ cho strategy thấy nến 4h có close_time <= decision_time.
5. Với mỗi nến 15m: xử lý PaperBroker theo đúng event time; sau khi nến đóng mới đánh giá nến 4h vừa hoàn tất,
   cập nhật trailing stop và submit signal để khớp ở open 15m kế tiếp.
6. Không tự sao chép logic phí, slippage, funding, liquidation, risk gate hoặc accounting ra ngoài PaperBroker.
7. Kết thúc dataset bằng PaperBroker.finalize(...) với tham số force_close tùy chọn (mặc định True).
8. Cố định random seed (deterministic replay).
"""
from datetime import datetime, timedelta, timezone
import math
import random
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
import numpy as np
import pandas as pd

from src.data_layer.cache_manager import timeframe_to_timedelta
from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    OrderDirection,
    OrderStatus,
    TradeRecord,
    _ensure_utc,
    _validate_finite_positive,
)
from src.execution.paper_broker import PaperBroker
from src.features import add_all_features
from src.strategies.base_strategy import BaseStrategy


class BacktestEngine:
    """
    Cỗ máy thực thi Backtest đa khung thời gian 4h/15m.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        data_4h: pd.DataFrame,
        data_15m: pd.DataFrame,
        strategy: BaseStrategy,
        broker: Optional[PaperBroker] = None,
        symbol: str = "BTCUSDT",
    ):
        # 1. Cố định random seed đảm bảo tính tất định 100%
        random.seed(42)
        np.random.seed(42)

        self.config = config
        self.symbol = symbol.upper()

        # 2. Tiền thẩm định schema và dữ liệu (Fail-closed nếu dữ liệu lỗi)
        self.validate_dataset(data_4h, "4h")
        self.validate_dataset(data_15m, "15m")

        # 3. Chuẩn bị Feature cho nến 4h nếu chưa có
        self.data_4h = self._prepare_features(data_4h.copy())
        self.data_15m = data_15m.copy()

        # 4. Kiểm tra khoảng thời gian giao nhau giữa 4h và 15m
        start_4h = self.data_4h.index[0]
        end_4h = self.data_4h.index[-1]
        start_15m = self.data_15m.index[0]
        end_15m = self.data_15m.index[-1]

        if start_15m > end_4h or end_15m < start_4h:
            raise ValueError(
                f"Time range mismatch: 15m ({start_15m} to {end_15m}) does not overlap with 4h ({start_4h} to {end_4h})"
            )

        # 5. Dependency Injection: Strategy và PaperBroker
        self.strategy = strategy
        if broker is not None:
            self.broker = broker
        else:
            self.broker = PaperBroker(config=self.config)

        # 6. Timeframes & Durations
        strat_cfg = self.config.get("strategy", {})
        self.timeframe_signal = strat_cfg.get("timeframe_signal", "4h")
        self.timeframe_execution = strat_cfg.get("timeframe_execution", "15m")
        self.duration_signal = timeframe_to_timedelta(self.timeframe_signal)
        self.duration_exec = timeframe_to_timedelta(self.timeframe_execution)
        for frame, duration in ((self.data_4h, self.duration_signal), (self.data_15m, self.duration_exec)):
            if (frame.index.to_series().diff().dropna() < duration).any():
                raise ValueError("overlapping candles for configured timeframe")
        if hasattr(strategy, "prime"):
            warm = self.data_4h.loc[self.data_4h.index + self.duration_signal <= self.data_15m.index[0]]
            strategy.prime(warm)

        # 7. Bộ đếm theo dõi
        self.submitted_orders_count = 0

    @staticmethod
    def validate_dataset(df: Any, name: str) -> None:
        """
        Thẩm định tính toàn vẹn và hợp lệ toán học của dataset đầu vào (Section 4.4 & Test 8-10).
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Dataset {name} must be a pd.DataFrame, got {type(df).__name__}")

        if df.empty:
            raise ValueError(f"Dataset {name} is empty.")

        # Thẩm định Index
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError(f"Dataset {name} index must be DatetimeIndex, got {type(df.index).__name__}")

        if df.index.tz is None or str(df.index.tz) not in ("UTC", "UTC+00:00"):
            raise ValueError(f"Dataset {name} DatetimeIndex must have UTC timezone.")

        if not df.index.is_monotonic_increasing:
            raise ValueError(f"Dataset {name} timestamps must be strictly monotonic increasing.")

        if df.index.has_duplicates:
            raise ValueError(f"Dataset {name} contains duplicate timestamps.")

        # Thẩm định các cột OHLCV bắt buộc
        req_cols = ["open", "high", "low", "close", "volume"]
        for c in req_cols:
            if c not in df.columns:
                raise ValueError(f"Dataset {name} missing required column '{c}'")

        # Thẩm định số học hữu hạn và dương
        for c in ["open", "high", "low", "close"]:
            col_data = df[c]
            if col_data.isna().any():
                raise ValueError(f"Dataset {name} column '{c}' contains NaN values.")
            # Kiểm tra kiểu không phải boolean
            if (col_data.apply(lambda x: type(x) is bool)).any():
                raise TypeError(f"Dataset {name} column '{c}' contains boolean values.")
            arr = col_data.to_numpy(dtype=float)
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"Dataset {name} column '{c}' contains non-finite values (Inf/-Inf).")
            if not np.all(arr > 0):
                raise ValueError(f"Dataset {name} column '{c}' contains non-positive values (<= 0).")

        # Thẩm định quan hệ hình học nến: High >= max(Open, Close), Low <= min(Open, Close), High >= Low
        opens = df["open"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)

        max_oc = np.maximum(opens, closes)
        min_oc = np.minimum(opens, closes)

        if np.any(highs < max_oc - 1e-6):
            raise ValueError(f"Dataset {name} contains candles where high < max(open, close).")
        if np.any(lows > min_oc + 1e-6):
            raise ValueError(f"Dataset {name} contains candles where low > min(open, close).")
        if np.any(highs < lows):
            raise ValueError(f"Dataset {name} contains candles where high < low.")

    def _prepare_features(self, df_4h: pd.DataFrame) -> pd.DataFrame:
        """Tính toán các chỉ báo kỹ thuật trên khung 4h nếu chưa có."""
        required_indicators = ["ema_20", "ema_50", "ema_200", "rsi_14"]
        if all(col in df_4h.columns for col in required_indicators):
            return df_4h

        logger.info(f"[{self.symbol}] Calculating indicators for {len(df_4h)} 4h candles...")
        return add_all_features(df_4h, self.config)

    def run(self, force_close: bool = True) -> Dict[str, Any]:
        """
        Thực thi chu trình Backtest causal từng nến 15m.
        
        Quy trình mỗi bước nến 15m:
        1. Xử lý PaperBroker.process_candle(candle_15m) theo đúng event time.
        2. Kiểm tra xem tại thời điểm 15m close_time có nến 4h nào vừa đóng hay không.
        3. Nếu có nến 4h vừa đóng:
           - Trích xuất lịch sử 4h causal đến nến đóng đó (tuyệt đối không nhìn trước).
           - Cập nhật Trailing Stop bám EMA50 cho các vị thế mở: strategy.update_trailing_stop.
           - Đánh giá tín hiệu: strategy.on_candle_close.
           - Nếu có OrderRequest: gửi broker.submit_order (khớp tại open nến 15m kế tiếp).
        4. Sau khi duyệt hết dữ liệu 15m: gọi broker.finalize(force_close=force_close).
        5. Tổng hợp và trả về báo cáo kết quả chi tiết.
        """
        logger.info(
            f"[{self.symbol}] Starting backtest: {len(self.data_15m)} 15m bars, {len(self.data_4h)} 4h bars, force_close={force_close}."
        )

        last_15m_close: Optional[datetime] = None

        # Duyệt từng nến 15m theo thứ tự thời gian tăng dần
        for open_time, row_15m in self.data_15m.iterrows():
            open_dt = _ensure_utc(open_time)
            close_dt = open_dt + self.duration_exec
            last_15m_close = close_dt

            # Tạo dictionary nến 15m chuẩn đưa vào PaperBroker
            candle_15m = {
                "symbol": self.symbol,
                "timeframe": self.timeframe_execution,
                "open_time": open_dt,
                "close_time": close_dt,
                "timestamp": open_dt,
                "open": float(row_15m["open"]),
                "high": float(row_15m["high"]),
                "low": float(row_15m["low"]),
                "close": float(row_15m["close"]),
                "volume": float(row_15m["volume"]),
            }

            # Chuyển tiếp metadata Funding và Open Interest nếu có
            if "funding_rate" in row_15m and pd.notna(row_15m["funding_rate"]):
                candle_15m["funding_rate"] = float(row_15m["funding_rate"])
            if "funding_time" in row_15m and pd.notna(row_15m["funding_time"]):
                candle_15m["funding_time"] = row_15m["funding_time"]
            if "funding_readiness" in row_15m:
                raw_readiness = row_15m["funding_readiness"]
                if pd.isna(raw_readiness):
                    candle_15m["funding_readiness"] = raw_readiness
                elif isinstance(raw_readiness, (bool, np.bool_)):
                    candle_15m["funding_readiness"] = bool(raw_readiness)
                else:
                    # Giữ nguyên giá trị thô (str, int, float, object) để PaperBroker kiểm tra kiểu nghiêm ngặt
                    candle_15m["funding_readiness"] = raw_readiness
            if "open_interest" in row_15m and pd.notna(row_15m["open_interest"]):
                candle_15m["open_interest"] = float(row_15m["open_interest"])

            # PHA A: Xử lý khớp lệnh, funding và quản lý vị thế trên nến 15m
            self.broker.process_candle(candle_15m)

            # PHA B: Kiểm tra xem nến 15m vừa đóng có trùng mốc đóng của nến 4h nào không
            # Nến 4h bắt đầu tại open_4h = close_dt - duration_signal và đóng đúng tại close_dt
            open_4h = close_dt - self.duration_signal

            if open_4h in self.data_4h.index:
                # Nến 4h này vừa đóng hoàn toàn tại close_dt!
                # Trích xuất toàn bộ lịch sử 4h causal tính đến và bao gồm open_4h
                # Tuyệt đối không bao gồm bất kỳ nến 4h nào sau open_4h (chống lookahead bias)
                history_4h_closed = self.data_4h.loc[:open_4h]
                closed_4h_row = history_4h_closed.iloc[-1]

                candle_4h_dict = closed_4h_row.to_dict()
                candle_4h_dict["symbol"] = self.symbol
                candle_4h_dict["timeframe"] = self.timeframe_signal
                candle_4h_dict["open_time"] = open_4h
                candle_4h_dict["close_time"] = close_dt
                candle_4h_dict["timestamp"] = open_4h

                # 1. Cập nhật Trailing Stop bám EMA50 nến 4h đóng (chỉ siết chặt rủi ro)
                self.strategy.update_trailing_stop(candle_4h_dict, self.broker)

                # 2. Đánh giá tín hiệu vào lệnh mới từ chiến lược
                order_req = self.strategy.on_candle_close(
                    candle_4h=candle_4h_dict,
                    history_4h=history_4h_closed,
                    broker_state=self.broker,
                )

                if order_req is not None:
                    self.submitted_orders_count += 1
                    self.broker.submit_order(order_req)

        # Kết thúc dataset: gọi broker.finalize
        finalize_summary = self.broker.finalize(
            timestamp=last_15m_close,
            force_close=force_close,
        )

        # Tính toán các chỉ số hiệu năng và đối soát kế toán
        metrics = self._calculate_metrics(finalize_summary, force_close)
        return metrics

    def _calculate_metrics(self, finalize_summary: Dict[str, Any], force_close: bool) -> Dict[str, Any]:
        """Tổng hợp số liệu thống kê chi tiết của phiên backtest theo chuẩn Stage 6."""
        from src.report.metrics import calculate_backtest_metrics
        gap_details: Dict[str, Dict[str, Any]] = {}
        for label, frame, timeframe in (
            (self.timeframe_execution, self.data_15m, self.timeframe_execution),
            (self.timeframe_signal, self.data_4h, self.timeframe_signal),
        ):
            expected = pd.Timedelta(timeframe_to_timedelta(timeframe))
            deltas = frame.index.to_series().diff().dropna()
            gaps = deltas[deltas > expected]
            gap_details[label] = {
                "gaps_detected_count": int(len(gaps)),
                "max_gap_duration_seconds": int(gaps.max().total_seconds()) if len(gaps) else 0,
            }

        combined_gap_stats = {
            "candle_gaps_count": sum(v["gaps_detected_count"] for v in gap_details.values()),
            "max_gap_duration_seconds": max(v["max_gap_duration_seconds"] for v in gap_details.values()),
            "candle_gaps_by_timeframe": gap_details,
        }
        return calculate_backtest_metrics(
            broker=self.broker,
            config=self.config,
            start_time=self.data_15m.index[0],
            end_time=self.data_15m.index[-1],
            bars_15m_count=len(self.data_15m),
            bars_4h_count=len(self.data_4h),
            setup_count=getattr(self.strategy, "setup_count", 0),
            candidate_count=getattr(self.strategy, "candidate_count", 0),
            submitted_orders_count=self.submitted_orders_count,
            force_close=force_close,
            finalize_summary=finalize_summary,
            candle_gap_stats=combined_gap_stats,
        )

