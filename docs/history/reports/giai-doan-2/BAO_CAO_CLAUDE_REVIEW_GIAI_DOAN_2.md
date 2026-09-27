# BÁO CÁO ĐẦY ĐỦ GIAI ĐOẠN 2: FEATURE ENGINE (GỬI CLAUDE REVIEW)

## 1. TỔNG QUAN KẾT QUẢ TRIỂN KHAI GIAI ĐOẠN 2

- **Trạng thái:** HOÀN THÀNH 100% mục 4.2, 4.3 và roadmap mục 6 Master Spec.
- **Kết quả Pytest:** **53/53 tests PASSED (100%)** trong 11.90s (bao gồm 28 test Giai đoạn 1 + 25 test mới Giai đoạn 2).
- **Kiểm thử dữ liệu thật BTC/USDT (70 ngày gần nhất):**
  - **Khung 4H (420 nến):** Warm-up EMA 200 = 199 nến NaN (đúng chuẩn toán học), 221 nến hợp lệ (52.6%). NaN OI delta = 20 nến (4.76% do shift lookback 20, sau đó 0% NaN). CVD Divergence: 380 NONE, 18 BULLISH, 22 BEARISH.
  - **Khung 15M (6,720 nến):** Warm-up EMA 200 = 199 nến NaN, 6,521 nến hợp lệ (97.0%). NaN OI delta = 20 nến (0.30%). CVD Divergence: 5,908 NONE, 355 BULLISH, 457 BEARISH.

---

## 2. GIẢI TRÌNH KỸ THUẬT: CƠ CHẾ XỬ LÝ ĐỘ TRỄ XÁC NHẬN SWING VÀ CHỐNG LOOKAHEAD BIAS

### 2.1 Bản chất toán học của Swing Point
Theo mục 4.3 của Spec, một nến tại chỉ số $i$ là **Swing High** nếu:
$$\text{high}[i] > \text{high}[i - j] \quad \text{và} \quad \text{high}[i] \ge \text{high}[i + j] \quad \forall j \in \{1, \dots, k\} \quad (k = \text{swing\_n} = 3)$$
Và tương tự cho **Swing Low**:
$$\text{low}[i] < \text{low}[i - j] \quad \text{và} \quad \text{low}[i] \le \text{low}[i + j] \quad \forall j \in \{1, \dots, k\}$$

### 2.2 Độ trễ xác nhận (Confirmation Lag)
Để biết được điều kiện trên có thỏa mãn tại nến $i$ hay không, ta **bắt buộc phải quan sát đủ $k$ nến nằm ở phía bên phải** của $i$ (tức là các nến $i+1, \dots, i+k$).
Điều này đồng nghĩa:
> **Nến tại chỉ số $i$ chỉ có thể được xác nhận là một Swing Point tại thời điểm nến $t = i + k$ đóng cửa.**

### 2.3 Cơ chế chống Lookahead Bias (Tuyệt đối không gán ngược)
1. **Tại thời điểm nến $t$:** Nến duy nhất có thể vừa được xác nhận là đỉnh/đáy là nến $i = t - k$. Toàn bộ các nến $i - k, \dots, i, \dots, i + k = t$ đều đã đóng và thuộc quá khứ/hiện tại relative to $t$.
2. **Không gán ngược (No Backfilling):** Nếu ta gán nhãn `BULLISH` hoặc `BEARISH` vào dòng $i$ ($t - k$), đó là **Lookahead Bias nghiêm trọng**, vì tại thời điểm $i$ trader không thể biết được tương lai $k$ nến sau đó. Thay vào đó, tín hiệu phân kỳ **chỉ được ghi nhận tại dòng $t$** — thời điểm mà thông tin thực sự đã được biết.
3. **Causal Streaming Loop:** Thuật toán duyệt tuần tự từng nến $t = 0 \to N-1$, duy trì một `deque` các swing point đã xác nhận trong phạm vi $[t - \text{lookback} + 1, t]$. Không sử dụng `center=True` trong bất kỳ phép rolling nào.
4. **Bảo chứng bằng unit test `test_no_lookahead.py`:** Kiểm thử xáo trộn dữ liệu tương lai sau điểm cắt $T$, chứng minh toán học mọi giá trị feature tại $t \le T$ giữ nguyên 100%.

---

## 3. XÁC NHẬN VỀ WARM-UP PERIOD (GIAI ĐOẠN KHỞI ĐỘNG)

- **EMA 200:** Theo chuẩn TA-Lib (`presma=True`), đường EMA 200 cần 200 nến đầu tiên để tính SMA làm mầm khởi tạo. Do đó, **đúng 199 nến đầu tiên luôn mang giá trị `NaN`**. Đây là tính chất toán học tất yếu, hoàn toàn không phải bug.
- **RSI 14 / ATR 14:** Cần 14 nến để khởi tạo chuỗi Wilder's smoothing.
- **OI Delta (lookback N=20):** 20 nến đầu tiên là `NaN` do phép `shift(20)`. Sau 20 nến, dữ liệu hoàn toàn không có NaN.

---

## 4. NỘI DUNG NGUYÊN VĂN CÁC FILE SOURCE CODE VÀ TEST GIAI ĐOẠN 2


### File: `src/features/indicators.py`

```python
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

```


### File: `src/features/oi_features.py`

```python
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

```


### File: `src/features/cvd.py`

```python
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

```


### File: `src/features/__init__.py`

```python
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

```


### File: `tests/test_indicators.py`

