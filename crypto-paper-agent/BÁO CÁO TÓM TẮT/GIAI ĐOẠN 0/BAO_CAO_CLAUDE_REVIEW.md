# BÁO CÁO TỔNG HỢP GIAI ĐOẠN 0 (DÀNH CHO CLAUDE REVIEW)
**Dự án:** Crypto Futures Paper-Trading Research Agent  
**Thời điểm:** 2026-09-18  
**Trạng thái Giai đoạn 0:** HOÀN THÀNH 100%  
**Mục đích tài liệu:** Cung cấp đầy đủ thông tin kỹ thuật, mã nguồn, cấu hình, và kết quả kiểm thử để Claude review trước khi chuyển sang Giai đoạn 1 (Data Layer).

---

## 1. TÓM TẮT 4 QUYẾT ĐỊNH CỐT LÕI (MỤC 10 SPEC) ĐÃ THỰC THI

1. **Mục 10.1 - News Filter:**
   - Đã cài đặt module `src/features/news_calendar.py` đọc lịch kinh tế từ file CSV với blackout window +-15 phút.
   - Trong `default_config.yaml`, cờ `news_filter.enabled: false` đúng theo yêu cầu (chưa kích hoạt chặn lệnh ở giai đoạn đầu, nhưng slot code và file mẫu `data/news_calendar.csv` đã sẵn sàng).
2. **Mục 10.2 - Khoảng thời gian backtest:**
   - Đã cấu hình `start_date: "2021-01-01"` và `end_date: "2026-09-01"` (~5.5 năm).
   - Bao phủ trọn vẹn: Bull run 2021, Bear market 2022 (LUNA/FTX), Giai đoạn phục hồi 2023-2024, và dữ liệu gần nhất 2025-2026.
3. **Mục 10.3 - Cơ chế phục hồi Risk sau Circuit Breaker:**
   - Đã cấu hình `recovery_mode: "after_3_wins"` và `consecutive_wins_to_recover: 3` (yêu cầu 3 lệnh thắng liên tiếp mới phục hồi risk về mức chuẩn, không phục hồi nóng sau 1 lệnh).
4. **Mục 10.4 - Reinforcement Learning (RL):**
   - Chưa tích hợp thư viện RL (không có stable-baselines3, gym) trong requirements.txt để giữ codebase tinh gọn, tập trung hoàn thiện rule-based engine ở Giai đoạn 0-10.

---

## 2. CẤU TRÚC THƯ MỤC THỰC TẾ (SO VỚI MỤC 3 SPEC)

```
crypto-paper-agent/
├── README.md
├── config/
│   ├── default_config.yaml
│   └── strategies/
│       ├── breakout_retest.yaml
│       ├── funding_arbitrage.yaml
│       ├── smc_liquidity_sweep.yaml
│       └── trend_following.yaml
├── data/
│   ├── news_calendar.csv
│   ├── processed/
│   └── raw/
├── notebooks/
├── pytest.ini
├── requirements.txt
├── run_backtest.py
├── src/
│   ├── __init__.py
│   ├── backtest/
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── data_layer/
│   │   ├── __init__.py
│   │   ├── cache_manager.py
│   │   └── fetcher.py
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_models.py
│   │   └── paper_broker.py
│   ├── features/
│   │   ├── __init__.py
│   │   ├── cvd.py
│   │   ├── indicators.py
│   │   ├── news_calendar.py
│   │   ├── oi_features.py
│   │   └── smc_features.py
│   ├── logging/
│   │   ├── __init__.py
│   │   └── trade_logger.py
│   ├── report/
│   │   ├── __init__.py
│   │   └── metrics.py
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── circuit_breakers.py
│   │   ├── invariant_checks.py
│   │   └── position_sizing.py
│   └── strategies/
│       ├── __init__.py
│       ├── base_strategy.py
│       ├── breakout_retest.py
│       ├── funding_arbitrage.py
│       ├── smc_liquidity_sweep.py
│       └── trend_following.py
└── tests/
    ├── conftest.py
    ├── test_circuit_breakers.py
    ├── test_liquidation_calc.py
    ├── test_news_calendar.py
    ├── test_no_lookahead.py
    └── test_position_sizing.py
```

