"""
src/features/indicators.py
==========================
Module tính toán các chỉ báo kỹ thuật cơ bản:
- EMA (các chu kỳ đọc từ config, mặc định 20, 50, 200)
- RSI (chu kỳ đọc từ config, mặc định 14)
- MACD (fast, slow, signal đọc từ config, mặc định 12, 26, 9)
- ATR (chu kỳ đọc từ config, mặc định 14)

Quy tắc:
1. Đọc toàn bộ tham số chu kỳ từ config['features'], KHÔNG hardcode.
2. Ưu tiên sử dụng `pandas-ta`. Nếu lỗi hoặc thiếu thư viện, tự động fallback
   sang pandas ewm/rolling thuần và log cảnh báo rõ ràng.
3. Không sửa đổi hay xóa các cột gốc của DataFrame đầu vào.
4. Tuyệt đối không dùng lookahead bias (chỉ dùng dữ liệu tại t <= thời điểm hiện tại).
"""
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
from loguru import logger

# Kiểm tra khả năng import pandas_ta
try:
    import pandas_ta as ta  # type: ignore
    _PANDAS_TA_AVAILABLE = True
except Exception as e:
    _PANDAS_TA_AVAILABLE = False
    logger.warning(
        f"[Indicators] pandas-ta không khả dụng ({e}). "
        "Sẽ sử dụng pure pandas fallback cho toàn bộ chỉ báo."
    )


