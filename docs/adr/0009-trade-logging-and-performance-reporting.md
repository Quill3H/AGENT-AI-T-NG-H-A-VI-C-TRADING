# ADR 0009: Kiến Trúc Lưu Trữ Sự Kiện Giao Dịch & Báo Cáo Hiệu Năng (Trade Logger & Performance Reporting)

**Trạng thái:** IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW (Stage6–11 repair; xem báo cáo và commit A hiện tại)
**Ngày đề xuất:** 2026-09-19  
**Người đề xuất:** Quill3H & Antigravity (theo đặc tả kỹ thuật Giai đoạn 6 — Master Spec Section 4.6)

---

## 1. Bối cảnh
Sau khi hoàn thành và nghiệm thu Giai đoạn 5 (Chiến lược Trend Following và cỗ máy BacktestEngine đa khung thời gian), hệ thống cần một cơ chế chuẩn hoá, bền vững và phi tập trung để:
1. Lưu trữ có cấu trúc toàn bộ vòng đời của mỗi phiên chạy backtest/paper trading (metadata phiên, lệnh, giao dịch đóng, sự kiện funding, snapshot tài khoản theo từng nến, chỉ số hiệu năng tổng hợp).
2. Xuất dữ liệu giao dịch chuẩn hoá (JSON trade schema) đúng nguyên văn theo Master Spec Section 4.6 để phục vụ đối soát, phân tích danh mục và kiểm định độc lập.
3. Thống nhất một nguồn chân lý tính toán số liệu hiệu năng (Single Source of Truth Performance Metrics) cho giao dịch phái sinh (Expectancy USD & R-multiple, Profit Factor xử lý nghiêm ngặt khi lỗ = 0, Peak-to-Valley Drawdown, Daily Sharpe Ratio resampled theo ngày lịch UTC với hệ số nhân $\sqrt{365}$).
4. Tự động sinh bộ 6 artifacts báo cáo đa định dạng (SQLite, JSON, CSV, PNG, Markdown) dưới thư mục riêng biệt `reports/<run_id>/` với đường dẫn phân giải tất định, độc lập hoàn toàn với thư mục thực thi (CWD).
5. Đảm bảo nguyên lý Không làm biến dạng ngữ nghĩa thực thi (Zero Semantic Drift): tầng logger và report generator hoạt động hoàn toàn bên ngoài và sau quá trình mô phỏng, không can thiệp hay làm lệch dù chỉ một xu giá khớp, số dư hay quyết định của cỗ máy khớp lệnh.

---

## 2. Quyết định Kiến trúc & Thiết kế (Nâng cấp toàn diện sau GPT Review 11)

### 2.1 Kho Lưu Trữ Sự Kiện SQLite (SQLite Event Store — `src/logging/trade_logger.py`)
- **Quản lý kết nối & Toàn vẹn tham chiếu:**
  - Bật bắt buộc ràng buộc khoá ngoại: thực thi `PRAGMA foreign_keys = ON;` ngay sau khi mở mỗi kết nối SQLite.
  - Thiết kế 6 bảng quan hệ có khoá ngoại ràng buộc về bảng gốc `runs`:
    1. `runs`: Lưu trữ metadata phiên chạy (`run_id` làm PRIMARY KEY, strategy, symbol, timeframe, thời gian, vốn ban đầu, equity kết thúc, config_json, canonical_payload_hash, created_at).
    2. `orders`: Khóa chính phức hợp `PRIMARY KEY (run_id, order_id)`. Lưu trữ toàn bộ các lệnh phát ra (`order_id`, `run_id`, hướng, loại lệnh, trạng thái, thời gian yêu cầu/xử lý, giá tham chiếu/khớp thực tế, slippage, số lượng, phí, `rejection_reasons_json`, `metadata_json`). Đảm bảo lưu trọn vẹn lý do từ chối và metadata từ `OrderRequest` qua `OrderExecutionRecord`.
    3. `trades`: Khóa chính phức hợp `PRIMARY KEY (run_id, trade_id)`. Lưu trữ toàn bộ các giao dịch đã đóng (`trade_id`, `run_id`, symbol, direction, quantity, entry/exit price, entry/exit time, leverage, initial margin, gross/net PnL, fees, funding cashflow, return %, exit reason, initial stop loss, initial risk USD, realized R-multiple, conviction tier, estimated_liquidation_price, take_profit_levels_json, metadata_json).
    4. `funding_events`: Khóa chính phức hợp `PRIMARY KEY (run_id, event_id)`. Lưu trữ chi tiết các lần thanh toán funding (`event_id`, `run_id`, position_id, symbol, timestamp, funding_rate, mark_price, position_quantity, payment, direction). Giữ nguyên `event_id` gốc và hướng vị thế.
    5. `account_snapshots`: Khóa chính phức hợp `PRIMARY KEY (run_id, timestamp)`. Lưu trữ trực tiếp ánh xạ từ `AccountSnapshot` không qua giá trị bịa: `wallet_balance`, `equity`, `unrealized_pnl`, `reserved_collateral`, `available_margin`, `open_positions_count`, `is_halted`.
    6. `run_metrics`: Khóa chính `run_id`. Lưu trữ toàn bộ dictionary metrics đầy đủ dưới dạng JSON (`run_id`, `metrics_json`, `created_at`).
