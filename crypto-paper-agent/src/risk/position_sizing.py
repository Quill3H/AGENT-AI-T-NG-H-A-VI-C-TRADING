"""
position_sizing.py - Position Sizing Module
============================================
Tính toán quy mô vị thế (position size), rủi ro USD, khối lượng hợp đồng (quantity),
và tiền ký quỹ yêu cầu (required margin) dựa trên số vốn, tỷ lệ rủi ro và khoảng cách Stop-Loss.

Tuân thủ nghiêm ngặt mục 4.4 trong CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md và ADR 0006:
- risk_usd = equity * risk_percent
- stop_distance_pct = abs(entry_price - stop_price) / entry_price
- position_size_usd = risk_usd / stop_distance_pct
- quantity = risk_usd / abs(entry_price - stop_price)
- required_margin_usd = position_size_usd / leverage
"""
import math
from typing import Any, Dict


def _validate_numeric(val: Any, name: str, min_value: float = 0.0, exclusive: bool = True) -> float:
    """
    Xác thực tham số số học:
    - Bắt buộc là int hoặc float, TUYỆT ĐỐI không chấp nhận bool (vì bool là subclass của int).
    - Phải là số hữu hạn (không chấp nhận NaN, +Inf, -Inf).
    - Phải thỏa mãn điều kiện cận dưới (> min_value hoặc >= min_value).
    """
    if type(val) is bool or not isinstance(val, (int, float)):
        raise TypeError(f"{name} must be a numeric float or int, got {type(val).__name__}: {val!r}")
    
    f_val = float(val)
    if not math.isfinite(f_val):
        raise ValueError(f"{name} must be a finite number, got {f_val}")
    
    if exclusive:
        if f_val <= min_value:
            raise ValueError(f"{name} must be strictly greater than {min_value}, got {f_val}")
    else:
        if f_val < min_value:
            raise ValueError(f"{name} must be greater than or equal to {min_value}, got {f_val}")
            
    return f_val


def calculate_position_size(
    equity: float,
    risk_percent: float,
    entry_price: float,
    stop_price: float,
    leverage: float,
) -> Dict[str, float]:
    """
    Tính toán quy mô vị thế và ký quỹ cho một lệnh giao dịch.

    Args:
        equity: Số dư vốn khả dụng của tài khoản (USD).
        risk_percent: Tỷ lệ rủi ro chấp nhận cho lệnh này (VD: 0.02 = 2%).
        entry_price: Giá vào lệnh dự kiến.
        stop_price: Giá dừng lỗ (Stop-Loss).
        leverage: Mức đòn bẩy dự kiến (>= 1.0).

    Returns:
        Dict gồm các trường:
            - risk_usd: Số tiền rủi ro tối đa (USD).
            - stop_distance_pct: Khoảng cách dừng lỗ tính theo tỷ lệ phần trăm so với entry.
            - position_size_usd: Quy mô vị thế tính theo danh nghĩa (USD).
            - quantity: Khối lượng tài sản cơ sở (VD: BTC).
            - required_margin_usd: Tiền ký quỹ ban đầu cần có (USD).

    Raises:
        TypeError: Nếu bất kỳ tham số nào là bool hoặc không phải kiểu số.
        ValueError: Nếu tham số là NaN, Inf, <= 0 hoặc leverage < 1.0.
        ValueError: Nếu stop_price == entry_price (lỗi chia cho 0).
    """
    eq = _validate_numeric(equity, "Account equity", min_value=0.0, exclusive=True)
    rp = _validate_numeric(risk_percent, "Risk percent", min_value=0.0, exclusive=True)
    ep = _validate_numeric(entry_price, "Entry price", min_value=0.0, exclusive=True)
    sp = _validate_numeric(stop_price, "Stop price", min_value=0.0, exclusive=True)
    lev = _validate_numeric(leverage, "Leverage", min_value=1.0, exclusive=False)

    if sp == ep:
        raise ValueError("Stop loss price cannot be equal to entry price (division by zero).")

    stop_distance = abs(ep - sp)
    stop_distance_pct = stop_distance / ep

    try:
        risk_usd = eq * rp
        position_size_usd = risk_usd / stop_distance_pct
        quantity = risk_usd / stop_distance
        required_margin_usd = position_size_usd / lev

        # Kiểm tra overflow / không hữu hạn của kết quả
        for k, v in [
            ("risk_usd", risk_usd),
            ("stop_distance_pct", stop_distance_pct),
            ("position_size_usd", position_size_usd),
            ("quantity", quantity),
            ("required_margin_usd", required_margin_usd),
        ]:
            if not math.isfinite(v):
                raise OverflowError(f"Calculation for {k} resulted in non-finite value: {v}")

    except OverflowError as oe:
        raise ValueError(f"Numeric overflow during position sizing calculation: {oe}") from oe

    return {
        "risk_usd": risk_usd,
        "stop_distance_pct": stop_distance_pct,
        "position_size_usd": position_size_usd,
        "quantity": quantity,
        "required_margin_usd": required_margin_usd,
    }
