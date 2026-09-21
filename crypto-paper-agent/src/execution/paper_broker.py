"""
src/execution/paper_broker.py - Paper Execution Engine (Event-Driven)
====================================================================
Triển khai cỗ máy khớp lệnh mô phỏng và hạch toán tài khoản cho giao dịch phái sinh
(USDT-margined isolated futures).

Tuân thủ:
1. Chu trình xử lý 5 pha chống nhìn trước (Anti-Lookahead Pipeline):
   - Pha 1: Open time & Gap check (xử lý gap exit tại giá open cho vị thế mang sang nến sau).
   - Pha 2: Funding settlement (chỉ áp dụng cho vị thế mở trước mốc và sống qua Pha 1).
   - Pha 3: Pending market entry (khớp tại open + slippage, đối soát qua Risk Invariant Gate).
   - Pha 4: Intrabar protection (quét range [low, high], ưu tiên Liquidation > SL > TP).
   - Pha 5: Close time & Mark-to-market (tính unrealized PnL, equity, nhận signal cho nến sau).
2. Hạch toán số học chính xác, kiểm tra bất biến tài khoản tự động sau mỗi nến.
3. Tích hợp chặt chẽ với Risk Manager (sizing, liquidation solver, circuit breaker).
"""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from loguru import logger

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    FundingEvent,
    OrderDirection,
    OrderExecutionRecord,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionStatus,
    TradeRecord,
    _ensure_utc,
    _validate_finite_non_negative,
    _validate_finite_positive,
)
from src.features.news_calendar import NewsCalendarFilter
from src.risk.circuit_breakers import CircuitBreakerState
from src.risk.invariant_checks import (
    check_all_invariants,
    calculate_estimated_liquidation_price,
    get_mmr_tier,
    get_brackets_for_symbol,
    parse_simulation_timestamp,
)
from src.risk.position_sizing import calculate_position_size


def _validate_config(config: dict) -> None:
    """Xác thực định dạng và miền giá trị hữu hạn của cấu hình hệ thống (E8, H4)."""
    if not isinstance(config, dict):
        raise TypeError(f"config must be dict, got {type(config).__name__}")

    # 1. account
    if "account" in config:
        acc = config["account"]
        if not isinstance(acc, dict):
            raise TypeError(f"account section must be dict, got {type(acc).__name__}")
        if "initial_equity_usd" in acc:
            val = acc["initial_equity_usd"]
            if type(val) is bool or not isinstance(val, (int, float)):
                raise TypeError(f"initial_equity_usd must be numeric, got {type(val).__name__}")
            f_val = float(val)
            if not math.isfinite(f_val) or f_val <= 0:
                raise ValueError(f"initial_equity_usd must be finite positive number, got {f_val}")

    # 2. fees
    if "fees" in config:
        fees = config["fees"]
        if not isinstance(fees, dict):
            raise TypeError(f"fees section must be dict, got {type(fees).__name__}")
        for fee_name in ("slippage_pct", "taker_pct", "maker_pct"):
            if fee_name in fees:
                val = fees[fee_name]
                if type(val) is bool or not isinstance(val, (int, float)):
                    raise TypeError(f"{fee_name} must be numeric, got {type(val).__name__}")
                f_val = float(val)
                if not math.isfinite(f_val) or f_val < 0 or f_val >= 1.0:
                    raise ValueError(f"{fee_name} must be finite in [0.0, 1.0), got {f_val}")

    # 3. funding_rate
    if "funding_rate" in config:
        fnd = config["funding_rate"]
        if not isinstance(fnd, dict):
            raise TypeError(f"funding_rate section must be dict, got {type(fnd).__name__}")
        if "settlement_hours_utc" in fnd:
            hours = fnd["settlement_hours_utc"]
            if not isinstance(hours, (list, tuple, set)):
                raise TypeError(f"settlement_hours_utc must be a list/set, got {type(hours).__name__}")
            for h in hours:
                if type(h) is bool or not isinstance(h, int) or not (0 <= h <= 23):
                    raise ValueError(f"settlement hour must be int in [0, 23], got {h}")

    # 4. execution
    if "execution" in config:
        exc = config["execution"]
        if not isinstance(exc, dict):
            raise TypeError(f"execution section must be dict, got {type(exc).__name__}")
        if "settlement_hours_utc" in exc:
            hours = exc["settlement_hours_utc"]
            if not isinstance(hours, (list, tuple, set)):
                raise TypeError(f"settlement_hours_utc must be a list/set, got {type(hours).__name__}")
            for h in hours:
                if type(h) is bool or not isinstance(h, int) or not (0 <= h <= 23):
                    raise ValueError(f"settlement hour must be int in [0, 23], got {h}")

    # 5. leverage_brackets
    if "leverage_brackets" in config:
        brk = config["leverage_brackets"]
        if not isinstance(brk, dict):
            raise TypeError(f"leverage_brackets section must be dict, got {type(brk).__name__}")

    # 6. circuit_breakers
    if "circuit_breakers" in config:
        cb = config["circuit_breakers"]
        if not isinstance(cb, dict):
            raise TypeError(f"circuit_breakers section must be dict, got {type(cb).__name__}")

    # 7. risk
    if "risk" in config:
        rsk = config["risk"]
        if not isinstance(rsk, dict):
            raise TypeError(f"risk section must be dict, got {type(rsk).__name__}")



