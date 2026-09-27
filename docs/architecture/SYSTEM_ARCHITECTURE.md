# SYSTEM ARCHITECTURE — Crypto Futures Paper-Trading Research Engine

Tài liệu này là **Source of Truth** chính thức mô tả kiến trúc phần mềm, luồng dữ liệu, các tầng xử lý và ranh giới an toàn của hệ thống.

---

## 1. Tổng quan Kiến trúc (High-Level Architecture)

Hệ thống được thiết kế theo nguyên tắc:
1. **Paper-Only & Research Boundary:** Toàn bộ quá trình thực thi chỉ diễn ra trong bộ nhớ mô phỏng hoặc cơ sở dữ liệu nội bộ. Tuyệt đối không có module nào kết nối API key đặt lệnh hoặc ký giao dịch ví thật.
2. **Causal & Zero-Lookahead:** Tại bất kỳ thời điểm mô phỏng $t$, dữ liệu và chỉ báo chỉ được phép lấy từ các nến đã đóng có $\text{timestamp} \le t$. Quyết định giao dịch sinh ra ở giá đóng nến $t$, thực thi tại giá mở nến $t+1$.
3. **Risk-First Gate:** Mọi yêu cầu vào lệnh (`OrderRequest`) đều phải đi qua cổng kiểm duyệt rủi ro nghiêm ngặt (Position Sizing, Circuit Breaker, Liquidation Buffer, Margin Check, News Filter) trước khi được khớp lệnh vào tài khoản.

```
                    ┌─────────────────────────┐
                    │   Binance Public Data   │
                    │  (Public REST API /     │
                    │    Vision Archives)     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    1. Data Layer        │
                    │  (Fetcher/CacheManager/ │
                    │   VisionDownloader)     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    2. Feature Engine    │
                    │  (Indicators / CVD /    │
                    │    OI / SMC Causal)     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    3. Strategy Layer    │
                    │  (Trend / Breakout /    │
                    │     SMC / Arbitrage)    │
                    └────────────┬────────────┘
                                 │ OrderRequest (PENDING)
                                 ▼
                    ┌─────────────────────────┐
                    │    4. Risk Gate         │
                    │ (PositionSizing / News/ │
                    │  CircuitBreaker / Tier) │
                    └────────────┬────────────┘
                                 │ Admitted & Sized
                                 ▼
                    ┌─────────────────────────┐
                    │ 5. Paper Execution      │
                    │ (5-Phase Candle Engine/ │
                    │   Funding / SL-TP-Liq)  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ 6. State & Persistence  │
                    │ (Ledger / SQLite Event  │
                    │   Store / JSON Backup)  │
                    └────────────┬────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
     ┌───────────────────────┐       ┌───────────────────────┐
     │ 7A. Reporting Engine  │       │ 7B. Web UI Console    │
     │  (Metrics / SQLite /  │       │ (ThreadingHTTPServer/ │
     │    JSON/CSV/PNG)      │       │  React Binance Dark)  │
     └───────────────────────┘       └───────────────────────┘
```

---

## 2. Hai Luồng Thực Thi: Backtest vs. Realtime Paper Stream

Hệ thống hỗ trợ 2 chế độ vận hành độc lập nhưng chia sẻ chung 100% logic Risk Gate và Paper Broker:

| Đặc tính | A. Backtest / Research Replay | B. Realtime Paper Web Stream |
| :--- | :--- | :--- |
| **Nguồn dữ liệu** | File Parquet cache lịch sử (`data/raw/`) hoặc Vision archives. | Binance Futures public REST polling (`/fapi/v1/klines`, `/fapi/v1/fundingRate`) qua `requests.Session()`. |
| **Đồng hồ thời gian** | Đồng hồ mô phỏng đơn điệu duyệt qua từng nến đóng. | Đồng hồ thực tế UTC chạy theo event stream nến đóng 15m/4h. |
| **Thực thi lệnh** | Khớp tại `Open` nến tiếp theo kèm trượt giá (slippage). | Khớp tại giá nến tiếp theo khi nến hiện tại xác nhận đóng. |
| **Phân hệ điều phối**| `crypto-paper-agent/src/backtest/engine.py` | `crypto-paper-agent/src/paper/live_session.py` |
| **Giao diện hiển thị**| Xuất artifacts JSON, CSV, SQLite, PNG. | Giao diện React hiển thị biểu đồ Candlestick, Ledger và Account status. |

---

## 3. Bản đồ Module & Phân bổ Tệp tin Canonical

### 3.1 Data Layer (`crypto-paper-agent/src/data_layer/`)
- `fetcher.py`: Kéo nến OHLCV, Open Interest, Funding Rate từ Binance public REST endpoints.
- `cache_manager.py`: Quản lý lưu trữ/đọc cache dưới định dạng Apache Parquet; chuẩn hóa UTC timezone.
- `binance_vision_downloader.py`: Tự động tải và xác thực checksum các file lưu trữ lịch sử lớn từ Binance Data Vision (>28 ngày).

### 3.2 Feature Engine (`crypto-paper-agent/src/features/`)
- `indicators.py`: Tính toán EMA (20/50/200), RSI, MACD, ATR bằng `pandas-ta` kèm tầng fallback thuần `pandas` (Wilder RMA).
- `cvd.py`: Cumulative Volume Delta, Swing point detection và CVD divergence causal (chống lookahead tuyệt đối theo ADR 0003).
- `oi_features.py`: Biến thiên Open Interest (`oi_delta_pct`), tỷ lệ giá/OI, hỗ trợ cơ chế fallback khi thiếu dữ liệu (ADR 0005).
- `smc_features.py`: Nhận diện vùng mất cân bằng giá Fair Value Gap (FVG), Order Block và cấu trúc thị trường BOS/CHoCH.
- `news_calendar.py`: Bộ lọc lịch kinh tế vĩ mô (CPI, FOMC, NFP) chống biến động bất thường (mặc định disabled).