- **Giao dịch Nguyên tử (Atomic Transaction):**
  - Toàn bộ quá trình ghi của một run được bao bọc trong một SQLite transaction duy nhất (`with conn:`).
  - Nếu xảy ra bất kỳ lỗi dữ liệu nào giữa chừng, toàn bộ transaction tự động rollback, cam kết không để lại dữ liệu rác hay trạng thái mồ côi (zero partial state).
- **Tính Luỹ thừa & Từ chối Xung đột Toàn diện (Full Canonical Payload Hash Idempotency):**
  - Khi gọi `log_backtest_run` với một `run_id` đã tồn tại trong database:
    - Tính mã băm SHA-256 chuẩn tắc (`canonical_payload_hash`) bao phủ toàn bộ: config chuẩn tắc, run metadata, orders, trades, funding events, account snapshots và metrics.
    - Nếu payload hash mới trùng khớp 100% với hash đã lưu: coi là thành công luỹ thừa (idempotent no-op), ghi log thông báo và trả về `True`.
    - Nếu payload hash có bất kỳ khác biệt nào (kể cả 1 trade, 1 snapshot hay 1 giá trị metric): ném ngoại lệ `ValueError` lập tức (fail-closed), kiên quyết từ chối ghi đè dữ liệu.

### 2.2 Xuất JSON Trade Chuẩn Hoá (Master Spec Section 4.6 Verbatim)
- Xuất mảng các giao dịch đóng tuân thủ tuyệt đối đúng nguyên văn cấu trúc Master Spec Mục 4.6:
  - Đúng 17 key ở cấp gốc: `trade_id`, `timestamp` (epoch seconds UTC), `asset`, `direction`, `strategy_used`, `conviction_tier`, `entry_price`, `stop_loss_price`, `take_profit_levels`, `nominal_position_size_usd`, `leverage`, `margin_used_usd`, `risk_amount_usd`, `risk_ratio_percent`, `estimated_liquidation_price`, `market_context`, `outcome`.
  - Object lồng `market_context` bắt buộc gồm 4 trường unmeasured dạng `null`: `oi_trend_4h`, `funding_rate_8h`, `cvd_divergence`, `fvg_consequent_encroachment`. Tuyệt đối không bịa dữ liệu giả lập.
  - Object lồng `outcome` gồm 7 trường: `exit_price`, `pnl_usd`, `fees_paid_usd`, `net_return_percent`, `max_adverse_excursion_mae` (`null`), `max_favorable_excursion_mfe` (`null`), `rule_compliance` (`true`).
  - Toàn bộ xuất JSON dùng `allow_nan=False` tuân thủ nghiêm ngặt RFC 8259 (fail-closed nếu phát hiện NaN hoặc Inf).