def _get_feature_params(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Trích xuất cấu hình features từ config dictionary hoặc trả về giá trị mặc định."""
    features_cfg = config.get("features", {}) if config else {}
    return {
        "ema_periods": features_cfg.get("ema_periods", [20, 50, 200]),
        "rsi_period": features_cfg.get("rsi_period", 14),
        "macd_fast": features_cfg.get("macd_fast", 12),
        "macd_slow": features_cfg.get("macd_slow", 26),
        "macd_signal": features_cfg.get("macd_signal", 9),
        "atr_period": features_cfg.get("atr_period", 14),
    }


def _ema_presma(series: pd.Series, length: int) -> pd.Series:
    """Tính EMA theo chuẩn TA-Lib: khởi tạo bằng SMA tại chu kỳ length."""
    if len(series) < length:
        return pd.Series(np.nan, index=series.index)
    s = series.copy()
    sma_val = s.iloc[:length].mean()
    s.iloc[:length - 1] = np.nan
    s.iloc[length - 1] = sma_val
    return s.ewm(span=length, adjust=False).mean()


def calculate_ema(
    df: pd.DataFrame,
    periods: Optional[List[int]] = None,
    config: Optional[Dict[str, Any]] = None,
    use_fallback: bool = False,
) -> pd.DataFrame:
    """
    Tính đường Exponential Moving Average (EMA) cho các chu kỳ được chỉ định.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame chứa cột 'close'.
    periods : Optional[List[int]]
        Danh sách chu kỳ EMA. Nếu None, đọc từ config['features']['ema_periods'].
    config : Optional[Dict[str, Any]]
        Từ điển cấu hình hệ thống.
    use_fallback : bool
        Nếu True, ép buộc sử dụng pure pandas fallback (dùng cho unit test).
        
    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm các cột 'ema_{period}'.
    """
    if "close" not in df.columns:
        raise ValueError("DataFrame phải chứa cột 'close' để tính EMA.")

    if periods is None:
        params = _get_feature_params(config)
        periods = params["ema_periods"]

    out = df.copy()
    for p in periods:
        col_name = f"ema_{p}"
        if _PANDAS_TA_AVAILABLE and not use_fallback:
            try:
                series = ta.ema(out["close"], length=p)
                if series is not None and not series.empty:
                    out[col_name] = series
                    continue
            except Exception as ex:
                logger.warning(
                    f"[Indicators] pandas-ta ta.ema(length={p}) lỗi: {ex}. "
                    f"Dùng pure pandas fallback."
                )
        
        # Fallback pure pandas (chuẩn TA-Lib)
        out[col_name] = _ema_presma(out["close"], p)

    return out


def calculate_rsi(
    df: pd.DataFrame,
    period: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
    use_fallback: bool = False,
) -> pd.DataFrame:
    """
    Tính Relative Strength Index (RSI) theo công thức chuẩn Wilder.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame chứa cột 'close'.
    period : Optional[int]
        Chu kỳ RSI. Nếu None, đọc từ config['features']['rsi_period'].
    config : Optional[Dict[str, Any]]
        Từ điển cấu hình hệ thống.
    use_fallback : bool
        Nếu True, ép buộc sử dụng pure pandas fallback.
        
    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm cột 'rsi_{period}'.
    """
    if "close" not in df.columns:
        raise ValueError("DataFrame phải chứa cột 'close' để tính RSI.")

    if period is None:
        params = _get_feature_params(config)
        period = params["rsi_period"]

    col_name = f"rsi_{period}"
    out = df.copy()

    if _PANDAS_TA_AVAILABLE and not use_fallback:
        try:
            series = ta.rsi(out["close"], length=period)
            if series is not None and not series.empty:
                out[col_name] = series
                return out
        except Exception as ex:
            logger.warning(
                f"[Indicators] pandas-ta ta.rsi(length={period}) lỗi: {ex}. "
                f"Dùng pure pandas fallback."
            )

    # Fallback pure pandas (Wilder's smoothing: alpha = 1 / period)
    delta = out["close"].diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Xử lý trường hợp đặc biệt: avg_loss == 0 hoặc cả hai == 0
    zero_loss = (avg_loss == 0) & (avg_gain > 0)
    zero_both = (avg_loss == 0) & (avg_gain == 0)
    rsi = rsi.mask(zero_loss, 100.0).mask(zero_both, 50.0)

    out[col_name] = rsi
    return out


def calculate_macd(
    df: pd.DataFrame,
    fast: Optional[int] = None,
    slow: Optional[int] = None,
    signal: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
    use_fallback: bool = False,
) -> pd.DataFrame:
    """
    Tính Moving Average Convergence Divergence (MACD).
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame chứa cột 'close'.
    fast, slow, signal : Optional[int]
        Chu kỳ fast, slow, signal. Nếu None, đọc từ config.
    config : Optional[Dict[str, Any]]
        Từ điển cấu hình hệ thống.
    use_fallback : bool
        Nếu True, ép buộc sử dụng pure pandas fallback.
        
    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm các cột 'macd', 'macd_signal', 'macd_hist'.
    """
    if "close" not in df.columns:
        raise ValueError("DataFrame phải chứa cột 'close' để tính MACD.")

    params = _get_feature_params(config)
    fast = fast if fast is not None else params["macd_fast"]
    slow = slow if slow is not None else params["macd_slow"]
    signal = signal if signal is not None else params["macd_signal"]

    out = df.copy()

    if _PANDAS_TA_AVAILABLE and not use_fallback:
        try:
            macd_df = ta.macd(out["close"], fast=fast, slow=slow, signal=signal)
            if macd_df is not None and not macd_df.empty:
                # pandas-ta đặt tên: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
                line_col = f"MACD_{fast}_{slow}_{signal}"
                hist_col = f"MACDh_{fast}_{slow}_{signal}"
                sig_col = f"MACDs_{fast}_{slow}_{signal}"
                if line_col in macd_df.columns:
                    out["macd"] = macd_df[line_col]
                    out["macd_signal"] = macd_df[sig_col]
                    out["macd_hist"] = macd_df[hist_col]
                    return out
        except Exception as ex:
            logger.warning(
                f"[Indicators] pandas-ta ta.macd lỗi: {ex}. Dùng pure pandas fallback."
            )

    # Fallback pure pandas (chuẩn TA-Lib)
    fast_ema = _ema_presma(out["close"], fast)
    slow_ema = _ema_presma(out["close"], slow)
    macd_line = fast_ema - slow_ema
    macd_sig = _ema_presma(macd_line.dropna(), signal).reindex(out.index)
    macd_hist = macd_line - macd_sig

    out["macd"] = macd_line
    out["macd_signal"] = macd_sig
    out["macd_hist"] = macd_hist
    return out


def calculate_atr(
    df: pd.DataFrame,
    period: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
    use_fallback: bool = False,
) -> pd.DataFrame:
    """
    Tính Average True Range (ATR) theo công thức chuẩn Wilder.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame chứa các cột 'high', 'low', 'close'.
    period : Optional[int]
        Chu kỳ ATR. Nếu None, đọc từ config['features']['atr_period'].
    config : Optional[Dict[str, Any]]
        Từ điển cấu hình hệ thống.
    use_fallback : bool
        Nếu True, ép buộc sử dụng pure pandas fallback.
        
    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm cột 'atr_{period}'.
    """
    required_cols = {"high", "low", "close"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"DataFrame phải chứa đủ các cột {required_cols} để tính ATR.")

    if period is None:
        params = _get_feature_params(config)
        period = params["atr_period"]

    col_name = f"atr_{period}"
    out = df.copy()

    if _PANDAS_TA_AVAILABLE and not use_fallback:
        try:
            series = ta.atr(out["high"], out["low"], out["close"], length=period, mamode="rma")
            if series is not None and not series.empty:
                out[col_name] = series
                return out
        except Exception as ex:
            logger.warning(
                f"[Indicators] pandas-ta ta.atr lỗi: {ex}. Dùng pure pandas fallback."
            )

    # Fallback pure pandas: True Range = max(high-low, |high-close_prev|, |low-close_prev|)
    high = out["high"]
    low = out["low"]
    close_prev = out["close"].shift(1)

    tr0 = high - low
    tr1 = (high - close_prev).abs()
    tr2 = (low - close_prev).abs()
    tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)

    # Wilder's smoothing (alpha = 1 / period)
    out[col_name] = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return out


def calculate_indicators(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    use_fallback: bool = False,
) -> pd.DataFrame:
    """
    Tính toàn bộ các chỉ báo kỹ thuật cơ bản: EMA, RSI, MACD, ATR.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame OHLCV.
    config : Optional[Dict[str, Any]]
        Từ điển cấu hình đọc từ default_config.yaml.
    use_fallback : bool
        Nếu True, ép buộc sử dụng pure pandas fallback.
        
    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm đầy đủ các cột chỉ báo mới:
        'ema_20', 'ema_50', 'ema_200', 'rsi_14', 'macd', 'macd_signal', 'macd_hist', 'atr_14'.
    """
    out = df.copy()
    out = calculate_ema(out, config=config, use_fallback=use_fallback)
    out = calculate_rsi(out, config=config, use_fallback=use_fallback)
    out = calculate_macd(out, config=config, use_fallback=use_fallback)
    out = calculate_atr(out, config=config, use_fallback=use_fallback)
    return out
