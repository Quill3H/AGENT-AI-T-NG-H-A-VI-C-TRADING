"""
src/features/cvd.py
===================
Module tính toán Cumulative Volume Delta (CVD) và phát hiện phân kỳ CVD (CVD Divergence):
- cvd: Cộng dồn delta khối lượng (taker_buy_volume - taker_sell_volume).
- cvd_divergence: Phát hiện phân kỳ giữa đỉnh/đáy giá và đỉnh/đáy CVD trong cửa sổ N nến.

Quy tắc chống Lookahead Bias nghiêm ngặt:
1. Mọi phép tính tại thời điểm t chỉ sử dụng thông tin có timestamp <= t.
2. Một Swing Point tại nến i chỉ được xác nhận khi đã có đủ k nến liền sau (i + k <= t).
   Do đó, tại nến t, đỉnh/đáy được xác nhận thực tế là nến i = t - k.
3. Tín hiệu phân kỳ chỉ được ghi nhận TẠI NẾN t (thời điểm thực tế được xác nhận),
   tuyệt đối KHÔNG gán ngược về nến i trong quá khứ.
"""
from typing import Dict, Optional, Any, List
from collections import deque
import numpy as np
import pandas as pd
from loguru import logger


def calculate_cvd(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tính Cumulative Volume Delta (CVD) theo chuỗi thời gian.
    
    Formula:
        delta = taker_buy_base_volume - (volume - taker_buy_base_volume)
              = 2 * taker_buy_base_volume - volume
        cvd   = cumsum(delta)
        
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame chứa cột 'volume' và 'taker_buy_base_volume'.
        
    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm cột mới 'cvd'.
    """
    if "volume" not in df.columns:
        raise ValueError("DataFrame phải chứa cột 'volume' để tính CVD.")

    out = df.copy()

    if "taker_buy_base_volume" in out.columns:
        nan_taker_count = out["taker_buy_base_volume"].isna().sum()
        if nan_taker_count > 0:
            logger.warning(
                f"[CVD] Cột 'taker_buy_base_volume' có {nan_taker_count}/{len(out)} giá trị NaN "
                "(ước tính 50% volume -> delta = 0). CVD sẽ đi ngang tại các nến này. "
                "Cần lưu ý nếu phát hiện cvd_divergence bất thường."
            )
        taker_buy = out["taker_buy_base_volume"].fillna(out["volume"] * 0.5)
        volume = out["volume"].fillna(0.0)
        delta = 2.0 * taker_buy - volume
    else:
        logger.warning(
            "[CVD] Cột 'taker_buy_base_volume' không có trong DataFrame. "
            "Ước tính taker buy = 50% volume (delta = 0). CVD sẽ hoàn toàn đi ngang."
        )
        delta = pd.Series(0.0, index=out.index)

    out["cvd"] = delta.cumsum()
    return out


def calculate_cvd_divergence(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    lookback: Optional[int] = None,
    swing_n: Optional[int] = None,
) -> pd.DataFrame:
    """
    Phát hiện phân kỳ CVD (CVD Divergence) với cơ chế chống Lookahead Bias 100%.
    
    Định nghĩa phân kỳ:
    - BULLISH Divergence: Giá tạo đáy thấp hơn đáy trước (Lower Low),
      nhưng CVD tại đáy mới lại cao hơn CVD tại đáy trước (Higher Low).
    - BEARISH Divergence: Giá tạo đỉnh cao hơn đỉnh trước (Higher High),
      nhưng CVD tại đỉnh mới lại thấp hơn CVD tại đỉnh trước (Lower High).
    - NONE: Không có phân kỳ hoặc chưa đủ dữ liệu xác nhận.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame chứa các cột 'high', 'low', 'cvd' (nếu chưa có 'cvd' sẽ tự động tính).
    config : Optional[Dict[str, Any]]
        Từ điển cấu hình hệ thống.
    lookback : Optional[int]
        Kích thước cửa sổ nhìn lại (số nến). Nếu None, đọc từ config['features']['cvd_divergence_lookback'] (mặc định 50).
    swing_n : Optional[int]
        Số nến lân cận để xác nhận swing point (mặc định 3).
        Đọc từ config['smc']['swing_n'] nếu có.
        
    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm cột mới 'cvd_divergence' ('BULLISH' | 'BEARISH' | 'NONE').
    """
    out = df.copy()

    # Đảm bảo đã có cột 'cvd'
    if "cvd" not in out.columns:
        out = calculate_cvd(out)

    required_cols = {"high", "low", "cvd"}
    if not required_cols.issubset(out.columns):
        raise ValueError(f"DataFrame phải chứa các cột {required_cols} để tính CVD Divergence.")

    # Đọc cấu hình
    features_cfg = config.get("features", {}) if config else {}
    smc_cfg = config.get("smc", {}) if config else {}

    if lookback is None:
        lookback = features_cfg.get("cvd_divergence_lookback", 50)
    if swing_n is None:
        swing_n = smc_cfg.get("swing_n", 3)

    n_rows = len(out)
    col_name = "cvd_divergence"

    if n_rows < (2 * swing_n + 1):
        out[col_name] = "NONE"
        return out

    high_arr = out["high"].to_numpy(dtype=float)
    low_arr = out["low"].to_numpy(dtype=float)
    cvd_arr = out["cvd"].to_numpy(dtype=float)

    divergence_signals = ["NONE"] * n_rows

    # Duy trì danh sách các đỉnh/đáy đã được xác nhận nằm trong cửa sổ lookback
    confirmed_highs: deque = deque()  # lưu index i của nến swing high
    confirmed_lows: deque = deque()   # lưu index i của nến swing low

    # Causal Loop: Duyệt từng nến từ t = 0 đến n_rows - 1
    for t in range(n_rows):
        # 1. Kiểm tra xem nến i = t - swing_n có thỏa mãn là Swing High / Swing Low không
        # Chỉ có thể kiểm tra khi i >= swing_n (đủ swing_n nến trước) và i + swing_n == t (đủ swing_n nến sau)
        i = t - swing_n
        if i >= swing_n:
            # Kiểm tra Swing High: high[i] > high các nến lân cận trước và >= các nến lân cận sau
            is_sh = True
            h_i = high_arr[i]
            for offset in range(1, swing_n + 1):
                if high_arr[i - offset] >= h_i or high_arr[i + offset] > h_i:
                    is_sh = False
                    break
            if is_sh:
                confirmed_highs.append(i)

            # Kiểm tra Swing Low: low[i] < low các nến lân cận trước và <= các nến lân cận sau
            is_sl = True
            l_i = low_arr[i]
            for offset in range(1, swing_n + 1):
                if low_arr[i - offset] <= l_i or low_arr[i + offset] < l_i:
                    is_sl = False
                    break
            if is_sl:
                confirmed_lows.append(i)

        # 2. Loại bỏ các swing point đã rơi ra ngoài cửa sổ [t - lookback + 1, t]
        min_valid_idx = t - lookback + 1
        while confirmed_highs and confirmed_highs[0] < min_valid_idx:
            confirmed_highs.popleft()
        while confirmed_lows and confirmed_lows[0] < min_valid_idx:
            confirmed_lows.popleft()

        # 3. Đánh giá phân kỳ tại thời điểm t
        # Cần xác định loại swing gần nhất được xác nhận
        last_h_idx = confirmed_highs[-1] if confirmed_highs else -1
        last_l_idx = confirmed_lows[-1] if confirmed_lows else -1

        signal = "NONE"

        # Nếu Swing Low là đỉnh/đáy gần nhất vừa xác nhận
        if last_l_idx > last_h_idx and len(confirmed_lows) >= 2:
            l2 = confirmed_lows[-1]  # đáy gần nhất
            l1 = confirmed_lows[-2]  # đáy trước đó
            # Bullish Divergence: Giá tạo Lower Low, nhưng CVD tạo Higher Low
            if low_arr[l2] < low_arr[l1] and cvd_arr[l2] > cvd_arr[l1]:
                signal = "BULLISH"

        # Nếu Swing High là đỉnh/đáy gần nhất vừa xác nhận
        elif last_h_idx > last_l_idx and len(confirmed_highs) >= 2:
            h2 = confirmed_highs[-1]  # đỉnh gần nhất
            h1 = confirmed_highs[-2]  # đỉnh trước đó
            # Bearish Divergence: Giá tạo Higher High, nhưng CVD tạo Lower High
            if high_arr[h2] > high_arr[h1] and cvd_arr[h2] < cvd_arr[h1]:
                signal = "BEARISH"

        divergence_signals[t] = signal

    out[col_name] = divergence_signals
    return out