### Đối chiếu với Spec Mục 3:
- Đầy đủ thư mục: `config/`, `config/strategies/`, `data/raw/`, `data/processed/`, `src/data_layer/`, `src/features/`, `src/strategies/`, `src/risk/`, `src/execution/`, `src/logging/`, `src/backtest/`, `src/report/`, `tests/`, `notebooks/`.
- Đầy đủ các file cấu hình chiến lược: `trend_following.yaml`, `breakout_retest.yaml`, `smc_liquidity_sweep.yaml`, `funding_arbitrage.yaml`.
- Đầy đủ 16 modules mã nguồn stubs có docstring hướng dẫn và chống lookahead bias.

---

## 3. NỘI DUNG NGUYÊN VĂN `default_config.yaml`

```yaml
# ============================================================
# default_config.yaml - Crypto Paper-Trading Research Agent
# Toàn bộ tham số hệ thống. KHÔNG lưu API key hoặc thông tin nhạy cảm ở đây.
# Mọi giá trị có thể override qua CLI hoặc config riêng cho từng chiến lược.
# ============================================================

account:
  initial_equity_usd: 10000
  base_currency: USDT

risk:
  conviction_tiers:
    low:        0.01   # 1% equity per trade
    normal:     0.02   # 2%
    high:       0.05   # 5%
    ultra_high: 0.10   # 10%
  max_leverage: 5
  # Khoảng cách tối thiểu giữa giá thanh lý và stop-loss (tính theo % entry price)
  # Hard invariant: |liq_price - stop_price| / entry_price >= 0.30
  min_liquidation_buffer_pct: 0.30

circuit_breakers:
  # Nếu lỗ ròng trong rolling 24h vượt mức này → đóng toàn bộ, khóa trading 24h
  daily_loss_limit_pct: 0.05
  # Chuỗi lệnh thua liên tiếp → giảm risk_percent xuống 50%
  consecutive_losses_threshold: 3
  risk_reduction_on_streak: 0.5    # hệ số nhân (0.5 = giảm 50%)
  # Điều kiện phục hồi risk về mức chuẩn: sau 3 lệnh thắng liên tiếp
  # Đã chốt với người dùng: after_3_wins
  recovery_mode: "after_3_wins"
  consecutive_wins_to_recover: 3

fees:
  taker_pct: 0.0005   # 0.05% (mặc định Binance Futures)
  maker_pct: 0.0002   # 0.02%
  slippage_pct: 0.0003  # 0.03% slippage mô phỏng

data:
  symbol: "BTC/USDT"
  timeframes:
    - "4h"
    - "15m"
    - "1m"
  exchange: "binance"
  # Khoảng backtest: 2021-01-01 → 2026-09-01 (~5.5 năm)
  # Bao phủ: bull run 2021, bear 2022 (LUNA/FTX), hồi phục 2023-2024, 2025-2026
  start_date: "2021-01-01"
  end_date:   "2026-09-01"
  # Thư mục cache local (Parquet)
  raw_data_dir: "data/raw"
  processed_data_dir: "data/processed"
  # Binance Futures sử dụng symbol format khác cho futures: BTCUSDT (không có /)
  futures_symbol: "BTCUSDT"

# Open Interest fetch config
open_interest:
  # Binance Futures public endpoint, không cần API key
  # ccxt sẽ gọi GET /fapi/v1/openInterestHist
  lookback_periods: 500   # số nến OI tối thiểu cần cho indicators

# Funding rate config
funding_rate:
  # Funding settlement: 00:00, 08:00, 16:00 UTC (Binance standard)
  settlement_hours_utc: [0, 8, 16]
  # Forward-fill tối đa N nến để không leak dữ liệu tương lai
  max_forward_fill_candles: 480   # tối đa 480 nến 1m = 8h (1 chu kỳ funding)

# Feature Engine
features:
  ema_periods: [20, 50, 200]
  rsi_period: 14
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  atr_period: 14
  # OI delta: % thay đổi OI so với N nến trước
  oi_delta_lookback: 20
  # CVD divergence: so sánh đỉnh/đáy giá với đỉnh/đáy CVD trong N nến
  cvd_divergence_lookback: 50

# SMC (Smart Money Concepts) - dùng cho Giai đoạn 9
smc:
  # Swing High/Low: nến có high > N nến trước + N nến sau
  swing_n: 3
  # Minimum BOS/CHoCH breakout để tính hợp lệ (% so với entry)
  min_bos_pct: 0.001   # 0.1%

# News Filter (placeholder - disabled cho giai đoạn 0-4)
# Khi enabled: true, sẽ đọc file CSV chứa các mốc CPI/FOMC/NFP
# Blackout: không mở lệnh trong ±15 phút quanh sự kiện
news_filter:
  enabled: false
  blackout_minutes_before: 15
  blackout_minutes_after: 15
  calendar_source: "manual_csv"
  calendar_file: "data/news_calendar.csv"   # người dùng tự chuẩn bị

# Logging
logging:
  trade_log_db: "data/trades.db"
  trade_log_json_dir: "data/trade_logs"
  log_level: "INFO"

# Backtest Engine
backtest:
  # Random seed để đảm bảo reproducibility
  random_seed: 42
  # Chuẩn thực thi: quyết định dựa trên nến đã đóng, thực thi ở nến kế tiếp
  # (tránh lookahead bias - không dùng giá close của nến hiện tại để vào lệnh)
  signal_on_close: true    # tín hiệu khi nến đóng
  execute_on_next_open: true   # thực thi ở open nến sau (hoặc dùng open làm entry)

# Binance Futures leverage brackets (dùng để tính MMR chính xác)
# Nguồn: https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin
# Format: [max_notional_usd, mmr_pct, cumulative_maintenance_amount]
leverage_brackets:
  BTCUSDT:
    - [50000,      0.004, 0]
    - [250000,     0.005, 50]
    - [1000000,    0.01,  1300]
    - [10000000,   0.025, 16300]
    - [20000000,   0.05,  266300]
    - [50000000,   0.10,  1266300]
    - [100000000,  0.125, 2516300]
    - [200000000,  0.15,  5016300]
    - [300000000,  0.25,  25016300]
    - [500000000,  0.50,  100016300]

```

