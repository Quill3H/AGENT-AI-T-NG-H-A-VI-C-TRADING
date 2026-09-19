# ADR 0009: Kiến Trúc Lưu Trữ Sự Kiện Giao Dịch & Báo Cáo Hiệu Năng (Trade Logger & Performance Reporting)

**Trạng thái:** PENDING REVIEW (Chờ nghiệm thu theo GPT Review 11)  
**Ngày đề xuất:** 2026-09-19  
**Người đề xuất:** Quill3H & Antigravity (theo đặc tả kỹ thuật Giai đoạn 6 — Master Spec Section 4.6)

---

## 1. Bối cảnh
Sau khi hoàn thành và nghiệm thu Giai đoạn 5 (Chiến lược Trend Following và cỗ máy BacktestEngine đa khung thời gian), hệ thống cần một cơ chế chuẩn hoá, bền vững và phi tập trung để:
1. Lưu trữ có cấu trúc toàn bộ vòng đời của mỗi phiên chạy backtest/paper trading (metadata phiên, lệnh, giao dịch đóng, sự kiện funding, snapshot tài khoản theo từng nến, chỉ số hiệu năng tổng hợp).
2. Xuất dữ liệu giao dịch chuẩn hoá (JSON trade schema) theo Master Spec Section 4.6 để phục vụ đối soát, phân tích danh mục và kiểm định độc lập.
3. Thống nhất một nguồn chân lý tính toán số liệu hiệu năng (Single Source of Truth Performance Metrics) cho giao dịch phái sinh (Expectancy USD & R-multiple, Profit Factor xử lý nghiêm ngặt khi lỗ = 0, Peak-to-Valley Drawdown, Daily Sharpe Ratio resampled theo ngày lịch UTC với hệ số nhân $\sqrt{365}$).
4. Tự động sinh bộ 6 artifacts báo cáo đa định dạng (SQLite, JSON, CSV, PNG, Markdown) dưới thư mục riêng biệt `reports/<run_id>/` độc lập hoàn toàn với thư mục thực thi (CWD).
5. Đảm bảo nguyên lý Không làm biến dạng ngữ nghĩa thực thi (Zero Semantic Drift): tầng logger và report generator hoạt động hoàn toàn bên ngoài và sau quá trình mô phỏng, không can thiệp hay làm lệch dù chỉ một xu giá khớp, số dư hay quyết định của cỗ máy khớp lệnh.

---

## 2. Quyết định Kiến trúc & Thiết kế

### 2.1 Kho Lưu Trữ Sự Kiện SQLite (SQLite Event Store — `src/logging/trade_logger.py`)
- **Quản lý kết nối & Toàn vẹn tham chiếu:**
  - Bật bắt buộc ràng buộc khoá ngoại: thực thi `PRAGMA foreign_keys = ON;` ngay sau khi mở mỗi kết nối SQLite.
  - Thiết kế 6 bảng quan hệ có khoá ngoại ràng buộc về bảng gốc `runs`:
    1. `runs`: Lưu trữ metadata phiên chạy (`run_id` làm PRIMARY KEY, strategy, symbol, timeframe, thời gian, vốn ban đầu, equity kết thúc, config_json, created_at).
    2. `orders`: Lưu trữ toàn bộ các lệnh phát ra (`order_id`, `run_id`, hướng, loại lệnh, trạng thái, thời gian yêu cầu/xử lý, giá tham chiếu/khớp thực tế, slippage, số lượng, phí, metadata).
    3. `trades`: Lưu trữ toàn bộ các giao dịch đã đóng (`trade_id`, `run_id`, symbol, direction, quantity, entry/exit price, entry/exit time, leverage, initial margin, gross/net PnL, fees, funding cashflow, return %, exit reason, initial stop loss, initial risk USD, realized R-multiple, conviction tier).
    4. `funding_events`: Lưu trữ chi tiết các lần thanh toán funding (`event_id`, `run_id`, symbol, timestamp, funding_rate, mark_price, position_quantity, payment, direction).
    5. `account_snapshots`: Lưu trữ ảnh chụp tài khoản từng nến (`snapshot_id`, `run_id`, timestamp, wallet_balance, equity, unrealized_pnl, margin_used, available_balance, active_positions, realized_pnl, drawdown_pct).
    6. `run_metrics`: Lưu trữ toàn bộ dictionary metrics đầy đủ dưới dạng JSON (`run_id`, `metrics_json`, `created_at`).
