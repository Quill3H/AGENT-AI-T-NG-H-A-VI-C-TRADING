"""
src/execution/order_models.py - Mô hình Dữ liệu Lệnh và Vị thế
=============================================================
Định nghĩa các Enum, Dataclass và Data Models bất biến, an toàn kiểu dữ liệu
cho hệ thống Paper Execution Engine (Giai đoạn 4).

Tuân thủ:
- Hạch toán USDT-margined isolated futures.
- Tạo ID xác định (deterministic ID), không dùng UUID ngẫu nhiên để đảm bảo tính tái lập 100%.
- Cung cấp đầy đủ trường dữ liệu phục vụ audit kế toán và đối soát rủi ro.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Union


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    MARKET_ENTRY = "MARKET_ENTRY"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    LIQUIDATION = "LIQUIDATION"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    LIQUIDATION = "LIQUIDATION"
    CIRCUIT_BREAKER_LOCK = "CIRCUIT_BREAKER_LOCK"
    FORCE_CLOSE_END_OF_DATA = "FORCE_CLOSE_END_OF_DATA"
    END_OF_DATA = "END_OF_DATA"
    MANUAL = "MANUAL"



def _validate_finite_positive(name: str, val: Any) -> float:
    """Xác thực số thực hữu hạn và dương (> 0)."""
    if type(val) is bool or not isinstance(val, (int, float)):
        raise TypeError(f"{name} must be numeric float or int, got {type(val).__name__}: {val!r}")
    f_val = float(val)
    if not math.isfinite(f_val) or f_val <= 0:
        raise ValueError(f"{name} must be finite positive number, got {f_val}")
    return f_val


def _validate_finite_non_negative(name: str, val: Any) -> float:
    """Xác thực số thực hữu hạn và không âm (>= 0)."""
    if type(val) is bool or not isinstance(val, (int, float)):
        raise TypeError(f"{name} must be numeric float or int, got {type(val).__name__}: {val!r}")
    f_val = float(val)
    if not math.isfinite(f_val) or f_val < 0:
        raise ValueError(f"{name} must be finite non-negative number, got {f_val}")
    return f_val


def _ensure_utc(ts: Any) -> datetime:
    """Đảm bảo datetime có tzinfo UTC."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    raise TypeError(f"Expected datetime object, got {type(ts).__name__}: {ts!r}")


@dataclass
class OrderRequest:
    """
    Yêu cầu mở vị thế gửi từ chiến lược (Strategy) đến Paper Broker.
    Chỉ sinh tín hiệu tại nến đóng, thực thi tại open nến tiếp theo.
    """
    symbol: str
    direction: OrderDirection
    signal_price: float
    stop_loss_price: float
    signal_time: datetime
    conviction_tier: str = "normal"
    take_profit_price: Optional[float] = None
    leverage: float = 1.0
    base_risk_percent: float = 0.02
    risk_percent: Optional[float] = None
    requested_quantity: Optional[float] = None
    order_type: OrderType = OrderType.MARKET_ENTRY
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = str(self.symbol).strip().upper()
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if isinstance(self.direction, str):
            self.direction = OrderDirection(self.direction.upper())
        if isinstance(self.order_type, str):
            self.order_type = OrderType(self.order_type.upper())
        self.signal_price = _validate_finite_positive("signal_price", self.signal_price)
        self.stop_loss_price = _validate_finite_positive("stop_loss_price", self.stop_loss_price)
        if self.take_profit_price is not None:
            self.take_profit_price = _validate_finite_positive("take_profit_price", self.take_profit_price)
        self.leverage = _validate_finite_positive("leverage", self.leverage)
        if self.leverage < 1.0:
            raise ValueError(f"leverage must be >= 1.0, got {self.leverage}")
        self.base_risk_percent = _validate_finite_positive("base_risk_percent", self.base_risk_percent)
        if self.risk_percent is not None:
            self.risk_percent = _validate_finite_positive("risk_percent", self.risk_percent)
        if self.requested_quantity is not None:
            self.requested_quantity = _validate_finite_positive("requested_quantity", self.requested_quantity)
        self.signal_time = _ensure_utc(self.signal_time)

        # Kiểm tra tính đúng chiều của Stop Loss ngay tại lúc tạo request
        if self.direction == OrderDirection.LONG and self.stop_loss_price >= self.signal_price:
            raise ValueError(
                f"For LONG order, stop_loss_price ({self.stop_loss_price}) must be < signal_price ({self.signal_price})"
            )
        if self.direction == OrderDirection.SHORT and self.stop_loss_price <= self.signal_price:
            raise ValueError(
                f"For SHORT order, stop_loss_price ({self.stop_loss_price}) must be > signal_price ({self.signal_price})"
            )
        if self.take_profit_price is not None:
            if self.direction == OrderDirection.LONG and self.take_profit_price <= self.signal_price:
                raise ValueError(
                    f"For LONG order, take_profit_price ({self.take_profit_price}) must be > signal_price ({self.signal_price})"
                )
            if self.direction == OrderDirection.SHORT and self.take_profit_price >= self.signal_price:
                raise ValueError(
                    f"For SHORT order, take_profit_price ({self.take_profit_price}) must be < signal_price ({self.signal_price})"
                )