---

## 4. NỘI DUNG NGUYÊN VĂN `requirements.txt`

```
# ============================================================
# Crypto Paper-Trading Research Agent - Requirements
# Python 3.11+ required
# KHÔNG chứa bất kỳ thư viện nào kết nối API key thật/đặt lệnh thật
# ============================================================

# --- Data Fetching (public endpoints, no API key needed for OHLCV/OI/funding) ---
ccxt==4.4.27

# --- Data Processing ---
pandas==2.2.3
numpy==1.26.4

# --- Technical Indicators ---
pandas-ta==0.3.14b0

# --- Data Storage ---
pyarrow==17.0.0          # Parquet read/write

# --- Configuration ---
pyyaml==6.0.2

# --- Testing ---
pytest==8.3.3
pytest-cov==5.0.0        # coverage reports

# --- Visualization (optional, for equity curve) ---
matplotlib==3.9.2
plotly==5.24.1

# --- Dashboard (optional, Giai đoạn 6+) ---
streamlit==1.39.0

# --- Jupyter (for exploratory_analysis.ipynb) ---
jupyterlab==4.2.5
ipykernel==6.29.5

# --- Utilities ---
python-dateutil==2.9.0
tqdm==4.66.5             # progress bar for long fetches
loguru==0.7.2            # structured logging

# --- Type hints / code quality ---
mypy==1.11.2

```

---

## 5. NỘI DUNG NGUYÊN VĂN `news_calendar.py` & CSV MẪU

