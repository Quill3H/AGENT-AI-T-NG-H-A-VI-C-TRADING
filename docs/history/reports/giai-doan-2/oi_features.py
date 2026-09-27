"""
src/features/oi_features.py
===========================
Module tính toán các đặc trưng biến động của Open Interest (OI):
- oi_delta_pct: % thay đổi của open_interest so với N nến trước đó.

Quy tắc:
1. Đọc N từ config['features']['oi_delta_lookback'] (mặc định 20).
2. Tương thích cơ chế oi_confluence:
   - Nếu open_interest là NaN tại một điểm, oi_delta_pct tại điểm đó cũng là NaN
     (tuyệt đối không forward-fill để che giấu).
   - Nếu cột open_interest không tồn tại hoặc toàn bộ là NaN, tạo cột oi_delta_pct
     chứa toàn bộ NaN và KHÔNG throw exception.
3. Không sửa đổi hay xóa các cột gốc của DataFrame đầu vào.
"""
from typing import Dict, Optional, Any
import numpy as np
import pandas as pd
from loguru import logger


def calculate_oi_features(
    df: pd.DataFrame,
    lookback: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Tính % biến động Open Interest (oi_delta_pct).
    
    Formula:
        oi_delta_pct_t = (open_interest_t - open_interest_{t - N}) / open_interest_{t - N} * 100
        
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame có thể chứa cột 'open_interest'.
    lookback : Optional[int]
        Số nến nhìn lại N. Nếu None, đọc từ config['features']['oi_delta_lookback'].
    config : Optional[Dict[str, Any]]
        Từ điển cấu hình hệ thống.
        
    Returns
    -------
    pd.DataFrame
        DataFrame gốc kèm cột mới 'oi_delta_pct'.
    """
    out = df.copy()

    # Đọc tham số lookback
    if lookback is None:
        features_cfg = config.get("features", {}) if config else {}
        lookback = features_cfg.get("oi_delta_lookback", 20)

    col_name = "oi_delta_pct"

    # Kiểm tra sự tồn tại của cột open_interest
    if "open_interest" not in out.columns:
        logger.debug(
            "[OIFeatures] Cột 'open_interest' không tồn tại trong DataFrame. "
            f"Tạo cột '{col_name}' với toàn bộ giá trị NaN."
        )
        out[col_name] = np.nan
        return out

    oi_series = out["open_interest"]

    # Nếu toàn bộ dữ liệu OI là NaN
    if oi_series.isna().all():
        logger.debug(
            f"[OIFeatures] Cột 'open_interest' toàn bộ là NaN. "
            f"Gán cột '{col_name}' toàn bộ NaN theo cơ chế oi_confluence."
        )
        out[col_name] = np.nan
        return out

    # Tính toán thay đổi phần trăm
    shifted_oi = oi_series.shift(lookback)
    
    # Tránh chia cho 0 hoặc giá trị âm/không hợp lệ
    denominator = shifted_oi.replace(0.0, np.nan)
    oi_delta = (oi_series - shifted_oi) / denominator * 100.0

    # Bảo đảm: nếu oi_series tại t là NaN hoặc shifted_oi là NaN thì oi_delta chắc chắn là NaN
    # NaN propagation tự nhiên của phép toán pandas
    out[col_name] = oi_delta
    return out