### 3.3 Strategy Layer (`crypto-paper-agent/src/strategies/`)
- `base_strategy.py`: Abstract Base Class định nghĩa giao diện chuẩn `generate_signals()`.
- `trend_following.py`: Chiến lược Trend Following đa khung thời gian (tín hiệu 4h, thực thi 15m, EMA crossover + RSI/OI confluence).
- `breakout_retest.py`: Chiến lược phá vỡ vùng kháng cự/hỗ trợ kèm kiểm định lại (Breakout & Retest).
- `smc_liquidity_sweep.py`: Chiến lược săn thanh khoản Smart Money Concepts với lệnh Limit tại FVG và chốt lời đa tầng 40/30/30 (ADR 0012).
- `funding_arbitrage.py`: Chiến lược kinh doanh chênh lệch lãi suất funding giữa Spot và Perpetual với rổ tài sản nguyên tử (ADR 0011).

### 3.4 Risk Gate (`crypto-paper-agent/src/risk/`)
- `position_sizing.py`: Tính toán kích thước vị thế theo tỷ lệ % rủi ro cố định trên vốn khả dụng (`available_margin`), kiểm tra leverage bracket.
- `circuit_breakers.py`: Cầu dao ngắt tự động (khóa giao dịch 24h nếu lỗ vượt 5%/ngày, giảm 50% risk sau chuỗi 3 lệnh thua, phục hồi sau 3 lệnh thắng liên tiếp).
- `invariant_checks.py`: Kiểm tra toàn diện các bất biến tài chính: chặn lùi thời gian, kiểm tra ký quỹ, đệm thanh lý an toàn tối thiểu.

### 3.5 Paper Execution Engine (`crypto-paper-agent/src/execution/`)
- `paper_broker.py`: Engine khớp lệnh mô phỏng Futures ký quỹ USDT độc lập (Isolated Margin), vận hành theo **Quy trình 5 pha bất biến**:
  1. *Pha 1 (Open Time & Gap Exits):* Kiểm tra gap nến, thoát lệnh Take Profit ưu tiên nếu có gap.
  2. *Pha 2 (Funding Settlement):* Thanh toán funding đúng thời điểm 00:00, 08:00, 16:00 UTC; kiểm tra funding provenance fail-closed.
  3. *Pha 3 (Pending Entry & Risk Gate):* Khớp lệnh thị trường đang chờ tại giá Open nến mới kèm slippage, trừ phí vào lệnh, tạo `Position`.
  4. *Pha 4 (Intrabar Protection):* Kiểm tra bảo vệ trong nến theo thứ tự nghiêm ngặt: $\text{Thanh lý (Liquidation)} \to \text{Cắt lỗ (Stop Loss)} \to \text{Chốt lời (Take Profit)}$.
  5. *Pha 5 (Close Time & Mark-to-Market):* Cập nhật giá đánh dấu, tính PnL tạm tính, đối soát kế toán tài khoản.
- `order_models.py`: Khai báo dataclass cho `OrderRequest`, `Position`, `OrderStatus`, `TradeSide`.

### 3.6 Trade Logger & Reporting (`crypto-paper-agent/src/logging/` & `src/report/`)
- `trade_logger.py`: Ghi nhận sự kiện giao dịch vào cơ sở dữ liệu SQLite chuẩn `trades.sqlite` và snapshot tài khoản.
- `metrics.py`: Tính toán hiệu suất định lượng: Win rate, Expectancy, Profit Factor, Max Drawdown, Sharpe Ratio, Calmar Ratio, SQN.
- `generator.py`: Điều phối xuất báo cáo hoàn chỉnh gồm `summary.json`, `summary.md`, `trades.json`, `equity_curve.csv`, `equity_curve.png`.

### 3.7 Web Preview & Realtime Stream (`crypto-paper-agent/src/paper/` & `web-preview/`)
- `local_server.py`: HTTP loopback server (`ThreadingHTTPServer` + `BaseHTTPRequestHandler`) cung cấp REST endpoints (`/api/state`, `/api/start`, `/api/stop`). Không dùng FastAPI, không có WebSocket server.
- `live_session.py`: Quản lý phiên giao dịch paper trading thời gian thực trên dữ liệu Binance công khai.
- `persistence.py`: Tự động lưu và khôi phục trạng thái vị thế/số dư vào file JSON khi restart server.
- `web-preview/`: Frontend React xây dựng bằng Vite, sử dụng giao diện tối chuẩn Binance Futures, tích hợp TradingView Lightweight Charts.

---

## 4. Ranh giới Phân hệ Nghiên cứu (Research Boundary)

Phân hệ nghiên cứu tại `crypto-paper-agent/src/research/` bao gồm:
- `rl_env.py`: Môi trường Gymnasium tùy biến phục vụ huấn luyện mô hình học tăng cường (PPO).
- `comparison.py`: Bộ so sánh đa chiến lược Walk-Forward với tài khoản vốn phân lập cho từng fold.
- `artifacts.py`: Kiểm toán checksum và tính toàn vẹn của dữ liệu mẫu.

> **Quy tắc cốt lõi (ADR 0010):** Kết quả từ môi trường nghiên cứu hoặc mô hình PPO là tài liệu tham khảo thực nghiệm, **không bao giờ tự động chuyển thành tín hiệu** cho phiên paper trading hay tài khoản live mà không qua quy trình nghiệm thu độc lập.
