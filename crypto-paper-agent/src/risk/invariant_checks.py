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
    """
    Xác thực cấu trúc bảng brackets:
    - Cap và MMR tăng dần nghiêm ngặt.
    - Duy trì tính liên tục của Maintenance Margin tại các điểm ranh giới giữa các tier kề nhau.
    """
    if not isinstance(brackets, list) or len(brackets) == 0:
        raise ValueError(f"Leverage brackets for symbol '{symbol}' must be a non-empty list.")
    
    parsed: List[Tuple[float, float, float]] = []
    last_cap = 0.0
    last_mmr = 0.0
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
        if mmr <= last_mmr:
            raise ValueError(f"Bracket MMR must be strictly increasing at row {idx} for symbol '{symbol}': {mmr} <= {last_mmr}")
        if cum < 0.0:
            raise ValueError(f"Invalid cum amount {cum} at row {idx} for symbol '{symbol}'")
        if idx == 0 and cum != 0.0:
            raise ValueError(f"First bracket tier must have cumulative maintenance amount == 0, got {cum}")
        if idx > 0:
            # Kiểm tra tính liên tục của ký quỹ duy trì tại điểm biên last_cap
            prev_cap, prev_mmr, prev_cum = parsed[-1]
            maint_prev = prev_cap * prev_mmr - prev_cum
            maint_curr = prev_cap * mmr - cum
            if abs(maint_prev - maint_curr) > 1e-3:
                raise ValueError(
                    f"Bracket maintenance margin discontinuity at row {idx} for symbol '{symbol}': "
                    f"tier {idx-1} maint={maint_prev:.4f} != tier {idx} maint={maint_curr:.4f}"
                )

        parsed.append((cap, mmr, cum))
        last_cap = cap
        last_mmr = mmr
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
    Từ chối nếu quy mô vượt quá trần hỗ trợ của bracket snapshot.
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

    raise ValueError(
        f"Position size {notional:,.2f} USD exceeds maximum supported leverage bracket cap "
        f"{brackets[-1][0]:,.2f} USD for symbol '{symbol}'."
    )


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

    Mô hình cân bằng độc lập:
    - Long:  Initial_Margin + q * (P - entry) = Maintenance_Margin(P)
             => q * entry / lev + q * (P - entry) = q * P * mmr - cum
             => P = [entry * (1 - 1/leverage) - cum/q] / (1 - mmr)
    - Short: Initial_Margin + q * (entry - P) = Maintenance_Margin(P)
             => q * entry / lev + q * (entry - P) = q * P * mmr - cum
             => P = [entry * (1 + 1/leverage) + cum/q] / (1 + mmr)

    Nghiệm P phải thỏa mãn:
    1. q * P nằm trong khoảng (lower_bound, upper_bound] của tier đó.
    2. Chiều giá thanh lý hợp lệ: Long P_liq < Entry; Short P_liq > Entry.
    3. Không ngoại suy ngoài miền bracket; báo lỗi rõ nếu initial margin <= maintenance margin tại entry.
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
    max_supported_cap = brackets[-1][0]
    if f_notional > max_supported_cap:
        raise ValueError(
            f"Position size {f_notional:,.2f} USD exceeds maximum supported leverage bracket cap "
            f"{max_supported_cap:,.2f} USD for symbol '{symbol}'."
        )

    # 2. Kiểm tra Initial Margin vs Maintenance Margin tại giá vào lệnh (Entry)
    entry_mmr, entry_cum = get_mmr_tier(f_notional, symbol, leverage_brackets)
    entry_maintenance_margin = f_notional * entry_mmr - entry_cum
    initial_margin = f_notional / f_lev
    if initial_margin <= entry_maintenance_margin:
        raise ValueError(
            f"Initial margin ({initial_margin:.2f} USD) is <= maintenance margin ({entry_maintenance_margin:.2f} USD) "
            f"at entry price. Position is already liquidatable (insufficient initial margin)."
        )

    q = f_notional / f_entry
    if not (math.isfinite(q) and q > 0):
        raise ValueError(f"Invalid calculated quantity: {q}")

    # 3. Duyệt qua từng tier để tìm nghiệm tự nhất quán (Tier-Consistent Solution)
    lower_bound = 0.0
    for idx, (upper_bound, mmr, cum) in enumerate(brackets):
        cum_per_q = cum / q

        if dir_str in ("LONG", "BUY"):
            # P = [entry * (1 - 1/lev) - cum/q] / (1 - mmr)
            numerator = f_entry * (1.0 - 1.0 / f_lev) - cum_per_q
            denominator = 1.0 - mmr
            if denominator <= 0:
                continue

            if f_lev == 1.0 and numerator <= 0:
                candidate_p = 0.0
            elif numerator <= 0:
                candidate_p = 0.0
            else:
                candidate_p = numerator / denominator

            if not (math.isfinite(candidate_p) and candidate_p >= 0):
                continue
            # Long: Giá thanh lý phải nhỏ hơn giá vào lệnh
            if candidate_p >= f_entry:
                continue

            candidate_notional = q * candidate_p
            is_in_tier = (lower_bound < candidate_notional <= upper_bound) or (idx == 0 and candidate_notional <= upper_bound)
            if is_in_tier:
                return float(candidate_p)

        else:
            # Short: P = [entry * (1 + 1/lev) + cum/q] / (1 + mmr)
            numerator = f_entry * (1.0 + 1.0 / f_lev) + cum_per_q
            denominator = 1.0 + mmr
            if denominator <= 0:
                continue
            candidate_p = numerator / denominator

            if not (math.isfinite(candidate_p) and candidate_p > 0):
                continue
            # Short: Giá thanh lý phải cao hơn giá vào lệnh
            if candidate_p <= f_entry:
                continue

            candidate_notional = q * candidate_p
            is_in_tier = (lower_bound < candidate_notional <= upper_bound) or (idx == 0 and candidate_notional <= upper_bound)
            if is_in_tier:
                return float(candidate_p)

        lower_bound = upper_bound

    # Tuyệt đối không fallback sang tier cuối nếu không có nghiệm hợp lệ trong miền
    raise ValueError(
        f"No tier-consistent liquidation price found within supported leverage brackets for "
        f"{dir_str} position (entry={f_entry}, size={f_notional}, lev={f_lev}, symbol='{symbol}')."
    )


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
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
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
    # 0. Xác thực Config & Account State cơ bản (G1)
    # -------------------------------------------------------------
    if not isinstance(config, dict):
        return False, ["INVARIANT_FAIL_CONFIG_ERROR: config must be a dictionary."]

    # Risk subconfig validation
    if "risk" in config:
        risk_cfg = config["risk"]
        if not isinstance(risk_cfg, dict):
            rejection_reasons.append(
                f"INVARIANT_FAIL_CONFIG_ERROR: config.risk must be a dictionary, got {type(risk_cfg).__name__}: {risk_cfg!r}"
            )
            risk_cfg = {}
            risk_cfg_valid = False
        else:
            risk_cfg_valid = True
    else:
        risk_cfg = {}
        risk_cfg_valid = True

    # max_leverage: default 5.0 only when omitted
    if "max_leverage" not in risk_cfg:
        max_leverage = 5.0
        max_lev_valid = True
    else:
        raw_max_lev = risk_cfg["max_leverage"]
        if type(raw_max_lev) is bool or not isinstance(raw_max_lev, (int, float)):
            rejection_reasons.append(
                f"INVARIANT_FAIL_CONFIG_ERROR: config.risk.max_leverage must be numeric, got {type(raw_max_lev).__name__}: {raw_max_lev!r}"
            )
            max_leverage = 5.0
            max_lev_valid = False
        else:
            f_max_lev = float(raw_max_lev)
            if not math.isfinite(f_max_lev) or f_max_lev < 1.0:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_CONFIG_ERROR: config.risk.max_leverage must be finite >= 1.0, got {f_max_lev}"
                )
                max_leverage = 5.0
                max_lev_valid = False
            else:
                max_leverage = f_max_lev
                max_lev_valid = True

    # min_liquidation_buffer_pct: default 0.30 only when omitted
    if "min_liquidation_buffer_pct" not in risk_cfg:
        min_buffer_pct = 0.30
        min_buffer_valid = True
    else:
        raw_buffer = risk_cfg["min_liquidation_buffer_pct"]
        if type(raw_buffer) is bool or not isinstance(raw_buffer, (int, float)):
            rejection_reasons.append(
                f"INVARIANT_FAIL_CONFIG_ERROR: config.risk.min_liquidation_buffer_pct must be numeric, got {type(raw_buffer).__name__}: {raw_buffer!r}"
            )
            min_buffer_pct = 0.30
            min_buffer_valid = False
        else:
            f_buf = float(raw_buffer)
            if not math.isfinite(f_buf) or not (0 < f_buf < 1.0):
                rejection_reasons.append(
                    f"INVARIANT_FAIL_CONFIG_ERROR: config.risk.min_liquidation_buffer_pct must be finite in (0, 1), got {f_buf}"
                )
                min_buffer_pct = 0.30
                min_buffer_valid = False
            else:
                min_buffer_pct = f_buf
                min_buffer_valid = True

    # conviction_tiers in config: default only when omitted
    if "conviction_tiers" not in risk_cfg:
        conviction_tiers = {
            "low": 0.01,
            "normal": 0.02,
            "high": 0.05,
            "ultra_high": 0.10,
        }
        tiers_cfg_valid = True
    else:
        raw_tiers = risk_cfg["conviction_tiers"]
        if not isinstance(raw_tiers, dict):
            rejection_reasons.append(
                f"INVARIANT_FAIL_CONFIG_ERROR: config.risk.conviction_tiers must be a dictionary, got {type(raw_tiers).__name__}: {raw_tiers!r}"
            )
            conviction_tiers = {}
            tiers_cfg_valid = False
        else:
            conviction_tiers = {}
            tiers_cfg_valid = True
            for k, v in raw_tiers.items():
                if type(v) is bool or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) <= 0:
                    rejection_reasons.append(
                        f"INVARIANT_FAIL_CONFIG_ERROR: config.risk.conviction_tiers['{k}'] must be positive finite numeric, got {v!r}"
                    )
                    tiers_cfg_valid = False
                else:
                    conviction_tiers[str(k)] = float(v)

    # fees subconfig: default taker_pct 0.0005 only when omitted
    if "fees" in config:
        fees_cfg = config["fees"]
        if not isinstance(fees_cfg, dict):
            rejection_reasons.append(
                f"INVARIANT_FAIL_CONFIG_ERROR: config.fees must be a dictionary, got {type(fees_cfg).__name__}: {fees_cfg!r}"
            )
            fees_valid = False
            taker_pct = 0.0005
        elif "taker_pct" in fees_cfg:
            raw_taker = fees_cfg["taker_pct"]
            if type(raw_taker) is bool or not isinstance(raw_taker, (int, float)):
                rejection_reasons.append(
                    f"INVARIANT_FAIL_CONFIG_ERROR: config.fees.taker_pct must be numeric, got {type(raw_taker).__name__}: {raw_taker!r}"
                )
                fees_valid = False
                taker_pct = 0.0005
            else:
                f_taker = float(raw_taker)
                if not math.isfinite(f_taker) or f_taker < 0:
                    rejection_reasons.append(
                        f"INVARIANT_FAIL_CONFIG_ERROR: config.fees.taker_pct must be finite and >= 0, got {f_taker}"
                    )
                    fees_valid = False
                    taker_pct = 0.0005
                else:
                    taker_pct = f_taker
                    fees_valid = True
        else:
            taker_pct = 0.0005
            fees_valid = True
    else:
        fees_cfg = {}
        taker_pct = 0.0005
        fees_valid = True

    # Account State validation
    if not isinstance(account_state, dict):
        return False, ["INVARIANT_FAIL_INVALID_ACCOUNT_STATE: account_state must be a dictionary."]

    # Equity
    raw_equity = account_state.get("equity")
    if type(raw_equity) is bool or not isinstance(raw_equity, (int, float)):
        rejection_reasons.append(
            f"INVARIANT_FAIL_INVALID_ACCOUNT_EQUITY: Account equity must be numeric, got {type(raw_equity).__name__}: {raw_equity!r}"
        )
        equity = 0.0
        equity_valid = False
    else:
        equity = float(raw_equity)
        if not math.isfinite(equity) or equity <= 0:
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_ACCOUNT_EQUITY: Account equity must be positive and finite, got {equity}"
            )
            equity_valid = False
        else:
            equity_valid = True

    # Available Margin (F2: Không ngầm lấy equity; bắt buộc khai báo và kiểm tra hữu hạn >= 0)
    raw_avail_margin = account_state.get("available_margin")
    if raw_avail_margin is None:
        rejection_reasons.append(
            "INVARIANT_FAIL_MISSING_AVAILABLE_MARGIN: account_state must explicitly specify available_margin."
        )
        avail_margin_valid = False
        available_margin = 0.0
    elif type(raw_avail_margin) is bool or not isinstance(raw_avail_margin, (int, float)):
        rejection_reasons.append(
            f"INVARIANT_FAIL_INVALID_AVAILABLE_MARGIN: available_margin must be numeric, got {type(raw_avail_margin).__name__}: {raw_avail_margin!r}"
        )
        avail_margin_valid = False
        available_margin = 0.0
    else:
        available_margin = float(raw_avail_margin)
        if not math.isfinite(available_margin) or available_margin < 0:
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_AVAILABLE_MARGIN: available_margin must be non-negative and finite, got {available_margin}"
            )
            avail_margin_valid = False
        else:
            avail_margin_valid = True

    # Circuit breaker component check (F2/G1: Kiểm tra callable và contract trạng thái hợp lệ)
    cb_state = account_state.get("circuit_breaker_state")
    if cb_state is None:
        rejection_reasons.append(
            "INVARIANT_FAIL_MISSING_CIRCUIT_BREAKER: account_state must contain a valid CircuitBreakerState instance."
        )
        cb_valid = False
        cb_multiplier = 0.0
    elif not hasattr(cb_state, "is_trading_allowed") or not callable(getattr(cb_state, "is_trading_allowed")):
        rejection_reasons.append(
            "INVARIANT_FAIL_MISSING_CIRCUIT_BREAKER: circuit_breaker_state object must provide a callable is_trading_allowed method."
        )
        cb_valid = False
        cb_multiplier = 0.0
    else:
        # Kiểm tra contract & internal state validity (G1)
        raw_cb_mult = getattr(cb_state, "risk_multiplier", None)
        if raw_cb_mult is None or type(raw_cb_mult) is bool or not isinstance(raw_cb_mult, (int, float)):
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_CIRCUIT_BREAKER_STATE: circuit_breaker_state.risk_multiplier must be numeric, got {type(raw_cb_mult).__name__}: {raw_cb_mult!r}"
            )
            cb_valid = False
            cb_multiplier = 0.0
        else:
            f_mult = float(raw_cb_mult)
            if not math.isfinite(f_mult) or not (0 < f_mult <= 1.0 + 1e-6):
                rejection_reasons.append(
                    f"INVARIANT_FAIL_INVALID_CIRCUIT_BREAKER_STATE: circuit_breaker_state.risk_multiplier must be finite in (0, 1.0], got {f_mult}"
                )
                cb_valid = False
                cb_multiplier = 0.0
            else:
                streak_red = getattr(cb_state, "risk_reduction_on_streak", None)
                if streak_red is None and isinstance(config, dict):
                    streak_red = config.get("circuit_breakers", {}).get("risk_reduction_on_streak", 0.5)
                if streak_red is not None and type(streak_red) is not bool and isinstance(streak_red, (int, float)) and math.isfinite(float(streak_red)):
                    valid_states = (1.0, float(streak_red))
                    if not any(abs(f_mult - s) < 1e-6 for s in valid_states):
                        rejection_reasons.append(
                            f"INVARIANT_FAIL_INVALID_CIRCUIT_BREAKER_STATE: circuit_breaker_state.risk_multiplier ({f_mult}) must be in valid states (1.0 or {float(streak_red)})."
                        )
                        cb_valid = False
                        cb_multiplier = 0.0
                    else:
                        cb_multiplier = f_mult
                        cb_valid = True
                else:
                    cb_multiplier = f_mult
                    cb_valid = True

        raw_locked = getattr(cb_state, "is_locked", None)
        if raw_locked is None or not isinstance(raw_locked, bool):
            rejection_reasons.append(
                f"INVARIANT_FAIL_INVALID_CIRCUIT_BREAKER_STATE: circuit_breaker_state.is_locked must be boolean, got {type(raw_locked).__name__}: {raw_locked!r}"
            )
            cb_valid = False

    # Thời điểm thẩm quyền duyệt lệnh (Admission Time - F3: account current_time là nguồn thẩm quyền)
    raw_admission_time = account_state.get("current_time")
    admission_time = parse_simulation_timestamp(raw_admission_time)
    if admission_time is None:
        rejection_reasons.append(
            "INVARIANT_FAIL_MISSING_ADMISSION_TIME: account_state must provide a valid current_time as authoritative admission timestamp."
        )

    # -------------------------------------------------------------
    # 1. Xác thực Order cơ bản
    # -------------------------------------------------------------
    if not isinstance(order, dict):
        return False, ["INVARIANT_FAIL_INVALID_ORDER: order must be a dictionary."]

    # Order Timestamp (Signal time - F3: Phải hợp lệ và không được trễ hơn admission time)
    raw_order_ts = order.get("timestamp")
    order_ts = parse_simulation_timestamp(raw_order_ts)
    if order_ts is None:
        rejection_reasons.append(
            "INVARIANT_FAIL_MISSING_ORDER_TIMESTAMP: order must provide a valid simulation timestamp (signal time)."
        )
    elif admission_time is not None and order_ts > admission_time:
        rejection_reasons.append(
            f"INVARIANT_FAIL_FUTURE_ORDER_TIMESTAMP: Order signal timestamp {order_ts.isoformat()} "
            f"cannot be later than admission time {admission_time.isoformat()}."
        )

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
        elif max_lev_valid and leverage > max_leverage:
            rejection_reasons.append(
                f"INVARIANT_FAIL_LEVERAGE_EXCEEDED: Requested leverage {leverage}x exceeds max allowable leverage {max_leverage}x."
            )
            leverage_valid = False
        else:
            leverage_valid = True

    # Conviction tier (F2: Kiểm tra kiểu str trước membership để tránh TypeError unhashable)
    raw_tier = order.get("conviction_tier")
    if not isinstance(raw_tier, str):
        rejection_reasons.append(
            f"INVARIANT_FAIL_INVALID_CONVICTION_TIER_TYPE: conviction_tier must be string, got {type(raw_tier).__name__}: {raw_tier!r}"
        )
        tier_valid = False
        tier_limit = 0.0
    elif not tiers_cfg_valid or raw_tier not in conviction_tiers:
        rejection_reasons.append(
            f"INVARIANT_FAIL_UNKNOWN_CONVICTION_TIER: Conviction tier '{raw_tier}' is not defined in configuration. "
            f"Allowed tiers: {list(conviction_tiers.keys())}."
        )
        tier_valid = False
        tier_limit = 0.0
    else:
        tier_limit = conviction_tiers[raw_tier]
        tier_valid = True

    # Stop-Loss check
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

    # Risk Percent, Base Risk Percent & Breaker Multiplier (F1/G1)
    effective_tier_ceiling = tier_limit * cb_multiplier if cb_valid else 0.0

    has_base = "base_risk_percent" in order
    has_effective = "risk_percent" in order

    if not has_base and not has_effective:
        rejection_reasons.append("INVARIANT_FAIL_INVALID_RISK_PERCENT: Order must specify 'risk_percent' or 'base_risk_percent'.")
        order_effective_risk_pct = 0.0
        risk_pct_valid = False
    else:
        base_val = None
        if has_base:
            raw_base = order.get("base_risk_percent")
            if type(raw_base) is bool or not isinstance(raw_base, (int, float)):
                rejection_reasons.append(f"INVARIANT_FAIL_INVALID_RISK_PERCENT: base_risk_percent must be numeric, got {type(raw_base).__name__}")
            else:
                f_base = float(raw_base)
                if not math.isfinite(f_base) or f_base <= 0:
                    rejection_reasons.append(f"INVARIANT_FAIL_INVALID_RISK_PERCENT: base_risk_percent must be positive finite, got {f_base}")
                else:
                    base_val = f_base

        eff_val = None
        if has_effective:
            raw_eff = order.get("risk_percent")
            if type(raw_eff) is bool or not isinstance(raw_eff, (int, float)):
                rejection_reasons.append(f"INVARIANT_FAIL_INVALID_RISK_PERCENT: risk_percent must be numeric, got {type(raw_eff).__name__}")
            else:
                f_eff = float(raw_eff)
                if not math.isfinite(f_eff) or f_eff <= 0:
                    rejection_reasons.append(f"INVARIANT_FAIL_INVALID_RISK_PERCENT: risk_percent must be positive finite, got {f_eff}")
                else:
                    eff_val = f_eff

        if has_base and has_effective and base_val is not None and eff_val is not None:
            if cb_valid:
                expected_eff = base_val * cb_multiplier
                if abs(eff_val - expected_eff) > 1e-6:
                    rejection_reasons.append(
                        f"INVARIANT_FAIL_RISK_PERCENT_MISMATCH: Provided risk_percent ({eff_val * 100:.2f}%) "
                        f"does not match base_risk_percent * cb_multiplier ({base_val * 100:.2f}% * {cb_multiplier:.2f} = {expected_eff * 100:.2f}%)."
                    )
                    order_effective_risk_pct = eff_val
                    risk_pct_valid = False
                else:
                    order_effective_risk_pct = eff_val
                    risk_pct_valid = True
            else:
                order_effective_risk_pct = eff_val
                risk_pct_valid = False
        elif has_effective and eff_val is not None:
            order_effective_risk_pct = eff_val
            risk_pct_valid = True
        elif has_base and base_val is not None:
            if cb_valid:
                order_effective_risk_pct = base_val * cb_multiplier
                risk_pct_valid = True
            else:
                order_effective_risk_pct = 0.0
                risk_pct_valid = False
        else:
            order_effective_risk_pct = 0.0
            risk_pct_valid = False

    if tier_valid and risk_pct_valid and cb_valid:
        if order_effective_risk_pct > effective_tier_ceiling + 1e-6:
            rejection_reasons.append(
                f"INVARIANT_FAIL_RISK_TIER_EXCEEDED: Requested effective risk_percent {order_effective_risk_pct * 100:.2f}% "
                f"exceeds effective conviction tier '{raw_tier}' ceiling of {effective_tier_ceiling * 100:.2f}% "
                f"(base tier limit: {tier_limit * 100:.2f}%, circuit breaker multiplier: {cb_multiplier:.2f})."
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
        if entry_valid and sl_valid and equity_valid and risk_pct_valid and cb_valid:
            stop_dist_pct = abs(entry_price - stop_loss_price) / entry_price
            position_size_usd = (equity * min(order_effective_risk_pct, effective_tier_ceiling)) / stop_dist_pct
            pos_size_valid = True
        else:
            pos_size_valid = False
            position_size_usd = 0.0

    # Đối soát rủi ro thực tế khi chạm Stop Loss (F1: So sánh với order risk budget thay vì chỉ trần tier)
    if pos_size_valid and entry_valid and sl_valid and equity_valid and risk_pct_valid:
        quantity = position_size_usd / entry_price
        actual_price_risk_usd = quantity * abs(entry_price - stop_loss_price)
        order_risk_budget_usd = equity * order_effective_risk_pct

        if actual_price_risk_usd > order_risk_budget_usd + 1e-4:
            rejection_reasons.append(
                f"INVARIANT_FAIL_ACTUAL_RISK_EXCEEDED: Actual stop-loss risk ({actual_price_risk_usd:.2f} USD) "
                f"exceeds order declared risk budget ({order_risk_budget_usd:.2f} USD = {order_effective_risk_pct * 100:.2f}% equity)."
            )

    # -------------------------------------------------------------
    # 2. Ký quỹ Khả dụng & Phí vào lệnh (F2: Required Margin & Fee Check)
    # -------------------------------------------------------------
    if pos_size_valid and leverage_valid and avail_margin_valid:
        required_margin_usd = position_size_usd / leverage
        if fees_valid:
            est_entry_fee_usd = position_size_usd * taker_pct
            total_required_capital = required_margin_usd + est_entry_fee_usd

            if total_required_capital > available_margin + 1e-4:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_INSUFFICIENT_MARGIN: Required initial margin and fee "
                    f"({total_required_capital:.2f} USD = {required_margin_usd:.2f} margin + {est_entry_fee_usd:.2f} fee) "
                    f"exceeds available margin ({available_margin:.2f} USD)."
                )

    # -------------------------------------------------------------
    # 3. Hard Invariant C: Min Liquidation Buffer (Tier-Consistent) (G1)
    # -------------------------------------------------------------
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
            elif min_buffer_valid:
                buffer_pct = abs(liq_price - stop_loss_price) / entry_price
                if buffer_pct < min_buffer_pct - 1e-6:
                    rejection_reasons.append(
                        f"INVARIANT_FAIL_LIQUIDATION_BUFFER: Liquidation buffer {buffer_pct * 100:.2f}% "
                        f"is below minimum required {min_buffer_pct * 100:.2f}% (P_liq: {liq_price:.2f}, SL: {stop_loss_price:.2f})."
                    )
        except Exception as e:
            rejection_reasons.append(f"INVARIANT_FAIL_LIQUIDATION_CALC_ERROR: {e}")

    # -------------------------------------------------------------
    # 4. Hard Invariant E: Circuit Breaker Lock check (F3/G2: tại admission_time và chống time reversal)
    # -------------------------------------------------------------
    if cb_valid and admission_time is not None:
        cb_clock = getattr(cb_state, "current_timestamp", None)
        if cb_clock is not None and admission_time < cb_clock:
            rejection_reasons.append(
                f"INVARIANT_FAIL_TIME_REVERSAL: Admission time {admission_time.isoformat()} "
                f"is earlier than circuit breaker clock {cb_clock.isoformat()} (time reversal)."
            )
        else:
            try:
                allowed = cb_state.is_trading_allowed(admission_time)
                if not allowed:
                    locked_until_str = str(getattr(cb_state, "locked_until", "unknown"))
                    rejection_reasons.append(
                        f"INVARIANT_FAIL_CIRCUIT_BREAKER_LOCKED: Trading is currently locked by circuit breaker until {locked_until_str}."
                    )
            except ValueError as e:
                rejection_reasons.append(f"INVARIANT_FAIL_CIRCUIT_BREAKER_ERROR: {e}")

    # -------------------------------------------------------------
    # 5. Hard Invariant F: News Blackout Window check (F3/G3: tại admission_time và readiness check)
    # -------------------------------------------------------------
    news_cfg = config.get("news_filter") if isinstance(config, dict) else {}
    if news_cfg is None:
        news_cfg = {}
    news_enabled = bool(news_cfg.get("enabled", False))

    if news_enabled:
        news_filter = account_state.get("news_filter")
        if news_filter is None or not hasattr(news_filter, "is_in_blackout") or not callable(getattr(news_filter, "is_in_blackout")):
            rejection_reasons.append(
                "INVARIANT_FAIL_MISSING_NEWS_FILTER: news_filter is enabled in configuration but missing or invalid in account_state."
            )
        elif not getattr(news_filter, "enabled", True):
            rejection_reasons.append(
                "INVARIANT_FAIL_NEWS_FILTER_CONFIG_MISMATCH: Configuration specifies news_filter enabled=True, but account_state['news_filter'] instance has enabled=False."
            )
        elif not getattr(news_filter, "is_ready", True):
            load_err = getattr(news_filter, "load_error", "CALENDAR_LOAD_ERROR")
            rejection_reasons.append(
                f"INVARIANT_FAIL_NEWS_FILTER_NOT_READY: news_filter is enabled but calendar is not ready. Reason: {load_err}"
            )
        elif admission_time is not None:
            is_blackout, event_name = news_filter.is_in_blackout(admission_time)
            if is_blackout:
                rejection_reasons.append(
                    f"INVARIANT_FAIL_NEWS_BLACKOUT: Admission time {admission_time.isoformat()} "
                    f"falls within blackout window of economic event '{event_name}'."
                )

    is_valid = (len(rejection_reasons) == 0)
    return is_valid, rejection_reasons