- **Giao dịch Nguyên tử (Atomic Transaction):**
  - Toàn bộ quá trình ghi của một run được bao bọc trong một SQLite transaction duy nhất (`with conn:`).
  - Nếu xảy ra bất kỳ lỗi dữ liệu nào giữa chừng, toàn bộ transaction tự động rollback, cam kết không để lại dữ liệu rác hay trạng thái mồ côi (zero partial state).
- **Tính Luỹ thừa & Từ chối Xung đột (Idempotency & Fail-closed Conflict Rejection):**
  - Khi gọi `log_backtest_run` với một `run_id` đã tồn tại trong database:
    - So sánh payload mới với payload đã lưu (strategy, symbol, timeframe, initial_capital, final_equity, total_trades).
    - Nếu payload hoàn toàn trùng khớp: coi là thành công luỹ thừa (idempotent no-op), ghi log thông báo và trả về `True` (không nhân đôi số dòng).
    - Nếu payload xung đột (khác biệt về equity, số lượng trade,...): ném ngoại lệ `ValueError` lập tức (fail-closed), kiên quyết không ghi đè dữ liệu lịch sử.

### 2.2 Xuất JSON Trade Chuẩn Hoá (JSON Exporter)
- Xuất mảng các giao dịch đóng tuân thủ tuyệt đối đặc tả Master Spec Section 4.6:
  - Thời gian (`entry_time`, `exit_time`) quy đổi chuẩn xác sang Unix epoch seconds UTC (kiểu `int`).
  - Sử dụng `json.dumps(..., allow_nan=False)` đảm bảo không chứa `NaN`, `Infinity` hay `-Infinity` (chuẩn RFC 8259).
  - Các trường chưa được đo lường ở nến 15m (`market_context`, `mae_usd`, `mfe_usd`) được gán giá trị `null` minh bạch, không ngụy tạo dữ liệu giả lập.

### 2.3 Động Cơ Tính Toán Chỉ Số Hiệu Năng (Standard Performance Metrics — `src/report/metrics.py`)
- Định nghĩa các công thức tính toán tài chính chuẩn:
  1. **Expectancy (USD):** Kỳ vọng toán học PnL trên mỗi trade:
     $$\text{Expectancy}_{\text{USD}} = \frac{1}{N} \sum_{i=1}^N \text{net\_pnl}_i$$
     (trả về 0.0 nếu $N=0$).
  2. **Initial Risk (USD) & Realized R-multiple:**
     $$\text{Initial Risk}_{\text{USD}} = Q \times |\text{entry\_price} - \text{initial\_stop\_loss\_price}|$$
     $$\text{Realized } R = \frac{\text{net\_pnl}}{\text{Initial Risk}_{\text{USD}}}$$
  3. **Expectancy (R-multiple):**
     $$\text{Expectancy}_R = \frac{1}{M} \sum_{j=1}^M \text{Realized } R_j$$
     (với $M$ là số trade có $\text{Initial Risk} > 0$; trả về `None`/`null` nếu $M=0$).
  4. **Profit Factor:**
     $$\text{Profit Factor} = \frac{\sum_{\text{net\_pnl} > 0} \text{net\_pnl}}{\sum_{\text{net\_pnl} < 0} |\text{net\_pnl}|}$$
     - Nếu tổng lỗ bằng 0: trả về `None` (biểu diễn là `null` trong JSON), tuyệt đối không để xảy ra phép chia cho 0 hay trả về `Infinity`.
     - Nếu không có trade thắng: trả về 0.0.
  5. **Peak-to-Valley Maximum Drawdown:**
     $$\text{Peak}_t = \max(\text{initial\_capital}, \max_{s \le t} \text{equity}_s)$$
     $$\text{Drawdown USD}_t = \text{Peak}_t - \text{equity}_t$$
     $$\text{Drawdown \%}_t = \frac{\text{Drawdown USD}_t}{\text{Peak}_t} \times 100\%$$
     $$\text{Max DD} = \max_t (\text{Drawdown}_t)$$
  6. **Daily Sharpe Ratio (Resampled 1D UTC):**
     - Trích xuất chuỗi equity tại các mốc snapshot, resample theo ngày lịch UTC lấy giá trị equity cuối cùng của mỗi ngày.
     - Tính tỷ suất lợi nhuận hàng ngày: $r_d = \frac{E_d - E_{d-1}}{E_{d-1}}$.
     - Chuẩn hoá năm hóa với thị trường Crypto hoạt động 365 ngày:
       $$\text{Sharpe} = \sqrt{365} \times \frac{\bar{r}_d - \frac{r_f}{365}}{\sigma(r_d, \text{ddof}=1)}$$
     - Xử lý biên nghiêm ngặt: nếu số ngày quan sát < 2 hoặc độ lệch chuẩn $\sigma = 0$ (chuỗi phẳng), trả về `None`/`null`.

