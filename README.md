# Crypto Futures Paper-Trading Research Engine

[![Paper Only](https://img.shields.io/badge/Mode-PAPER%20TRADING%20ONLY-green.svg)](#ranh-gi%E1%BB%9Bi-an-to%C3%A0n)
[![Tests Passing](https://img.shields.io/badge/Tests-450%20passed-brightgreen.svg)](#ch%E1%BA%A1y-tests)
[![Python 3.12](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](#c%C3%A0i-%C4%91%E1%BA%B7t)
[![Architecture Docs](https://img.shields.io/badge/Docs-docs%2FINDEX.md-blueviolet.svg)](docs/INDEX.md)

Hệ thống mã nguồn mở nghiên cứu định lượng, kiểm thử hồi quy (backtest) và mô phỏng giao dịch hợp đồng tương lai tiền điện tử (Crypto Futures Paper Trading) trên sàn Binance, tích hợp các nguyên tắc quản trị rủi ro cứng (hard risk invariants) và giao diện điều khiển thời gian thực.

> ⚠️ **RANH GIỚI AN TOÀN TUYỆT ĐỐI (SAFETY BOUNDARY):**  
> Dự án này phục vụ mục đích **nghiên cứu khoa học và mô phỏng giả lập 100% (Paper Trading Only)**.  
> - **KHÔNG** yêu cầu hoặc lưu trữ API key thật, secret key hay seed phrase.  
> - **KHÔNG** đặt lệnh thật lên bất kỳ sàn giao dịch nào (kể cả testnet).  
> - **KHÔNG** thực hiện ký ví hay chuyển tiền thật dưới mọi hình thức.

---

## 1. Hệ thống làm được gì? (What It Does)

1. **Thu thập dữ liệu thị trường thực tế:** Tự động kéo dữ liệu nến OHLCV, Open Interest (OI) và Funding Rate từ Binance public API và kho lưu trữ Binance Data Vision mà không cần tài khoản.
2. **Feature Engine tính toán đa chỉ báo:** Tính toán EMA (20/50/200), RSI, MACD, ATR, Cumulative Volume Delta (CVD) phân kỳ nhân quả chống nhìn trước, biến thiên OI và cấu trúc Smart Money Concepts (FVG, Order Block).
3. **Quản trị rủi ro cứng (Risk Gate):** Tự động tính khối lượng vị thế (Position Sizing) theo tỷ lệ rủi ro cố định, kiểm soát ký quỹ cô lập (Isolated Margin), đệm thanh lý an toàn và tự động kích hoạt Circuit Breaker (ngắt giao dịch 24h khi lỗ ngày >5%, giảm 50% rủi ro khi thua chuỗi 3 lệnh).
4. **Mô phỏng khớp lệnh thực tế (Paper Broker):** Khớp lệnh theo quy trình 5 pha độc lập, trượt giá (slippage), phí sàn (Maker 0.02%, Taker 0.05%), thanh toán funding rate định kỳ 8 giờ và bảo vệ đa tầng (Liquidation > Stop Loss > Take Profit).
5. **Đa dạng chiến lược định lượng:**
   - *Trend Following:* Bám theo xu hướng đa khung thời gian (tín hiệu 4h, khớp 15m).
   - *Breakout & Retest:* Giao dịch bứt phá cản và kiểm định lại hỗ trợ/kháng cự.
   - *SMC Liquidity Sweep:* Săn thanh khoản với lệnh Limit tại FVG và chốt lời 3 phần 40/30/30.
   - *Funding Arbitrage:* Khai thác chênh lệch lãi suất funding giữa Spot và Perpetual.
   - *Reinforcement Learning (PPO):* Môi trường huấn luyện tác tử AI dựa trên Gymnasium.
6. **Ứng dụng Web Console thời gian thực:** Giao diện tối chuyên nghiệp mô phỏng sàn Binance Futures, tự động cập nhật nến thời gian thực qua Binance public REST polling cho cặp BTC, ETH, SOL.

---

## 2. Kiến trúc Tổng quát (Architecture Overview)

```
Binance Public Data (Public REST / Vision Archives)
       ↓
1. Data Layer (Fetcher / Parquet Cache / Vision Downloader)
       ↓
2. Feature Engine (EMA / RSI / ATR / CVD Causal / OI / SMC)
       ↓
3. Strategy Layer (Trend / Breakout / SMC / Funding Arbitrage)
       ↓  [OrderRequest PENDING]
4. Risk Gate (Position Sizing / Circuit Breaker / Liquidation Buffer / News)
       ↓  [Admitted & Sized]
5. Paper Execution (5-Phase Isolated Margin Broker / Funding / Exits)
       ↓
6. State & Persistence (Ledger / SQLite / JSON Recovery)
       ↓
  ┌────┴──────────────────────────┐
  ▼                               ▼
7A. Backtest Reporting           7B. Realtime Web Console
(JSON / CSV / SQLite / PNG)      (HTTP Loopback + React Dark UI)
```
*Chi tiết kiến trúc:* Xem tài liệu [docs/architecture/SYSTEM_ARCHITECTURE.md](docs/architecture/SYSTEM_ARCHITECTURE.md).

---

## 3. Cấu trúc Thư mục Chuẩn (Repository Layout)

```
AGENT-AI-T-NG-H-A-VI-C-TRADING/
├── AGENTS.md                  # Sổ tay vận hành cho AI Agent
├── README.md                  # Tài liệu nhập môn này
├── start-paper-web.cmd        # Script khởi động nhanh Web Console trên Windows
├── .gitignore                 # Quy tắc loại trừ rác runtime & cache
│
├── docs/                      # Trung tâm tài liệu chuẩn của toàn dự án
│   ├── INDEX.md               # Bản đồ dẫn đường toàn bộ tài liệu
│   ├── PROJECT_STATE.md       # Báo cáo trạng thái sống hiện hành
│   ├── architecture/          # Kiến trúc hệ thống chuẩn
│   ├── specs/                 # Bản đặc tả kỹ thuật (Master Spec)
│   ├── adr/                   # 12 Architecture Decision Records (0001–0012)
│   ├── operations/            # Hướng dẫn vận hành CLI & Web UI
│   ├── planning/              # Điều lệ sản phẩm & ma trận điều phối
│   ├── superpowers/plans/     # Kế hoạch chi tiết từng giai đoạn
│   ├── handover/              # Hồ sơ bàn giao tiếp nối
│   └── history/               # Bằng chứng, walkthroughs và báo cáo cũ
│
└── crypto-paper-agent/        # Thư mục chứa toàn bộ mã nguồn ứng dụng
    ├── config/                # Cấu hình hệ thống & chiến lược (YAML)
    ├── data/                  # Dữ liệu tĩnh (lịch tin tức CSV)
    ├── scripts/               # Các script thực thi CLI, huấn luyện PPO
    ├── src/                   # Mã nguồn Python phân tầng
    ├── tests/                 # 450+ unit/integration test cases (Pytest)
    ├── web-preview/           # Ứng dụng web React + Vite (Binance Dark UI)
    └── pytest.ini             # Cấu hình chạy test Pytest
```

---

## 4. Cài đặt & Chuẩn bị Môi trường (Setup)

### Yêu cầu tiên quyết:
- **Hệ điều hành:** Windows 10/11, Linux hoặc macOS.
- **Python:** Phiên bản 3.11 hoặc 3.12 (khuyến nghị 3.12).
- **Node.js:** Phiên bản 18+ (phục vụ Web Preview).

### Khởi tạo môi trường ảo Python:
Thư mục `.venv-paper` tại `crypto-paper-agent/.venv-paper` là môi trường cục bộ (được cấu hình trong `.gitignore` và **KHÔNG** commit sẵn vào Git).

Môi trường này được tạo tự động khi chạy `start-paper-web.cmd` (nếu máy đã cài `uv`), hoặc người dùng có thể tự tạo thủ công:
```powershell
cd crypto-paper-agent
python -m venv .venv-paper
.\.venv-paper\Scripts\activate
pip install -r requirements.txt
```

---

## 5. Chạy Ứng dụng Web Console (Run Web UI)

Cách nhanh nhất trên Windows: click đúp file **`start-paper-web.cmd`** tại thư mục gốc, hoặc chạy từ terminal:

```powershell
.\start-paper-web.cmd
```

Script sẽ tự động:
1. Khởi động server backend HTTP (`ThreadingHTTPServer`) tại cổng `8765`.
2. Build frontend React nếu cần và phục vụ trang web tại `http://localhost:8765`.
3. Tự động mở trình duyệt hiển thị biểu đồ Candlestick, số dư tài khoản và danh sách lệnh giả lập.

---

## 6. Chạy Kiểm thử (Run Tests)

Dự án sở hữu bộ test suite tự động bảo vệ toàn bộ các bất biến tài chính:

```powershell
# Chạy toàn bộ 450+ tests Python
cd crypto-paper-agent
.\.venv-paper\Scripts\python.exe -m pytest -q -m "not network"

# Chạy kiểm thử giao diện Web
cd web-preview
npm test
```

---

## 7. Cấu hình Hệ thống ở đâu? (Configuration)

Toàn bộ tham số được quản lý tập trung bằng YAML tại `crypto-paper-agent/config/`:
- **`config/default_config.yaml`:** Tham số chung (vốn khởi tạo, đòn bẩy tối đa 5×, phí taker/maker, cấu hình Circuit Breaker).
- **`config/strategies/trend_following.yaml`:** Tham số chiến lược xu hướng.
- **`config/strategies/breakout_retest.yaml`:** Tham số chiến lược phá vỡ cản.
- **`config/strategies/smc_liquidity_sweep.yaml`:** Tham số chiến lược săn thanh khoản SMC.
- **`config/strategies/funding_arbitrage.yaml`:** Tham số chiến lược kinh doanh lãi suất funding.

---

## 8. Tài liệu đọc tiếp ở đâu? (Further Reading)

- **Dành cho AI Agent:** Đọc ngay [AGENTS.md](AGENTS.md) để tra cứu bảng phân công tác vụ (Task Routing Map).
- **Bản đồ tài liệu tổng quan:** Đọc [docs/INDEX.md](docs/INDEX.md).
- **Trạng thái dự án hiện hành:** Đọc [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md).
- **Kiến trúc hệ thống chi tiết:** Đọc [docs/architecture/SYSTEM_ARCHITECTURE.md](docs/architecture/SYSTEM_ARCHITECTURE.md).
- **Các quyết định kỹ thuật đã chốt:** Xem danh sách 12 ADR tại [docs/adr/](docs/adr/).