```python
"""
tests/test_indicators.py
========================
Unit tests kiểm tra tính đúng đắn toán học của module indicators.py:
- EMA, RSI, MACD, ATR
- So sánh kết quả tính bằng pandas-ta và pure pandas fallback
- Kiểm tra không đột biến (mutate) cột gốc
- Kiểm tra ngoại lệ khi thiếu cột bắt buộc
- Kiểm tra warm-up periods
"""
import numpy as np
import pandas as pd
import pytest

from src.features.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_atr,
    calculate_indicators,
    _PANDAS_TA_AVAILABLE,
)


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Tạo chuỗi OHLCV nhân tạo gồm 250 nến phục vụ test chỉ báo."""
    np.random.seed(42)
    n = 250
    dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    
    # Bước đi ngẫu nhiên cho giá đóng cửa
    returns = np.random.normal(0.001, 0.02, n)
    close = 40000.0 * np.exp(np.cumsum(returns))
    high = close * (1.0 + np.abs(np.random.normal(0, 0.005, n)))
    low = close * (1.0 - np.abs(np.random.normal(0, 0.005, n)))
    open_p = (high + low) / 2.0
    volume = np.random.uniform(100, 1000, n)
    taker_buy = volume * np.random.uniform(0.4, 0.6, n)

    df = pd.DataFrame(
        {
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "taker_buy_base_volume": taker_buy,
        },
        index=dates,
    )
    return df


class TestIndicators:
    """Bộ test cho các chỉ báo kỹ thuật cơ bản."""

    def test_ema_known_small_series(self):
        """Kiểm tra EMA trên chuỗi dữ liệu 5 giá trị tính tay."""
        # Giá trị: [10, 20, 30, 40, 50]
        # Chuẩn TA-Lib (presma=True):
        # Index 0, 1: NaN
        # Index 2: SMA(3) = (10 + 20 + 30) / 3 = 20.0
        # Index 3: alpha = 2/(3+1) = 0.5 -> 0.5 * 40 + 0.5 * 20 = 30.0
        # Index 4: 0.5 * 50 + 0.5 * 30 = 40.0
        df = pd.DataFrame({"close": [10.0, 20.0, 30.0, 40.0, 50.0]})
        res = calculate_ema(df, periods=[3], use_fallback=True)

        expected = [np.nan, np.nan, 20.0, 30.0, 40.0]
        np.testing.assert_allclose(res["ema_3"].values, expected, rtol=1e-5)

    def test_ema_fallback_matches_pandas_ta(self, sample_ohlcv):
        """Kiểm tra kết quả fallback pure pandas trùng khớp với pandas-ta."""
        if not _PANDAS_TA_AVAILABLE:
            pytest.skip("pandas-ta không được cài đặt, bỏ qua so sánh chéo.")

        res_ta = calculate_ema(sample_ohlcv, periods=[20, 50], use_fallback=False)
        res_fb = calculate_ema(sample_ohlcv, periods=[20, 50], use_fallback=True)

        for p in [20, 50]:
            # Bỏ qua các nến đầu do min_periods nếu có
            col = f"ema_{p}"
            valid_idx = res_ta[col].dropna().index
            np.testing.assert_allclose(
                res_ta.loc[valid_idx, col].values,
                res_fb.loc[valid_idx, col].values,
                rtol=1e-3,
                err_msg=f"EMA {p} giữa pandas-ta và fallback bị lệch",
            )

    def test_rsi_constant_and_trending(self):
        """Kiểm tra RSI khi giá đi ngang (RSI ~ 50) và khi giá tăng liên tục (RSI -> 100)."""
        # Chuỗi tăng liên tục: mọi delta > 0, avg_loss = 0 -> RSI = 100
        df_up = pd.DataFrame({"close": np.linspace(100, 200, 50)})
        res_up = calculate_rsi(df_up, period=14, use_fallback=True)
        assert res_up["rsi_14"].iloc[-1] == pytest.approx(100.0, abs=1e-4)

        # Chuỗi giảm liên tục: mọi delta < 0, avg_gain = 0 -> RSI = 0
        df_down = pd.DataFrame({"close": np.linspace(200, 100, 50)})
        res_down = calculate_rsi(df_down, period=14, use_fallback=True)
        assert res_down["rsi_14"].iloc[-1] == pytest.approx(0.0, abs=1e-4)

    def test_rsi_fallback_matches_pandas_ta(self, sample_ohlcv):
        """Kiểm tra RSI giữa pandas-ta và fallback pure pandas tương đồng."""
        if not _PANDAS_TA_AVAILABLE:
            pytest.skip("pandas-ta không được cài đặt, bỏ qua so sánh chéo.")

        res_ta = calculate_rsi(sample_ohlcv, period=14, use_fallback=False)
        res_fb = calculate_rsi(sample_ohlcv, period=14, use_fallback=True)

        # Cả 2 đều dùng Wilder's smoothing (alpha = 1/14)
        valid = res_ta["rsi_14"].dropna().index.intersection(res_fb["rsi_14"].dropna().index)
        # So sánh sau warm-up period (từ index 30 trở đi)
        valid = valid[30:]
        np.testing.assert_allclose(
            res_ta.loc[valid, "rsi_14"].values,
            res_fb.loc[valid, "rsi_14"].values,
            rtol=1e-2,
            atol=0.5,
            err_msg="RSI 14 giữa pandas-ta và fallback bị lệch",
        )

    def test_macd_formula(self, sample_ohlcv):
        """Kiểm tra quan hệ định nghĩa MACD: macd_hist = macd - macd_signal."""
        res = calculate_macd(sample_ohlcv, fast=12, slow=26, signal=9, use_fallback=True)
        assert "macd" in res.columns
        assert "macd_signal" in res.columns
        assert "macd_hist" in res.columns

        diff = res["macd"] - res["macd_signal"]
        np.testing.assert_allclose(res["macd_hist"].values, diff.values, atol=1e-8)

    def test_atr_positive_and_matches_tr(self):
        """Kiểm tra ATR luôn dương và đúng tính chất biên độ nến."""
        df = pd.DataFrame({
            "high": [105.0, 110.0, 108.0, 115.0, 112.0],
            "low":  [95.0,  100.0, 98.0,  102.0, 100.0],
            "close":[100.0, 105.0, 102.0, 110.0, 105.0],
        })
        res = calculate_atr(df, period=3, use_fallback=True)
        assert "atr_3" in res.columns
        # ATR phải luôn > 0
        valid_atr = res["atr_3"].dropna()
        assert (valid_atr > 0).all()

    def test_calculate_indicators_all_columns_present(self, sample_ohlcv, config):
        """Kiểm tra calculate_indicators tạo đủ toàn bộ các cột từ config."""
        orig_cols = list(sample_ohlcv.columns)
        res = calculate_indicators(sample_ohlcv, config=config)

        # Cột gốc phải giữ nguyên
        for col in orig_cols:
            assert col in res.columns
            pd.testing.assert_series_equal(res[col], sample_ohlcv[col])

        # Cột chỉ báo mới
        expected_cols = [
            "ema_20", "ema_50", "ema_200",
            "rsi_14",
            "macd", "macd_signal", "macd_hist",
            "atr_14",
        ]
        for ec in expected_cols:
            assert ec in res.columns, f"Thiếu cột {ec} trong output của calculate_indicators"

    def test_warmup_period_ema200(self, sample_ohlcv, config):
        """Xác nhận warm-up period: 200 nến đầu của EMA 200 có thể là NaN hoặc hội tụ."""
        res = calculate_indicators(sample_ohlcv, config=config)
        # Nến thứ 200 trở đi chắc chắn phải có giá trị hợp lệ
        assert pd.notna(res["ema_200"].iloc[200])

    def test_missing_required_columns_raises(self):
        """Kiểm tra bắt lỗi ngoại lệ khi DataFrame thiếu cột cần thiết."""
        df_bad = pd.DataFrame({"open": [1, 2], "volume": [10, 20]})
        with pytest.raises(ValueError, match="close"):
            calculate_ema(df_bad)
        with pytest.raises(ValueError, match="close"):
            calculate_rsi(df_bad)
        with pytest.raises(ValueError, match="close"):
            calculate_macd(df_bad)
        with pytest.raises(ValueError, match="high"):
            calculate_atr(df_bad)

```


