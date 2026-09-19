"""
src/report/__init__.py - Performance reporting and metrics calculation module.
"""
from src.report.metrics import (
    calculate_backtest_metrics,
    calculate_daily_sharpe,
    calculate_max_drawdown,
    calculate_trade_metrics,
)
from src.report.generator import ReportGenerator

__all__ = [
    "calculate_backtest_metrics",
    "calculate_daily_sharpe",
    "calculate_max_drawdown",
    "calculate_trade_metrics",
    "ReportGenerator",
]