### `src/features/news_calendar.py`
```python
"""
news_calendar.py - News Filter & Economic Calendar (Placeholder)
================================================================
Quản lý lịch kinh tế (CPI, FOMC, NFP) từ file CSV và kiểm tra
khoảng thời gian cấm mở lệnh (news blackout window: ±15 phút quanh sự kiện).

Theo quyết định mục 10.1:
- Mặc định: enabled = False (tạm thời không chặn lệnh).
- Slot đã sẵn sàng: khi người dùng chuẩn bị file CSV và bật enabled = True,
  module này sẽ tự động parse và kích hoạt chặn lệnh ở Risk Invariants.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple
import pandas as pd


class EconomicEvent:
    """Đại diện cho 1 sự kiện kinh tế quan trọng."""
    def __init__(self, timestamp: datetime, event_name: str, impact: str = "HIGH"):
        if timestamp.tzinfo is None:
            self.timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            self.timestamp = timestamp.astimezone(timezone.utc)
        self.event_name = event_name
        self.impact = impact

    def in_blackout_window(
        self,
        current_time: datetime,
        minutes_before: int = 15,
        minutes_after: int = 15
    ) -> bool:
        """Kiểm tra current_time có nằm trong [event - before, event + after] không."""
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        else:
            current_time = current_time.astimezone(timezone.utc)

        start_window = self.timestamp - timedelta(minutes=minutes_before)
        end_window = self.timestamp + timedelta(minutes=minutes_after)
        return start_window <= current_time <= end_window


class NewsCalendarFilter:
    """
    Bộ lọc sự kiện vĩ mô theo lịch CSV.
    Nếu config news_filter.enabled == False -> luôn cho phép (no-op).
    """
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.news_cfg = self.config.get("news_filter", {})
        self.enabled: bool = bool(self.news_cfg.get("enabled", False))
        self.blackout_before: int = int(self.news_cfg.get("blackout_minutes_before", 15))
        self.blackout_after: int = int(self.news_cfg.get("blackout_minutes_after", 15))
        self.calendar_file: str = self.news_cfg.get("calendar_file", "data/news_calendar.csv")
        self.events: List[EconomicEvent] = []

        if self.enabled:
            self.load_calendar(self.calendar_file)

    def load_calendar(self, file_path: str) -> None:
        """Đọc danh sách sự kiện từ file CSV."""
        path = Path(file_path)
        if not path.exists():
            self.events = []
            return

        try:
            df = pd.read_csv(path)
            time_col = "datetime_utc" if "datetime_utc" in df.columns else "timestamp"
            name_col = "event" if "event" in df.columns else "event_name"
            impact_col = "impact" if "impact" in df.columns else None

            loaded = []
            for _, row in df.iterrows():
                dt = pd.to_datetime(row[time_col])
                if pd.isna(dt):
                    continue
                name = str(row[name_col])
                impact = str(row[impact_col]) if impact_col else "HIGH"
                loaded.append(EconomicEvent(timestamp=dt, event_name=name, impact=impact))
            self.events = loaded
        except Exception:
            self.events = []

    def is_in_blackout(self, check_time: datetime) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra thời điểm hiện tại có bị cấm giao dịch vì tin tức không.
        Returns:
            (True, event_name) nếu đang trong khung cấm tin.
            (False, None) nếu bình thường (hoặc nếu enabled=False).
        """
        if not self.enabled:
            return False, None

        for event in self.events:
            if event.in_blackout_window(check_time, self.blackout_before, self.blackout_after):
                return True, event.event_name

        return False, None

```

### `data/news_calendar.csv` (File CSV mẫu đi kèm)
```csv
datetime_utc,event,currency,impact
2024-01-11 13:30:00,US CPI YoY,USD,HIGH
2024-01-31 19:00:00,FOMC Rate Decision,USD,HIGH
2024-02-02 13:30:00,US Non-Farm Payrolls (NFP),USD,HIGH
2024-02-13 13:30:00,US CPI YoY,USD,HIGH
2024-03-20 18:00:00,FOMC Rate Decision,USD,HIGH

```

---

## 6. KẾT QUẢ KIỂM THỬ THỰC TẾ (PYTEST)

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
cachedir: .pytest_cache
plugins: cov-7.1.0
collecting ... collected 7 items

tests/test_no_lookahead.py::test_synthetic_data_creation PASSED       [ 14%]
tests/test_news_calendar.py::test_economic_event_blackout_window PASSED [ 28%]
tests/test_news_calendar.py::test_news_filter_disabled_by_default PASSED [ 42%]
tests/test_news_calendar.py::test_news_filter_enabled_with_csv PASSED [ 57%]
tests/test_position_sizing.py::test_placeholder SKIPPED                 [ 71%]
tests/test_circuit_breakers.py::test_placeholder SKIPPED                [ 85%]
tests/test_liquidation_calc.py::test_placeholder SKIPPED                [100%]

======================== 4 passed, 3 skipped in 0.31s =========================
```

- **Pass 4 tests:**
  - `test_synthetic_data_creation`: Kiểm tra thuật toán sinh dữ liệu giả lập không lookahead bias hoạt động chính xác.
  - `test_economic_event_blackout_window`: Kiểm tra logic cấm giao dịch trong khoảng +-15 phút quanh sự kiện kinh tế.
  - `test_news_filter_disabled_by_default`: Xác nhận cờ mặc định `enabled: false` không chặn bất kỳ lệnh nào.
  - `test_news_filter_enabled_with_csv`: Xác nhận khi người dùng bật `enabled: true`, hệ thống chặn đúng các mốc CPI/FOMC/NFP.
- **Skip 3 tests:** Các test placeholder cho `position_sizing`, `circuit_breakers`, `liquidation_calc` sẽ được kích hoạt tại Giai đoạn 3 (Risk Manager).
