"""
position_sizing.py - Position Sizing Module
============================================
Tính toán quy mô vị thế (position size), rủi ro USD, khối lượng hợp đồng (quantity),
và tiền ký quỹ yêu cầu (required margin) dựa trên số vốn, tỷ lệ rủi ro và khoảng cách Stop-Loss.

Tuân thủ nghiêm ngặt mục 4.4 trong CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md:
- risk_usd = equity * risk_percent
- stop_distance_pct = abs(entry_price - stop_price) / entry_price
- position_size_usd = risk_usd / stop_distance_pct
- quantity = risk_usd / abs(entry_price - stop_price)
- required_margin_usd = position_size_usd / leverage
"""
from typing import Dict


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
        leverage: Mức đòn bẩy dự kiến (VD: 3, 5).

    Returns:
        Dict gồm các trường:
            - risk_usd: Số tiền rủi ro tối đa (USD).
            - stop_distance_pct: Khoảng cách dừng lỗ tính theo tỷ lệ phần trăm so với entry.
            - position_size_usd: Quy mô vị thế tính theo danh nghĩa (USD).
            - quantity: Khối lượng tài sản cơ sở (VD: BTC).
            - required_margin_usd: Tiền ký quỹ ban đầu cần có (USD).

    Raises:
        ValueError: Nếu stop_price == entry_price (lỗi chia cho 0).
        ValueError: Nếu bất kỳ tham số đầu vào nào không hợp lệ (<= 0 hoặc leverage < 1).
    """
    if equity <= 0:
        raise ValueError(f"Account equity must be positive, got {equity}")
    if risk_percent <= 0:
        raise ValueError(f"Risk percent must be positive, got {risk_percent}")
    if entry_price <= 0:
        raise ValueError(f"Entry price must be positive, got {entry_price}")
    if stop_price <= 0:
        raise ValueError(f"Stop price must be positive, got {stop_price}")
    if leverage < 1:
        raise ValueError(f"Leverage must be at least 1.0, got {leverage}")
    if stop_price == entry_price:
        raise ValueError("Stop loss price cannot be equal to entry price (division by zero).")

    risk_usd = equity * risk_percent
    stop_distance = abs(entry_price - stop_price)
    stop_distance_pct = stop_distance / entry_price
    position_size_usd = risk_usd / stop_distance_pct
    quantity = risk_usd / stop_distance
    required_margin_usd = position_size_usd / leverage

    return {
        "risk_usd": risk_usd,
        "stop_distance_pct": stop_distance_pct,
        "position_size_usd": position_size_usd,
        "quantity": quantity,
        "required_margin_usd": required_margin_usd,
    }