### 2.3 Động Cơ Tính Toán Chỉ Số Hiệu Năng (`src/report/metrics.py`)
- Định nghĩa các công thức tính toán tài chính chuẩn:
  1. **Expectancy (USD):** Kỳ vọng toán học PnL trên mỗi trade:
     $$\text{Expectancy}_{\text{USD}} = \frac{1}{N} \sum_{i=1}^N \text{net\_pnl}_i$$
  2. **Initial Risk (USD) & Realized R-multiple:**
     $$\text{Initial Risk}_{\text{USD}} = Q \times |\text{entry\_price} - \text{initial\_stop\_loss\_price}|$$
     $$\text{Realized } R = \frac{\text{net\_pnl}}{\text{Initial Risk}_{\text{USD}}}$$
  3. **Expectancy (R-multiple):**
     $$\text{Expectancy}_R = \frac{1}{M} \sum_{j=1}^M \text{Realized } R_j$$
  4. **Profit Factor:**
     $$\text{Profit Factor} = \frac{\sum_{\text{net\_pnl} > 0} \text{net\_pnl}}{\sum_{\text{net\_pnl} < 0} |\text{net\_pnl}|}$$
     - Nếu tổng lỗ bằng 0: trả về `None` (`null` trong JSON), tuyệt đối không để xảy ra phép chia cho 0 hay trả về `Infinity`.
     - Nếu không có trade thắng: trả về 0.0.
  5. **Peak-to-Valley Maximum Drawdown:**
     $$\text{Peak}_t = \max(\text{initial\_capital}, \max_{s \le t} \text{equity}_s)$$
     $$\text{Drawdown USD}_t = \text{Peak}_t - \text{equity}_t$$
     $$\text{Drawdown \%}_t = \frac{\text{Drawdown USD}_t}{\text{Peak}_t} \times 100\%$$
     $$\text{Max DD} = \max_t (\text{Drawdown}_t)$$
  6. **Daily Sharpe Ratio (Resampled 1D UTC):**
     $$\text{Sharpe} = \sqrt{365} \times \frac{\bar{r}_d - \frac{r_f}{365}}{\sigma(r_d, \text{ddof}=1)}$$
      - Xử lý biên nghiêm ngặt: nếu số ngày quan sát < 2, trả về `None`/`null`; nếu có đủ mẫu nhưng độ lệch chuẩn $\sigma = 0$, trả về `0.0` hữu hạn và deterministic.
  7. **Kiểm tra kiểu dữ liệu & Chống ngụy tạo:** Ném `TypeError` nếu nhận giá trị boolean ở các trường tài chính, ném `ValueError` nếu nhận NaN hoặc Inf.
  8. **Phân tách Rủi ro Rõ ràng:** Tách biệt tuyệt đối trạng thái / số lần khóa của Circuit Breaker (`circuit_breaker_status`, `circuit_breaker_risk_multiplier`, `circuit_breaker_lock_count`, `circuit_breaker_rejections_count`) khỏi các lần từ chối do thiếu ký quỹ riêng lẻ (`margin_rejections_count`).

### 2.4 Bộ Tạo Lập Báo Cáo Đa Định Dạng (`src/report/generator.py`)
- Với mỗi `run_id`, tự động tạo thư mục `reports/<run_id>/` chứa đầy đủ 6 artifacts độc lập:
  1. `summary.json`: Toàn bộ chỉ số hiệu năng được làm sạch (`allow_nan=False`), tích hợp đầy đủ provenance dữ liệu, candle counts, candle gaps, accounting reconciliation và verification status.
  2. `summary.md`: Báo cáo Markdown chi tiết cho con người, phân bảng rõ ràng, bắt buộc đính kèm nhãn `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`, bảng đối soát kế toán và khối tuyên bố miễn trừ trách nhiệm (Benchmark Caveats & Disclosures).
  3. `trades.json`: Danh sách các trade đã đóng theo định dạng Master Spec Section 4.6 verbatim.
  4. `equity_curve.csv`: Dữ liệu bảng (timestamp, equity, balance, unrealized PnL, margin used, drawdown USD & %).
  5. `equity_curve.png`: Biểu đồ 2 khung thời gian thực thi (khung trên: Đường cong Equity vs Đường đỉnh High Watermark; khung dưới: Vùng sụt giảm Underwater Drawdown %).
  6. `trades.sqlite`: File cơ sở dữ liệu SQLite lưu trữ trọn vẹn run đó.

