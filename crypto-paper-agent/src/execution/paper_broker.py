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
import math
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
    parse_simulation_timestamp,
)
from src.risk.position_sizing import calculate_position_size


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
        self.funding_hours: Set[int] = funding_hours or {0, 8, 16}

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
        self.order_history: List[OrderExecutionRecord] = []
        self.trade_history: List[TradeRecord] = []
        self.funding_history: List[FundingEvent] = []
        self.account_snapshots: List[AccountSnapshot] = []

        # 5. Đồng hồ & Biến cờ
        self.current_time: Optional[datetime] = None
        self.last_candle_open_time: Optional[datetime] = None
        self.is_halted: bool = False

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
        if self.is_halted:
            rec = OrderExecutionRecord(
                order_id=self._next_order_id(request.symbol, request.signal_time),
                symbol=request.symbol,
                direction=request.direction,
                status=OrderStatus.REJECTED,
                requested_at=request.signal_time,
                reference_price=request.signal_price,
                rejection_reasons=["EXECUTION_REJECT_ACCOUNT_HALTED: Account is halted due to insolvency or circuit breaker."]
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
                reference_price=request.signal_price,
                rejection_reasons=[f"EXECUTION_REJECT_POSITION_EXISTS: Symbol {request.symbol} already has an open position."]
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
                    reference_price=request.signal_price,
                    rejection_reasons=[f"EXECUTION_REJECT_PENDING_ORDER_EXISTS: Pending order for {request.symbol} already queued."]
                )
                self.order_history.append(rec)
                return rec

        rec = OrderExecutionRecord(
            order_id=self._next_order_id(request.symbol, request.signal_time),
            symbol=request.symbol,
            direction=request.direction,
            status=OrderStatus.PENDING,
            requested_at=request.signal_time,
            reference_price=request.signal_price,
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
        # 1. Trích xuất và xác thực nến
        open_time = _ensure_utc(candle["open_time"] if "open_time" in candle else candle["timestamp"])
        open_p = _validate_finite_positive("open", candle["open"])
        high_p = _validate_finite_positive("high", candle["high"])
        low_p = _validate_finite_positive("low", candle["low"])
        close_p = _validate_finite_positive("close", candle["close"])
        symbol = str(candle.get("symbol", self.config.get("data", {}).get("futures_symbol", "BTCUSDT"))).upper()

        if high_p < max(open_p, close_p) - 1e-6 or low_p > min(open_p, close_p) + 1e-6 or high_p < low_p:
            raise ValueError(f"Malformed candle OHLC values: O={open_p}, H={high_p}, L={low_p}, C={close_p}")

        if self.last_candle_open_time is not None and open_time < self.last_candle_open_time:
            raise ValueError(f"Time reversal in candle sequence: {open_time} < {self.last_candle_open_time}")
        self.last_candle_open_time = open_time

        # Tính close_time dựa trên timeframe nếu có (mặc định 1m = 60s, 15m = 900s, 4h = 14400s)
        timeframe_str = str(candle.get("timeframe", self.config.get("data", {}).get("timeframes", ["1m"])[0]))
        duration = self._parse_timeframe_duration(timeframe_str)
        close_time = candle.get("close_time")
        if close_time is not None:
            close_time = _ensure_utc(close_time)
        else:
            close_time = open_time + duration

        candle_events = []

        # =========================================================
        # PHA 1: Open Time & Gap Exits
        # =========================================================
        self.current_time = open_time
        # Tiến đồng hồ Circuit Breaker tới open_time
        self.circuit_breaker.advance_time(open_time)

        # Kiểm tra Gap Exit cho vị thế đang mở mang từ nến trước
        if symbol in self.positions:
            pos = self.positions[symbol]
            gap_exit_triggered = False
            gap_reason = None
            gap_exit_price = open_p

            if pos.direction == OrderDirection.LONG:
                if open_p <= pos.liquidation_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.LIQUIDATION
                    gap_exit_price = open_p
                elif open_p <= pos.stop_loss_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.STOP_LOSS
                    # Gap qua SL: khớp tại open với slippage bất lợi (SELL: open * (1 - s))
                    gap_exit_price = open_p * (1.0 - self.slippage_pct)
            else:  # SHORT
                if open_p >= pos.liquidation_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.LIQUIDATION
                    gap_exit_price = open_p
                elif open_p >= pos.stop_loss_price:
                    gap_exit_triggered = True
                    gap_reason = ExitReason.STOP_LOSS
                    # Gap qua SL: khớp tại open với slippage bất lợi (BUY: open * (1 + s))
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

        # =========================================================
        # PHA 2: Funding Settlement
        # =========================================================
        # Chỉ những vị thế còn tồn tại sau Pha 1 mới chịu funding nếu trùng mốc
        if symbol in self.positions:
            pos = self.positions[symbol]
            # Mốc funding: kiểm tra giờ UTC (00, 08, 16) tại phút 0
            if open_time.hour in self.funding_hours and open_time.minute == 0:
                raw_funding_rate = candle.get("funding_rate")
                if raw_funding_rate is not None:
                    f_rate = float(raw_funding_rate)
                    if math.isfinite(f_rate):
                        funding_evt = self._apply_funding_settlement(
                            position=pos,
                            timestamp=open_time,
                            funding_rate=f_rate,
                            mark_price=open_p,
                        )
                        candle_events.append({"type": "FUNDING", "event": funding_evt})

        # =========================================================
        # PHA 3: Pending Market Entry & Risk Gate Admission
        # =========================================================
        # Lọc các lệnh pending cho symbol hiện tại mà có signal_time <= open_time
        pending_to_process = [req for req in self.pending_orders if req.symbol == symbol and req.signal_time <= open_time]
        self.pending_orders = [req for req in self.pending_orders if not (req.symbol == symbol and req.signal_time <= open_time)]

        for req in pending_to_process:
            # Nếu đang có vị thế (vừa sống qua Pha 1 & 2), từ chối lệnh pending
            if symbol in self.positions:
                self._update_order_record(
                    req=req,
                    status=OrderStatus.REJECTED,
                    processed_at=open_time,
                    reasons=["EXECUTION_REJECT_POSITION_ALREADY_ACTIVE"],
                )
                continue

            # Tính giá fill dự kiến kèm slippage
            if req.direction == OrderDirection.LONG:
                fill_price = open_p * (1.0 + self.slippage_pct)
            else:
                fill_price = open_p * (1.0 - self.slippage_pct)

            # Tính toán kích thước vị thế và ký quỹ
            effective_risk_pct = req.base_risk_percent * self.circuit_breaker.risk_multiplier
            sizing = calculate_position_size(
                equity=self.equity,
                risk_percent=effective_risk_pct,
                entry_price=fill_price,
                stop_price=req.stop_loss_price,
                leverage=req.leverage,
            )
            calc_quantity = sizing["quantity"] if req.requested_quantity is None else req.requested_quantity
            calc_notional = calc_quantity * fill_price

            # Ước tính giá thanh lý từ solver chuẩn
            liq_price = calculate_estimated_liquidation_price(
                direction=req.direction.value,
                entry_price=fill_price,
                position_size_usd=calc_notional,
                leverage=req.leverage,
                symbol=symbol,
                leverage_brackets=self.config.get("leverage_brackets"),
            )

            # Đóng gói order để kiểm tra Invariants
            order_dict = {
                "symbol": symbol,
                "direction": req.direction.value,
                "entry_price": fill_price,
                "stop_loss_price": req.stop_loss_price,
                "leverage": req.leverage,
                "base_risk_percent": req.base_risk_percent,
                "risk_percent": effective_risk_pct,
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

            if is_valid:
                # Trừ phí vào lệnh Taker
                entry_fee = calc_notional * self.taker_fee_pct
                initial_margin = calc_notional / req.leverage

                self.wallet_balance -= entry_fee

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

        # =========================================================
        # PHA 4: Intrabar Protection (High / Low Range)
        # =========================================================
        # Kiểm tra cho vị thế còn hoạt động (vừa sống qua Pha 1, hoặc mới mở ở Pha 3)
        if symbol in self.positions:
            pos = self.positions[symbol]
            intrabar_exit_triggered = False
            exit_reason = None
            raw_exit_price = 0.0

            if pos.direction == OrderDirection.LONG:
                # Ưu tiên bảo thủ: Liquidation > Stop Loss > Take Profit
                if low_p <= pos.liquidation_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.LIQUIDATION
                    raw_exit_price = pos.liquidation_price
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
                    raw_exit_price = pos.liquidation_price
                elif high_p >= pos.stop_loss_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.STOP_LOSS
                    raw_exit_price = pos.stop_loss_price * (1.0 + self.slippage_pct)
                elif pos.take_profit_price is not None and low_p <= pos.take_profit_price:
                    intrabar_exit_triggered = True
                    exit_reason = ExitReason.TAKE_PROFIT
                    raw_exit_price = pos.take_profit_price * (1.0 + self.slippage_pct)

            if intrabar_exit_triggered and exit_reason is not None:
                trade_rec = self._execute_exit(
                    position=pos,
                    exit_price=raw_exit_price,
                    exit_time=close_time,
                    exit_reason=exit_reason,
                    intrabar_estimated=True,
                )
                candle_events.append({"type": "INTRABAR_EXIT", "trade": trade_rec})

        # =========================================================
        # PHA 5: Close Time & Mark-to-Market
        # =========================================================
        self.current_time = close_time
        # Tiến đồng hồ ngắt mạch tới close_time
        self.circuit_breaker.advance_time(close_time)

        # Cập nhật unrealized PnL theo giá close
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos._last_unrealized_pnl = pos.calculate_unrealized_pnl(close_p)
        
        # Kiểm tra cạn vốn / deficit
        if self.equity <= 0:
            self.is_halted = True
            logger.error("[PaperBroker] Tài khoản cạn vốn (equity = {:.2f} <= 0). Halted toàn bộ.", self.equity)

        # Chụp ảnh tài khoản tại close_time
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
    ) -> TradeRecord:
        """
        Thực hiện đóng vị thế, hạch toán PnL, giải phóng ký quỹ và đồng bộ Circuit Breaker.
        """
        exit_notional = position.quantity * exit_price
        exit_fee = exit_notional * self.taker_fee_pct

        if position.direction == OrderDirection.LONG:
            gross_pnl = position.quantity * (exit_price - position.entry_price)
        else:
            gross_pnl = position.quantity * (position.entry_price - exit_price)

        # Net trade PnL = Gross Price PnL - Entry Fee - Exit Fee + Cumulative Funding
        net_trade_pnl = gross_pnl - position.entry_fee - exit_fee + position.cumulative_funding

        # Giải phóng isolated collateral và cập nhật wallet:
        # Wallet trước đó đã trừ entry_fee và cộng/trừ funding.
        # Nay cộng thêm gross_pnl và trừ exit_fee.
        self.wallet_balance += (gross_pnl - exit_fee)

        return_pct = (net_trade_pnl / position.initial_margin) * 100.0 if position.initial_margin > 0 else 0.0

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
        )
        self.trade_history.append(trade_rec)

        # Ghi nhận kết quả giao dịch vào Circuit Breaker để theo dõi chuỗi và daily loss limit
        # Lưu ý: CircuitBreaker yêu cầu current_equity sau lệnh
        safe_equity = max(0.0, self.equity)
        self.circuit_breaker.record_trade_result(
            pnl=net_trade_pnl,
            timestamp=exit_time,
            equity=safe_equity,
        )

        # Xóa vị thế khỏi danh sách active
        del self.positions[position.symbol]

        # Nếu Circuit Breaker vừa kích hoạt trạng thái khóa (locked), hủy toàn bộ pending orders
        if self.circuit_breaker.is_locked:
            for pending in self.pending_orders:
                self._update_order_record(
                    req=pending,
                    status=OrderStatus.CANCELLED,
                    processed_at=exit_time,
                    reasons=["ORDER_CANCELLED_CIRCUIT_BREAKER_LOCKED"],
                )
            self.pending_orders.clear()

        return trade_rec

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
        """
        direction_sign = 1.0 if position.direction == OrderDirection.LONG else -1.0
        cashflow = -direction_sign * position.quantity * mark_price * funding_rate

        self.wallet_balance += cashflow
        position.isolated_collateral += cashflow
        position.cumulative_funding += cashflow

        event = FundingEvent(
            event_id=self._next_funding_id(position.symbol, timestamp),
            timestamp=timestamp,
            symbol=position.symbol,
            position_id=position.position_id,
            funding_rate=funding_rate,
            settlement_mark_price=mark_price,
            position_quantity=position.quantity,
            cashflow_usd=cashflow,
        )
        self.funding_history.append(event)
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
                if reasons:
                    rec.rejection_reasons = list(reasons)
                break

    def update_stop_loss(self, symbol: str, new_stop_loss: float) -> bool:
        """
        Cập nhật Stop Loss cho vị thế đang mở.
        Chỉ cho phép thắt chặt rủi ro:
        - LONG: chỉ được nâng SL lên cao hơn.
        - SHORT: chỉ được hạ SL xuống thấp hơn.
        """
        symbol = str(symbol).upper()
        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        new_sl = _validate_finite_positive("new_stop_loss", new_stop_loss)

        if pos.direction == OrderDirection.LONG:
            if new_sl <= pos.stop_loss_price:
                return False  # Không cho phép nới rộng SL
            if new_sl >= pos.entry_price:
                # Cho phép trailing stop dương hoặc bảo hòa vốn
                pass
            pos.stop_loss_price = new_sl
            return True
        else:  # SHORT
            if new_sl >= pos.stop_loss_price:
                return False  # Không cho phép nới rộng SL
            pos.stop_loss_price = new_sl
            return True

    def close_all_positions(self, current_price: float, timestamp: datetime, reason: ExitReason) -> List[TradeRecord]:
        """Đóng khẩn cấp toàn bộ vị thế đang mở (dùng khi ngắt mạch hoặc kết thúc backtest)."""
        closed_trades = []
        for symbol in list(self.positions.keys()):
            pos = self.positions[symbol]
            trade = self._execute_exit(
                position=pos,
                exit_price=current_price,
                exit_time=timestamp,
                exit_reason=reason,
                intrabar_estimated=False,
            )
            closed_trades.append(trade)
        return closed_trades

    def verify_accounting_invariants(self) -> None:
        """
        Kiểm tra tính nhất quán toán học của toàn bộ sổ cái kế toán (Accounting Invariants).
        Bắt buộc thỏa mãn với sai số số học 1e-4:
        1. wallet_balance == initial_balance + sum(gross_pnl) - sum(all_fees) + sum(funding)
        2. available_margin == wallet_balance - reserved_collateral
        3. equity == wallet_balance + unrealized_pnl
        """
        total_gross_pnl = sum(t.gross_price_pnl for t in self.trade_history)
        total_fees = sum(t.entry_fee + t.exit_fee for t in self.trade_history) + sum(
            pos.entry_fee for pos in self.positions.values()
        )
        total_funding = sum(f.cashflow_usd for f in self.funding_history)

        expected_wallet = self.initial_balance + total_gross_pnl - total_fees + total_funding

        if abs(self.wallet_balance - expected_wallet) > 1e-4:
            raise AssertionError(
                f"Accounting invariant violated! wallet_balance ({self.wallet_balance:.4f}) != expected_wallet ({expected_wallet:.4f})"
            )

        expected_available = self.wallet_balance - self.reserved_collateral
        if abs(self.available_margin - expected_available) > 1e-4:
            raise AssertionError(
                f"Margin invariant violated! available_margin ({self.available_margin:.4f}) != expected ({expected_available:.4f})"
            )

        expected_equity = self.wallet_balance + self.unrealized_pnl
        if abs(self.equity - expected_equity) > 1e-4:
            raise AssertionError(
                f"Equity invariant violated! equity ({self.equity:.4f}) != expected ({expected_equity:.4f})"
            )

    @staticmethod
    def _parse_timeframe_duration(tf: str) -> timedelta:
        """Chuyển chuỗi timeframe ('1m', '15m', '4h', '1d') sang timedelta."""
        tf = tf.strip().lower()
        if tf.endswith("m"):
            return timedelta(minutes=int(tf[:-1]))
        elif tf.endswith("h"):
            return timedelta(hours=int(tf[:-1]))
        elif tf.endswith("d"):
            return timedelta(days=int(tf[:-1]))
        return timedelta(minutes=1)