### File: `tests/test_oi_features.py`

```python
"""
tests/test_oi_features.py
=========================
Unit tests kiểm tra module oi_features.py:
- Tính % thay đổi Open Interest (oi_delta_pct) đúng công thức
- Cơ chế lan truyền NaN (NaN propagation) khi OI bị thiếu
- Xử lý an toàn khi không có cột open_interest hoặc cột toàn NaN (không raise lỗi)
- Không mutate các cột gốc
"""
import numpy as np
import pandas as pd
import pytest

from src.features.oi_features import calculate_oi_features


class TestOIFeatures:
    """Bộ test kiểm tra tính năng Open Interest."""

    def test_oi_delta_pct_known_values(self):
        """Kiểm tra công thức oi_delta_pct với dữ liệu biết trước."""
        # OI: [100.0, 110.0, 121.0, 108.9]
        # Lookback = 1
        # t=0: NaN
        # t=1: (110 - 100) / 100 * 100 = 10.0%
        # t=2: (121 - 110) / 110 * 100 = 10.0%
        # t=3: (108.9 - 121) / 121 * 100 = -10.0%
        df = pd.DataFrame({"open_interest": [100.0, 110.0, 121.0, 108.9]})
        res = calculate_oi_features(df, lookback=1)

        assert "oi_delta_pct" in res.columns
        assert pd.isna(res["oi_delta_pct"].iloc[0])
        assert res["oi_delta_pct"].iloc[1] == pytest.approx(10.0, rel=1e-4)
        assert res["oi_delta_pct"].iloc[2] == pytest.approx(10.0, rel=1e-4)
        assert res["oi_delta_pct"].iloc[3] == pytest.approx(-10.0, rel=1e-4)

    def test_oi_delta_pct_lookback_from_config(self, config):
        """Kiểm tra đọc lookback từ config (mặc định 20)."""
        n = 50
        df = pd.DataFrame({"open_interest": np.linspace(1000, 2000, n)})
        res = calculate_oi_features(df, config=config)

        # 20 dòng đầu phải là NaN do shift(20)
        assert res["oi_delta_pct"].iloc[:20].isna().all()
        # Dòng thứ 20 (index 20) phải có giá trị hợp lệ
        assert pd.notna(res["oi_delta_pct"].iloc[20])

    def test_nan_propagation_when_oi_has_nan(self):
        """Kiểm tra lan truyền NaN: nếu OI tại t hoặc t-N là NaN thì oi_delta_pct là NaN."""
        df = pd.DataFrame({
            "open_interest": [100.0, 120.0, np.nan, 150.0, 160.0]
        })
        res = calculate_oi_features(df, lookback=1)

        # t=0: NaN (shift)
        assert pd.isna(res["oi_delta_pct"].iloc[0])
        # t=1: hợp lệ
        assert res["oi_delta_pct"].iloc[1] == pytest.approx(20.0)
        # t=2: OI tại t là NaN -> oi_delta_pct phải là NaN
        assert pd.isna(res["oi_delta_pct"].iloc[2])
        # t=3: OI tại t-1 là NaN -> oi_delta_pct phải là NaN
        assert pd.isna(res["oi_delta_pct"].iloc[3])
        # t=4: OI(4)=160, OI(3)=150 -> hợp lệ
        assert res["oi_delta_pct"].iloc[4] == pytest.approx((160 - 150) / 150 * 100)

    def test_missing_oi_column_does_not_raise(self):
        """Khi DataFrame không có cột open_interest, không được raise lỗi và gán cột toàn NaN."""
        df = pd.DataFrame({"close": [10, 20, 30]})
        res = calculate_oi_features(df, lookback=5)

        assert "oi_delta_pct" in res.columns
        assert res["oi_delta_pct"].isna().all()
        assert len(res) == 3

    def test_all_nan_oi_column_does_not_raise(self):
        """Khi cột open_interest toàn bộ là NaN, không được raise lỗi và gán cột toàn NaN."""
        df = pd.DataFrame({"open_interest": [np.nan, np.nan, np.nan]})
        res = calculate_oi_features(df, lookback=2)

        assert "oi_delta_pct" in res.columns
        assert res["oi_delta_pct"].isna().all()

    def test_original_columns_not_mutated(self):
        """Đảm bảo hàm không làm thay đổi các cột gốc."""
        df = pd.DataFrame({"open_interest": [100.0, 200.0], "close": [1.0, 2.0]})
        df_copy = df.copy()
        res = calculate_oi_features(df, lookback=1)

        pd.testing.assert_frame_equal(df, df_copy)
        assert "oi_delta_pct" in res.columns
        assert "close" in res.columns

```


