"""
src/features/__init__.py
========================
Feature Engine package:
Cung cấp các hàm tính toán chỉ báo kỹ thuật, Open Interest delta, CVD và CVD divergence.
"""
from typing import Dict, Optional, Any
import pandas as pd

from src.features.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_atr,
    calculate_indicators,
)
from src.features.oi_features import calculate_oi_features
from src.features.cvd import calculate_cvd, calculate_cvd_divergence
from src.features.news_calendar import NewsCalendarFilter, EconomicEvent


def add_all_features(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    use_fallback_indicators: bool = False,
) -> pd.DataFrame:
    """
    Chạy toàn bộ pipeline Feature Engine:
    1. Indicators: EMA (20/50/200), RSI (14), MACD (12/26/9), ATR (14)
    2. OI Features: oi_delta_pct
    3. CVD & CVD Divergence: cvd, cvd_divergence

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame OHLCV (kèm volume, taker_buy_base_volume, open_interest nếu có).
    config : Optional[Dict[str, Any]]
        Từ điển cấu hình đọc từ default_config.yaml.
    use_fallback_indicators : bool
        Ép buộc dùng pure pandas fallback cho indicators.

    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm toàn bộ các cột feature mới.
    """
    out = calculate_indicators(df, config=config, use_fallback=use_fallback_indicators)
    out = calculate_oi_features(out, config=config)
    out = calculate_cvd(out)
    out = calculate_cvd_divergence(out, config=config)
    return out


__all__ = [
    "calculate_ema",
    "calculate_rsi",
    "calculate_macd",
    "calculate_atr",
    "calculate_indicators",
    "calculate_oi_features",
    "calculate_cvd",
    "calculate_cvd_divergence",
    "add_all_features",
    "NewsCalendarFilter",
    "EconomicEvent",
]