class PaperBroker:
    """
    Paper Execution Engine mô phỏng sàn giao dịch phái sinh theo nến (Event-Driven).
    """
    def __init__(
        self,
        config: Optional[dict] = None,
        initial_balance: Optional[float] = None,
        circuit_breaker: Optional[CircuitBreakerState] = None,
        news_filter: Optional[NewsCalendarFilter] = None,
        funding_hours: Optional[Set[int]] = None,
    ):
        self.config: dict = config or {}
        _validate_config(self.config)

        acc_cfg = self.config.get("account", {})
        fees_cfg = self.config.get("fees", {})

        # 1. Số dư và tham số vốn
        if initial_balance is not None:
            self.initial_balance: float = _validate_finite_positive("initial_balance", initial_balance)
        else:
            self.initial_balance = float(acc_cfg.get("initial_equity_usd", 10000.0))

        self.wallet_balance: float = self.initial_balance

        # 2. Phí & Trượt giá
        self.slippage_pct: float = float(fees_cfg.get("slippage_pct", 0.0003))
        self.taker_fee_pct: float = float(fees_cfg.get("taker_pct", 0.0005))
        self.maker_fee_pct: float = float(fees_cfg.get("maker_pct", 0.0002))

        # Đọc funding_hours theo thứ tự ưu tiên (E1)
        if funding_hours is not None:
            self.funding_hours: Set[int] = set()
            for h in funding_hours:
                if type(h) is bool or not isinstance(h, int) or not (0 <= h <= 23):
                    raise ValueError(f"Invalid funding hour: {h}")
                self.funding_hours.add(h)
        elif "funding_rate" in self.config and "settlement_hours_utc" in self.config["funding_rate"]:
            self.funding_hours = set(self.config["funding_rate"]["settlement_hours_utc"])
        else:
            self.funding_hours = {0, 8, 16}

        # 3. Quản lý rủi ro & Ngắt mạch
        if circuit_breaker is not None:
            self.circuit_breaker: CircuitBreakerState = circuit_breaker
        else:
            self.circuit_breaker = CircuitBreakerState.from_config(self.config)

        if news_filter is not None:
            self.news_filter: NewsCalendarFilter = news_filter
        else:
            self.news_filter = NewsCalendarFilter(self.config)

        # 4. Trạng thái vị thế và đơn hàng
        self.positions: Dict[str, Position] = {}  # symbol -> Position (tối đa 1 position/symbol)
        self.pending_orders: List[OrderRequest] = []
        self.pending_closes: Dict[str, datetime] = {}
        self.order_history: List[OrderExecutionRecord] = []
        self.trade_history: List[TradeRecord] = []
        self.funding_history: List[FundingEvent] = []
        self.account_snapshots: List[AccountSnapshot] = []

        # 5. Đồng hồ & Biến cờ
        self.current_time: Optional[datetime] = None
        self.last_candle_open_time: Optional[datetime] = None
        self.last_candle_open_time_per_symbol: Dict[str, datetime] = {}
        self.current_batch_open_time: Optional[datetime] = None
        self.symbols_in_current_batch: Set[str] = set()
        self.is_halted: bool = False
        self.is_finalized: bool = False
        self.last_mark_prices: Dict[str, float] = {}
        self._settled_funding_keys: Set[Tuple[str, datetime]] = set()
        self._is_handling_cb_lock: bool = False

        # 6. Bộ đếm định danh xác định (Deterministic ID generator)
        self._order_seq: int = 0
        self._trade_seq: int = 0
        self._funding_seq: int = 0

    @property
    def reserved_collateral(self) -> float:
        """Tổng ký quỹ đang bị khóa trong các vị thế mở."""
        return sum(pos.isolated_collateral for pos in self.positions.values())

    @property
    def unrealized_pnl(self) -> float:
        """Tổng lãi/lỗ chưa thực hiện của các vị thế mở (theo mark price gần nhất)."""
        # Sẽ được tính chính xác khi có nến mark price
        return sum(getattr(pos, "_last_unrealized_pnl", 0.0) for pos in self.positions.values())

    @property
    def equity(self) -> float:
        """Tổng giá trị vốn tài khoản = Wallet Balance + Unrealized PnL."""
        return self.wallet_balance + self.unrealized_pnl

    @property
    def available_margin(self) -> float:
        """Ký quỹ khả dụng = Wallet Balance - Reserved Collateral."""
        return self.wallet_balance - self.reserved_collateral

    @property
    def settled_funding_keys(self) -> Set[Tuple[str, datetime]]:
        """Tập hợp các mốc (symbol, timestamp) funding đã được thanh toán thành công."""
        return self._settled_funding_keys

    @settled_funding_keys.setter
    def settled_funding_keys(self, val: Set[Tuple[str, datetime]]) -> None:
        self._settled_funding_keys = set(val)

    def _next_order_id(self, symbol: str, dt: datetime) -> str:
        self._order_seq += 1
        date_str = dt.strftime("%Y%m%d")
        sym_clean = symbol.replace("/", "").replace("-", "").upper()
        return f"ORD_{sym_clean}_{date_str}_{self._order_seq:04d}"

    def _next_trade_id(self, symbol: str, dt: datetime) -> str:
        self._trade_seq += 1
        date_str = dt.strftime("%Y%m%d")
        sym_clean = symbol.replace("/", "").replace("-", "").upper()
        return f"TRD_{sym_clean}_{date_str}_{self._trade_seq:04d}"

    def _next_funding_id(self, symbol: str, dt: datetime) -> str:
        self._funding_seq += 1
        date_str = dt.strftime("%Y%m%d")
        sym_clean = symbol.replace("/", "").replace("-", "").upper()
        return f"FND_{sym_clean}_{date_str}_{self._funding_seq:04d}"

    def submit_order(self, request: OrderRequest) -> OrderExecutionRecord:
        """
        Nhận yêu cầu mở lệnh từ chiến lược (sinh tại close của nến đã đóng).
        Lệnh được xếp hàng vào pending_orders để thực thi tại open của nến tiếp theo.
        """
        if self.is_finalized:
            rec = OrderExecutionRecord(
                order_id=self._next_order_id(request.symbol, request.signal_time),
                symbol=request.symbol,
                direction=request.direction,
                status=OrderStatus.REJECTED,
                requested_at=request.signal_time,
                order_type=request.order_type,
                reference_price=request.signal_price,
                rejection_reasons=["EXECUTION_REJECT_FINALIZED: Broker has finalized (end of data)."],
                metadata=dict(request.metadata) if getattr(request, "metadata", None) else {},
            )
            self.order_history.append(rec)
            return rec

        if self.is_halted:
            rec = OrderExecutionRecord(
                order_id=self._next_order_id(request.symbol, request.signal_time),
                symbol=request.symbol,
                direction=request.direction,
                status=OrderStatus.REJECTED,
                requested_at=request.signal_time,
                order_type=request.order_type,
                reference_price=request.signal_price,
                rejection_reasons=["EXECUTION_REJECT_ACCOUNT_HALTED: Account is halted due to insolvency or circuit breaker."],
                metadata=dict(request.metadata) if getattr(request, "metadata", None) else {},
            )
            self.order_history.append(rec)
            return rec

        # Kiểm tra xem symbol đã có vị thế mở chưa (Chính sách 1 vị thế/symbol)
        if request.symbol in self.positions:
            rec = OrderExecutionRecord(
                order_id=self._next_order_id(request.symbol, request.signal_time),
                symbol=request.symbol,
                direction=request.direction,
                status=OrderStatus.REJECTED,
                requested_at=request.signal_time,
                order_type=request.order_type,
                reference_price=request.signal_price,
                rejection_reasons=[f"EXECUTION_REJECT_POSITION_EXISTS: Symbol {request.symbol} already has an open position."],
                metadata=dict(request.metadata) if getattr(request, "metadata", None) else {},
            )
            self.order_history.append(rec)
            return rec

        # Kiểm tra xem đã có lệnh pending cho symbol này chưa
        for pending in self.pending_orders:
            if pending.symbol == request.symbol:
                rec = OrderExecutionRecord(
                    order_id=self._next_order_id(request.symbol, request.signal_time),
                    symbol=request.symbol,
                    direction=request.direction,
                    status=OrderStatus.REJECTED,
                    requested_at=request.signal_time,
                    order_type=request.order_type,
                    reference_price=request.signal_price,
                    rejection_reasons=[f"EXECUTION_REJECT_PENDING_ORDER_EXISTS: Pending order for {request.symbol} already queued."],
                    metadata=dict(request.metadata) if getattr(request, "metadata", None) else {},
                )
                self.order_history.append(rec)
                return rec

        rec = OrderExecutionRecord(
            order_id=self._next_order_id(request.symbol, request.signal_time),
            symbol=request.symbol,
            direction=request.direction,
            status=OrderStatus.PENDING,
            requested_at=request.signal_time,
            order_type=request.order_type,
            reference_price=request.signal_price,
            metadata=dict(request.metadata) if getattr(request, "metadata", None) else {},
        )
        self.pending_orders.append(request)
        self.order_history.append(rec)
        return rec

    def process_candle(self, candle: Union[dict, Any]) -> Dict[str, Any]:
        """
        Xử lý 1 nến theo quy trình 5 pha chống nhìn trước:
        Pha 1: Open time & Gap Exits
        Pha 2: Funding Settlement (nếu trùng mốc)
        Pha 3: Pending Market Entry & Risk Gate
        Pha 4: Intrabar Protection (High / Low: Liquidation > SL > TP)
        Pha 5: Close time & Mark to Market
        """
        # =========================================================
        # PREFLIGHT PHASE - TUYỆT ĐỐI KHÔNG MUTATE BẤT KỲ TRƯỜNG NÀO CỦA SELF NẾU NẾN LỖI (E6)
        # =========================================================
        if self.is_finalized:
            raise RuntimeError("Cannot process candle after broker has finalized (terminal session).")

        if not isinstance(candle, dict):
            raise TypeError(f"candle must be dict, got {type(candle).__name__}")

        # 1. Xác thực OHLC
        for k in ("open", "high", "low", "close"):
            if k not in candle:
                raise ValueError(f"Candle missing required key: {k}")
        open_p = _validate_finite_positive("open", candle["open"])
        high_p = _validate_finite_positive("high", candle["high"])
        low_p = _validate_finite_positive("low", candle["low"])
        close_p = _validate_finite_positive("close", candle["close"])

        if high_p < max(open_p, close_p) - 1e-6 or low_p > min(open_p, close_p) + 1e-6 or high_p < low_p:
            raise ValueError(f"Malformed candle OHLC values: O={open_p}, H={high_p}, L={low_p}, C={close_p}")

        # 2. Xác thực open_time
        if "open_time" in candle:
            open_time = _ensure_utc(candle["open_time"])
        elif "timestamp" in candle:
            open_time = _ensure_utc(candle["timestamp"])
        else:
            raise ValueError("Candle missing open_time or timestamp")

        # 3. Phân tích timeframe và close_time (E6)
        timeframe_str = candle.get("timeframe", self.config.get("data", {}).get("timeframes", ["1m"])[0])
        duration = self._parse_timeframe_duration(timeframe_str)

        if "close_time" in candle and candle["close_time"] is not None:
            close_time = _ensure_utc(candle["close_time"])
            if close_time <= open_time:
                raise ValueError(f"Invalid candle close_time ({close_time}) <= open_time ({open_time})")
            if close_time != open_time + duration:
                raise ValueError(f"Candle close_time ({close_time}) != open_time + duration ({open_time + duration})")
        else:
            close_time = open_time + duration

        # 4. Xác định symbol
        symbol = str(candle.get("symbol", self.config.get("data", {}).get("futures_symbol", "BTCUSDT"))).upper()

        # 5. Kiểm tra tính đơn điệu của thời gian theo symbol và watermark batch (H3)
        last_sym_open = self.last_candle_open_time_per_symbol.get(symbol)
        if last_sym_open is not None and open_time <= last_sym_open:
            raise ValueError(
                f"Time reversal or duplicate in candle sequence for {symbol}: {open_time} <= {last_sym_open}"
            )

        if self.current_batch_open_time is not None:
            if open_time < self.current_batch_open_time:
                raise ValueError(
                    f"Time reversal in candle batch sequence: {open_time} < current batch {self.current_batch_open_time}"
                )
            elif open_time == self.current_batch_open_time:
                if symbol in self.symbols_in_current_batch:
                    raise ValueError(
                        f"Duplicate candle for {symbol} at open_time {open_time} in current batch"
                    )

        # 6. Kiểm tra bỏ sót mốc Funding Settlement khi đang có vị thế mở (E1, H3)
        if last_sym_open is not None and symbol in self.positions:
            t_cur = last_sym_open.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            while t_cur < open_time:
                if t_cur > last_sym_open and t_cur.hour in self.funding_hours:
                    raise ValueError(f"Data gap: candle for {symbol} skipped funding settlement at {t_cur.isoformat()} while position is open.")
                t_cur += timedelta(hours=1)

        # 7. Kiểm tra Funding Rate, Metadata Provenance và Solver Pre-check (E1, H6, J1, J2)
        if open_time.hour in self.funding_hours and open_time.minute == 0 and open_time.second == 0:
            if symbol in self.positions:
                pos = self.positions[symbol]
                # Nếu vị thế sẽ gap exit (TP/SL/Liq) ngay tại Pha 1 thì không cần funding
                will_gap_exit = False
                if pos.direction == OrderDirection.LONG:
                    if (pos.take_profit_price is not None and open_p >= pos.take_profit_price) or \
                       open_p <= pos.stop_loss_price or open_p <= pos.liquidation_price:
                        will_gap_exit = True
                else:
                    if (pos.take_profit_price is not None and open_p <= pos.take_profit_price) or \
                       open_p >= pos.stop_loss_price or open_p >= pos.liquidation_price:
                        will_gap_exit = True

                if not will_gap_exit:
                    raw_rate = candle.get("funding_rate")
                    if raw_rate is None or type(raw_rate) is bool or not isinstance(raw_rate, (int, float)):
                        raise ValueError(f"Missing or invalid funding rate at settlement boundary {open_time.isoformat()}: {raw_rate!r}")
                    f_rate = float(raw_rate)
                    if not math.isfinite(f_rate):
                        raise ValueError(f"Non-finite funding rate at settlement boundary {open_time.isoformat()}: {f_rate}")

                    # J1 & K1: Bắt buộc funding_readiness is True (kiểu bool) vô điều kiện
                    if "funding_readiness" not in candle:
                        raise ValueError(f"Missing funding_readiness at settlement boundary {open_time.isoformat()} for {symbol}")
                    raw_readiness = candle.get("funding_readiness")
                    if type(raw_readiness) is not bool:
                        raise TypeError(f"Invalid funding_readiness type: expected bool, got {type(raw_readiness).__name__} ({raw_readiness!r})")
                    if raw_readiness is False:
                        raise ValueError(f"Funding data marked not ready at settlement boundary {open_time.isoformat()} for {symbol}")
                    if raw_readiness is not True:
                        raise ValueError(f"Funding readiness must be True at settlement boundary {open_time.isoformat()} for {symbol}")

                    # J1 & K1: Bắt buộc source timestamp hợp lệ vô điều kiện
                    f_time = candle.get("funding_time")
                    if f_time is None:
                        f_time = candle.get("funding_timestamp") or candle.get("funding_source_time")
                    if f_time is None:
                        raise ValueError(f"Missing funding source timestamp at settlement boundary {open_time.isoformat()} for {symbol}")
                    if type(f_time) is bool or not isinstance(f_time, (datetime, str, int, float)):
                        raise TypeError(f"Invalid funding timestamp type: {type(f_time).__name__} ({f_time!r})")
                    f_dt = _ensure_utc(f_time)
                    if f_dt > open_time:
                        raise ValueError(f"Funding source time {f_dt.isoformat()} is in future relative to open_time {open_time.isoformat()} (lookahead bias)")
                    if f_dt < open_time - timedelta(hours=24):
                        raise ValueError(f"Funding source time {f_dt.isoformat()} is excessively stale (>24h before {open_time.isoformat()})")

                    # J2: Pre-check liquidation solver với candidate collateral (zero mutation if solver fails)
                    direction_sign = 1.0 if pos.direction == OrderDirection.LONG else -1.0
                    cand_cashflow = -direction_sign * pos.quantity * open_p * f_rate
                    cand_collateral = pos.isolated_collateral + cand_cashflow
                    _ = self._calculate_liquidation_price_for_collateral(
                        symbol=pos.symbol,
                        direction=pos.direction,
                        quantity=pos.quantity,
                        entry_price=pos.entry_price,
                        collateral=cand_collateral,
                        position_id=pos.position_id,
                    )

        # 8. Kiểm tra provenance nguồn dữ liệu funding nếu được cung cấp (H6)
        f_time_gen = candle.get("funding_time") or candle.get("funding_timestamp") or candle.get("funding_source_time")
        if f_time_gen is not None:
            f_dt_gen = _ensure_utc(f_time_gen)
            if f_dt_gen > open_time:
                raise ValueError(f"Funding source time {f_dt_gen.isoformat()} is in future relative to open_time {open_time.isoformat()} (lookahead bias)")
            if f_dt_gen < open_time - timedelta(hours=24):
                raise ValueError(f"Funding source time {f_dt_gen.isoformat()} is excessively stale (>24h before {open_time.isoformat()})")

        # =========================================================
        # HẾT PREFLIGHT - TẤT CẢ DỮ LIỆU ĐÃ HỢP LỆ, BẮT ĐẦU CẬP NHẬT TRẠNG THÁI VÀ THỰC THI
        # =========================================================
        if self.current_batch_open_time is None or open_time > self.current_batch_open_time:
            self.current_batch_open_time = open_time
            self.symbols_in_current_batch = {symbol}
        else:
            self.symbols_in_current_batch.add(symbol)

        self.last_candle_open_time_per_symbol[symbol] = open_time
        self.last_candle_open_time = open_time
        self.current_time = open_time
        self.last_mark_prices[symbol] = open_p

        candle_events = []

        # PHA 1: Open Time & Gap Exits (Gap Liq > Gap SL > Gap TP)
        self.circuit_breaker.advance_time(open_time)

        if symbol in self.positions:
            pos = self.positions[symbol]
            gap_exit_triggered = False
            gap_reason = None
            gap_exit_price = open_p

            if pos.direction == OrderDirection.LONG:
                if open_p <= pos.liquidation_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.LIQUIDATION
                    gap_exit_price = open_p * (1.0 - self.slippage_pct)
                elif open_p <= pos.stop_loss_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.STOP_LOSS
                    gap_exit_price = open_p * (1.0 - self.slippage_pct)
                elif pos.take_profit_price is not None and open_p >= pos.take_profit_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.TAKE_PROFIT
                    gap_exit_price = open_p * (1.0 - self.slippage_pct)
            else:  # SHORT
                if open_p >= pos.liquidation_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.LIQUIDATION
                    gap_exit_price = open_p * (1.0 + self.slippage_pct)
                elif open_p >= pos.stop_loss_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.STOP_LOSS
                    gap_exit_price = open_p * (1.0 + self.slippage_pct)
                elif pos.take_profit_price is not None and open_p <= pos.take_profit_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.TAKE_PROFIT
                    gap_exit_price = open_p * (1.0 + self.slippage_pct)

            if gap_exit_triggered and gap_reason is not None:
                trade_rec = self._execute_exit(
                    position=pos,
                    exit_price=gap_exit_price,
                    exit_time=open_time,
                    exit_reason=gap_reason,
                    intrabar_estimated=False,
                )
                candle_events.append({"type": "GAP_EXIT", "trade": trade_rec})

        # Gap partial take-profits execute before funding, just like full gap TP.
        if symbol in self.positions:
            pos = self.positions[symbol]
            targets = pos.metadata.get("partial_targets", [])
            for idx in range(pos.metadata.get("partials_done", 0), len(targets)):
                target, fraction = targets[idx]
                crossed = open_p >= target if pos.direction == OrderDirection.LONG else open_p <= target
                if not crossed:
                    break
                price = open_p * (1 - self.slippage_pct if pos.direction == OrderDirection.LONG else 1 + self.slippage_pct)
                self._execute_exit(pos, price, open_time, ExitReason.TAKE_PROFIT,
                                   quantity=pos.metadata["original_quantity"] * fraction)
                if symbol not in self.positions:
                    break
                pos = self.positions[symbol]
                pos.metadata["partials_done"] = idx + 1
                pos.metadata["breakeven_pending"] = True

        # PHA 2: Funding Settlement (chỉ cho vị thế còn sống qua Pha 1)
        if symbol in self.positions:
            pos = self.positions[symbol]
            if open_time.hour in self.funding_hours and open_time.minute == 0 and open_time.second == 0:
                f_key = (symbol, open_time)
                if f_key not in self._settled_funding_keys:
                    raw_rate = candle.get("funding_rate", 0.0)
                    f_rate = float(raw_rate)
                    funding_evt = self._apply_funding_settlement(
                        position=pos,
                        timestamp=open_time,
                        funding_rate=f_rate,
                        mark_price=open_p,
                    )
                    self._settled_funding_keys.add(f_key)
                    candle_events.append({"type": "FUNDING", "event": funding_evt})

        # A close decision made after the prior bar closes executes at this open,
        # after gap protection and funding. It cannot evade a due settlement.
        close_signal = self.pending_closes.get(symbol)
        if close_signal is not None and close_signal <= open_time:
            self.pending_closes.pop(symbol)
            if symbol in self.positions:
                pos = self.positions[symbol]
                price = open_p * (1 - self.slippage_pct if pos.direction == OrderDirection.LONG else 1 + self.slippage_pct)
                self._execute_exit(pos, price, open_time, ExitReason.MANUAL)

        # PHA 3: Pending Market Entry & Admission Gate
        pending_to_process = [req for req in self.pending_orders if req.symbol == symbol and req.signal_time <= open_time]
        self.pending_orders = [req for req in self.pending_orders if not (req.symbol == symbol and req.signal_time <= open_time)]

        for req in pending_to_process:
            if req.expires_at is not None and open_time >= req.expires_at:
                self._update_order_record(req, OrderStatus.CANCELLED, open_time, reasons=["LIMIT_EXPIRED"])
                continue
            # 1. Limit orders remain pending until the bar trades through their price.
            if req.order_type == OrderType.LIMIT_ENTRY:
                touched = low_p <= req.signal_price if req.direction == OrderDirection.LONG else high_p >= req.signal_price
                if not touched:
                    self.pending_orders.append(req)
                    continue
                fill_price = (min(open_p * (1 + self.slippage_pct), req.signal_price)
                              if req.direction == OrderDirection.LONG
                              else max(open_p * (1 - self.slippage_pct), req.signal_price))
            elif req.order_type not in (OrderType.MARKET_ENTRY, getattr(OrderType, "MARKET", OrderType.MARKET_ENTRY)):
                self._update_order_record(
                    req=req,
                    status=OrderStatus.REJECTED,
                    processed_at=open_time,
                    reference_price=open_p,
                    reasons=[f"EXECUTION_REJECT_UNSUPPORTED_ORDER_TYPE: Order type {req.order_type} not supported for entry."],
                )
                candle_events.append({"type": "ORDER_REJECTED", "reasons": ["EXECUTION_REJECT_UNSUPPORTED_ORDER_TYPE"]})
                continue

            # 2. Vị thế đang mở
            if symbol in self.positions:
                self._update_order_record(
                    req=req,
                    status=OrderStatus.REJECTED,
                    processed_at=open_time,
                    reference_price=open_p,
                    reasons=["EXECUTION_REJECT_POSITION_ALREADY_ACTIVE"],
                )
                candle_events.append({"type": "ORDER_REJECTED", "reasons": ["EXECUTION_REJECT_POSITION_ALREADY_ACTIVE"]})
                continue

            # 3. Tài khoản halted / circuit breaker locked
            if self.is_halted or self.circuit_breaker.is_locked:
                self._update_order_record(
                    req=req,
                    status=OrderStatus.REJECTED,
                    processed_at=open_time,
                    reference_price=open_p,
                    reasons=["EXECUTION_REJECT_CIRCUIT_BREAKER_LOCKED"],
                )
                candle_events.append({"type": "ORDER_REJECTED", "reasons": ["EXECUTION_REJECT_CIRCUIT_BREAKER_LOCKED"]})
                continue

            # 4. Tính giá fill kèm slippage
            if req.order_type == OrderType.LIMIT_ENTRY:
                pass
            elif req.direction == OrderDirection.LONG:
                fill_price = open_p * (1.0 + self.slippage_pct)
            elif req.direction == OrderDirection.SHORT:
                fill_price = open_p * (1.0 - self.slippage_pct)
            else:
                self._update_order_record(
                    req=req,
                    status=OrderStatus.REJECTED,
                    processed_at=open_time,
                    reference_price=open_p,
                    reasons=[f"EXECUTION_REJECT_INVALID_DIRECTION: {req.direction!r}"],
                )
                candle_events.append({"type": "ORDER_REJECTED", "reasons": [f"EXECUTION_REJECT_INVALID_DIRECTION: {req.direction!r}"]})
                continue

            # 5. Xác thực lại SL và TP đối với actual fill price (E5)
            invalid_bounds = False
            bound_reasons = []
            if req.direction == OrderDirection.LONG:
                if req.stop_loss_price >= fill_price:
                    invalid_bounds = True
                    bound_reasons.append(f"EXECUTION_REJECT_INVALID_PRICE_BOUNDS: LONG stop_loss ({req.stop_loss_price}) >= fill_price ({fill_price})")
                if req.take_profit_price is not None and req.take_profit_price <= fill_price:
                    invalid_bounds = True
                    bound_reasons.append(f"EXECUTION_REJECT_INVALID_PRICE_BOUNDS: LONG take_profit ({req.take_profit_price}) <= fill_price ({fill_price})")
            else:  # SHORT
                if req.stop_loss_price <= fill_price:
                    invalid_bounds = True
                    bound_reasons.append(f"EXECUTION_REJECT_INVALID_PRICE_BOUNDS: SHORT stop_loss ({req.stop_loss_price}) <= fill_price ({fill_price})")
                if req.take_profit_price is not None and req.take_profit_price >= fill_price:
                    invalid_bounds = True
                    bound_reasons.append(f"EXECUTION_REJECT_INVALID_PRICE_BOUNDS: SHORT take_profit ({req.take_profit_price}) >= fill_price ({fill_price})")

            if invalid_bounds:
                self._update_order_record(
                    req=req,
                    status=OrderStatus.REJECTED,
                    processed_at=open_time,
                    reference_price=open_p,
                    actual_fill_price=fill_price,
                    reasons=bound_reasons,
                )
                candle_events.append({"type": "ORDER_REJECTED", "reasons": bound_reasons})
                continue

            # 6. Sizing và solver bọc try/except (E5)
            effective_risk_pct = req.base_risk_percent * self.circuit_breaker.risk_multiplier
            try:
                sizing = calculate_position_size(
                    equity=self.equity,
                    risk_percent=effective_risk_pct,
                    entry_price=fill_price,
                    stop_price=req.stop_loss_price,
                    leverage=req.leverage,
                )
                calc_quantity = sizing["quantity"] if req.requested_quantity is None else req.requested_quantity
                calc_notional = calc_quantity * fill_price

                liq_price = calculate_estimated_liquidation_price(
                    direction=req.direction.value,
                    entry_price=fill_price,
                    position_size_usd=calc_notional,
                    leverage=req.leverage,
                    symbol=symbol,
                    leverage_brackets=self.config.get("leverage_brackets"),
                )
            except Exception as exc:
                self._update_order_record(
                    req=req,
                    status=OrderStatus.REJECTED,
                    processed_at=open_time,
                    reference_price=open_p,
                    actual_fill_price=fill_price,
                    reasons=[f"EXECUTION_REJECT_SIZING_ERROR: {exc}"],
                )
                candle_events.append({"type": "ORDER_REJECTED", "reasons": [f"EXECUTION_REJECT_SIZING_ERROR: {exc}"]})
                continue

            # 7. Đóng gói order để kiểm tra Invariants (E5: risk_percent authority)
            declared_risk = req.risk_percent if req.risk_percent is not None else effective_risk_pct
            order_dict = {
                "symbol": symbol,
                "direction": req.direction.value,
                "entry_price": fill_price,
                "stop_loss_price": req.stop_loss_price,
                "leverage": req.leverage,
                "base_risk_percent": req.base_risk_percent,
                "risk_percent": declared_risk,
                "conviction_tier": req.conviction_tier,
                "position_size_usd": calc_notional,
                "timestamp": req.signal_time,
            }

            account_state = {
                "equity": self.equity,
                "available_margin": self.available_margin,
                "current_time": open_time,
                "circuit_breaker_state": self.circuit_breaker,
                "news_filter": self.news_filter,
            }

            is_valid, reasons = check_all_invariants(order_dict, account_state, self.config)

            if is_valid and req.partial_exits:
                sign = 1 if req.direction == OrderDirection.LONG else -1
                distance = abs(fill_price - req.stop_loss_price)
                if any(not math.isfinite(fill_price + sign * rr * distance) or fill_price + sign * rr * distance <= 0
                       for rr, _ in req.partial_exits):
                    is_valid = False
                    reasons = ["EXECUTION_REJECT_INVALID_PARTIAL_TARGET"]

            if is_valid:
                entry_fee = calc_notional * self.taker_fee_pct
                initial_margin = calc_notional / req.leverage
                entry_equity = self.equity

                self.wallet_balance -= entry_fee

                actual_risk_usd = calc_quantity * abs(fill_price - req.stop_loss_price)
                actual_risk_ratio_percent = (actual_risk_usd / entry_equity) * 100.0
                position_metadata = dict(req.metadata) if hasattr(req, "metadata") and req.metadata else {}
                position_metadata.update({
                    "entry_equity": entry_equity,
                    "risk_ratio_percent": actual_risk_ratio_percent,
                })
                if req.partial_exits:
                    sign = 1 if req.direction == OrderDirection.LONG else -1
                    distance = abs(fill_price - req.stop_loss_price)
                    position_metadata["partial_targets"] = [
                        [fill_price + sign * rr * distance, fraction] for rr, fraction in req.partial_exits
                    ]
                    position_metadata["original_quantity"] = calc_quantity
                    position_metadata["partials_done"] = 0
                if req.order_type == OrderType.LIMIT_ENTRY:
                    position_metadata["intrabar_limit_entry"] = (
                        open_p > req.signal_price if req.direction == OrderDirection.LONG else open_p < req.signal_price
                    )

                new_pos = Position(
                    position_id=f"POS_{symbol}_{open_time.strftime('%Y%m%d%H%M')}_{self._trade_seq+1:04d}",
                    symbol=symbol,
                    direction=req.direction,
                    quantity=calc_quantity,
                    entry_price=fill_price,
                    initial_margin=initial_margin,
                    isolated_collateral=initial_margin,
                    leverage=req.leverage,
                    stop_loss_price=req.stop_loss_price,
                    take_profit_price=req.take_profit_price,
                    liquidation_price=liq_price,
                    opened_at=open_time,
                    conviction_tier=req.conviction_tier,
                    entry_fee=entry_fee,
                    initial_stop_loss_price=req.stop_loss_price,
                    initial_liquidation_price=liq_price,
                    metadata=position_metadata,
                )
                self.positions[symbol] = new_pos

                self._update_order_record(
                    req=req,
                    status=OrderStatus.FILLED,
                    processed_at=open_time,
                    reference_price=open_p,
                    actual_fill_price=fill_price,
                    slippage_usd=abs(fill_price - open_p) * calc_quantity,
                    filled_quantity=calc_quantity,
                    notional_usd=calc_notional,
                    fee_usd=entry_fee,
                )
                candle_events.append({"type": "ORDER_FILLED", "position": new_pos})

                # Ghi nhận entry fee vào rolling cashflow ledger ngay sau khi fill (H1)
                if entry_fee > 0:
                    self.circuit_breaker.record_cashflow(
                        amount=-entry_fee,
                        timestamp=open_time,
                        equity=max(0.0, self.equity),
                        param_name="entry_fee",
                    )
                    if self.circuit_breaker.is_locked:
                        self._handle_circuit_breaker_lock(open_time)
            else:
                self._update_order_record(
                    req=req,
                    status=OrderStatus.REJECTED,
                    processed_at=open_time,
                    reference_price=open_p,
                    actual_fill_price=fill_price,
                    reasons=reasons,
                )
                candle_events.append({"type": "ORDER_REJECTED", "reasons": reasons})

        # PHA 4: Intrabar Protection (Liquidation > SL > TP trên [low_p, high_p])
        if symbol in self.positions:
            pos = self.positions[symbol]
            intrabar_exit_triggered = False
            exit_reason = None
            raw_exit_price = 0.0

            if pos.direction == OrderDirection.LONG:
                if low_p <= pos.liquidation_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.LIQUIDATION
                    raw_exit_price = pos.liquidation_price * (1.0 - self.slippage_pct)
                elif low_p <= pos.stop_loss_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.STOP_LOSS
                    raw_exit_price = pos.stop_loss_price * (1.0 - self.slippage_pct)
                elif pos.take_profit_price is not None and high_p >= pos.take_profit_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.TAKE_PROFIT
                    raw_exit_price = pos.take_profit_price * (1.0 - self.slippage_pct)
            else:  # SHORT
                if high_p >= pos.liquidation_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.LIQUIDATION
                    raw_exit_price = pos.liquidation_price * (1.0 + self.slippage_pct)
                elif high_p >= pos.stop_loss_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.STOP_LOSS
                    raw_exit_price = pos.stop_loss_price * (1.0 + self.slippage_pct)
                elif pos.take_profit_price is not None and low_p <= pos.take_profit_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.TAKE_PROFIT
                    raw_exit_price = pos.take_profit_price * (1.0 + self.slippage_pct)

            # Unknown pre-fill path cannot award a same-bar limit-entry profit.
            if (pos.metadata.get("intrabar_limit_entry") and pos.opened_at == open_time
                    and exit_reason == ExitReason.TAKE_PROFIT):
                intrabar_exit_triggered = False
            if intrabar_exit_triggered and exit_reason is not None:
                trade_rec = self._execute_exit(
                    position=pos,
                    exit_price=raw_exit_price,
                    exit_time=close_time,
                    exit_reason=exit_reason,
                    intrabar_estimated=True,
                )
                candle_events.append({"type": "INTRABAR_EXIT", "trade": trade_rec})

        if symbol in self.positions:
            pos = self.positions[symbol]
            if not (pos.metadata.get("intrabar_limit_entry") and pos.opened_at == open_time):
                targets = pos.metadata.get("partial_targets", [])
                for idx in range(pos.metadata.get("partials_done", 0), len(targets)):
                    if symbol not in self.positions:
                        break
                    target, fraction = targets[idx]
                    touched = high_p >= target if pos.direction == OrderDirection.LONG else low_p <= target
                    if not touched:
                        break
                    price = target * (1 - self.slippage_pct if pos.direction == OrderDirection.LONG else 1 + self.slippage_pct)
                    quantity = pos.metadata["original_quantity"] * fraction
                    self._execute_exit(pos, price, close_time, ExitReason.TAKE_PROFIT,
                                       intrabar_estimated=True, quantity=quantity)
                    if symbol in self.positions:
                        pos = self.positions[symbol]
                        pos.metadata["partials_done"] = idx + 1
                        pos.metadata["breakeven_pending"] = True

        # PHA 5: Close Time & Mark-to-Market
        self.current_time = close_time
        self.last_mark_prices[symbol] = close_p

        if symbol in self.positions:
            pos = self.positions[symbol]
            pos._last_unrealized_pnl = pos.calculate_unrealized_pnl(close_p)
            # Effective only after this bar; never move a stop retroactively.
            if pos.metadata.get("breakeven_pending"):
                if self.update_stop_loss(symbol, pos.entry_price):
                    pos.metadata["breakeven_pending"] = False
                elif ((pos.direction == OrderDirection.LONG and close_p <= pos.entry_price)
                      or (pos.direction == OrderDirection.SHORT and close_p >= pos.entry_price)):
                    # Closed below/above BE before it could become effective:
                    # queue a next-open exit; do not invent an earlier BE fill.
                    self.request_close(symbol, close_time)

        if self.equity <= 0:
            self.is_halted = True
            logger.error("[PaperBroker] Tài khoản cạn vốn (equity = {:.2f} <= 0). Halted toàn bộ.", self.equity)

        snapshot = AccountSnapshot(
            timestamp=close_time,
            wallet_balance=self.wallet_balance,
            reserved_collateral=self.reserved_collateral,
            available_margin=self.available_margin,
            unrealized_pnl=self.unrealized_pnl,
            equity=self.equity,
            open_positions_count=len(self.positions),
            is_halted=self.is_halted,
        )
        self.account_snapshots.append(snapshot)

        # Đối soát kế toán sau nến
        self.verify_accounting_invariants()

        return {
            "timestamp": close_time,
            "events": candle_events,
            "snapshot": snapshot,
        }

    def _execute_exit(
        self,
        position: Position,
        exit_price: float,
        exit_time: datetime,
        exit_reason: ExitReason,
        intrabar_estimated: bool = False,
        quantity: Optional[float] = None,
    ) -> TradeRecord:
        """
        Thực hiện đóng vị thế, hạch toán PnL, giải phóng ký quỹ và đồng bộ Circuit Breaker (E4).
        """
        remaining = None
        previous_slices = position.metadata.get("realized_slices_net", 0.0)
        if quantity is not None:
            quantity = _validate_finite_positive("exit quantity", quantity)
            if quantity >= position.quantity:
                raise ValueError("partial exit quantity must be less than remaining position")
            ratio = quantity / position.quantity
            remaining = deepcopy(position)
            position = deepcopy(position)
            for name in ("quantity", "initial_margin", "isolated_collateral", "entry_fee", "cumulative_funding"):
                original = getattr(position, name)
                setattr(position, name, original * ratio)
                setattr(remaining, name, original * (1 - ratio))
            remaining.liquidation_price = self._calculate_collateral_aware_liquidation_price(remaining)
            remaining._last_unrealized_pnl = remaining.calculate_unrealized_pnl(
                self.last_mark_prices.get(remaining.symbol, remaining.entry_price))
            position.metadata["partial_exit"] = True
        exit_notional = position.quantity * exit_price
        exit_fee = exit_notional * self.taker_fee_pct

        if position.direction == OrderDirection.LONG:
            gross_pnl = position.quantity * (exit_price - position.entry_price)
        else:
            gross_pnl = position.quantity * (position.entry_price - exit_price)

        # Net trade PnL = Gross Price PnL - Entry Fee - Exit Fee + Cumulative Funding
        net_trade_pnl = gross_pnl - position.entry_fee - exit_fee + position.cumulative_funding

        # Giải phóng isolated collateral và cập nhật wallet
        self.wallet_balance += (gross_pnl - exit_fee)

        return_pct = (net_trade_pnl / position.initial_margin) * 100.0 if position.initial_margin > 0 else 0.0

        # Cập nhật các trường đóng vị thế
        position.status = PositionStatus.CLOSED
        position.closed_at = exit_time
        position.exit_price = exit_price
        position.exit_reason = exit_reason
        position.exit_fee = exit_fee

        trade_rec = TradeRecord(
            trade_id=self._next_trade_id(position.symbol, exit_time),
            symbol=position.symbol,
            direction=position.direction,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_time=position.opened_at,
            exit_time=exit_time,
            leverage=position.leverage,
            initial_margin=position.initial_margin,
            gross_price_pnl=gross_pnl,
            entry_fee=position.entry_fee,
            exit_fee=exit_fee,
            funding_cashflow=position.cumulative_funding,
            net_pnl=net_trade_pnl,
            return_pct=return_pct,
            exit_reason=exit_reason,
            intrabar_estimated=intrabar_estimated,
            metadata=dict(position.metadata) if hasattr(position, "metadata") and position.metadata else {},
            initial_stop_loss_price=getattr(position, "initial_stop_loss_price", position.stop_loss_price),
            conviction_tier=getattr(position, "conviction_tier", "normal"),
            estimated_liquidation_price=getattr(
                position,
                "initial_liquidation_price",
                getattr(position, "liquidation_price", None),
            ),
            take_profit_levels=[position.take_profit_price] if getattr(position, "take_profit_price", None) is not None else [],
        )
        self.trade_history.append(trade_rec)

        # XÓA VỊ THẾ KHỎI self.positions TRƯỚC KHI TÍNH EQUITY (E4)
        self.positions.pop(position.symbol, None)
        if remaining is not None:
            remaining.metadata["realized_slices_net"] = previous_slices + net_trade_pnl
            self.positions[position.symbol] = remaining

        # Tính post-close equity sạch (không bị dính stale unrealized pnl của vị thế vừa đóng)
        post_close_equity = max(0.0, self.equity)

        # Ghi nhận kết quả giao dịch vào Circuit Breaker (E4, H1)
        # Chỉ ghi nhận khi không phải forced close do chính CB lock
        exit_cashflow = gross_pnl - exit_fee
        if remaining is not None:
            self.circuit_breaker.record_cashflow(exit_cashflow, exit_time, post_close_equity)
        elif exit_reason != ExitReason.CIRCUIT_BREAKER_LOCK:
            try:
                self.circuit_breaker.record_trade_result(
                    pnl=net_trade_pnl + previous_slices,
                    timestamp=exit_time,
                    equity=post_close_equity,
                    cashflow=exit_cashflow,
                )
            except TypeError:
                self.circuit_breaker.record_trade_result(
                    pnl=net_trade_pnl,
                    timestamp=exit_time,
                    equity=post_close_equity,
                )
        else:
            self.circuit_breaker.record_cashflow(
                amount=exit_cashflow,
                timestamp=exit_time,
                equity=post_close_equity,
                param_name="exit_cashflow",
            )

        # Nếu Circuit Breaker vừa kích hoạt trạng thái khóa (locked), hủy pending và đóng các vị thế khác (E3)
        if self.circuit_breaker.is_locked:
            self._handle_circuit_breaker_lock(exit_time)

        return trade_rec

    def _handle_circuit_breaker_lock(self, timestamp: datetime) -> None:
        """
        Cưỡng chế đóng toàn bộ vị thế đang mở và hủy pending orders khi Circuit Breaker bị khóa (E3).
        Không gọi đệ quy.
        """
        if self._is_handling_cb_lock:
            return
        self._is_handling_cb_lock = True
        try:
            # 1. Hủy pending orders
            for pending in self.pending_orders:
                self._update_order_record(
                    req=pending,
                    status=OrderStatus.CANCELLED,
                    processed_at=timestamp,
                    reasons=["ORDER_CANCELLED_CIRCUIT_BREAKER_LOCKED"],
                )
            self.pending_orders.clear()

            # 2. Đóng toàn bộ positions đang mở theo giá mark từng symbol kèm slippage
            symbols_to_close = list(self.positions.keys())
            for sym in symbols_to_close:
                if sym not in self.positions:
                    continue
                pos = self.positions[sym]
                mark_p = self.last_mark_prices.get(sym, pos.entry_price)
                if pos.direction == OrderDirection.LONG:
                    exit_p = mark_p * (1.0 - self.slippage_pct)
                else:
                    exit_p = mark_p * (1.0 + self.slippage_pct)

                self._execute_exit(
                    position=pos,
                    exit_price=exit_p,
                    exit_time=timestamp,
                    exit_reason=ExitReason.CIRCUIT_BREAKER_LOCK,
                    intrabar_estimated=False,
                )
        finally:
            self._is_handling_cb_lock = False

    def _calculate_collateral_aware_liquidation_price(self, position: Position) -> float:
        """
        Tính toán lại giá thanh lý chính xác dựa trên isolated_collateral thực tế (E2, H2).
        Giải nhất quán theo tier tại chính candidate_notional = q * P_liq.
        Tuyệt đối không fallback sang hardcoded mmr hay tier sai khi có lỗi (H2).
        """
        return self._calculate_liquidation_price_for_collateral(
            symbol=position.symbol,
            direction=position.direction,
            quantity=position.quantity,
            entry_price=position.entry_price,
            collateral=position.isolated_collateral,
            position_id=position.position_id,
        )

    def _calculate_liquidation_price_for_collateral(
        self,
        symbol: str,
        direction: OrderDirection,
        quantity: float,
        entry_price: float,
        collateral: float,
        position_id: str = "",
    ) -> float:
        """
        Giải giá thanh lý cho một mức ký quỹ (collateral) cụ thể theo bảng leverage brackets (H2, J2).
        LONG:  C + q * (P - entry) = q * P * mmr - cum  => P = (q * entry - C - cum) / (q * (1 - mmr))
        SHORT: C + q * (entry - P) = q * P * mmr - cum  => P = (q * entry + C + cum) / (q * (1 + mmr))
        """
        brackets = get_brackets_for_symbol(
            symbol,
            self.config.get("leverage_brackets"),
        )
        q = quantity
        entry = entry_price
        c = collateral

        if type(q) is bool or not isinstance(q, (int, float)) or not (math.isfinite(q) and q > 0):
            raise ValueError(f"Invalid position quantity: {q}")
        if type(entry) is bool or not isinstance(entry, (int, float)) or not (math.isfinite(entry) and entry > 0):
            raise ValueError(f"Invalid position entry price: {entry}")
        if type(c) is bool or not isinstance(c, (int, float)) or not math.isfinite(c):
            raise ValueError(f"Invalid position isolated collateral: {c}")

        lower_bound = 0.0
        for idx, (upper_bound, mmr, cum) in enumerate(brackets):
            if direction == OrderDirection.LONG:
                denom = q * (1.0 - mmr)
                if denom <= 0:
                    continue
                num = q * entry - c - cum
                if num <= 0:
                    candidate_p = 0.0
                else:
                    candidate_p = num / denom

                if not (math.isfinite(candidate_p) and candidate_p >= 0):
                    continue
                # Long liquidation price must be <= entry price
                if candidate_p > entry:
                    continue

                candidate_notional = q * candidate_p
                is_in_tier = (lower_bound < candidate_notional <= upper_bound) or (idx == 0 and candidate_notional <= upper_bound)
                if is_in_tier:
                    return float(candidate_p)
            else:  # SHORT
                denom = q * (1.0 + mmr)
                if denom <= 0:
                    continue
                num = q * entry + c + cum
                if num <= 0:
                    candidate_p = 0.0
                else:
                    candidate_p = num / denom

                if not (math.isfinite(candidate_p) and candidate_p >= 0):
                    continue
                # Short liquidation price must be >= entry price
                if candidate_p < entry:
                    continue

                candidate_notional = q * candidate_p
                is_in_tier = (lower_bound < candidate_notional <= upper_bound) or (idx == 0 and candidate_notional <= upper_bound)
                if is_in_tier:
                    return float(candidate_p)

            lower_bound = upper_bound

        raise ValueError(
            f"No tier-consistent liquidation price found for position {position_id} "
            f"({direction.value}, qty={q}, entry={entry}, collateral={c})"
        )

    def _apply_funding_settlement(
        self,
        position: Position,
        timestamp: datetime,
        funding_rate: float,
        mark_price: float,
    ) -> FundingEvent:
        """
        Tính và áp dụng cashflow funding tại mốc 00/08/16 UTC.
        LONG: cashflow = -1 * Qty * Mark * Rate
        SHORT: cashflow = +1 * Qty * Mark * Rate
        Đảm bảo transactional: tính toàn bộ state mới và solver trước khi commit (J2).
        """
        direction_sign = 1.0 if position.direction == OrderDirection.LONG else -1.0
        cashflow = -direction_sign * position.quantity * mark_price * funding_rate
        new_collateral = position.isolated_collateral + cashflow

        # Precompute new liquidation price first (H2, J2)
        new_liq = self._calculate_liquidation_price_for_collateral(
            symbol=position.symbol,
            direction=position.direction,
            quantity=position.quantity,
            entry_price=position.entry_price,
            collateral=new_collateral,
            position_id=position.position_id,
        )

        # Commit thay đổi state sau khi solver thành công
        self.wallet_balance += cashflow
        position.isolated_collateral = new_collateral
        position.cumulative_funding += cashflow
        position.liquidation_price = new_liq

        event = FundingEvent(
            event_id=self._next_funding_id(position.symbol, timestamp),
            timestamp=timestamp,
            symbol=position.symbol,
            position_id=position.position_id,
            funding_rate=funding_rate,
            settlement_mark_price=mark_price,
            position_quantity=position.quantity,
            cashflow_usd=cashflow,
            direction=position.direction,
        )
        self.funding_history.append(event)

        # Ghi nhận ngay cashflow vào Circuit Breaker (E3)
        self.circuit_breaker.record_cashflow(
            amount=cashflow,
            timestamp=timestamp,
            equity=max(0.0, self.equity),
            param_name="amount",
        )

        # Nếu Circuit Breaker bị khóa do funding loss, đóng toàn bộ vị thế ngay (E3)
        if self.circuit_breaker.is_locked:
            self._handle_circuit_breaker_lock(timestamp)

        return event

    def _update_order_record(
        self,
        req: OrderRequest,
        status: OrderStatus,
        processed_at: datetime,
        reference_price: float = 0.0,
        actual_fill_price: float = 0.0,
        slippage_usd: float = 0.0,
        filled_quantity: float = 0.0,
        notional_usd: float = 0.0,
        fee_usd: float = 0.0,
        reasons: Optional[List[str]] = None,
    ) -> None:
        """Cập nhật bản ghi đơn hàng trong order_history."""
        for rec in reversed(self.order_history):
            if rec.symbol == req.symbol and rec.requested_at == req.signal_time and rec.status == OrderStatus.PENDING:
                rec.status = status
                rec.processed_at = processed_at
                rec.reference_price = reference_price
                rec.actual_fill_price = actual_fill_price
                rec.slippage_usd = slippage_usd
                rec.filled_quantity = filled_quantity
                rec.notional_usd = notional_usd
                rec.fee_usd = fee_usd
                if getattr(req, "metadata", None):
                    rec.metadata.update(req.metadata)
                if reasons:
                    rec.rejection_reasons = list(reasons)
                break

    def request_close(self, symbol: str, signal_time: datetime) -> None:
        """Queue a causal market exit; execution and funding stay in the broker."""
        timestamp = _ensure_utc(signal_time)
        if self.is_finalized:
            raise RuntimeError("broker finalized")
        if self.current_time is not None and timestamp < self.current_time:
            raise ValueError("close signal time reversal")
        self.pending_closes[str(symbol).upper()] = timestamp

    def update_stop_loss(self, symbol: str, new_stop_loss: float) -> bool:
        """
        Cập nhật Stop Loss cho vị thế đang mở (E7).
        Chỉ cho phép thắt chặt rủi ro và không được vượt qua giá thị trường hiện tại:
        - LONG: chỉ được nâng SL lên cao hơn và phải nhỏ hơn mark price hiện tại.
        - SHORT: chỉ được hạ SL xuống thấp hơn và phải lớn hơn mark price hiện tại.
        """
        symbol = str(symbol).upper()
        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        new_sl = _validate_finite_positive("new_stop_loss", new_stop_loss)
        current_mark = self.last_mark_prices.get(symbol, pos.entry_price)

        if pos.direction == OrderDirection.LONG:
            if new_sl <= pos.stop_loss_price:
                return False  # Không cho phép nới rộng SL
            if new_sl >= current_mark:
                return False  # Không cho phép SL vượt qua giá thị trường hiện tại (E7)
            pos.stop_loss_price = new_sl
            return True
        else:  # SHORT
            if new_sl >= pos.stop_loss_price:
                return False  # Không cho phép nới rộng SL
            if new_sl <= current_mark:
                return False  # Không cho phép SL vượt qua giá thị trường hiện tại (E7)
            pos.stop_loss_price = new_sl
            return True

    def close_all_positions(self, current_price: float, timestamp: datetime, reason: ExitReason) -> List[TradeRecord]:
        """
        Đóng khẩn cấp toàn bộ vị thế đang mở kèm exit slippage (E7, H4).
        Pre-validate mọi tham số và kiểm tra tính đơn điệu thời gian TRƯỚC KHI thay đổi bất kỳ trạng thái nào (transactional).
        """
        p = _validate_finite_positive("current_price", current_price)
        t = _ensure_utc(timestamp)
        if not isinstance(reason, ExitReason):
            raise TypeError(f"reason must be ExitReason enum, got {type(reason).__name__}")

        if self.current_time is not None and t < self.current_time:
            raise ValueError(f"Time reversal in close_all_positions: timestamp {t} < current_time {self.current_time}")

        if self.circuit_breaker.last_event_time is not None and t < self.circuit_breaker.last_event_time:
            raise ValueError(
                f"Time reversal in close_all_positions: timestamp {t} < circuit_breaker.last_event_time {self.circuit_breaker.last_event_time}"
            )

        for pos in self.positions.values():
            if pos.opened_at is not None and t < pos.opened_at:
                raise ValueError(
                    f"Time reversal in close_all_positions: timestamp {t} < position.opened_at {pos.opened_at}"
                )

        closed_trades = []
        for symbol in list(self.positions.keys()):
            if symbol not in self.positions:
                continue
            pos = self.positions[symbol]
            if pos.direction == OrderDirection.LONG:
                exit_price = p * (1.0 - self.slippage_pct)
            else:
                exit_price = p * (1.0 + self.slippage_pct)
            trade = self._execute_exit(
                position=pos,
                exit_price=exit_price,
                exit_time=t,
                exit_reason=reason,
                intrabar_estimated=False,
            )
            closed_trades.append(trade)
        return closed_trades

    def finalize(
        self,
        timestamp: Optional[datetime] = None,
        force_close: bool = False,
    ) -> Dict[str, Any]:
        """
        Kết thúc vòng đời phiên giao dịch / dataset (H5, J3).
        Idempotent: gọi lại nhiều lần trả về cùng một kết quả tóm tắt.
        Sau khi finalize, broker chuyển sang trạng thái terminal:
        - Không nhận nến mới (process_candle raise RuntimeError).
        - Không nhận lệnh mới (submit_order trả về status REJECTED).
        - Mặc định (force_close=False): giữ nguyên các vị thế đang mở và báo cáo chi tiết.
        - Force mode (force_close=True): đóng toàn bộ vị thế đang mở theo giá mark gần nhất
          kèm slippage/phí với exit_reason = ExitReason.END_OF_DATA.
        """
        if self.is_finalized:
            return getattr(self, "_finalized_summary", self._build_finalize_summary(self.current_time or datetime.now(timezone.utc)))

        if timestamp is not None:
            t = _ensure_utc(timestamp)
            if self.current_time is not None and t < self.current_time:
                raise ValueError(f"Time reversal in finalize: timestamp {t} < current_time {self.current_time}")
            if self.circuit_breaker.last_event_time is not None and t < self.circuit_breaker.last_event_time:
                raise ValueError(f"Time reversal in finalize: timestamp {t} < last_event_time {self.circuit_breaker.last_event_time}")
        else:
            t = self.current_time or datetime.now(timezone.utc)

        # 1. Hủy toàn bộ pending orders
        for pending in self.pending_orders:
            self._update_order_record(
                req=pending,
                status=OrderStatus.CANCELLED,
                processed_at=t,
                reasons=["ORDER_CANCELLED_BROKER_FINALIZED: Session finalized."],
            )
        self.pending_orders.clear()

        # 2. Nếu force_close=True, đóng các vị thế đang mở (J3: an toàn khi breaker kích hoạt lồng nhau)
        if force_close and self.positions:
            for symbol in list(self.positions.keys()):
                if symbol not in self.positions:
                    continue
                pos = self.positions[symbol]
                mark_p = self.last_mark_prices.get(symbol, pos.entry_price)
                if pos.direction == OrderDirection.LONG:
                    exit_p = mark_p * (1.0 - self.slippage_pct)
                else:
                    exit_p = mark_p * (1.0 + self.slippage_pct)
                self._execute_exit(
                    position=pos,
                    exit_price=exit_p,
                    exit_time=t,
                    exit_reason=ExitReason.END_OF_DATA,
                    intrabar_estimated=False,
                )

        # Finalization can close positions after the last candle snapshot.  Replace
        # the same-timestamp snapshot (or append a new one) so drawdown, Sharpe and
        # exported equity curves include the final exit fee/slippage exactly once.
        final_snapshot = AccountSnapshot(
            timestamp=t,
            wallet_balance=self.wallet_balance,
            reserved_collateral=self.reserved_collateral,
            available_margin=self.available_margin,
            unrealized_pnl=self.unrealized_pnl,
            equity=self.equity,
            open_positions_count=len(self.positions),
            is_halted=self.is_halted,
        )
        if self.account_snapshots and self.account_snapshots[-1].timestamp == t:
            self.account_snapshots[-1] = final_snapshot
        else:
            self.account_snapshots.append(final_snapshot)

        # 3. Đánh dấu trạng thái finalized
        self.is_finalized = True
        self.current_time = t

        # 4. Kiểm tra Accounting Invariants
        self.verify_accounting_invariants()

        # 5. Xây dựng bản tóm tắt phiên
        summary = self._build_finalize_summary(t)
        self._finalized_summary = summary
        return summary

    def _build_finalize_summary(self, t: datetime) -> Dict[str, Any]:
        """Tạo từ điển tóm tắt trạng thái tài khoản tại thời điểm finalize."""
        return {
            "finalized_at": t,
            "wallet_balance": self.wallet_balance,
            "reserved_collateral": self.reserved_collateral,
            "available_margin": self.available_margin,
            "unrealized_pnl": self.unrealized_pnl,
            "equity": self.equity,
            "open_positions_count": len(self.positions),
            "open_positions": {
                sym: {
                    "direction": pos.direction.value,
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "isolated_collateral": pos.isolated_collateral,
                    "unrealized_pnl": pos.calculate_unrealized_pnl(self.last_mark_prices.get(sym, pos.entry_price)),
                }
                for sym, pos in self.positions.items()
            },
            "trade_count": len(self.trade_history),
            "funding_count": len(self.funding_history),
            "is_halted": self.is_halted,
            "circuit_breaker_locked": self.circuit_breaker.is_locked,
        }

    def verify_accounting_invariants(self) -> None:
        """
        Kiểm tra tính nhất quán toán học của toàn bộ sổ cái kế toán (Accounting Invariants).
        Bắt buộc thỏa mãn với sai số số học 1e-4.
        Kiểm tra math.isfinite trước khi so sánh tolerance (E8).
        1. wallet_balance == initial_balance + sum(gross_pnl) - sum(all_fees) + sum(funding)
        2. available_margin == wallet_balance - reserved_collateral
        3. equity == wallet_balance + unrealized_pnl
        """
        # Kiểm tra finite trên tất cả các trường
        for name, val in [
            ("wallet_balance", self.wallet_balance),
            ("reserved_collateral", self.reserved_collateral),
            ("available_margin", self.available_margin),
            ("unrealized_pnl", self.unrealized_pnl),
            ("equity", self.equity),
        ]:
            if not math.isfinite(val):
                raise AssertionError(f"Accounting invariant violated! {name} is not finite: {val}")

        total_gross_pnl = sum(t.gross_price_pnl for t in self.trade_history)
        total_fees = sum(t.entry_fee + t.exit_fee for t in self.trade_history) + sum(
            pos.entry_fee for pos in self.positions.values()
        )
        total_funding = sum(f.cashflow_usd for f in self.funding_history)

        expected_wallet = self.initial_balance + total_gross_pnl - total_fees + total_funding
        if not math.isfinite(expected_wallet):
            raise AssertionError(f"Accounting invariant violated! expected_wallet is not finite: {expected_wallet}")

        if abs(self.wallet_balance - expected_wallet) > 1e-4:
            raise AssertionError(
                f"Accounting invariant violated! wallet_balance ({self.wallet_balance:.4f}) != expected_wallet ({expected_wallet:.4f})"
            )

        expected_available = self.wallet_balance - self.reserved_collateral
        if not math.isfinite(expected_available):
            raise AssertionError(f"Margin invariant violated! expected_available is not finite: {expected_available}")

        if abs(self.available_margin - expected_available) > 1e-4:
            raise AssertionError(
                f"Margin invariant violated! available_margin ({self.available_margin:.4f}) != expected ({expected_available:.4f})"
            )

        expected_equity = self.wallet_balance + self.unrealized_pnl
        if not math.isfinite(expected_equity):
            raise AssertionError(f"Equity invariant violated! expected_equity is not finite: {expected_equity}")

        if abs(self.equity - expected_equity) > 1e-4:
            raise AssertionError(
                f"Equity invariant violated! equity ({self.equity:.4f}) != expected ({expected_equity:.4f})"
            )

    @staticmethod
    def _parse_timeframe_duration(tf: Any) -> timedelta:
        """
        Chuyển chuỗi timeframe ('1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d')
        sang timedelta.
        Ném ValueError / TypeError nếu chuỗi không hợp lệ hoặc duration <= 0 (E6).
        """
        if type(tf) is bool or not isinstance(tf, str):
            raise TypeError(f"timeframe must be string, got {type(tf).__name__}: {tf!r}")
        tf_str = tf.strip().lower()
        m = re.match(r"^([1-9]\d*)([mhd])$", tf_str)
        if not m:
            raise ValueError(f"Invalid or unsupported timeframe format: {tf!r}")
        num = int(m.group(1))
        unit = m.group(2)
        if num <= 0:
            raise ValueError(f"timeframe duration must be positive, got {num}")
        if unit == "m":
            return timedelta(minutes=num)
        elif unit == "h":
            return timedelta(hours=num)
        elif unit == "d":
            return timedelta(days=num)
        raise ValueError(f"Unsupported timeframe unit: {unit}")