### File: `tests/test_cvd.py`

```python
"""
tests/test_cvd.py
=================
Unit tests kiểm tra module cvd.py:
- Tính CVD cộng dồn đúng công thức
- Nhận diện đúng kịch bản phân kỳ tăng (BULLISH divergence)
- Nhận diện đúng kịch bản phân kỳ giảm (BEARISH divergence)
- Xác nhận độ trễ xác nhận (confirmation lag) không bị leak về quá khứ
"""
import numpy as np
import pandas as pd
import pytest

from src.features.cvd import calculate_cvd, calculate_cvd_divergence


class TestCVD:
    """Bộ test kiểm tra CVD và CVD Divergence."""

    def test_cvd_calculation_known_values(self):
        """Kiểm tra cộng dồn delta khối lượng với dữ liệu biết trước."""
        # Volume: [100, 200, 150]
        # Taker buy: [60, 80, 100]
        # Taker sell = Volume - Taker buy: [40, 120, 50]
        # Delta = Taker buy - Taker sell = [20, -40, 50]
        # CVD = cumsum(Delta) = [20, -20, 30]
        df = pd.DataFrame({
            "volume": [100.0, 200.0, 150.0],
            "taker_buy_base_volume": [60.0, 80.0, 100.0],
        })
        res = calculate_cvd(df)

        assert "cvd" in res.columns
        expected_cvd = [20.0, -20.0, 30.0]
        np.testing.assert_allclose(res["cvd"].values, expected_cvd)

    def test_cvd_divergence_bullish_scenario(self):
        """
        Kịch bản BULLISH Divergence rõ ràng:
        - Swing Low 1 (L1) tại index 5: Low = 100.0, CVD = 50.0
        - Đỉnh trung gian tại index 9: High = 120.0
        - Swing Low 2 (L2) tại index 13: Low = 90.0 (Lower Low), CVD = 75.0 (Higher Low)
        - swing_n = 2: Cần 2 nến xác nhận sau L2 -> Được xác nhận tại index 15 (13 + 2).
        """
        n = 20
        swing_n = 2
        lookback = 18

        # Khởi tạo giá nền cao
        high = [130.0] * n
        low = [110.0] * n
        cvd = [100.0] * n

        # Tạo Swing Low 1 tại index 5 (L1)
        # Nến 3, 4: low = 110
        # Nến 5: low = 100 (đáy)
        # Nến 6, 7: low = 110
        low[5] = 100.0
        cvd[5] = 50.0

        # Đỉnh giữa tại index 9
        high[9] = 140.0

        # Tạo Swing Low 2 tại index 13 (L2)
        # Nến 11, 12: low = 110
        # Nến 13: low = 90.0 (thấp hơn L1: Lower Low)
        # Nến 14, 15: low = 110
        low[13] = 90.0
        cvd[13] = 75.0  # CVD tại L2 cao hơn tại L1 (Higher Low)

        df = pd.DataFrame({"high": high, "low": low, "cvd": cvd})
        res = calculate_cvd_divergence(df, lookback=lookback, swing_n=swing_n)

        # 1. Tại chính thời điểm L2 xảy ra (index 13): Chưa đủ nến xác nhận -> KHÔNG ĐƯỢC là BULLISH
        assert res["cvd_divergence"].iloc[13] != "BULLISH", (
            "Lookahead Bias! Tín hiệu phân kỳ bị gán ngược về nến index 13 trước khi được xác nhận."
        )

        # 2. Tại nến index 14: Mới có 1 nến sau L2 -> Chưa đủ 2 nến xác nhận
        assert res["cvd_divergence"].iloc[14] != "BULLISH"

        # 3. Tại nến index 15 (13 + swing_n): Đã đủ 2 nến xác nhận L2 -> Bắt đầu ghi nhận BULLISH
        assert res["cvd_divergence"].iloc[15] == "BULLISH", (
            "Tại index 15 (13 + 2), L2 phải được xác nhận và phát hiện BULLISH divergence!"
        )

    def test_cvd_divergence_bearish_scenario(self):
        """
        Kịch bản BEARISH Divergence rõ ràng:
        - Swing High 1 (H1) tại index 4: High = 150.0, CVD = 200.0
        - Đáy trung gian tại index 8: Low = 120.0
        - Swing High 2 (H2) tại index 12: High = 165.0 (Higher High), CVD = 160.0 (Lower High)
        - swing_n = 2: Xác nhận tại index 14 (12 + 2).
        """
        n = 20
        swing_n = 2
        lookback = 18

        high = [130.0] * n
        low = [110.0] * n
        cvd = [100.0] * n

        # Tạo Swing High 1 tại index 4 (H1)
        high[4] = 150.0
        cvd[4] = 200.0

        # Đáy giữa tại index 8
        low[8] = 95.0

        # Tạo Swing High 2 tại index 12 (H2)
        high[12] = 165.0  # Cao hơn H1: Higher High
        cvd[12] = 160.0  # CVD thấp hơn H1: Lower High

        df = pd.DataFrame({"high": high, "low": low, "cvd": cvd})
        res = calculate_cvd_divergence(df, lookback=lookback, swing_n=swing_n)

        # Chưa xác nhận tại index 12
        assert res["cvd_divergence"].iloc[12] != "BEARISH"
        # Chưa đủ nến tại index 13
        assert res["cvd_divergence"].iloc[13] != "BEARISH"
        # Đã đủ 2 nến xác nhận tại index 14
        assert res["cvd_divergence"].iloc[14] == "BEARISH"

    def test_cvd_divergence_none_when_in_agreement(self):
        """Khi giá và CVD đồng thuận (cùng tạo Higher High) -> Không có phân kỳ (NONE)."""
        n = 20
        swing_n = 2
        lookback = 18

        high = [130.0] * n
        low = [110.0] * n
        cvd = [100.0] * n

        # H1
        high[4] = 150.0
        cvd[4] = 150.0
        # Đáy giữa
        low[8] = 100.0
        # H2: Giá cao hơn VÀ CVD cũng cao hơn (đồng thuận xu hướng tăng)
        high[12] = 165.0
        cvd[12] = 220.0

        df = pd.DataFrame({"high": high, "low": low, "cvd": cvd})
        res = calculate_cvd_divergence(df, lookback=lookback, swing_n=swing_n)

        assert res["cvd_divergence"].iloc[14] == "NONE"

```


