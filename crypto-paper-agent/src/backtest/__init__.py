"""
src/backtest/__init__.py
========================
Package thực thi kiểm thử chiến lược trên dữ liệu lịch sử (Backtest Engine).
Giai đoạn 5: BacktestEngine tối thiểu, nhân quả đa khung thời gian 4h/15m.
"""
from src.backtest.engine import BacktestEngine

__all__ = [
    "BacktestEngine",
]