### 2.4 Bộ Tạo Lập Báo Cáo Đa Định Dạng (Multi-format Report Generator — `src/report/generator.py`)
- Với mỗi `run_id`, tự động tạo thư mục `reports/<run_id>/` chứa đầy đủ 6 artifacts độc lập:
  1. `summary.json`: Toàn bộ chỉ số hiệu năng được làm sạch, serialize với `allow_nan=False`.
  2. `summary.md`: Báo cáo Markdown chi tiết cho con người, phân bảng rõ ràng, bắt buộc đính kèm nhãn `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED` và khối tuyên bố miễn trừ trách nhiệm (Benchmark Caveats & Disclosures).
  3. `trades.json`: Danh sách các trade đã đóng theo định dạng Section 4.6.
  4. `equity_curve.csv`: Dữ liệu bảng (timestamp, equity, balance, unrealized PnL, margin used, drawdown USD & %).
  5. `equity_curve.png`: Biểu đồ 2 khung thời gian thực thi (khung trên: Đường cong Equity vs Đường đỉnh High Watermark; khung dưới: Vùng sụt giảm Underwater Drawdown %).
  6. `trades.sqlite`: File cơ sở dữ liệu SQLite lưu trữ trọn vẹn run đó.

### 2.5 Tích Hợp CLI & Độc Lập Môi Trường Thực Thi (`run_backtest.py`)
- Bổ sung các cờ dòng lệnh linh hoạt:
  - `--output-dir`: Đường dẫn thư mục lưu báo cáo (mặc định `reports`).
  - `--run-id`: Định danh tuỳ chọn (mặc định tự sinh theo mẫu `run_{strategy}_{symbol}_{YYYYMMDD_HHMMSS}`).
  - `--db-path`: Đường dẫn SQLite database chỉ định ngoài.
  - `--no-report`: Bỏ qua việc sinh file artifacts khi chỉ muốn xem kết quả console.
- CWD-independence: Mọi đường dẫn tương đối đều được phân giải an toàn và độc lập với thư mục hiện hành của người dùng.

---

## 3. Hệ Quả & Đánh Giá Kỹ Thuật

### 3.1 Ưu điểm
- **Tính Toàn vẹn & Chống Lookahead:** Tách biệt triệt để tầng phân tích/ghi nhận khỏi tầng thực thi. PaperBroker và BacktestEngine không phụ thuộc vào tầng báo cáo để ra quyết định.
- **Tương thích ngược 100%:** Toàn bộ các key của `_calculate_metrics` từ Giai đoạn 5 vẫn được duy trì đầy đủ, không gây breaking changes cho các kiểm thử trước đó.
- **Tính Minh bạch & Khiêm tốn Kỹ thuật:** Mọi số liệu mô phỏng đều gắn nhãn `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED` và kèm theo các lưu ý về giới hạn của dữ liệu lịch sử, slippage giả định và kích thước mẫu thống kê.

### 3.2 Hạn chế & Phạm vi Mở rộng
- Intrabar MAE/MFE hiện để `null` do nến 15m không chứa thứ tự biến động tick bên trong nến. Sẽ được kích hoạt khi nâng cấp lên tick/orderbook data ở các phiên bản tương lai.
- Dashboard Streamlit tiếp tục được hoãn lại đúng theo phạm vi đã thống nhất.