### File: `tests/test_no_lookahead.py`

```python
"""
tests/test_no_lookahead.py
==========================
Kiểm thử tính bất biến nhân quả (Causal Invariance / Anti-Lookahead Bias Test).
Theo đúng mục 5 trong CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md:

Quy tắc:
Bắt buộc có unit test riêng shuffle/thay đổi ngẫu nhiên toàn bộ dữ liệu tương lai
(sau thời điểm T) để đảm bảo việc thay đổi dữ liệu tương lai tuyệt đối không ảnh hưởng
tới bất kỳ feature nào tại thời điểm T (và các thời điểm < T trong quá khứ).
"""
import numpy as np
import pandas as pd
import pytest

from src.features import add_all_features


@pytest.fixture
def base_market_dataframe() -> pd.DataFrame:
    """Tạo chuỗi dữ liệu 300 nến đầy đủ OHLCV, volume, taker_buy và open_interest."""
    np.random.seed(123)
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")

    returns = np.random.normal(0.0002, 0.01, n)
    close = 50000.0 * np.exp(np.cumsum(returns))
    high = close * (1.0 + np.abs(np.random.normal(0, 0.003, n)))
    low = close * (1.0 - np.abs(np.random.normal(0, 0.003, n)))
    open_p = (high + low) / 2.0
    volume = np.random.uniform(50, 500, n)
    taker_buy = volume * np.random.uniform(0.3, 0.7, n)
    open_interest = 10000.0 + np.cumsum(np.random.normal(0, 50, n))

    df = pd.DataFrame(
        {
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "taker_buy_base_volume": taker_buy,
            "open_interest": open_interest,
        },
        index=dates,
    )
    return df


class TestNoLookaheadBias:
    """Kiểm tra triệt để chống Lookahead Bias."""

    @pytest.mark.parametrize("cutoff_t", [80, 150, 220])
    @pytest.mark.parametrize("use_fallback", [False, True])
    def test_future_data_tampering_does_not_alter_past_features(
        self, base_market_dataframe, config, cutoff_t, use_fallback
    ):
        """
        Tại thời điểm T:
        Thay đổi ngẫu nhiên toàn bộ dữ liệu từ T + 1 đến cuối chuỗi (giá tăng x10, xáo trộn).
        Tính lại toàn bộ feature trên chuỗi bị sửa đổi.
        Khẳng định: Mọi feature tại t <= T giữa 2 chuỗi là BẰNG NHAU TUYỆT ĐỐI.
        """
        df_original = base_market_dataframe.copy()
        features_orig = add_all_features(
            df_original, config=config, use_fallback_indicators=use_fallback
        )

        # Tạo bản sao và bóp méo hoàn toàn dữ liệu tương lai (sau cutoff_t)
        df_tampered = df_original.copy()
        n = len(df_tampered)

        np.random.seed(999)
        tampered_slice = slice(cutoff_t + 1, n)

        # Nhân giá lên 10 lần và đảo ngược biến động
        df_tampered.loc[df_tampered.index[tampered_slice], "close"] *= 10.0
        df_tampered.loc[df_tampered.index[tampered_slice], "high"] *= 12.0
        df_tampered.loc[df_tampered.index[tampered_slice], "low"] *= 8.0
        df_tampered.loc[df_tampered.index[tampered_slice], "open"] *= 10.0
        df_tampered.loc[df_tampered.index[tampered_slice], "volume"] *= 50.0
        df_tampered.loc[df_tampered.index[tampered_slice], "taker_buy_base_volume"] *= 50.0
        df_tampered.loc[df_tampered.index[tampered_slice], "open_interest"] = np.nan

        # Tính lại toàn bộ features trên dataframe đã bị phá hoại tương lai
        features_tampered = add_all_features(
            df_tampered, config=config, use_fallback_indicators=use_fallback
        )

        # Kiểm tra tất cả các cột feature:
        feature_columns = [
            "ema_20", "ema_50", "ema_200",
            "rsi_14",
            "macd", "macd_signal", "macd_hist",
            "atr_14",
            "oi_delta_pct",
            "cvd",
            "cvd_divergence",
        ]

        # Cắt lấy phần quá khứ và hiện tại (t <= cutoff_t)
        past_orig = features_orig.iloc[: cutoff_t + 1][feature_columns]
        past_tamp = features_tampered.iloc[: cutoff_t + 1][feature_columns]

        # Kiểm tra từng cột
        for col in feature_columns:
            s_orig = past_orig[col]
            s_tamp = past_tamp[col]

            if col == "cvd_divergence":
                # Kiểu chuỗi categorical
                mismatches = s_orig != s_tamp
                if mismatches.any():
                    mismatch_idx = past_orig.index[mismatches]
                    pytest.fail(
                        f"Lookahead bias phát hiện tại cột '{col}' ở các index: {mismatch_idx}! "
                        f"Dữ liệu tương lai đã làm thay đổi giá trị quá khứ."
                    )
            else:
                # Kiểu số float
                # NaN phải xuất hiện ở đúng cùng một vị trí
                assert s_orig.isna().equals(s_tamp.isna()), (
                    f"Lookahead bias tại cột '{col}': vị trí NaN bị thay đổi bởi tương lai!"
                )
                valid = s_orig.dropna().index
                np.testing.assert_allclose(
                    s_orig.loc[valid].values,
                    s_tamp.loc[valid].values,
                    rtol=1e-7,
                    atol=1e-7,
                    err_msg=f"Lookahead bias tại cột '{col}'! Dữ liệu tương lai thay đổi giá trị tại t <= {cutoff_t}",
                )

```


