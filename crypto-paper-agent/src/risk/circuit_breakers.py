"""
circuit_breakers.py - Circuit Breakers Module
=============================================
Quản lý trạng thái ngắt mạch bảo vệ tài khoản (Circuit Breakers):
1. Rolling 24h PnL Loss Limit: Nếu tổng lỗ ròng trong 24h qua vượt daily_loss_limit_pct (5%),
   khóa giao dịch trong 24 giờ.
2. Consecutive Losses Streak: Nếu thua liên tiếp >= consecutive_losses_threshold (3 lệnh),
   giảm risk_percent xuống 50% (risk_multiplier = 0.5).
3. Recovery Mode (after_3_wins - ADR 0002): Khi đang ở mức risk 50%, cần đúng 3 lệnh
   thắng liên tiếp để phục hồi về 100% (risk_multiplier = 1.0). Nếu có bất kỳ lệnh
   thua nào xen giữa, chuỗi thắng lập tức reset về 0 (không cộng dồn xuyên qua lệnh thua).
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Union
from loguru import logger


def _ensure_utc_datetime(ts: Union[datetime, int, float, str]) -> datetime:
    """Chuyển đổi timestamp thành timezone-aware UTC datetime."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if isinstance(ts, (int, float)):
        # Nếu > 1e11 coi như milliseconds
        if ts > 1e11:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise TypeError(f"Unsupported timestamp type: {type(ts)}")


class CircuitBreakerState:
    """
    Quản lý trạng thái và luật ngắt mạch của hệ thống paper trading.
    """
    def __init__(
        self,
        daily_loss_limit_pct: float = 0.05,
        consecutive_losses_threshold: int = 3,
        risk_reduction_on_streak: float = 0.5,
        consecutive_wins_to_recover: int = 3,
        recovery_mode: str = "after_3_wins",
    ):
        self.daily_loss_limit_pct: float = daily_loss_limit_pct
        self.consecutive_losses_threshold: int = consecutive_losses_threshold
        self.risk_reduction_on_streak: float = risk_reduction_on_streak
        self.consecutive_wins_to_recover: int = consecutive_wins_to_recover
        self.recovery_mode: str = recovery_mode

        # Trạng thái động
        self.rolling_24h_pnl: float = 0.0
        self.trade_history_24h: List[Tuple[datetime, float]] = []
        self.consecutive_losses: int = 0
        self.consecutive_wins: int = 0
        self.risk_multiplier: float = 1.0
        self.is_locked: bool = False
        self.locked_until: Optional[datetime] = None

    @classmethod
    def from_config(cls, config: dict) -> "CircuitBreakerState":
        """Khởi tạo instance từ dictionary cấu hình hệ thống."""
        cb_cfg = config.get("circuit_breakers", {})
        return cls(
            daily_loss_limit_pct=float(cb_cfg.get("daily_loss_limit_pct", 0.05)),
            consecutive_losses_threshold=int(cb_cfg.get("consecutive_losses_threshold", 3)),
            risk_reduction_on_streak=float(cb_cfg.get("risk_reduction_on_streak", 0.5)),
            consecutive_wins_to_recover=int(cb_cfg.get("consecutive_wins_to_recover", 3)),
            recovery_mode=str(cb_cfg.get("recovery_mode", "after_3_wins")),
        )

    def record_trade_result(
        self,
        pnl: float,
        timestamp: Union[datetime, int, float, str],
        equity: float,
    ) -> None:
        """
        Ghi nhận kết quả PnL của 1 lệnh đã đóng và cập nhật trạng thái ngắt mạch.

        Args:
            pnl: Lợi nhuận/thua lỗ ròng bằng USD (dương là thắng, âm là thua).
            timestamp: Thời điểm đóng lệnh.
            equity: Số dư vốn hiện tại của tài khoản (USD) tại thời điểm đóng lệnh.
        """
        dt = _ensure_utc_datetime(timestamp)

        # 1. Cập nhật cửa sổ trượt 24h
        cutoff_time = dt - timedelta(hours=24)
        self.trade_history_24h = [
            (t, p) for t, p in self.trade_history_24h if t >= cutoff_time
        ]
        self.trade_history_24h.append((dt, pnl))
        self.rolling_24h_pnl = sum(p for _, p in self.trade_history_24h)

        # 2. Kiểm tra Daily Loss Limit (ngưỡng 5% vốn hiện tại)
        loss_limit_usd = equity * self.daily_loss_limit_pct
        if self.rolling_24h_pnl <= -1.0 * loss_limit_usd:
            self.is_locked = True
            self.locked_until = dt + timedelta(hours=24)
            logger.warning(
                "[CircuitBreaker] KÍCH HOẠT KHÓA 24H! Rolling 24h PnL: {:.2f}$ vượt ngưỡng lỗ tối đa: -{:.2f}$ ({:.1f}%). "
                "Khóa giao dịch tới: {}",
                self.rolling_24h_pnl, loss_limit_usd, self.daily_loss_limit_pct * 100, self.locked_until.isoformat()
            )

        # 3. Quản lý chuỗi thắng / thua và điều chỉnh risk_multiplier
        if pnl < 0:
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
        elif pnl > 0:
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
            # Lệnh HÒA (pnl == 0): Không làm thay đổi chuỗi thắng/thua
            pass

    def get_effective_risk_percent(self, base_risk_percent: float) -> float:
        """
        Tính tỷ lệ rủi ro hiệu lực sau khi áp dụng hệ số ngắt mạch.
        """
        return base_risk_percent * self.risk_multiplier

    def is_trading_allowed(self, current_timestamp: Union[datetime, int, float, str]) -> bool:
        """
        Kiểm tra xem hệ thống có đang được phép mở lệnh mới tại thời điểm hiện tại không.

        Returns:
            True nếu được phép giao dịch.
            False nếu đang trong thời gian khóa ngắt mạch 24h.
        """
        if not self.is_locked:
            return True

        dt = _ensure_utc_datetime(current_timestamp)
        if self.locked_until is not None and dt >= self.locked_until:
            # Khóa 24h đã hết hạn -> Tự động mở khóa
            logger.info(
                "[CircuitBreaker] Thời gian khóa 24h đã hết hạn tại {}. Mở lại quyền giao dịch.",
                dt.isoformat()
            )
            self.is_locked = False
            self.locked_until = None
            return True

        return False

    def reset(self) -> None:
        """Reset toàn bộ trạng thái về ban đầu (dùng khi khởi động lại backtest)."""
        self.rolling_24h_pnl = 0.0
        self.trade_history_24h = []
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.risk_multiplier = 1.0
        self.is_locked = False
        self.locked_until = None