### 2.5 Tích Hợp CLI & Độc Lập Môi Trường Thực Thi (`run_backtest.py`)
- **Deterministic Run ID:** Nếu người dùng không truyền `--run-id`, ID được tự động sinh tất định từ mã SHA-256 của `code_sha | strategy | symbol | start | end | config_hash` theo định dạng `run_{strategy}_{symbol}_{hash12}`. Không còn phụ thuộc đồng hồ hệ thống (wall-clock).
- **Phân giải Đường dẫn Chuẩn tắc (Hermetic Path Resolution):** Mọi đường dẫn tương đối truyền vào `--output-dir` và `--db-path` đều được resolve từ `PROJECT_ROOT`, bảo đảm tính độc lập 100% với CWD của process gọi bên ngoài. Các đường dẫn tuyệt đối được giữ nguyên vẹn.
- **Canonical Config Identity:** Config runtime có thể chứa cache root tuyệt đối để đọc dữ liệu, nhưng identity được canonicalize với placeholder ổn định (`<RAW_DATA_DIR>`, `<PROCESSED_DATA_DIR>` hoặc `<ABSOLUTE_PATH>`). Cùng config logic ở các máy/cache root khác nhau có cùng `config_hash` và run ID; thay đổi tham số có ý nghĩa như `fees.taker_pct` làm thay đổi cả hai. `summary.json`, `summary.md`, SQLite metadata và run ID dùng cùng định nghĩa này.
- **Reproduction Metadata:** Reproduction command ghi đường dẫn config repo-relative khi có thể; config bên ngoài repository dùng `<CONFIG_PATH>`, không được tự nhận là `config/default_config.yaml`.

---

## 3. Đối Soát & Thống Nhất Benchmark Chuẩn Tắc (Benchmark Reconciliation)

Theo yêu cầu của GPT Review 11, phần này lưu đối chiếu do tác giả lịch sử cung cấp giữa hai bộ số liệu; không xác minh lại dataset hoặc kết quả trong repair pass hiện tại:

### 3.1 Benchmark Chuẩn Tắc (Canonical Benchmark 2021-2023 BTCUSDT)
**AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED — không chạy lại trong repair pass hiện tại; chưa được reviewer xác minh hoặc nghiệm thu.**

Số liệu do tác giả lịch sử báo cáo trên tập dữ liệu 3 năm (2021-01-01 đến 2023-12-31, 105,120 nến 15m, 6,570 nến 4h):
- **Vốn ban đầu:** 10,000.00 USDT
- **Equity kết thúc:** 12,100.96 USDT (+21.01%)
- **Max Drawdown:** -2,050.72 USDT (-16.15%)
- **Daily Sharpe Ratio:** 0.54
- **Profit Factor:** 3.05
- **Expectancy:** +131.31 USDT / +0.68 R
- **Lệnh phát ra:** 22 lệnh (16 khớp FILLED, 6 bị từ chối do INVARIANT_FAIL_INSUFFICIENT_MARGIN)
- **Giao dịch đóng:** 16 trades (10 LONG, 6 SHORT, 8 thắng / 8 thua, win rate 50.00%)
- **Gross Price PnL:** +2,489.66 USDT
- **Tổng phí giao dịch (Fees):** -162.82 USDT
- **Dòng tiền Funding:** -225.89 USDT
- **Net Realized PnL:** +2,100.96 USDT
- **Lý do đóng lệnh:** 16/16 STOP_LOSS (trailing stop)
- **Kiểm toán Kế toán:** 100% PASSED (`wallet_balance` khớp chính xác ledger)

### 3.2 Bác Bỏ Số Liệu Dự Thảo Không Đồng Bộ (Repudiation of Discordant Draft Figures)
Các số liệu từng xuất hiện trong một số bản thảo nháp chưa qua nghiệm thu (ví dụ: *48 orders, 24 trades, fees 82.49 USDT, funding -22.56 USDT*) là các con số giả định/dự phóng chưa được kiểm chứng. Văn bản này **chính thức bác bỏ và tuyên bố vô hiệu** các con số dự thảo không nhất quán đó; bộ số liệu lịch sử được giữ để truy vết là mục 3.1, nhưng vẫn AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED và không có giá trị nghiệm thu độc lập.

## 4. Repair addendum (2026-09-21)

Config identity now snapshots the exact bytes parsed by NewsCalendarFilter and shares that snapshot across CLI/folds/PPO and persisted outputs. Str/Path and different roots with equal content have equal identity; changed enabled calendar content changes identity; repeated canonicalization is stable. Atomic UTF-8 LF output ensures manifest SHA matches actual Windows file bytes and SQLite payload. ISO UTC CLI input and custom config reproduction are tested. See the repair report for exact A and gate results; historical benchmark numbers above remain unverified.

For partial exits, report rows count realization slices. `sample_unit` discloses this limitation; `bars_by_timeframe` supplements legacy count keys and Markdown displays actual configured timeframes. Descriptive win-rate ranges are strategy-specific, never optimization targets.
