"""
invariant_checks.py - Invariant Checks & Liquidation Calculation
=================================================================
Đảm bảo mọi lệnh giao dịch trước khi gửi vào execution engine đều phải thỏa mãn
toàn bộ 6 Hard Invariants (Luật bất biến cứng) theo mục 4.4 của Master Spec:

1. Stop-Loss check: Bắt buộc có stop_loss_price và đúng chiều so với entry_price.
2. Leverage Cap check: Đòn bẩy không vượt quá config.risk.max_leverage (mặc định 5x).
3. Min Liquidation Buffer check: |P_liq - P_stop| / P_entry >= config.risk.min_liquidation_buffer_pct (30%).
4. Conviction Tier Limit check: risk_percent <= trần của tier tương ứng trong config.
5. Circuit Breaker Lock check: Không mở lệnh nếu hệ thống đang bị khóa bởi Circuit Breaker.
6. News Blackout Window check: Không mở lệnh trong cửa sổ ±15 phút quanh sự kiện kinh tế lớn (nếu news_filter được bật).

Hàm check_all_invariants() LUÔN trả về toàn bộ danh sách vi phạm (không dừng ở lỗi đầu tiên).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from loguru import logger

# Bảng leverage brackets chuẩn Binance Futures BTCUSDT (fallback nếu config không có)
DEFAULT_LEVERAGE_BRACKETS_BTC = [
    [50000,      0.004, 0],
    [250000,     0.005, 50],
    [1000000,    0.01,  1300],
    [10000000,   0.025, 16300],
    [20000000,   0.05,  266300],
    [50000000,   0.10,  1266300],
    [100000000,  0.125, 2516300],
    [200000000,  0.15,  5016300],
    [300000000,  0.25,  25016300],
    [500000000,  0.50,  100016300],
]


def get_mmr_tier(
    position_size_usd: float,
    symbol: str = "BTCUSDT",
    leverage_brackets: Optional[Dict[str, List[List[Union[float, int]]]]] = None,
) -> Tuple[float, float]:
    """
    Tra bảng leverage brackets để lấy Maintenance Margin Rate (MMR) và
    Maintenance Amount (cum_amt) tích lũy theo quy mô vị thế danh nghĩa (position_size_usd).

    Args:
        position_size_usd: Quy mô danh nghĩa của vị thế tính theo USD.
        symbol: Ký hiệu cặp giao dịch (mặc định 'BTCUSDT').
        leverage_brackets: Bảng brackets từ config.

    Returns:
        (mmr_pct, cumulative_maintenance_amount)
    """
    brackets = None
    if leverage_brackets and symbol in leverage_brackets:
        brackets = leverage_brackets[symbol]
    elif leverage_brackets and "BTC/USDT" in leverage_brackets:
        brackets = leverage_brackets["BTC/USDT"]
    else:
        brackets = DEFAULT_LEVERAGE_BRACKETS_BTC

    abs_notional = abs(position_size_usd)
    for max_notional, mmr_pct, cum_amt in brackets:
        if abs_notional <= max_notional:
            return float(mmr_pct), float(cum_amt)

    # Nếu quy mô vượt nấc cao nhất, dùng tier cuối cùng
    return float(brackets[-1][1]), float(brackets[-1][2])


def calculate_estimated_liquidation_price(
    direction: str,
    entry_price: float,
    position_size_usd: float,
    leverage: float,
    symbol: str = "BTCUSDT",
    leverage_brackets: Optional[Dict[str, List[List[Union[float, int]]]]] = None,
) -> float:
    """
    Tính giá thanh lý ước tính (Estimated Liquidation Price) theo chuẩn Binance Futures Isolated Margin:
    - Tra đúng MMR tier và cum_amt theo quy mô vị thế danh nghĩa.
    - Long:  P_liq = [entry_price * (1 - 1/leverage) - (cum_amt / quantity)] / (1 - MMR)
    - Short: P_liq = [entry_price * (1 + 1/leverage) + (cum_amt / quantity)] / (1 + MMR)

    Args:
        direction: 'LONG' hoặc 'SHORT' (không phân biệt hoa thường).
        entry_price: Giá mở vị thế.
        position_size_usd: Quy mô danh nghĩa tính theo USD (Position Size USD = Quantity * Entry Price).
        leverage: Đòn bẩy sử dụng (>= 1.0).
        symbol: Cặp tiền giao dịch.
        leverage_brackets: Bảng brackets tra cứu MMR.

    Returns:
        Giá thanh lý ước tính (float).
    """
    if entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    if position_size_usd <= 0:
        raise ValueError(f"position_size_usd must be positive, got {position_size_usd}")
    if leverage < 1.0:
        raise ValueError(f"leverage must be >= 1.0, got {leverage}")

    dir_str = str(direction).strip().upper()
    if dir_str not in ("LONG", "SHORT", "BUY", "SELL"):
        raise ValueError(f"Invalid direction: '{direction}'. Expected 'LONG' or 'SHORT'.")

    quantity = position_size_usd / entry_price
    mmr_pct, cum_amt = get_mmr_tier(position_size_usd, symbol, leverage_brackets)

    cum_per_qty = cum_amt / quantity if quantity > 0 else 0.0

    if dir_str in ("LONG", "BUY"):
        # Với Long: Giá giảm thì bị thanh lý
        numerator = entry_price * (1.0 - 1.0 / leverage) - cum_per_qty
        denominator = 1.0 - mmr_pct
        if denominator <= 0:
            liq_price = 0.0
        else:
            liq_price = numerator / denominator
        return max(0.0, float(liq_price))
    else:
        # Với Short: Giá tăng thì bị thanh lý
        numerator = entry_price * (1.0 + 1.0 / leverage) + cum_per_qty
        denominator = 1.0 + mmr_pct
        liq_price = numerator / denominator
        return float(liq_price)


def check_all_invariants(
    order: Dict[str, Any],
    account_state: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Kiểm tra toàn bộ 6 Hard Invariants của một lệnh trước khi được chấp nhận.
    LUÔN kiểm tra toàn bộ và trả về đầy đủ danh sách lý do vi phạm (nếu có).

    Args:
        order: Dict thông tin lệnh, gồm:
            - symbol: str (VD: 'BTCUSDT')
            - direction: str ('LONG' hoặc 'SHORT')
            - entry_price: float
            - stop_loss_price: Optional[float]
            - leverage: float
            - risk_percent: float
            - conviction_tier: Optional[str] (VD: 'low', 'normal', 'high', 'ultra_high')
            - position_size_usd: Optional[float] (nếu thiếu sẽ tự tính từ risk_usd và SL)
            - timestamp: Optional[Union[datetime, int, float]]
        account_state: Dict trạng thái tài khoản hiện tại:
            - equity: float
            - circuit_breaker_state: Optional[CircuitBreakerState]
            - news_filter: Optional[NewsCalendarFilter]
            - current_time: Optional[Union[datetime, int, float]]
        config: Dict cấu hình hệ thống (default_config.yaml).

    Returns:
        (is_valid, rejection_reasons)
        - is_valid: True nếu vượt qua toàn bộ 6 invariant, False nếu có ít nhất 1 vi phạm.
        - rejection_reasons: List các chuỗi mô tả chi tiết từng lỗi vi phạm.
    """
    rejection_reasons: List[str] = []
    risk_cfg = config.get("risk", {})
    brackets = config.get("leverage_brackets", {})

    entry_price = float(order.get("entry_price", 0.0))
    stop_loss_price = order.get("stop_loss_price")
    direction = str(order.get("direction", "")).strip().upper()
    leverage = float(order.get("leverage", 1.0))
    risk_percent = float(order.get("risk_percent", 0.0))
    symbol = str(order.get("symbol", "BTCUSDT"))

    # -------------------------------------------------------------
    # 1. Hard Invariant A: Stop-Loss check
    # -------------------------------------------------------------
    if stop_loss_price is None or float(stop_loss_price) <= 0:
        rejection_reasons.append(
            "INVARIANT_FAIL_STOP_LOSS_MISSING: Order must have a valid positive stop_loss_price."
        )
    else:
        sl = float(stop_loss_price)
        if direction in ("LONG", "BUY") and sl >= entry_price:
            rejection_reasons.append(
                f"INVARIANT_FAIL_STOP_LOSS_DIRECTION: LONG stop_loss_price ({sl}) "
                f"must be strictly lower than entry_price ({entry_price})."
            )
        elif direction in ("SHORT", "SELL") and sl <= entry_price:
            rejection_reasons.append(
                f"INVARIANT_FAIL_STOP_LOSS_DIRECTION: SHORT stop_loss_price ({sl}) "
                f"must be strictly higher than entry_price ({entry_price})."
            )

    # -------------------------------------------------------------
    # 2. Hard Invariant B: Leverage Cap check
    # -------------------------------------------------------------
    max_leverage = float(risk_cfg.get("max_leverage", 5.0))
    if leverage > max_leverage:
        rejection_reasons.append(
            f"INVARIANT_FAIL_LEVERAGE_EXCEEDED: Requested leverage {leverage}x "
            f"exceeds max allowable leverage {max_leverage}x."
        )

    # -------------------------------------------------------------
    # 3. Hard Invariant C: Min Liquidation Buffer check
    # -------------------------------------------------------------
    # Tính position_size_usd nếu chưa có
    position_size_usd = order.get("position_size_usd")
    equity = float(account_state.get("equity", 10000.0))
    if position_size_usd is None or float(position_size_usd) <= 0:
        if stop_loss_price is not None and float(stop_loss_price) > 0 and entry_price > 0 and float(stop_loss_price) != entry_price:
            stop_dist_pct = abs(entry_price - float(stop_loss_price)) / entry_price
            position_size_usd = (equity * risk_percent) / stop_dist_pct
        else:
            position_size_usd = equity * leverage

    position_size_usd = float(position_size_usd)
    min_buffer_pct = float(risk_cfg.get("min_liquidation_buffer_pct", 0.30))

    if entry_price > 0 and position_size_usd > 0 and leverage >= 1.0 and direction in ("LONG", "SHORT", "BUY", "SELL"):
        try:
            liq_price = calculate_estimated_liquidation_price(
                direction=direction,
                entry_price=entry_price,
                position_size_usd=position_size_usd,
                leverage=leverage,
                symbol=symbol,
                leverage_brackets=brackets,
            )

            if stop_loss_price is not None and float(stop_loss_price) > 0:
                sl = float(stop_loss_price)
                # Kiểm tra liquidation có kích hoạt trước stop loss không
                if direction in ("LONG", "BUY") and liq_price >= sl:
                    rejection_reasons.append(
                        f"INVARIANT_FAIL_LIQUIDATION_BEFORE_SL: Estimated liquidation price ({liq_price:.2f}) "
                        f"would trigger before stop loss ({sl:.2f}) on LONG position."
                    )
                elif direction in ("SHORT", "SELL") and liq_price <= sl:
                    rejection_reasons.append(
                        f"INVARIANT_FAIL_LIQUIDATION_BEFORE_SL: Estimated liquidation price ({liq_price:.2f}) "
                        f"would trigger before stop loss ({sl:.2f}) on SHORT position."
                    )
                else:
                    # Kiểm tra khoảng cách buffer tối thiểu >= 30%
                    buffer_pct = abs(liq_price - sl) / entry_price
                    if buffer_pct < min_buffer_pct - 1e-6:
                        rejection_reasons.append(
                            f"INVARIANT_FAIL_LIQUIDATION_BUFFER: Liquidation buffer {buffer_pct * 100:.2f}% "
                            f"is below minimum required {min_buffer_pct * 100:.2f}% (P_liq: {liq_price:.2f}, SL: {sl:.2f})."
                        )
        except Exception as e:
            rejection_reasons.append(f"INVARIANT_FAIL_LIQUIDATION_CALC_ERROR: Failed to calculate liquidation price: {e}")

    # -------------------------------------------------------------
    # 4. Hard Invariant D: Conviction Tier Limit check
    # -------------------------------------------------------------
    conviction_tiers = risk_cfg.get("conviction_tiers", {
        "low": 0.01,
        "normal": 0.02,
        "high": 0.05,
        "ultra_high": 0.10,
    })
    tier_name = order.get("conviction_tier")
    if tier_name and tier_name in conviction_tiers:
        tier_limit = float(conviction_tiers[tier_name])
    else:
        tier_limit = float(max(conviction_tiers.values()))

    if risk_percent > tier_limit + 1e-6:
        tier_label = tier_name or "max_tier"
        rejection_reasons.append(
            f"INVARIANT_FAIL_RISK_TIER_EXCEEDED: Requested risk_percent {risk_percent * 100:.2f}% "
            f"exceeds conviction tier '{tier_label}' limit of {tier_limit * 100:.2f}%."
        )

    # -------------------------------------------------------------
    # 5. Hard Invariant E: Circuit Breaker Lock check
    # -------------------------------------------------------------
    cb_state = account_state.get("circuit_breaker_state")
    current_time = (
        order.get("timestamp")
        or account_state.get("current_time")
        or datetime.now(timezone.utc)
    )
    if cb_state is not None:
        if hasattr(cb_state, "is_trading_allowed"):
            if not cb_state.is_trading_allowed(current_time):
                locked_until_str = str(getattr(cb_state, "locked_until", "unknown"))
                rejection_reasons.append(
                    f"INVARIANT_FAIL_CIRCUIT_BREAKER_LOCKED: Trading is currently locked "
                    f"by circuit breaker until {locked_until_str}."
                )

    # -------------------------------------------------------------
    # 6. Hard Invariant F: News Blackout Window check
    # -------------------------------------------------------------
    news_filter = account_state.get("news_filter")
    if news_filter is not None and getattr(news_filter, "enabled", False):
        if hasattr(news_filter, "is_in_blackout"):
            is_blackout, event_name = news_filter.is_in_blackout(current_time)
            if is_blackout:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_NEWS_BLACKOUT: Order time {current_time} falls within "
                    f"blackout window of economic event '{event_name}'."
                )

    # -------------------------------------------------------------
    # Tổng kết
    # -------------------------------------------------------------
    is_valid = (len(rejection_reasons) == 0)
    if not is_valid:
        logger.warning(
            "[RiskManager] Lệnh bị từ chối với {} vi phạm: {}",
            len(rejection_reasons), rejection_reasons
        )
    return is_valid, rejection_reasons
