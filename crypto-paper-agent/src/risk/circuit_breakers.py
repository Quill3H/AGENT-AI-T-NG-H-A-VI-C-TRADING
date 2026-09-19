"""
circuit_breakers.py - Circuit Breakers Module
=============================================
Quản lý trạng thái ngắt mạch bảo vệ tài khoản (Circuit Breakers) tuân thủ ADR 0002 và ADR 0006:
1. Rolling 24h PnL Loss Limit:
   - Cửa sổ trượt là khoảng nửa mở nửa đóng (T - 24h, T].
   - Tự động làm mới khi thời gian tiến lên (trong cả record_trade_result và is_trading_allowed).
   - Nếu tổng lỗ ròng rolling 24h <= -1 * (equity * daily_loss_limit_pct) -> khóa giao dịch đúng 24h kể từ lần kích hoạt đầu.
   - Các lệnh tất toán phát sinh trong thời gian đang bị khóa không kéo dài thêm locked_until.
2. Consecutive Losses Streak:
   - Thua liên tiếp >= consecutive_losses_threshold (3 lệnh) -> giảm risk_multiplier = 0.5.
3. Recovery Mode (after_3_wins - ADR 0002):
   - Đang ở mức risk 0.5, cần đúng 3 lệnh thắng liên tiếp để phục hồi về 1.0.
   - Nếu có lệnh thua hoặc lệnh hòa xen giữa, chuỗi thắng lập tức reset về 0 (không cộng dồn).
4. Lệnh hòa (pnl == 0):
   - Reset cả chuỗi thắng và chuỗi thua về 0, nhưng giữ nguyên risk_multiplier hiện tại.
5. Vệ sinh dữ liệu & Thời gian đơn điệu:
   - Từ chối NaN/Inf/bool/chuỗi sai cho pnl và equity; không mutate state khi input lỗi.
   - Từ chối sự kiện lùi thời gian (t < last_recorded_time).
"""
from datetime import datetime, timedelta, timezone
import math
from typing import Any, List, Optional, Tuple, Union
from loguru import logger


