"""
invariant_checks.py - Invariant Checks & Tier-Consistent Liquidation Calculation
=================================================================================
Đảm bảo mọi lệnh giao dịch trước khi gửi vào execution engine đều phải thỏa mãn
toàn bộ các Hard Invariants (Luật bất biến cứng) theo Master Spec mục 4.4, ADR 0002 và ADR 0006:

1. Stop-Loss check: Bắt buộc có stop_loss_price và đúng chiều so với entry_price.
2. Leverage Cap check: Đòn bẩy không vượt quá config.risk.max_leverage (mặc định 5x).
3. Min Liquidation Buffer check: |P_liq - P_stop| / P_entry >= config.risk.min_liquidation_buffer_pct (30%).
   Tính giá thanh lý nhất quán với MMR tier tại chính giá thanh lý (q * P_liq).
4. Conviction Tier Limit check: risk_percent <= trần của tier tương ứng; từ chối tier không hợp lệ.
5. Actual Risk & Margin check: Đối soát tổn thất giá thực tế Q * |Entry - Stop| với ngân sách rủi ro hiệu lực;
   đối soát required margin với available margin.
6. Circuit Breaker Lock check: Bắt buộc có CircuitBreakerState hợp lệ; không mở lệnh khi đang bị khóa.
7. News Blackout Window check: Khi news_filter.enabled=true, bắt buộc có NewsCalendarFilter hợp lệ;
   không mở lệnh trong cửa sổ tin tức.
8. Simulation Time: Bắt buộc dùng thời gian mô phỏng UTC rõ ràng, loại bỏ hoàn toàn fallback datetime.now().
"""
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from loguru import logger

# Bảng leverage brackets mặc định chuẩn Binance Futures BTCUSDT
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


def _normalize_symbol(symbol: str) -> str:
    """Chuẩn hóa symbol bỏ gạch chéo và in hoa (VD: 'BTC/USDT' -> 'BTCUSDT')."""
    return str(symbol).replace("/", "").strip().upper()


def _validate_brackets(brackets: List[List[Union[float, int]]], symbol: str) -> List[Tuple[float, float, float]]:
    """Xác thực cấu trúc bảng brackets: cap tăng dần, mmr hợp lệ, cum hợp lệ."""
    if not isinstance(brackets, list) or len(brackets) == 0:
        raise ValueError(f"Leverage brackets for symbol '{symbol}' must be a non-empty list.")
    
    parsed = []
    last_cap = 0.0
    for idx, row in enumerate(brackets):
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            raise ValueError(f"Invalid bracket row {idx} for symbol '{symbol}': {row}")
        cap, mmr, cum = float(row[0]), float(row[1]), float(row[2])
        if not (math.isfinite(cap) and math.isfinite(mmr) and math.isfinite(cum)):
            raise ValueError(f"Non-finite values in bracket row {idx} for symbol '{symbol}': {row}")
        if cap <= last_cap:
            raise ValueError(f"Bracket cap must be strictly increasing at row {idx} for symbol '{symbol}': {cap} <= {last_cap}")
        if not (0.0 < mmr < 1.0):
            raise ValueError(f"Invalid MMR rate {mmr} at row {idx} for symbol '{symbol}'")
        if cum < 0.0:
            raise ValueError(f"Invalid cum amount {cum} at row {idx} for symbol '{symbol}'")
        parsed.append((cap, mmr, cum))
        last_cap = cap
    return parsed


def get_brackets_for_symbol(
    symbol: str,
    leverage_brackets: Optional[Dict[str, Any]] = None,
) -> List[Tuple[float, float, float]]:
    """Lấy và xác thực bảng leverage brackets cho symbol được chỉ định."""
    norm_sym = _normalize_symbol(symbol)
    if leverage_brackets:
        # Tìm theo key chuẩn hóa
        for k, v in leverage_brackets.items():
            if _normalize_symbol(k) == norm_sym:
                return _validate_brackets(v, norm_sym)
        # Nếu truyền bảng brackets nhưng không có symbol này -> Báo lỗi rõ, KHÔNG tự mượn bảng BTC
        raise ValueError(f"Symbol '{symbol}' (normalized: '{norm_sym}') not found in provided leverage brackets configuration.")

    # Nếu hoàn toàn không truyền config brackets, dùng fallback chuẩn BTCUSDT
    if norm_sym == "BTCUSDT":
        return _validate_brackets(DEFAULT_LEVERAGE_BRACKETS_BTC, "BTCUSDT")
    raise ValueError(f"No leverage brackets configured for symbol '{symbol}'.")