@dataclass
class OrderExecutionRecord:
    """
    Bản ghi trạng thái và kết quả xử lý lệnh của Paper Broker.
    """
    order_id: str
    symbol: str
    direction: OrderDirection
    status: OrderStatus
    requested_at: datetime
    processed_at: Optional[datetime] = None
    reference_price: float = 0.0
    actual_fill_price: float = 0.0
    slippage_usd: float = 0.0
    filled_quantity: float = 0.0
    notional_usd: float = 0.0
    fee_usd: float = 0.0
    rejection_reasons: List[str] = field(default_factory=list)

    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED


@dataclass
class Position:
    """
    Đại diện cho vị thế phái sinh đang mở (Isolated Margin).
    """
    position_id: str
    symbol: str
    direction: OrderDirection
    quantity: float
    entry_price: float
    initial_margin: float
    isolated_collateral: float
    leverage: float
    stop_loss_price: float
    liquidation_price: float
    opened_at: datetime
    conviction_tier: str = "normal"
    take_profit_price: Optional[float] = None
    cumulative_funding: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    entry_fee: float = 0.0
    exit_fee: float = 0.0

    def notional_value(self, current_price: float) -> float:
        """Giá trị danh nghĩa theo giá hiện tại."""
        return self.quantity * _validate_finite_positive("current_price", current_price)

    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """
        Tính lãi/lỗ chưa thực hiện (Unrealized PnL).
        LONG: Qty * (Mark - Entry)
        SHORT: Qty * (Entry - Mark)
        """
        p = _validate_finite_positive("current_price", current_price)
        if self.direction == OrderDirection.LONG:
            return self.quantity * (p - self.entry_price)
        else:
            return self.quantity * (self.entry_price - p)


@dataclass
class TradeRecord:
    """
    Bản ghi đầy đủ của một giao dịch đã tất toán (Position đã đóng hoàn tất).
    Dùng cho việc kiểm toán, thống kê streak của Circuit Breaker và sinh báo cáo.
    """
    trade_id: str
    symbol: str
    direction: OrderDirection
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    leverage: float
    initial_margin: float
    gross_price_pnl: float
    entry_fee: float
    exit_fee: float
    funding_cashflow: float
    net_pnl: float
    return_pct: float
    exit_reason: ExitReason
    intrabar_estimated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FundingEvent:
    """
    Ghi nhận sự kiện thanh toán phí Funding (00:00, 08:00, 16:00 UTC).
    """
    event_id: str
    timestamp: datetime
    symbol: str
    position_id: str
    funding_rate: float
    settlement_mark_price: float
    position_quantity: float
    cashflow_usd: float  # Âm nếu trả phí, dương nếu nhận phí


@dataclass
class AccountSnapshot:
    """
    Ảnh chụp số dư và trạng thái tài khoản tại từng mốc thời gian.
    """
    timestamp: datetime
    wallet_balance: float
    reserved_collateral: float
    available_margin: float
    unrealized_pnl: float
    equity: float
    open_positions_count: int
    is_halted: bool = False