def _ensure_utc_datetime(ts: Any) -> datetime:
    """Chuyển đổi timestamp bất kỳ thành timezone-aware UTC datetime."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if isinstance(ts, (int, float)):
        if type(ts) is bool or not math.isfinite(float(ts)):
            raise ValueError(f"Invalid timestamp value: {ts}")
        val = float(ts)
        if val > 1e11:
            val = val / 1000.0
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as e:
            raise ValueError(f"Timestamp value out of valid platform range: {ts!r}") from e
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError, OSError) as e:
            raise ValueError(f"Malformed or out-of-range ISO timestamp string: {ts!r}") from e
    raise TypeError(f"Unsupported timestamp type: {type(ts).__name__}: {ts!r}")


class CircuitBreakerState:
    """
    Quản lý trạng thái và luật ngắt mạch của hệ thống paper trading.
    """
    SUPPORTED_RECOVERY_MODES = {"after_3_wins", "after_1_win"}

    def __init__(
        self,
        daily_loss_limit_pct: float = 0.05,
        consecutive_losses_threshold: int = 3,
        risk_reduction_on_streak: float = 0.5,
        consecutive_wins_to_recover: int = 3,
        recovery_mode: str = "after_3_wins",
    ):
        # Validate tham số cấu hình
        if recovery_mode not in self.SUPPORTED_RECOVERY_MODES:
            raise ValueError(
                f"Unsupported recovery_mode '{recovery_mode}'. Supported modes: {sorted(self.SUPPORTED_RECOVERY_MODES)}"
            )

        if type(daily_loss_limit_pct) is bool or not isinstance(daily_loss_limit_pct, (int, float)) or not (0 < daily_loss_limit_pct < 1.0):
            raise ValueError(f"daily_loss_limit_pct must be between 0 and 1, got {daily_loss_limit_pct}")
        if type(consecutive_losses_threshold) is bool or not isinstance(consecutive_losses_threshold, int) or consecutive_losses_threshold < 1:
            raise ValueError(f"consecutive_losses_threshold must be integer >= 1, got {consecutive_losses_threshold}")
        if type(risk_reduction_on_streak) is bool or not isinstance(risk_reduction_on_streak, (int, float)) or not (0 < risk_reduction_on_streak < 1.0):
            raise ValueError(f"risk_reduction_on_streak must be between 0 and 1, got {risk_reduction_on_streak}")
        if type(consecutive_wins_to_recover) is bool or not isinstance(consecutive_wins_to_recover, int) or consecutive_wins_to_recover < 1:
            raise ValueError(f"consecutive_wins_to_recover must be integer >= 1, got {consecutive_wins_to_recover}")

        # Kiểm tra tính nhất quán giữa recovery_mode và consecutive_wins_to_recover
        if recovery_mode == "after_3_wins" and consecutive_wins_to_recover != 3:
            raise ValueError(
                f"Configuration mismatch: recovery_mode is '{recovery_mode}' but consecutive_wins_to_recover is {consecutive_wins_to_recover}"
            )
        if recovery_mode == "after_1_win" and consecutive_wins_to_recover != 1:
            raise ValueError(
                f"Configuration mismatch: recovery_mode is '{recovery_mode}' but consecutive_wins_to_recover is {consecutive_wins_to_recover}"
            )

        self.daily_loss_limit_pct: float = float(daily_loss_limit_pct)
        self.consecutive_losses_threshold: int = consecutive_losses_threshold
        self.risk_reduction_on_streak: float = float(risk_reduction_on_streak)
        self.consecutive_wins_to_recover: int = consecutive_wins_to_recover
        self.recovery_mode: str = recovery_mode

        # Trạng thái động
        self.rolling_24h_pnl: float = 0.0
        self.trade_history_24h: List[Tuple[datetime, float]] = []
        self.consecutive_losses: int = 0
        self.consecutive_wins: int = 0
        self.risk_multiplier: float = 1.0
        self.is_locked: bool = False
        self.is_halted: bool = False
        self.locked_until: Optional[datetime] = None
        self.last_event_time: Optional[datetime] = None

    @property
    def current_timestamp(self) -> Optional[datetime]:
        """Thời điểm sự kiện hoặc truy vấn gần nhất của đồng hồ ngắt mạch."""
        return self.last_event_time

    @classmethod
    def from_config(cls, config: dict) -> "CircuitBreakerState":
        """Khởi tạo instance từ dictionary cấu hình hệ thống."""
        cb_cfg = config.get("circuit_breakers", {})
        return cls(
            daily_loss_limit_pct=cb_cfg.get("daily_loss_limit_pct", 0.05),
            consecutive_losses_threshold=cb_cfg.get("consecutive_losses_threshold", 3),
            risk_reduction_on_streak=cb_cfg.get("risk_reduction_on_streak", 0.5),
            consecutive_wins_to_recover=cb_cfg.get("consecutive_wins_to_recover", 3),
            recovery_mode=cb_cfg.get("recovery_mode", "after_3_wins"),
        )

    def _prune_window(self, current_time: datetime) -> None:
        """
        Làm mới cửa sổ trượt 24h: loại bỏ các giao dịch đã cũ hơn 24h tính đến current_time.
        Cửa sổ quy ước: (current_time - 24h, current_time].
        """
        cutoff_time = current_time - timedelta(hours=24)
        self.trade_history_24h = [
            (t, p) for t, p in self.trade_history_24h if t > cutoff_time
        ]
        self.rolling_24h_pnl = sum(p for _, p in self.trade_history_24h)

    def advance_time(self, current_timestamp: Union[datetime, int, float, str]) -> datetime:
        """
        Tiến đồng hồ hệ thống ngắt mạch đến current_timestamp.
        - Kiểm tra tính đơn điệu của thời gian (chống time reversal).
        - Cắt tỉa các giao dịch cũ hơn 24h: (current_time - 24h, current_time].
        - Tự động mở khóa nếu đã hết hạn locked_until.
        """
        dt = _ensure_utc_datetime(current_timestamp)
        if self.last_event_time is not None and dt < self.last_event_time:
            raise ValueError(
                f"Cannot advance time backwards: timestamp {dt.isoformat()} is earlier than "
                f"last recorded time {self.last_event_time.isoformat()} (time reversal)."
            )
        self.last_event_time = dt
        self._prune_window(dt)

        # Kiểm tra hết hạn khóa 24h
        if self.is_locked and self.locked_until is not None and dt >= self.locked_until:
            logger.info(
                "[CircuitBreaker] Thời gian khóa 24h đã hết hạn tại {}. Mở lại quyền giao dịch.",
                dt.isoformat()
            )
            self.is_locked = False
            self.locked_until = None

        return dt

    def record_cashflow(
        self,
        amount: float,
        timestamp: Union[datetime, int, float, str],
        equity: float,
        param_name: str = "amount",
    ) -> None:
        """
        Ghi nhận trực tiếp dòng tiền (ví dụ: funding, phí) vào cửa sổ rolling 24h PnL
        mà KHÔNG tính vào chuỗi thắng/thua của các lệnh (consecutive_losses / consecutive_wins).
        """
        if type(amount) is bool or not isinstance(amount, (int, float)):
            raise TypeError(f"{param_name} must be numeric float or int, got {type(amount).__name__}: {amount!r}")
        f_amt = float(amount)
        if not math.isfinite(f_amt):
            raise ValueError(f"{param_name} must be finite, got {f_amt}")

        if type(equity) is bool or not isinstance(equity, (int, float)):
            raise TypeError(f"equity must be numeric float or int, got {type(equity).__name__}: {equity!r}")
        f_eq = float(equity)
        if not math.isfinite(f_eq) or f_eq < 0:
            raise ValueError(f"equity must be non-negative finite number, got {f_eq}")

        dt = self.advance_time(timestamp)

        if f_eq == 0:
            self.is_halted = True
            self.is_locked = True
            self.locked_until = None
            logger.error("[CircuitBreaker] Tài khoản cạn vốn (equity = 0)! Kích hoạt HALTED hoàn toàn.")
            return

        self.trade_history_24h.append((dt, f_amt))
        self.rolling_24h_pnl = sum(p for _, p in self.trade_history_24h)

        loss_limit_usd = f_eq * self.daily_loss_limit_pct
        if self.rolling_24h_pnl <= -1.0 * loss_limit_usd:
            if not self.is_locked:
                self.is_locked = True
                self.locked_until = dt + timedelta(hours=24)
                logger.warning(
                    "[CircuitBreaker] KÍCH HOẠT KHÓA 24H qua cashflow! Rolling 24h PnL: {:.2f}$ vượt ngưỡng lỗ tối đa: -{:.2f}$ ({:.1f}%). "
                    "Khóa giao dịch tới: {}",
                    self.rolling_24h_pnl, loss_limit_usd, self.daily_loss_limit_pct * 100, self.locked_until.isoformat()
                )
            else:
                logger.info(
                    "[CircuitBreaker] Đang trong thời gian khóa, ghi nhận thêm cashflow: {:.2f}$. Giữ nguyên mốc khóa: {}",
                    f_amt, self.locked_until.isoformat()
                )

    def record_trade_outcome(
        self,
        net_pnl: float,
        timestamp: Union[datetime, int, float, str],
    ) -> None:
        """
        Cập nhật chuỗi thắng/thua (consecutive_losses / consecutive_wins) và risk_multiplier
        từ kết quả của lệnh vừa tất toán mà KHÔNG ghi nhận thêm vào rolling 24h cashflow ledger.
        """
        if type(net_pnl) is bool or not isinstance(net_pnl, (int, float)):
            raise TypeError(f"net_pnl must be numeric float or int, got {type(net_pnl).__name__}: {net_pnl!r}")
        f_pnl = float(net_pnl)
        if not math.isfinite(f_pnl):
            raise ValueError(f"net_pnl must be finite, got {f_pnl}")

        dt = self.advance_time(timestamp)

        if f_pnl < 0:
            # Lệnh THUA
            self.consecutive_losses += 1
            self.consecutive_wins = 0  # BẮT BUỘC reset chuỗi thắng nếu có lệnh thua xen giữa
            if self.consecutive_losses >= self.consecutive_losses_threshold:
                if self.risk_multiplier != self.risk_reduction_on_streak:
                    self.risk_multiplier = self.risk_reduction_on_streak
                    logger.warning(
                        "[CircuitBreaker] Thua {} lệnh liên tiếp (ngưỡng: {}). "
                        "Giảm risk xuống {:.0f}% (multiplier = {:.2f}).",
                        self.consecutive_losses, self.consecutive_losses_threshold,
                        self.risk_reduction_on_streak * 100, self.risk_multiplier
                    )
        elif f_pnl > 0:
            # Lệnh THẮNG
            self.consecutive_losses = 0
            if self.risk_multiplier < 1.0:
                self.consecutive_wins += 1
                logger.info(
                    "[CircuitBreaker] Đang ở chế độ giảm risk, ghi nhận lệnh thắng ({}/{} để phục hồi).",
                    self.consecutive_wins, self.consecutive_wins_to_recover
                )
                if self.consecutive_wins >= self.consecutive_wins_to_recover:
                    self.risk_multiplier = 1.0
                    self.consecutive_wins = 0
                    logger.info(
                        "[CircuitBreaker] PHỤC HỒI RISK THÀNH CÔNG! Đã đạt đủ {} lệnh thắng liên tiếp. "
                        "Risk multiplier trở lại 1.0.",
                        self.consecutive_wins_to_recover
                    )
            else:
                self.consecutive_wins += 1
        else:
            # Lệnh HÒA (f_pnl == 0.0): Theo ADR 0006, ngắt cả chuỗi thắng và thua, giữ nguyên multiplier
            self.consecutive_losses = 0
            self.consecutive_wins = 0
            logger.info("[CircuitBreaker] Lệnh hòa (pnl=0). Reset cả chuỗi thắng và thua về 0.")

    def record_trade_result(
        self,
        pnl: float,
        timestamp: Union[datetime, int, float, str],
        equity: float,
        cashflow: Optional[float] = None,
        *args,
        **kwargs,
    ) -> None:
        """
        Ghi nhận kết quả PnL của 1 lệnh đã đóng và cập nhật trạng thái ngắt mạch.
        Nếu cashflow được cung cấp (vd: gross_pnl - exit_fee), chỉ ghi nhận cashflow đó vào rolling ledger
        thay vì net pnl (để tránh cộng trùng entry fee và funding đã ghi trước đó theo H1).
        """
        amt = cashflow if cashflow is not None else pnl
        self.record_cashflow(amount=amt, timestamp=timestamp, equity=equity, param_name="pnl")
        self.record_trade_outcome(net_pnl=pnl, timestamp=timestamp)


    def get_effective_risk_percent(self, base_risk_percent: float) -> float:
        """
        Tính tỷ lệ rủi ro hiệu lực sau khi áp dụng hệ số ngắt mạch.
        """
        if type(base_risk_percent) is bool or not isinstance(base_risk_percent, (int, float)):
            raise TypeError(f"base_risk_percent must be numeric, got {type(base_risk_percent).__name__}")
        f_brp = float(base_risk_percent)
        if not math.isfinite(f_brp) or f_brp <= 0:
            raise ValueError(f"base_risk_percent must be positive finite number, got {f_brp}")
        return f_brp * self.risk_multiplier

    def is_trading_allowed(self, current_timestamp: Union[datetime, int, float, str]) -> bool:
        """
        Kiểm tra xem hệ thống có đang được phép mở lệnh mới tại thời điểm hiện tại không.
        Tự động tiến đồng hồ và làm mới trạng thái khóa.

        Returns:
            True nếu được phép giao dịch.
            False nếu đang trong thời gian khóa ngắt mạch hoặc tài khoản bị halted.
        """
        dt = self.advance_time(current_timestamp)

        if self.is_halted:
            return False

        if self.is_locked:
            return False

        return True

    def reset(self) -> None:
        """Reset toàn bộ trạng thái về ban đầu (dùng khi khởi động lại backtest)."""
        self.rolling_24h_pnl = 0.0
        self.trade_history_24h = []
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.risk_multiplier = 1.0
        self.is_locked = False
        self.is_halted = False
        self.locked_until = None
        self.last_event_time = None