---

## 5. BÁO CÁO THỰC THI TRÊN DỮ LIỆU THẬT BINANCE

# BÁO CÁO KIỂM THỬ THỰC TẾ GIAI ĐOẠN 2: FEATURE ENGINE

- **Thời gian chạy kiểm thử:** 2026-09-18 11:57:30 UTC
- **Cặp giao dịch:** `BTC/USDT`
- **Khoảng thời gian:** 2026-07-10 → 2026-09-18 (~70 ngày)


### Khung thời gian: 4h
- **Tổng số nến:** 420 nến
- **Warm-up period EMA 200:** 199 nến đầu mang giá trị `NaN` (hoàn toàn đúng chuẩn toán học, cần 200 nến để tích lũy).
- **Warm-up RSI 14:** 1 nến mang giá trị `NaN`.
- **Warm-up ATR 14:** 13 nến mang giá trị `NaN`.
- **Số dòng có đầy đủ toàn bộ chỉ báo kỹ thuật (sau warm-up EMA 200):** 221 / 420 nến (52.6%).
- **Tỷ lệ NaN ở `oi_delta_pct`:** 20 / 420 nến (4.76%) (trong đó 20 nến đầu là do lookback shift N=20).
- **Thống kê tín hiệu `cvd_divergence`:**
  - `NONE`: 380 nến (90.5%)
  - `BULLISH`: 18 nến (4.3%)
  - `BEARISH`: 22 nến (5.2%)


#### 8 dòng mẫu gần nhất (đầy đủ feature):
| timestamp | close | volume | ema_20 | ema_50 | ema_200 | rsi_14 | atr_14 | open_interest | oi_delta_pct | cvd | cvd_divergence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-09-17 04:00 | 76433.1000 | 11864.9070 | 76585.9574 | 77201.4997 | 75385.9153 | 45.9129 | 890.5356 | 108245.0260 | 3.2025 | 24665.6110 | NONE |
| 2026-09-17 08:00 | 76449.7000 | 15787.0850 | 76572.9805 | 77172.0174 | 75396.5003 | 46.1352 | 870.4973 | 108358.7760 | 3.3600 | 24666.4680 | NONE |
| 2026-09-17 12:00 | 76751.8000 | 48665.3580 | 76590.0109 | 77155.5382 | 75409.9858 | 50.1510 | 892.2332 | 108505.1450 | 2.1887 | 25176.9420 | NONE |
| 2026-09-17 16:00 | 76561.1000 | 14381.6080 | 76587.2575 | 77132.2269 | 75421.4397 | 47.7319 | 865.6666 | 108490.3990 | 1.8022 | 24966.8140 | NONE |
| 2026-09-17 20:00 | 76385.9000 | 8010.4290 | 76568.0806 | 77102.9592 | 75431.0363 | 45.5576 | 839.6189 | 108199.4210 | 2.1872 | 24714.9390 | NONE |
| 2026-09-18 00:00 | 77349.0000 | 24333.1150 | 76642.4539 | 77112.6079 | 75450.1205 | 57.1206 | 873.6747 | 108245.1780 | 2.2926 | 26477.2940 | NONE |
| 2026-09-18 04:00 | 77776.1000 | 23928.0870 | 76750.4202 | 77138.6272 | 75473.2646 | 61.0694 | 856.2694 | 108297.3630 | 3.4713 | 25868.8150 | NONE |
| 2026-09-18 08:00 | 78047.3000 | 29932.8740 | 76873.9325 | 77174.2614 | 75498.8769 | 63.3758 | 853.3502 | 108445.7380 | 4.7648 | 25796.5010 | NONE |


