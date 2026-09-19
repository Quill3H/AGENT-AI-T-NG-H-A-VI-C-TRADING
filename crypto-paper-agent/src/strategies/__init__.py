"""
src/strategies/__init__.py
==========================
Package chứa các chiến lược giao dịch định lượng.
Giai đoạn 5: BaseStrategy và TrendFollowingStrategy.
"""
from src.strategies.base_strategy import BaseStrategy
from src.strategies.trend_following import TrendFollowingStrategy, SetupState

__all__ = [
    "BaseStrategy",
    "TrendFollowingStrategy",
    "SetupState",
]