def get_mmr_tier(
    position_size_usd: float,
    symbol: str = "BTCUSDT",
    leverage_brackets: Optional[Dict[str, Any]] = None,
) -> Tuple[float, float]:
    """
    Tra bảng leverage brackets để lấy MMR và cum_amt theo quy mô vị thế danh nghĩa position_size_usd.
    """
    if type(position_size_usd) is bool or not isinstance(position_size_usd, (int, float)):
        raise TypeError(f"position_size_usd must be numeric, got {type(position_size_usd).__name__}")
    notional = abs(float(position_size_usd))
    if not math.isfinite(notional):
        raise ValueError(f"position_size_usd must be finite, got {position_size_usd}")

    brackets = get_brackets_for_symbol(symbol, leverage_brackets)
    for max_notional, mmr_pct, cum_amt in brackets:
        if notional <= max_notional:
            return mmr_pct, cum_amt

    return brackets[-1][1], brackets[-1][2]


def calculate_estimated_liquidation_price(
    direction: str,
    entry_price: float,
    position_size_usd: float,
    leverage: float,
    symbol: str = "BTCUSDT",
    leverage_brackets: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Tính giá thanh lý ước tính theo chuẩn Binance Futures Isolated Margin và ADR 0006:
    Giải nhất quán theo tier của quy mô vị thế tại chính giá thanh lý (q * P_liq).

    Mô hình cân bằng:
    - Long:  M + q * (P - entry) = q * P * mmr - cum
             => P = [entry * (1 - 1/leverage) - cum/q] / (1 - mmr)
    - Short: M + q * (entry - P) = q * P * mmr - cum
             => P = [entry * (1 + 1/leverage) + cum/q] / (1 + mmr)

    Nghiệm P phải thỏa mãn: q * P nằm trong khoảng (lower_bound, upper_bound] của tier đó.
    """
    # 1. Validate numeric inputs
    for val, name in [
        (entry_price, "entry_price"),
        (position_size_usd, "position_size_usd"),
        (leverage, "leverage"),
    ]:
        if type(val) is bool or not isinstance(val, (int, float)):
            raise TypeError(f"{name} must be numeric, got {type(val).__name__}")
        if not math.isfinite(float(val)):
            raise ValueError(f"{name} must be finite, got {val}")

    f_entry = float(entry_price)
    f_notional = float(position_size_usd)
    f_lev = float(leverage)

    if f_entry <= 0:
        raise ValueError(f"entry_price must be positive, got {f_entry}")
    if f_notional <= 0:
        raise ValueError(f"position_size_usd must be positive, got {f_notional}")
    if f_lev < 1.0:
        raise ValueError(f"leverage must be >= 1.0, got {f_lev}")

    dir_str = str(direction).strip().upper()
    if dir_str not in ("LONG", "SHORT", "BUY", "SELL"):
        raise ValueError(f"Invalid direction: '{direction}'. Expected 'LONG' or 'SHORT'.")

    brackets = get_brackets_for_symbol(symbol, leverage_brackets)
    q = f_notional / f_entry

    # 2. Duyệt qua từng tier để tìm nghiệm tự nhất quán (Tier-Consistent Solution)
    lower_bound = 0.0
    for idx, (upper_bound, mmr, cum) in enumerate(brackets):
        cum_per_q = cum / q

        if dir_str in ("LONG", "BUY"):
            # P = [entry * (1 - 1/lev) - cum/q] / (1 - mmr)
            numerator = f_entry * (1.0 - 1.0 / f_lev) - cum_per_q
            denominator = 1.0 - mmr
            if denominator <= 0 or numerator <= 0:
                # Giá thanh lý <= 0 nghĩa là vị thế không thể bị thanh lý
                candidate_p = 0.0
            else:
                candidate_p = numerator / denominator

            candidate_notional = q * candidate_p
            # Kiểm tra candidate_notional có thuộc tier này không
            is_in_tier = (lower_bound < candidate_notional <= upper_bound) or (idx == 0 and candidate_notional <= upper_bound)
            # Nếu ở tier cuối cùng và notional vượt upper_bound, dùng tier cuối
            if idx == len(brackets) - 1 and candidate_notional > upper_bound:
                is_in_tier = True

            if is_in_tier:
                return max(0.0, float(candidate_p))

        else:
            # Short: P = [entry * (1 + 1/lev) + cum/q] / (1 + mmr)
            numerator = f_entry * (1.0 + 1.0 / f_lev) + cum_per_q
            denominator = 1.0 + mmr
            candidate_p = numerator / denominator

            candidate_notional = q * candidate_p
            is_in_tier = (lower_bound < candidate_notional <= upper_bound) or (idx == 0 and candidate_notional <= upper_bound)
            if idx == len(brackets) - 1 and candidate_notional > upper_bound:
                is_in_tier = True

            if is_in_tier:
                return float(candidate_p)

        lower_bound = upper_bound

    # Fallback an toàn nếu không rơi vào tier nào (dùng tier cuối)
    last_upper, last_mmr, last_cum = brackets[-1]
    if dir_str in ("LONG", "BUY"):
        num = f_entry * (1.0 - 1.0 / f_lev) - (last_cum / q)
        p = max(0.0, num / (1.0 - last_mmr))
    else:
        num = f_entry * (1.0 + 1.0 / f_lev) + (last_cum / q)
        p = num / (1.0 + last_mmr)
    return float(p)


def parse_simulation_timestamp(ts: Any) -> Optional[datetime]:
    """Chuyển đổi an toàn timestamp sang UTC datetime, trả về None nếu không hợp lệ."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if isinstance(ts, (int, float)):
        if type(ts) is bool or not math.isfinite(float(ts)):
            return None
        val = float(ts)
        if val > 1e11:
            val = val / 1000.0
        return datetime.fromtimestamp(val, tz=timezone.utc)
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


def check_all_invariants(
    order: Dict[str, Any],
    account_state: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Kiểm tra toàn diện 6 Hard Invariants cùng với xác thực dữ liệu đầu vào và đối soát rủi ro thực tế.
    LUÔN kiểm tra toàn bộ các điều kiện độc lập và trả về trọn vẹn danh sách lỗi.

    Returns:
        (is_valid: bool, rejection_reasons: List[str])
    """
    rejection_reasons: List[str] = []

    # -------------------------------------------------------------
    # 0. Xác thực Account State cơ bản
    # -------------------------------------------------------------
    if not isinstance(account_state, dict):
        return False, ["INVARIANT_FAIL_INVALID_ACCOUNT_STATE: account_state must be a dictionary."]

    raw_equity = account_state.get("equity")
    if type(raw_equity) is bool or not isinstance(raw_equity, (int, float)):
        rejection_reasons.append(
            f"INVARIANT_FAIL_INVALID_ACCOUNT_EQUITY: Account equity must be numeric, got {type(raw_equity).__name__}: {raw_equity!r}"
        )
        equity = 0.0
    else:
        equity = float(raw_equity)
        if not math.isfinite(equity) or equity <= 0:
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_ACCOUNT_EQUITY: Account equity must be positive and finite, got {equity}"
            )

    # Circuit breaker component check
    cb_state = account_state.get("circuit_breaker_state")
    if cb_state is None or not hasattr(cb_state, "is_trading_allowed"):
        rejection_reasons.append(
            "INVARIANT_FAIL_MISSING_CIRCUIT_BREAKER: account_state must contain a valid CircuitBreakerState instance."
        )

    # Xác định thời điểm mô phỏng (Admission Time) - KHÔNG dùng datetime.now() fallback
    order_ts = parse_simulation_timestamp(order.get("timestamp")) if isinstance(order, dict) else None
    account_ts = parse_simulation_timestamp(account_state.get("current_time"))
    admission_time = order_ts or account_ts

    if admission_time is None:
        rejection_reasons.append(
            "INVARIANT_FAIL_MISSING_TIMESTAMP: A valid simulation timestamp must be provided in order['timestamp'] or account_state['current_time']."
        )
    elif order_ts is not None and account_ts is not None and order_ts > account_ts:
        rejection_reasons.append(
            f"INVARIANT_FAIL_FUTURE_ORDER_TIMESTAMP: Order timestamp {order_ts.isoformat()} cannot be later than admission time {account_ts.isoformat()}."
        )

    # -------------------------------------------------------------
    # 1. Xác thực Order cơ bản
    # -------------------------------------------------------------
    if not isinstance(order, dict):
        return False, ["INVARIANT_FAIL_INVALID_ORDER: order must be a dictionary."]

    # Direction
    raw_dir = order.get("direction")
    norm_dir = str(raw_dir).strip().upper() if raw_dir is not None else ""
    if norm_dir not in ("LONG", "SHORT", "BUY", "SELL"):
        rejection_reasons.append(
            f"INVARIANT_FAIL_INVALID_DIRECTION: Invalid direction '{raw_dir}'. Expected 'LONG' or 'SHORT'."
        )
        direction_valid = False
    else:
        direction_valid = True

    # Entry price
    raw_entry = order.get("entry_price")
    if type(raw_entry) is bool or not isinstance(raw_entry, (int, float)):
        rejection_reasons.append(
            f"INVARIANT_FAIL_INVALID_ENTRY_PRICE: entry_price must be numeric, got {type(raw_entry).__name__}: {raw_entry!r}"
        )
        entry_price = 0.0
        entry_valid = False
    else:
        entry_price = float(raw_entry)
        if not math.isfinite(entry_price) or entry_price <= 0:
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_ENTRY_PRICE: entry_price must be positive and finite, got {entry_price}"
            )
            entry_valid = False
        else:
            entry_valid = True

    # Leverage
    risk_cfg = config.get("risk", {}) if isinstance(config, dict) else {}
    max_leverage = float(risk_cfg.get("max_leverage", 5.0))
    raw_lev = order.get("leverage")
    if type(raw_lev) is bool or not isinstance(raw_lev, (int, float)):
        rejection_reasons.append(
            f"INVARIANT_FAIL_INVALID_LEVERAGE: leverage must be numeric, got {type(raw_lev).__name__}: {raw_lev!r}"
        )
        leverage = 1.0
        leverage_valid = False
    else:
        leverage = float(raw_lev)
        if not math.isfinite(leverage) or leverage < 1.0:
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_LEVERAGE: leverage must be >= 1.0, got {leverage}"
            )
            leverage_valid = False
        elif leverage > max_leverage:
            rejection_reasons.append(
                f"INVARIANT_FAIL_LEVERAGE_EXCEEDED: Requested leverage {leverage}x exceeds max allowable leverage {max_leverage}x."
            )
            leverage_valid = False
        else:
            leverage_valid = True

    # Conviction tier & Risk percent
    conviction_tiers = risk_cfg.get("conviction_tiers", {
        "low": 0.01,
        "normal": 0.02,
        "high": 0.05,
        "ultra_high": 0.10,
    })
    tier_name = order.get("conviction_tier")
    if tier_name is None or tier_name not in conviction_tiers:
        rejection_reasons.append(
            f"INVARIANT_FAIL_UNKNOWN_CONVICTION_TIER: Conviction tier '{tier_name}' is not defined in configuration. "
            f"Allowed tiers: {list(conviction_tiers.keys())}."
        )
        tier_limit = 0.0
        tier_valid = False
    else:
        tier_limit = float(conviction_tiers[tier_name])
        tier_valid = True

    raw_risk_pct = order.get("risk_percent")
    if type(raw_risk_pct) is bool or not isinstance(raw_risk_pct, (int, float)):
        rejection_reasons.append(
            f"INVARIANT_FAIL_INVALID_RISK_PERCENT: risk_percent must be numeric, got {type(raw_risk_pct).__name__}: {raw_risk_pct!r}"
        )
        risk_percent = 0.0
        risk_pct_valid = False
    else:
        risk_percent = float(raw_risk_pct)
        if not math.isfinite(risk_percent) or risk_percent <= 0:
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_RISK_PERCENT: risk_percent must be positive and finite, got {risk_percent}"
            )
            risk_pct_valid = False
        else:
            risk_pct_valid = True

    # -------------------------------------------------------------
    # 2. Hard Invariant A: Stop-Loss check
    # -------------------------------------------------------------
    raw_sl = order.get("stop_loss_price")
    if raw_sl is None or type(raw_sl) is bool or not isinstance(raw_sl, (int, float)):
        rejection_reasons.append(
            "INVARIANT_FAIL_STOP_LOSS_MISSING: Order must have a valid positive numeric stop_loss_price."
        )
        sl_valid = False
        stop_loss_price = 0.0
    else:
        stop_loss_price = float(raw_sl)
        if not math.isfinite(stop_loss_price) or stop_loss_price <= 0:
            rejection_reasons.append(
                f"INVARIANT_FAIL_STOP_LOSS_MISSING: stop_loss_price must be positive and finite, got {stop_loss_price}"
            )
            sl_valid = False
        elif entry_valid:
            if norm_dir in ("LONG", "BUY") and stop_loss_price >= entry_price:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_STOP_LOSS_DIRECTION: LONG stop_loss_price ({stop_loss_price}) "
                    f"must be strictly lower than entry_price ({entry_price})."
                )
                sl_valid = False
            elif norm_dir in ("SHORT", "SELL") and stop_loss_price <= entry_price:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_STOP_LOSS_DIRECTION: SHORT stop_loss_price ({stop_loss_price}) "
                    f"must be strictly higher than entry_price ({entry_price})."
                )
                sl_valid = False
            else:
                sl_valid = True
        else:
            sl_valid = False

    # -------------------------------------------------------------
    # 3. Hard Invariant D: Effective Risk Limit & True Risk Reconciliation (R2)
    # -------------------------------------------------------------
    cb_multiplier = getattr(cb_state, "risk_multiplier", 1.0) if cb_state else 1.0
    effective_tier_risk = tier_limit * cb_multiplier

    if tier_valid and risk_pct_valid:
        if risk_percent > effective_tier_risk + 1e-6:
            rejection_reasons.append(
                f"INVARIANT_FAIL_RISK_TIER_EXCEEDED: Requested risk_percent {risk_percent * 100:.2f}% "
                f"exceeds effective conviction tier '{tier_name}' limit of {effective_tier_risk * 100:.2f}% "
                f"(base: {tier_limit * 100:.2f}%, breaker multiplier: {cb_multiplier:.2f})."
            )

    # Position size và đối soát rủi ro thực tế (Quantity * |Entry - Stop|)
    raw_pos_size = order.get("position_size_usd")
    if raw_pos_size is not None:
        if type(raw_pos_size) is bool or not isinstance(raw_pos_size, (int, float)):
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_POSITION_SIZE: position_size_usd must be numeric, got {type(raw_pos_size).__name__}"
            )
            pos_size_valid = False
            position_size_usd = 0.0
        else:
            position_size_usd = float(raw_pos_size)
            if not math.isfinite(position_size_usd) or position_size_usd <= 0:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_INVALID_POSITION_SIZE: position_size_usd must be positive finite, got {position_size_usd}"
                )
                pos_size_valid = False
            else:
                pos_size_valid = True
    else:
        # Nếu chưa truyền, tự tính toán nếu các tham số liên quan hợp lệ
        if entry_valid and sl_valid and equity > 0 and risk_pct_valid:
            stop_dist_pct = abs(entry_price - stop_loss_price) / entry_price
            position_size_usd = (equity * min(risk_percent, effective_tier_risk)) / stop_dist_pct
            pos_size_valid = True
        else:
            pos_size_valid = False
            position_size_usd = 0.0

    # Đối soát rủi ro thực tế khi chạm Stop Loss
    if pos_size_valid and entry_valid and sl_valid and equity > 0:
        quantity = position_size_usd / entry_price
        actual_price_risk_usd = quantity * abs(entry_price - stop_loss_price)
        max_allowed_risk_usd = equity * effective_tier_risk

        if actual_price_risk_usd > max_allowed_risk_usd + 1e-4:
            rejection_reasons.append(
                f"INVARIANT_FAIL_ACTUAL_RISK_EXCEEDED: Actual stop-loss risk ({actual_price_risk_usd:.2f} USD) "
                f"exceeds maximum allowed risk budget ({max_allowed_risk_usd:.2f} USD = {effective_tier_risk * 100:.2f}% equity)."
            )

    # -------------------------------------------------------------
    # 4. Ký quỹ Khả dụng (Available Margin Check)
    # -------------------------------------------------------------
    if pos_size_valid and leverage_valid and equity > 0:
        required_margin_usd = position_size_usd / leverage
        available_margin = float(account_state.get("available_margin", equity))
        if required_margin_usd > available_margin + 1e-4:
            rejection_reasons.append(
                f"INVARIANT_FAIL_INSUFFICIENT_MARGIN: Required margin ({required_margin_usd:.2f} USD) "
                f"exceeds available margin ({available_margin:.2f} USD)."
            )

    # -------------------------------------------------------------
    # 5. Hard Invariant C: Min Liquidation Buffer (Tier-Consistent)
    # -------------------------------------------------------------
    min_buffer_pct = float(risk_cfg.get("min_liquidation_buffer_pct", 0.30))
    symbol = str(order.get("symbol", "BTCUSDT"))
    brackets_cfg = config.get("leverage_brackets") if isinstance(config, dict) else None

    if entry_valid and pos_size_valid and leverage_valid and direction_valid and sl_valid:
        try:
            liq_price = calculate_estimated_liquidation_price(
                direction=norm_dir,
                entry_price=entry_price,
                position_size_usd=position_size_usd,
                leverage=leverage,
                symbol=symbol,
                leverage_brackets=brackets_cfg,
            )

            # Kiểm tra thanh lý trước SL
            if norm_dir in ("LONG", "BUY") and liq_price >= stop_loss_price:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_LIQUIDATION_BEFORE_SL: Estimated liquidation price ({liq_price:.2f}) "
                    f"would trigger before stop loss ({stop_loss_price:.2f}) on LONG position."
                )
            elif norm_dir in ("SHORT", "SELL") and liq_price <= stop_loss_price:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_LIQUIDATION_BEFORE_SL: Estimated liquidation price ({liq_price:.2f}) "
                    f"would trigger before stop loss ({stop_loss_price:.2f}) on SHORT position."
                )
            else:
                buffer_pct = abs(liq_price - stop_loss_price) / entry_price
                if buffer_pct < min_buffer_pct - 1e-6:
                    rejection_reasons.append(
                        f"INVARIANT_FAIL_LIQUIDATION_BUFFER: Liquidation buffer {buffer_pct * 100:.2f}% "
                        f"is below minimum required {min_buffer_pct * 100:.2f}% (P_liq: {liq_price:.2f}, SL: {stop_loss_price:.2f})."
                    )
        except Exception as e:
            rejection_reasons.append(f"INVARIANT_FAIL_LIQUIDATION_CALC_ERROR: {e}")

    # -------------------------------------------------------------
    # 6. Hard Invariant E: Circuit Breaker Lock check
    # -------------------------------------------------------------
    if cb_state is not None and admission_time is not None:
        if not cb_state.is_trading_allowed(admission_time):
            locked_until_str = str(getattr(cb_state, "locked_until", "unknown"))
            rejection_reasons.append(
                f"INVARIANT_FAIL_CIRCUIT_BREAKER_LOCKED: Trading is currently locked by circuit breaker until {locked_until_str}."
            )

    # -------------------------------------------------------------
    # 7. Hard Invariant F: News Blackout Window check
    # -------------------------------------------------------------
    news_cfg = config.get("news_filter", {}) if isinstance(config, dict) else {}
    news_enabled = bool(news_cfg.get("enabled", False))

    if news_enabled:
        news_filter = account_state.get("news_filter")
        if news_filter is None or not hasattr(news_filter, "is_in_blackout"):
            rejection_reasons.append(
                "INVARIANT_FAIL_MISSING_NEWS_FILTER: news_filter is enabled in configuration but missing or invalid in account_state."
            )
        elif admission_time is not None:
            is_blackout, event_name = news_filter.is_in_blackout(admission_time)
            if is_blackout:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_NEWS_BLACKOUT: Simulation time {admission_time.isoformat()} "
                    f"falls within blackout window of economic event '{event_name}'."
                )

    is_valid = (len(rejection_reasons) == 0)
    return is_valid, rejection_reasons
