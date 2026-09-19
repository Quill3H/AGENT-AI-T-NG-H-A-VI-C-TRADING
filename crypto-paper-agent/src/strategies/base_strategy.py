"""
src/strategies/base_strategy.py
===============================
Abstract Base Class cho các chiến lược giao dịch định lượng.
Giai đoạn 5: Hợp đồng tối thiểu, ổn định cho Trend Following.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import pandas as pd

from src.execution.order_models import OrderRequest


class BaseStrategy(ABC):
    """Lớp cơ sở trừu tượng cho chiến lược giao dịch."""

    def __init__(self, config: Dict[str, Any], symbol: str = "BTCUSDT"):
        self.config = config
        self.symbol = symbol

    @abstractmethod
    def on_candle_close(
        self,
        candle_4h: Dict[str, Any],
        history_4h: pd.DataFrame,
        broker_state: Any,
    ) -> Optional[OrderRequest]:
        """
        Được gọi mỗi khi một nến 4h đóng cửa hoàn toàn.

        Parameters
        ----------
        candle_4h : Dict[str, Any]
            Dữ liệu nến 4h vừa đóng (chứa OHLCV, indicator values: EMA20, EMA50, EMA200, RSI, OI delta...).
        history_4h : pd.DataFrame
            Lịch sử nến 4h đã đóng đến thời điểm hiện tại (index UTC).
        broker_state : Any
            Đối tượng PaperBroker hoặc trạng thái tài khoản hiện tại.

        Returns
        -------
        Optional[OrderRequest]
            Lệnh chờ khớp (Pending OrderRequest) nếu có tín hiệu thỏa mãn, hoặc None.
        """
        pass

    @abstractmethod
    def update_trailing_stop(
        self,
        candle_4h: Dict[str, Any],
        broker: Any,
    ) -> None:
        """
        Cập nhật trailing stop loss cho các vị thế đang mở sau mỗi nến 4h đóng.
        Chỉ gọi broker.update_stop_loss khi thỏa mãn điều kiện thắt chặt rủi ro.
        """
        pass
