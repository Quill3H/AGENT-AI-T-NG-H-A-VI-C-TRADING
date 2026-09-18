# CHANGELOG - Crypto Paper-Trading Research Agent

Toàn bộ lịch sử cập nhật và hoàn thành các giai đoạn theo [CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md](file:///D:/Ta%CC%80i%20lie%CC%A3%CC%82u/Default%20Project/Project%20spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md).

---

## [Giai đoạn 3] - Risk Manager Refinements Lần 3 (Theo GPT Review 03) (2026-09-19)
### Đã triển khai (Khắc phục toàn diện 3 nhóm phát hiện G1–G3)
- **G1 - Xác thực Nghiêm ngặt Cấu hình & Trạng thái (`src/risk/invariant_checks.py`):**
  - Kiểm tra `math.isfinite` và kiểu số thực cho `config.risk` (`max_leverage >= 1.0`, `min_liquidation_buffer_pct in (0, 1)`, `conviction_tiers > 0`) và `config.fees.taker_pct >= 0`. Nếu sai kiểu/NaN/Inf/chuỗi sai, từ chối với `INVARIANT_FAIL_CONFIG_ERROR`.
  - Bỏ qua so sánh liquidation buffer nếu `min_buffer_valid` là False, ngăn chặn việc `min_liquidation_buffer_pct = NaN` làm tê liệt phép so sánh và lọt lệnh rủi ro cao.
  - Kiểm tra `cb_state.risk_multiplier` phải là số thực hữu hạn trong $(0, 1.0]$ và khớp với trạng thái hợp lệ ($1.0$ hoặc `risk_reduction_on_streak`). Nếu sai, từ chối với `INVARIANT_FAIL_INVALID_CIRCUIT_BREAKER_STATE`, tuyệt đối không tự ý fallback về 1.0 full risk.
  - Kiểm tra `cb_state.is_locked` bắt buộc là kiểu `bool`.
- **G2 - Cổng Duyệt & Lùi Thời gian Breaker (`src/risk/invariant_checks.py`):**
  - Phát hiện `admission_time < cb_state.current_timestamp` tại cổng duyệt lệnh và từ chối với `INVARIANT_FAIL_TIME_REVERSAL`.
  - Không gọi `cb_state.is_trading_allowed(admission_time)` khi lùi thời gian, giúp bảo toàn nguyên vẹn đồng hồ, lịch sử giao dịch và trạng thái khóa của Circuit Breaker mà không văng unhandled exception.
  - Tiếp tục thu thập các lỗi vi phạm độc lập khác (nếu có) thay vì dừng sớm.
  - Giữ nguyên vẹn hợp đồng toán học trực tiếp của `CircuitBreakerState` (`advance_time` và `record_trade_result` ném `ValueError` khi lùi thời gian).
- **G3 - Quản lý Trạng thái Sẵn sàng của Bộ lọc Tin tức (`src/features/news_calendar.py`, `src/risk/invariant_checks.py`):**
  - Bổ sung `is_ready: bool` và `load_error: Optional[str]` cho `NewsCalendarFilter`.
  - Quy ước: `enabled = False` => bypass (`is_ready = True`). Khi `enabled = True`, bắt buộc nạp lịch thành công.
  - Nếu file lịch không tồn tại, thiếu cột bắt buộc (`datetime_utc`/`timestamp` hoặc `event`/`event_name`), hoặc chứa dòng timestamp/sự kiện hỏng (`NaT`, rác) -> đánh dấu `is_ready = False` và lưu `load_error = "CALENDAR_LOAD_ERROR: ..."` (không nuốt lỗi).
  - Cổng duyệt lệnh lập tức chặn mở lệnh nếu `news_filter` chưa sẵn sàng với `INVARIANT_FAIL_NEWS_FILTER_NOT_READY`.
  - File CSV có header nhưng 0 dòng sự kiện được công nhận là lịch hợp lệ (`is_ready = True`, `events = []`).
  - Cung cấp API `set_events` và cơ chế reload khôi phục `is_ready = True`.
- **Bộ kiểm thử mở rộng:**
  - Bổ sung 11 unit tests mới trong `tests/test_invariant_checks.py` (tổng: 41 tests).
  - Bổ sung 6 unit tests mới trong `tests/test_news_calendar.py` (tổng: 9 tests).
  - Báo cáo: `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 3/BAO_CAO_SUA_DOI_THEO_GPT_REVIEW_03.md`.
  - Cập nhật Phụ lục 2 trong `docs/decisions/0006-circuit-breaker-and-risk-gate-refinements.md`.
### Kết quả kiểm thử
- **Pytest Offline:** **153/153 tests PASSED** trong 1.64s.
- **Pytest Network:** **5/5 tests PASSED** trong 11.62s.
- **Tổng cộng:** **158/158 tests PASSED (100% xanh)**.
- **Mô phỏng 10 lệnh:** Chạy thông suốt 2 Phase, đối soát tài chính chính xác 100%.

---

## [Giai đoạn 3] - Risk Manager Refinements Lần 2 (Theo GPT Review 02) (2026-09-19)
### Đã triển khai (Khắc phục toàn diện 5 nhóm phát hiện F1–F5)
- **F1 - Ngân sách Rủi ro Khai báo & Chống Double Reduction (`src/risk/invariant_checks.py`):**
  - Đối soát tổn thất giá thực tế $Q \times |Entry - Stop|$ với ngân sách rủi ro khai báo của lệnh (`order_declared_budget_usd = equity * order_effective_risk_pct`), thay vì chỉ đối soát với trần tier.
  - Ép buộc kiểm tra đẳng thức `risk_percent == base_risk_percent * cb_multiplier` (sai số $10^{-6}$) khi truyền cả hai, chống double reduction.
- **F2 - Cung ứng Ký quỹ Bắt buộc & Độ Bền Input (`src/risk/invariant_checks.py`, `src/features/news_calendar.py`):**
  - Yêu cầu bắt buộc `available_margin` hữu hạn $\ge 0$, loại bỏ fallback ngầm dùng `equity`.
  - Kiểm tra tổng vốn cần trước khi mở vị thế bao gồm cả ký quỹ ban đầu và phí vào lệnh ước tính: `required_margin + est_entry_fee <= available_margin`.
  - Kiểm tra an toàn `isinstance(conviction_tier, str)` trước khi tra cứu dict (chống `TypeError` khi input là unhashable list/dict).
  - Kiểm tra `callable(getattr(cb_state, "is_trading_allowed"))` (chống `AttributeError` khi truyền object lạ).
  - Bọc try/except `(OverflowError, OSError, ValueError)` khi parse timestamp (chống crash khi gặp giá trị cực lớn như `1e100`).
- **F3 - Phân lập Thẩm quyền Admission Time (`src/risk/invariant_checks.py`):**
  - Thiết lập `account_state['current_time']` là nguồn thời gian thẩm quyền duy nhất tại cổng duyệt lệnh (Admission Time).
  - Ràng buộc nhân quả: `order['timestamp'] <= account_state['current_time']`.
  - Đánh giá trạng thái Circuit Breaker và News Blackout Window nghiêm ngặt tại Admission Time, loại bỏ hoàn toàn lỗ hổng dùng signal cũ ngoài giờ cấm để lách qua blackout.
  - Bổ sung kiểm tra mâu thuẫn cấu hình tin tức (`INVARIANT_FAIL_NEWS_FILTER_CONFIG_MISMATCH`).
- **F4 - Đồng hồ Đơn nhất & Khóa Breaker Tuyệt đối (`src/risk/circuit_breakers.py`):**
  - Xây dựng phương thức chuẩn hóa `advance_time(current_timestamp)` dùng chung cho cả `is_trading_allowed` và `record_trade_result`, đảm bảo thời gian đơn điệu monotonic.
  - Giải quyết triệt để Scenario A (query tiến thời gian khóa chặn sự kiện quá khứ) và Scenario B (tự động giải phóng khóa cũ và bắt vi phạm mới ngay tại thời điểm sự kiện mà không cần query thăm dò xen giữa).
  - Khi `equity <= 0` (cháy vốn): chuyển sang trạng thái `self.is_halted = True`, khóa giao dịch vĩnh viễn thay vì dùng số ngày tượng trưng.
  - Kiểm soát danh mục `recovery_mode` hợp lệ qua `SUPPORTED_RECOVERY_MODES = {"after_3_wins", "after_1_win"}`.
- **F5 - Giải thuật Thanh lý Nghiêm ngặt (Strict Liquidation Solver) (`src/risk/invariant_checks.py`):**
  - Kiểm tra tính liên tục của bảng leverage brackets tại các ranh giới tier ($C_i \cdot \text{MMR}_i - \text{cum}_i == C_i \cdot \text{MMR}_{i+1} - \text{cum}_{i+1}$).
  - Từ chối vị thế danh nghĩa vượt quá trần tối đa của bảng bracket với `ValueError` (không ngoại suy).
  - Từ chối vị thế vi phạm điều kiện thanh lý ngay tại entry (`initial_margin <= maintenance_margin_entry`) với `ValueError("already liquidatable")`.
  - Ràng buộc phương hướng nghiệm: Long $P_{cand} < P_{entry}$, Short $P_{cand} > P_{entry}$.
  - Loại bỏ hoàn toàn fallback sang tier cuối; ném `ValueError` nếu không có nghiệm hợp lệ trong miền bracket.
  - Kiểm chứng độc lập nghiệm với phương trình cân bằng ký quỹ độc lập.
- **Bộ kiểm thử mở rộng:**
  - Bổ sung 11 unit tests mới trong `tests/test_invariant_checks.py` (tổng: 30 tests).
  - Bổ sung 6 unit tests mới trong `tests/test_circuit_breakers.py` (tổng: 16 tests).
  - Bổ sung 5 unit tests mới trong `tests/test_liquidation_calc.py` (tổng: 15 tests).
  - Báo cáo: `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 3/BAO_CAO_SUA_DOI_THEO_GPT_REVIEW_02.md`.
### Kết quả kiểm thử
- **Pytest Offline:** **130/130 tests PASSED** trong 1.52s.
- **Pytest Network:** **5/5 tests PASSED** trong 13.37s.
- **Tổng cộng:** **135/135 tests PASSED (100% xanh)**.
- **Mô phỏng 10 lệnh:** Chạy thông suốt 2 Phase, đối soát tài chính chính xác 100%.

---

## [Giai đoạn 3] - Risk Manager Refinements (Theo Independent GPT Review) (2026-09-19)
### Đã triển khai (Khắc phục toàn diện 6 vấn đề R1-R6 theo ADR 0006)
- **ADR 0006 (`docs/decisions/0006-circuit-breaker-and-risk-gate-refinements.md`):** Quy chuẩn hóa các quyết định kiến trúc: cửa sổ trượt $(T-24h, T]$, monotonic time, breakeven trade streak reset, lockout non-extension, Tier-Consistent Liquidation Solver, đối soát tổn thất giá thực tế.
- **R1 - Input Sanitization & Admission Gate (`src/risk/position_sizing.py`, `src/risk/invariant_checks.py`):**
  - Hàm `_validate_numeric`: Chặn dứt khoát `bool`, `NaN`, `+/-Inf`, số âm/không dương, overflow.
  - Từ chối dứt khoát `conviction_tier` không có trong cấu hình (`INVARIANT_FAIL_UNKNOWN_CONVICTION_TIER`), xóa bỏ hoàn toàn fallback âm thầm 10%.
- **R2 - Đối soát rủi ro thực tế & Ký quỹ khả dụng (`src/risk/invariant_checks.py`):**
  - Đối soát tổn thất giá $Q \times |Entry - Stop| \le \text{Max Effective Risk USD}$ (`INVARIANT_FAIL_ACTUAL_RISK_EXCEEDED`).
  - Kiểm tra ký quỹ yêu cầu $\le \text{Available Margin}$ (`INVARIANT_FAIL_INSUFFICIENT_MARGIN`).
- **R3 - Tính toàn vẹn của bảo vệ & Chuẩn hóa UTC (`src/features/news_calendar.py`, `src/risk/invariant_checks.py`):**
  - Nâng cấp `parse_utc_datetime`: Hỗ trợ Unix float/int timestamp, chống crash.
  - Loại bỏ hoàn toàn fallback `datetime.now()`, bắt buộc dùng timestamp UTC mô phỏng (`INVARIANT_FAIL_MISSING_TIMESTAMP`).
  - Kiểm tra bắt buộc có `CircuitBreakerState` và `NewsCalendarFilter` khi enabled.
- **R4 - Làm sạch Circuit Breaker (`src/risk/circuit_breakers.py`):**
  - Validate numeric cho PnL và equity (chặn NaN, Inf, bool).
  - Kiểm tra thứ tự thời gian đơn điệu, chặn time reversal.
  - Tự động tỉa cửa sổ trượt `_prune_window` cả trong `is_trading_allowed`.
  - Lệnh hòa vốn ($pnl=0$) reset cả chuỗi thắng và thua về 0.
  - Giữ nguyên `locked_until` 24h ban đầu khi có thêm lệnh trong thời gian khóa (không kéo dài vô tận).
- **R5 - Thuật toán giải giá thanh lý nhất quán theo Tier (`src/risk/invariant_checks.py`):**
  - Triển khai Tier-Consistent Solver: $q \times P_{cand} \in (\text{tier\_min}, \text{tier\_max}]$.
  - Khớp chính xác 100% với 2 benchmark của GPT Review: Long $33,467.20$ USD và Short $66,390.27$ USD.
- **R6 - Minh bạch kịch bản mô phỏng (`scripts/simulate_risk_manager_10_trades.py`):**
  - Xóa bỏ toàn bộ lệnh ngầm ("lệnh 4b").
  - Tách bạch rõ 2 Phase: Phase 1 (10 lệnh giả lập cho chuỗi thua, giảm 50% risk, khóa 24h) và Phase 2 (3 lệnh post-unlock phục hồi 100% risk).
  - Đối soát vốn tự động `assert abs(final_equity - (start_equity + total_pnl)) < 1e-4`.
- **Tập test mở rộng:** Bổ sung 28 unit tests chuyên sâu.
  - `tests/test_position_sizing.py`: 21 tests (tăng từ 10).
  - `tests/test_liquidation_calc.py`: 10 tests (tăng từ 6).
  - `tests/test_circuit_breakers.py`: 10 tests (tăng từ 5).
  - `tests/test_invariant_checks.py`: 19 tests (tăng từ 11).
  - Báo cáo: `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 3/BAO_CAO_SUA_DOI_THEO_GPT_REVIEW.md`.
### Kết quả kiểm thử
- **Pytest:** **113/113 tests PASSED (100% xanh)** trong 12.70s.
- **Mô phỏng:** 2 Phase chạy mượt mà, đối soát vốn chính xác 100%.

---

## [Giai đoạn 3] - Risk Manager (2026-09-18)
### Đã triển khai
- `src/risk/position_sizing.py`: Tính toán Position Size, Required Margin, Stop Distance, Quantity; xử lý ngoại lệ chia cho 0 khi stop == entry và validation input.
- `src/risk/invariant_checks.py`:
  - Tra cứu MMR tier và `cumulative_maintenance_amount` theo `leverage_brackets` cho BTCUSDT.
  - Tính toán giá thanh lý `estimated_liquidation_price` theo chuẩn Binance Futures Isolated Margin (LONG & SHORT).
  - Kiểm tra toàn diện 6 Hard Invariants (Stop-Loss, Leverage Cap, Min Liquidation Buffer 30%, Conviction Tier Limits, Circuit Breaker Lock, News Blackout Window); LUÔN trả về toàn bộ danh sách lỗi vi phạm (không dừng ở lỗi đầu tiên).
- `src/risk/circuit_breakers.py`:
  - Quản lý trạng thái `CircuitBreakerState` với cửa sổ trượt rolling 24h PnL.
  - Tự động kích hoạt khóa 24h khi lỗ rolling 24h $\ge 5\%$ vốn hiện tại.
  - Tự động giảm risk xuống 50% (`risk_multiplier = 0.5`) khi thua liên tiếp $\ge 3$ lệnh.
  - Phục hồi 100% risk sau đúng 3 lệnh thắng liên tiếp (`recovery_mode: "after_3_wins"`, ADR 0002).
  - Xử lý reset chuỗi thắng về 0 nếu có lệnh thua xen ngang trong giai đoạn phục hồi.
  - Tự động mở khóa khi thời gian khóa 24h kết thúc.
- `src/risk/__init__.py`: Export subsystem Risk Manager.
- `tests/test_position_sizing.py`: 10 unit tests cho công thức tính tay, biên số học và bắt ngoại lệ.
- `tests/test_liquidation_calc.py`: 6 unit tests tra cứu qua 4 MMR tiers và công thức giá thanh lý Long/Short.
- `tests/test_circuit_breakers.py`: 5 unit tests cho 5 kịch bản ngắt mạch, chuỗi thua/thắng và khóa 24h.
- `tests/test_invariant_checks.py`: 11 unit tests cho 6 invariants riêng biệt, all-pass và multiple-fails.
- Script mô phỏng trực quan `scripts/simulate_risk_manager_10_trades.py` chạy qua 10 lệnh giả lập liên tiếp, in bảng ASCII chi tiết.
- Báo cáo chi tiết `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 3/BAO_CAO_GIAI_DOAN_3.md`.
### Kết quả kiểm thử
- **Pytest:** 85/85 tests PASSED (100% xanh) trong 25.17s (32 test mới của Giai đoạn 3).
- **Mô phỏng 10 lệnh:** Chạy thông suốt qua đầy đủ các trạng thái (duyệt lệnh, từ chối lệnh do vi phạm invariant, giảm 50% risk sau 3 loss, khóa 24h khi lỗ 5%, từ chối do khóa, mở khóa và phục hồi 100% risk sau 3 win).

---

## [Giai đoạn 2] - Feature Engine (2026-09-18)
### Đã triển khai
- `src/features/indicators.py`: Tính toán EMA (20/50/200), RSI (14), MACD (12/26/9), ATR (14) từ cấu hình động; hỗ trợ 2 tầng (pandas-ta + pure pandas fallback theo chuẩn TA-Lib).
- `src/features/oi_features.py`: Tính `% thay đổi Open Interest (oi_delta_pct)` với cơ chế lan truyền NaN và tương thích `oi_confluence`.
- `src/features/cvd.py`: Tính Cumulative Volume Delta (`cvd`) và phát hiện phân kỳ CVD (`cvd_divergence`) với cơ chế chống Lookahead Bias 100% (xác nhận trễ $k=3$ nến, không backfill).
- `src/features/__init__.py`: Export toàn bộ hàm và pipeline tích hợp `add_all_features`.
- Nâng cấp `src/data_layer/fetcher.py`: Trích xuất trực tiếp `taker_buy_base_volume` thực từ Binance Futures klines endpoint.
- `tests/test_indicators.py`: Kiểm thử toán học EMA, RSI, MACD, ATR và so sánh chéo fallback.
- `tests/test_oi_features.py`: Kiểm thử công thức và lan truyền NaN.
- `tests/test_cvd.py`: Kiểm thử cộng dồn CVD và nhận diện 2 kịch bản phân kỳ Bullish/Bearish mẫu.
- `tests/test_no_lookahead.py`: Kiểm thử xáo trộn dữ liệu tương lai sau điểm $T$, chứng minh tính bất biến nhân quả.
- Script thực nghiệm `scripts/verify_stage2_real_data.py` và báo cáo `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 2/BAO_CAO_CLAUDE_REVIEW_GIAI_DOAN_2.md`.
### Kết quả kiểm thử
- **Pytest:** 53/53 tests PASSED (100%) trong 11.90s.
- **Thực nghiệm dữ liệu thật Binance (70 ngày BTC/USDT):** Khung 4H (420 nến, 52.6% đầy đủ sau warm-up EMA200); Khung 15M (6,720 nến, 97.0% đầy đủ). Phân kỳ CVD hoạt động chuẩn xác.

---

## [Giai đoạn 1] - Data Layer (2026-09-18)
### Đã triển khai
- `src/data_layer/fetcher.py`: Kéo dữ liệu OHLCV, Funding Rate và cơ chế Hybrid Open Interest từ Binance Futures API qua `ccxt`.
- `src/data_layer/binance_vision_downloader.py`: Tải dữ liệu OI lịch sử sâu từ Binance Data Vision (`data.binance.vision`), giải nén, parse và downsample về 4h/15m/1m bằng forward-fill.
- `src/data_layer/cache_manager.py`: Quản lý lưu trữ/đọc cache Parquet local, kiểm tra khoảng trống dữ liệu (`detect_gaps`), hàm public `ensure_utc_index` và `timeframe_to_timedelta`.
- `src/features/news_calendar.py`: Quản lý lịch kinh tế CSV với log warning chi tiết (không nuốt lỗi).
- Cấu hình `oi_confluence` mode `optional` và `fallback_when_nan: true`.
### Kết quả kiểm thử
- **Pytest:** 28/28 tests PASSED (100%) trong 14.06s.
- **Thực nghiệm dữ liệu thật Binance:** Tải trơn tru 60 ngày dữ liệu không còn NaN ở đuôi.

---

## [Giai đoạn 0] - Khởi tạo dự án & Cấu hình (2026-09-18)
### Đã triển khai
- Thiết lập cấu trúc thư mục module hóa: `src/data_layer`, `src/features`, `src/risk_manager`, `src/execution`, `src/strategies`, `src/analytics`, `config/`, `tests/`, `data/`.
- File cấu hình trung tâm `config/default_config.yaml` và các config chiến lược mẫu (`trend_following.yaml`, `smc_liquidity_sweep.yaml`).
- Chốt 4 quyết định kỹ thuật: `news_filter.enabled: false`, `start_date: "2021-01-01"`, `recovery_mode: "after_3_wins"`, loại bỏ hoàn toàn phần thừa RL.
- Cập nhật `requirements.txt` tương thích Python 3.13 (`numpy>=2.1.0`).