### Khung thời gian: 15m
- **Tổng số nến:** 6720 nến
- **Warm-up period EMA 200:** 199 nến đầu mang giá trị `NaN` (hoàn toàn đúng chuẩn toán học, cần 200 nến để tích lũy).
- **Warm-up RSI 14:** 1 nến mang giá trị `NaN`.
- **Warm-up ATR 14:** 13 nến mang giá trị `NaN`.
- **Số dòng có đầy đủ toàn bộ chỉ báo kỹ thuật (sau warm-up EMA 200):** 6521 / 6720 nến (97.0%).
- **Tỷ lệ NaN ở `oi_delta_pct`:** 20 / 6720 nến (0.30%) (trong đó 20 nến đầu là do lookback shift N=20).
- **Thống kê tín hiệu `cvd_divergence`:**
  - `NONE`: 5908 nến (87.9%)
  - `BULLISH`: 355 nến (5.3%)
  - `BEARISH`: 457 nến (6.8%)


#### 8 dòng mẫu gần nhất (đầy đủ feature):
| timestamp | close | volume | ema_20 | ema_50 | ema_200 | rsi_14 | atr_14 | open_interest | oi_delta_pct | cvd | cvd_divergence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-09-18 10:00 | 78158.6000 | 1441.0990 | 77828.7538 | 77390.2785 | 76767.3295 | 68.6225 | 193.9936 | 107551.5450 | -0.6152 | 26192.2930 | NONE |
| 2026-09-18 10:15 | 78245.1000 | 913.4020 | 77868.4058 | 77423.8009 | 76782.0337 | 70.6868 | 189.0798 | 107318.9780 | -1.1555 | 26242.1430 | NONE |
| 2026-09-18 10:30 | 78194.2000 | 674.5380 | 77899.4338 | 77454.0126 | 76796.0851 | 67.8578 | 184.7312 | 107320.1590 | -1.1609 | 26127.5910 | NONE |
| 2026-09-18 10:45 | 78246.8000 | 886.1400 | 77932.5163 | 77485.1023 | 76810.5201 | 69.2284 | 182.9647 | 107399.7740 | -1.2722 | 26283.8670 | NONE |
| 2026-09-18 11:00 | 78076.4000 | 2569.2250 | 77946.2195 | 77508.2905 | 76823.1159 | 60.2635 | 198.4315 | 107481.0270 | -1.1557 | 26058.7560 | NONE |
| 2026-09-18 11:15 | 78008.8000 | 1285.2310 | 77952.1796 | 77527.9183 | 76834.9137 | 57.1042 | 193.2293 | 107351.7870 | -1.3512 | 25860.6470 | NONE |
| 2026-09-18 11:30 | 77993.3000 | 1230.9050 | 77956.0958 | 77546.1686 | 76846.4400 | 56.3744 | 190.0557 | 107547.9900 | -1.0866 | 25794.5260 | NONE |
| 2026-09-18 11:45 | 78047.3000 | 703.6890 | 77964.7819 | 77565.8208 | 76858.3888 | 58.3704 | 181.9732 | 107722.4560 | -0.7847 | 25796.4170 | NONE |


---

## 6. TOÀN BỘ LOG KẾT QUẢ PYTEST (53/53 PASSED)

```text
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0 -- D:\\Ta\u0300i lie\u0323\u0302u\\Default Project\\crypto-paper-agent\\venv\\Scripts\\python.exe
cachedir: .pytest_cache
rootdir: D:\\Ta\u0300i lie\u0323\u0302u\\Default Project\\crypto-paper-agent
configfile: pytest.ini
testpaths: tests
plugins: cov-7.1.0
collecting ... collected 53 items

tests/test_cvd.py::TestCVD::test_cvd_calculation_known_values PASSED     [  1%]
tests/test_cvd.py::TestCVD::test_cvd_divergence_bullish_scenario PASSED  [  3%]
tests/test_cvd.py::TestCVD::test_cvd_divergence_bearish_scenario PASSED  [  5%]
tests/test_cvd.py::TestCVD::test_cvd_divergence_none_when_in_agreement PASSED [  7%]
tests/test_data_layer.py::TestCacheManager::test_get_cache_path_no_slash PASSED [  9%]
tests/test_data_layer.py::TestCacheManager::test_get_cache_path_structure PASSED [ 11%]
tests/test_data_layer.py::TestCacheManager::test_save_and_load_roundtrip PASSED [ 13%]
tests/test_data_layer.py::TestCacheManager::test_save_merge_no_duplicates PASSED [ 15%]
tests/test_data_layer.py::TestCacheManager::test_load_returns_none_if_missing PASSED [ 16%]
tests/test_data_layer.py::TestCacheManager::test_detect_gaps_no_gaps PASSED [ 18%]
tests/test_data_layer.py::TestCacheManager::test_detect_gaps_with_gap PASSED [ 20%]
tests/test_data_layer.py::TestCacheManager::test_timeframe_to_timedelta PASSED [ 22%]
tests/test_data_layer.py::TestCacheManager::test_timeframe_invalid_raises PASSED [ 24%]
tests/test_data_layer.py::TestCacheManager::test_ensure_utc_index PASSED [ 26%]
tests/test_data_layer.py::TestFetcherLogic::test_candles_to_dataframe_basic PASSED [ 28%]
tests/test_data_layer.py::TestFetcherLogic::test_candles_to_dataframe_no_duplicates PASSED [ 30%]
tests/test_data_layer.py::TestFetcherLogic::test_timeframe_to_ms PASSED  [ 32%]
tests/test_data_layer.py::TestFetcherLogic::test_map_to_oi_timeframe PASSED [ 33%]
tests/test_data_layer.py::TestFetcherLogic::test_merge_uses_backward_direction PASSED [ 35%]
tests/test_data_layer.py::TestFetcherLogic::test_funding_rate_no_backfill PASSED [ 37%]
tests/test_data_layer.py::TestFetcherLogic::test_funding_rate_ffill_limit PASSED [ 39%]
tests/test_data_layer.py::test_fetch_real_ohlcv_7days PASSED             [ 41%]
tests/test_data_layer.py::test_fetch_real_funding_rate PASSED            [ 43%]
tests/test_data_layer.py::test_no_lookahead_in_live_merge PASSED         [ 45%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_downsample_5m_to_4h_no_lookahead PASSED [ 47%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_downsample_5m_to_1m_forward_fill PASSED [ 49%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_oi_confluence_config_loaded PASSED [ 50%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_vision_live_download_single_day PASSED [ 52%]
tests/test_data_layer.py::TestBinanceVisionDownloader::test_hybrid_oi_fetch_recent_60d PASSED [ 54%]
tests/test_indicators.py::TestIndicators::test_ema_known_small_series PASSED [ 56%]
tests/test_indicators.py::TestIndicators::test_ema_fallback_matches_pandas_ta PASSED [ 58%]
tests/test_indicators.py::TestIndicators::test_rsi_constant_and_trending PASSED [ 60%]
tests/test_indicators.py::TestIndicators::test_rsi_fallback_matches_pandas_ta PASSED [ 62%]
tests/test_indicators.py::TestIndicators::test_macd_formula PASSED       [ 64%]
tests/test_indicators.py::TestIndicators::test_atr_positive_and_matches_tr PASSED [ 66%]
tests/test_indicators.py::TestIndicators::test_calculate_indicators_all_columns_present PASSED [ 67%]
tests/test_indicators.py::TestIndicators::test_warmup_period_ema200 PASSED [ 69%]
tests/test_indicators.py::TestIndicators::test_missing_required_columns_raises PASSED [ 71%]
tests/test_news_calendar.py::test_economic_event_blackout_window PASSED  [ 73%]
tests/test_news_calendar.py::test_news_filter_disabled_by_default PASSED [ 75%]
tests/test_news_calendar.py::test_news_filter_enabled_with_csv PASSED    [ 77%]
tests/test_no_lookahead.py::TestNoLookaheadBias::test_future_data_tampering_does_not_alter_past_features[False-80] PASSED [ 79%]
tests/test_no_lookahead.py::TestNoLookaheadBias::test_future_data_tampering_does_not_alter_past_features[False-150] PASSED [ 81%]
tests/test_no_lookahead.py::TestNoLookaheadBias::test_future_data_tampering_does_not_alter_past_features[False-220] PASSED [ 83%]
tests/test_no_lookahead.py::TestNoLookaheadBias::test_future_data_tampering_does_not_alter_past_features[True-80] PASSED [ 84%]
tests/test_no_lookahead.py::TestNoLookaheadBias::test_future_data_tampering_does_not_alter_past_features[True-150] PASSED [ 86%]
tests/test_no_lookahead.py::TestNoLookaheadBias::test_future_data_tampering_does_not_alter_past_features[True-220] PASSED [ 88%]
tests/test_oi_features.py::TestOIFeatures::test_oi_delta_pct_known_values PASSED [ 90%]
tests/test_oi_features.py::TestOIFeatures::test_oi_delta_pct_lookback_from_config PASSED [ 92%]
tests/test_oi_features.py::TestOIFeatures::test_nan_propagation_when_oi_has_nan PASSED [ 94%]
tests/test_oi_features.py::TestOIFeatures::test_missing_oi_column_does_not_raise PASSED [ 96%]
tests/test_oi_features.py::TestOIFeatures::test_all_nan_oi_column_does_not_raise PASSED [ 98%]
tests/test_oi_features.py::TestOIFeatures::test_original_columns_not_mutated PASSED [100%]

============================== warnings summary ===============================
venv\Lib\site-packages\pandas_ta\__init__.py:37
  D:\\Ta\u0300i lie\u0323\u0302u\\Default Project\\crypto-paper-agent\\venv\\Lib\\site-packages\\pandas_ta\\__init__.py:37: Pandas4Warning: The 'mode.copy_on_write' option is deprecated. Copy-on-Write can no longer be disabled (it is always enabled with pandas >= 3.0), and setting the option has no impact. This option will be removed in pandas 4.0.\n    from pandas_ta.core import AnalysisIndicators

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 53 passed, 1 warning in 11.65s ========================

```
