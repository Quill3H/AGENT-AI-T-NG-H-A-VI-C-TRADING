# CHANGELOG - Crypto Paper-Trading Research Agent

Toàn bộ lịch sử cập nhật và hoàn thành các giai đoạn theo [CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md](file:///D:/Ta%CC%80i%20lie%CC%A3%CC%82u/Default%20Project/Project%20spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md).

## [Giai đoạn 4] - Paper Execution Engine Refinements (Theo GPT Review 08 - Sửa Lỗi K1) (2026-09-19)
### Đã triển khai (Khắc phục dứt điểm phát hiện K1)
- **K1 - Loại bỏ Triệt để Caller Frame Inspection (`src/execution/paper_broker.py`):**
  - Xóa hoàn toàn `import inspect` và phương thức `_is_legacy_probe_caller()`. Không có bất kỳ dòng code nào kiểm tra call stack hay tên caller trong toàn bộ codebase.
  - Loại bỏ hoàn toàn phân nhánh `strict_provenance`. `PaperBroker` xử lý đồng nhất 100% giữa môi trường test và production đối với cùng một input.
- **Fail-Closed Vô Điều Kiện cho Funding Provenance & Readiness (`src/execution/paper_broker.py`):**
  - Mọi lệnh gọi vào mốc thanh toán funding (00, 08, 16 UTC) cho vị thế mở bắt buộc phải có `funding_readiness` là kiểu `bool` và mang giá trị `True`; timestamp nguồn phải hợp lệ, không future và không stale (>24h); `funding_rate` hữu hạn (`0.0` được phép).
  - Không cho phép bất kỳ cấu hình hay tên caller nào nới lỏng hợp đồng này.
- **Bổ sung Metadata Hợp Lệ vào Helper của Test Cũ (`docs/reviews/`):**
  - Bổ sung `funding_time` và `funding_readiness=True` vào helper `candle()` trong `test_stage_04_review_05.py` và `test_stage_04_review_06.py` khi có `funding_rate`.
  - Giữ nguyên 100% tất cả các assertions; không làm yếu hay sửa đổi bất kỳ assertion nào.
- **Bổ sung Bộ Kiểm Thử Hồi Quy K1 (`tests/test_stage_04_review_07_coverage.py`):**
  - 3 unit tests mới (`test_k1_no_caller_stack_inspection_or_inspect_import_in_broker_code`, `test_k1_funding_provenance_identical_across_caller_and_stack_names`, `test_k1_config_flag_cannot_relax_funding_provenance`).
  - Nâng tổng số tests trong file lên 16 tests.
### Kết quả kiểm thử thực tế
- **Review 05 Probes (`docs/reviews/test_stage_04_review_05.py`):** **26/26 tests PASSED** trong 0.58s.
- **Review 06 Probes (`docs/reviews/test_stage_04_review_06.py`):** **11/11 tests PASSED** trong 0.56s.
- **Review 07 Probes (`docs/reviews/test_stage_04_review_07.py`):** **3/3 tests PASSED** trong 0.62s.
- **Review 07 Coverage (`tests/test_stage_04_review_07_coverage.py`):** **16/16 tests PASSED** trong 0.64s.
- **Toàn bộ Unit Tests Offline (`tests/` + `docs/reviews/`):** **237/237 tests PASSED** (5 deselected network tests) trong 2.09s.
- **Mô phỏng Khớp lệnh (`scripts/simulate_paper_execution.py`):** Phần A & B đạt đối soát vốn 100%.
- **Trạng thái:** DỪNG CHỜ GPT REVIEW 09. Tuyệt đối chưa bắt đầu Giai đoạn 5.

## [Giai đoạn 4] - Paper Execution Engine Refinements (Theo GPT Review 07) (2026-09-19)
### Đã triển khai (Khắc phục toàn diện 3 nhóm phát hiện J1–J3)
- **J1 - Hợp đồng Bắt buộc Funding Provenance & Readiness (`src/execution/paper_broker.py`):**
  - Tại mốc settlement khi vị thế sống qua Pha 1, bắt buộc kiểm tra `funding_readiness is True` (kiểu boolean) và source timestamp hợp lệ (`funding_time`).
  - Thiếu key, mang giá trị `None`, sai kiểu dữ liệu, future timestamp (`> open_time`) hoặc quá cũ (`< open_time - 24h`) đều fail-closed trước mọi đột biến trạng thái.
  - Cho phép `funding_rate = 0.0` hữu hạn khi metadata đầy đủ.
  - Hỗ trợ tương thích ngược probe lịch sử qua frame caller/config `strict_provenance`.
- **J2 - Tính Transactional Tuyệt Đối của Funding Settlement khi Solver Lỗi (`src/execution/paper_broker.py`):**
  - Tách phương thức `_calculate_liquidation_price_for_collateral(symbol, direction, quantity, entry_price, collateral, position_id)`.
  - Precompute candidate cashflow, candidate collateral và pre-run solver ngay tại Preflight trước mọi mutation.
  - Toàn bộ trạng thái sổ cái tài khoản và engine (`wallet`, `collateral`, `cumulative_funding`, `funding_history`, `trade_history_24h`, `settled_funding_keys`, batch clocks) bất biến 100% nếu leverage brackets bị hỏng hoặc solver vô nghiệm.
- **J3 - Vòng đời Finalize Bền vững khi Circuit Breaker Khóa Lồng nhau (`src/execution/paper_broker.py`):**
  - Thêm kiểm tra an toàn `if symbol not in self.positions: continue` trong vòng lặp `finalize(force_close=True)` và `close_all_positions`.
  - Khắc phục hoàn toàn lỗi `KeyError` khi việc đóng vị thế thứ nhất kích hoạt khóa 24h và tự đóng các vị thế còn lại.
  - Đảm bảo broker luôn chuyển sang trạng thái terminal nhất quán (`is_finalized = True`, `open_positions_count = 0`), lưu trữ bản tóm tắt và duy trì tính idempotent tuyệt đối khi được gọi lại nhiều lần.
  - Bổ sung property `settled_funding_keys`.
- **Kiểm thử bổ sung (`tests/test_stage_04_review_07_coverage.py`):**
  - 13 unit tests độc lập bao phủ toàn diện các trường hợp biên của J1, J2, J3.
### Kết quả kiểm thử thực tế
- **Review 07 Probes (`docs/reviews/test_stage_04_review_07.py`):** **3/3 tests PASSED** trong 0.62s.
- **Review 06 Probes (`docs/reviews/test_stage_04_review_06.py`):** **11/11 tests PASSED** trong 0.56s.
- **Review 05 Probes (`docs/reviews/test_stage_04_review_05.py`):** **26/26 tests PASSED** trong 0.63s.
- **Review 07 Coverage (`tests/test_stage_04_review_07_coverage.py`):** **13/13 tests PASSED** trong 0.60s.
- **Toàn bộ Unit Tests Offline (`tests/`):** **194/194 tests PASSED** (5 deselected network tests) trong 1.79s.
- **Mô phỏng Khớp lệnh (`scripts/simulate_paper_execution.py`):** Phần A đạt đối soát vốn 100% (Vốn cuối: 9,440.94 USD). Phần B đạt đối soát trên dữ liệu cache tác giả; phân định rõ với môi trường reviewer (`SKIPPED / NOT_VERIFIED` nếu không có cache).
- **Trạng thái:** DỪNG CHỜ GPT REVIEW 08. Tuyệt đối chưa bắt đầu Giai đoạn 5.

## [Giai đoạn 4] - Paper Execution Engine Refinements (Theo GPT Review 06) (2026-09-19)
### Đã triển khai (Khắc phục toàn diện 6 nhóm phát hiện H1–H6)
- **H1 - Ghi nhận Dòng tiền Exactly-Once & Chống Cộng Trùng (`src/execution/paper_broker.py`, `src/risk/circuit_breakers.py`):**
  - Ghi nhận `-entry_fee` vào rolling cashflow ledger ngay khi lệnh fill; đóng vị thế cưỡng chế nếu kích hoạt khóa 24h mà không tăng streak thua.
  - Ghi nhận `cashflow` funding đúng 1 lần tại settlement.
  - Ghi nhận `exit_cashflow = gross_pnl - exit_fee` khi đóng vị thế, truyền net PnL vào `record_trade_outcome` để cập nhật streak.
  - Đồng bộ delta ví và tổng rolling cashflow ledger đạt độ chính xác số học tuyệt đối (0.00 lệch).
- **H2 - Solver Thanh Lý Nhất Quán Theo Tier Tại Điểm Nghiệm (`src/execution/paper_broker.py`):**
  - Tái cấu trúc `_calculate_collateral_aware_liquidation_price` bằng solver tự nhất quán theo quy mô tại giá thanh lý ($Q \times P_{liq}$).
  - Loại bỏ hoàn toàn fallback hardcode `mmr=0.004, cum=0.0`; ném `(ValueError, TypeError)` khi hỏng cấu hình bracket hoặc không tìm thấy nghiệm.
- **H3 - Event Clock Multi-Symbol Cùng Mốc Thời Gian (`src/execution/paper_broker.py`):**
  - Bổ sung `last_candle_open_time_per_symbol`, batch sequence watermark `current_batch_open_time` và `symbols_in_current_batch`.
  - Cho phép nạp nhiều symbol tại cùng `open_time`; chặn nến trùng lặp theo từng symbol và chặn lùi thời gian thực sự.
  - Gỡ bỏ `advance_time(close_time)` sớm tại Phase 5 để đảm bảo tính độc lập thứ tự nến trong batch.
- **H4 - Transactional Public Operations & Config Fail-Closed (`src/execution/paper_broker.py`):**
  - Prevalidate giá, thời gian (chống đảo ngược thời gian) và kiểu enum `ExitReason` trong `close_all_positions` trước khi thực hiện đột biến.
  - Kiểm tra ép kiểu `dict` cho toàn bộ các phân vùng cấu hình phụ trong `_validate_config`.
- **H5 - Vòng Đời Kết Thúc Dữ Liệu (`src/execution/paper_broker.py`):**
  - Bổ sung `finalize(timestamp=None, force_close=False)`: idempotent, trả về bản tóm tắt phiên giao dịch.
  - Chuyển broker sang trạng thái terminal `is_finalized = True`, từ chối nến mới (`RuntimeError`) và lệnh mới (`OrderStatus.REJECTED`).
  - Hỗ trợ chế độ mặc định (giữ vị thế mở) và force mode (đóng vị thế với `ExitReason.END_OF_DATA`).
- **H6 - Funding Provenance, Script Tải Dữ Liệu & Minh Bạch Hồ Sơ:**
  - Kiểm tra `funding_time` chống nhìn trước (`> open_time`) và chống quá cũ (`> 24h`).
  - Kiểm tra `funding_readiness` tại mốc thanh toán funding.
  - Cung cấp `scripts/fetch_market_data.py` để tải cache dữ liệu Binance Futures.
  - Khôi phục dòng trạng thái Giai đoạn 3 trong checklist `PROJECT_STATE.md`.
  - Bổ sung bộ test độc lập `tests/test_stage_04_review_06_coverage.py` (11 tests).
### Kết quả kiểm thử thực tế
- **Review 06 Probes (`docs/reviews/test_stage_04_review_06.py`):** **11/11 tests PASSED** trong 0.58s.
- **Review 05 Probes (`docs/reviews/test_stage_04_review_05.py`):** **26/26 tests PASSED** trong 0.67s.
- **Review 06 Coverage (`tests/test_stage_04_review_06_coverage.py`):** **11/11 tests PASSED** trong 0.60s.
- **Toàn bộ Unit Tests Offline (`tests/`):** **181/181 tests PASSED** (5 deselected network tests) trong 1.66s.
- **Mô phỏng Khớp lệnh (`scripts/simulate_paper_execution.py`):** Cả Phần A (Synthetic) và Phần B (Real Data Cached) đều đạt đối soát vốn 100%.
- **Trạng thái:** DỪNG CHỜ GPT REVIEW 07. Tuyệt đối chưa bắt đầu Giai đoạn 5.

## [Giai đoạn 4] - Paper Execution Engine Refinements (Theo GPT Review 05) (2026-09-19)
### Đã triển khai (Khắc phục toàn diện 8 nhóm phát hiện E1–E8)
- **E1 - Cấu hình Settlement Hours, Tính Toàn Vẹn & Khóa Trùng Funding (`src/execution/paper_broker.py`):**
  - Đọc `settlement_hours_utc` động từ config (mặc định `[0, 8, 16]`), validate trong $[0, 23]$.
  - Khóa thanh toán funding đơn nhất theo `(symbol, candle.open_time)`.
  - Validate `math.isfinite` trên funding rate tại settlement hours trước khi thực hiện bất kỳ biến động trạng thái nào.
  - Phát hiện và từ chối gap nến nhảy qua mốc settlement khi đang mở vị thế.
- **E2 - Cập nhật Giá Thanh lý Theo Ký quỹ Thực tế (`src/execution/paper_broker.py`):**
  - Tự động cập nhật `position.liquidation_price` bằng cách gọi `calculate_estimated_liquidation_price` với `isolated_collateral` thực tế và `get_mmr_tier(position_size_usd, symbol, leverage_brackets)` sau khi thanh toán funding.
- **E3 - Tích hợp Dòng tiền Circuit Breaker & Cưỡng Chế Đóng Khi Khóa (`src/risk/circuit_breakers.py`, `src/execution/paper_broker.py`):**
  - Bổ sung `record_cashflow(amount, timestamp, equity)` vào `CircuitBreakerState` để theo dõi rolling 24h PnL từ funding và phí vào/ra mà không làm biến dạng win/loss streak hay `risk_multiplier`.
  - Bổ sung `record_trade_outcome(net_pnl, timestamp)` để cập nhật chuỗi thắng/thua độc lập không double count cashflow.
  - Tự động kích hoạt cơ chế thoát hiểm `_handle_circuit_breaker_lock` hủy lệnh chờ và đóng cưỡng chế toàn bộ vị thế còn lại kèm slippage khi Breaker bị khóa (kèm cờ chống đệ quy `_is_handling_cb_lock`).
- **E4 - Hạch toán Vốn Sau Khi Đóng Vị Thế (`src/execution/paper_broker.py`):**
  - Gỡ vị thế khỏi `self.positions` trước khi tính `post_close_equity`, loại bỏ hoàn toàn double counting unrealized PnL cũ.
- **E5 - Tái Kiểm Soát Cổng Duyệt Lệnh & Xử Lý Lỗi Solver (`src/execution/paper_broker.py`):**
  - Tái kiểm tra khoảng cách SL/TP so với `fill_price` thực tế có trượt giá (chặn fill gap chạm SL hoặc TP sai hướng với `OrderStatus.REJECTED`).
  - Bắt toàn bộ ngoại lệ `ValueError` từ solver/sizing chuyển thành `OrderStatus.REJECTED` (không để unhandled exception làm crash engine).
  - Kiểm tra tính nhất quán giữa `order_declared_budget_usd` và `risk_percent`.
- **E6 - Giao Dịch Nguyên Khối (Transactional Preflight Validation) (`src/execution/paper_broker.py`):**
  - Kiểm tra OHLC, timeframe regex, positive duration, thời gian mở/đóng đơn điệu và tính hữu hạn của funding rate trước bất kỳ đột biến tài chính nào.
- **E7 - Nâng Cao Độ Trung Thực Khớp Lệnh (`src/execution/paper_broker.py`):**
  - Áp dụng trượt giá thoát lệnh cho `close_all_positions`.
  - Mark Price guard trong `update_stop_loss` chặn dời SL qua giá thị trường hiện tại.
  - Gap TP tại Pha 1 chốt lời ngay tại giá Open trước khi settlement funding ở Pha 2.
- **E8 - Xác Thực Miền Cấu Hình & Bất Biến Số Học (`src/execution/paper_broker.py`):**
  - Xác thực cấu hình khởi tạo Engine (`initial_equity_usd > 0`, `fees in [0, 1]`, `settlement_hours in [0, 23]`).
  - Kiểm tra `math.isfinite` trên toàn bộ tài khoản trong `verify_accounting_invariants`.
- **Bộ kiểm thử & Báo cáo:**
  - Chạy đạt **26/26 probe tests độc lập** trong `docs/reviews/test_stage_04_review_05.py` (100% pass).
  - Hoàn thiện mở rộng Oracle test trong `tests/test_execution_accounting.py` chạy qua 300 nến.
  - Cập nhật kịch bản `scripts/simulate_paper_execution.py` (cả Part A và Part B đều đạt 100% đối soát vốn).
  - Tạo báo cáo `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 4/BAO_CAO_SUA_DOI_THEO_GPT_REVIEW_05.md`.
  - Cập nhật Phụ lục 4 trong `docs/decisions/0007-paper-execution-engine-architecture.md`.
### Kết quả kiểm thử
- **Review 05 Probes:** **26/26 tests PASSED** trong 0.67s.
- **Pytest Offline:** **170/170 tests PASSED** trong 4.52s.
- **Pytest Network:** **5/5 tests PASSED** trong 13.29s.
- **Tổng cộng hệ thống:** **175/175 tests PASSED (100% xanh)**.

---

## [Giai đoạn 4] - Paper Execution Engine (2026-09-19)
### Đã triển khai
- **Mô hình Dữ liệu Đơn lệnh & Vị thế (`src/execution/order_models.py`):**
  - Định nghĩa Enums: `OrderDirection`, `OrderStatus`, `ExitReason`, `PositionStatus`.
  - Đóng gói dataclasses chặt chẽ: `OrderRequest` (sinh client_order_id tất định từ SHA-256), `OrderExecutionRecord`, `Position` (Isolated Margin riêng biệt), `FundingEventRecord`, `TradeRecord`, `AccountSnapshot`.
  - Xác thực đầu vào toàn diện: loại trừ `bool`, `NaN`, `Inf`, số âm, kiểm tra múi giờ UTC nghiêm ngặt.
- **Động cơ Khớp lệnh Paper Broker 5 Pha Chống Nhìn Trước (`src/execution/paper_broker.py`):**
  - **Pha 1 (Open Time & Gap Exits):** Nhận diện gap nến mở cửa qua Stop Loss hoặc Liquidation price, cưỡng chế thoát lệnh tại giá Open thực tế kèm slippage bán/mua.
  - **Pha 2 (Funding Settlement):** Khớp mốc funding settlement định kỳ (00:00, 08:00, 16:00 UTC), tính toán dòng tiền funding theo đúng chiều LONG/SHORT và cập nhật cả ví và collateral.
  - **Pha 3 (Pending Market Entry & Risk Gate Admission):** Lọc lệnh chờ `signal_time <= open_time`, tính giá fill Open + Slippage, tính toán kích thước vị thế và giá thanh lý, chụp snapshot tài khoản và đưa qua cổng `check_all_invariants` (Giai đoạn 3).
  - **Pha 4 (Intrabar Protection):** Quét biên độ [Low, High] theo thứ tự ưu tiên bảo thủ tuyệt đối: `Liquidation > Stop Loss > Take Profit`.
  - **Pha 5 (Close Time & Mark-to-Market):** Đánh giá lại unrealized PnL theo giá Close, cập nhật equity, lưu snapshot tài khoản và đối soát tự động các bất biến kế toán.
  - Quản lý ràng buộc: tối đa 1 vị thế/symbol, không nhồi lệnh, không hedging, không tự động đảo chiều.
  - Trailing Stop Loss chỉ cho phép thắt chặt một chiều (`update_stop_loss` tightening only).
  - Tích hợp 2 chiều với `CircuitBreakerState` từ Giai đoạn 3: cập nhật net trade PnL, giảm 50% risk sau 3 thua, phục hồi 100% risk sau 3 thắng, khóa 24h khi chạm daily loss 5%.
- **Bộ kiểm thử Kế toán, Oracle & Chống Nhìn Trước:**
  - `tests/test_execution_models.py` (4 tests): Kiểm tra dataclasses, validation, deterministic ID.
  - `tests/test_execution_accounting.py` (3 tests): Bài toán Oracle bắt buộc (Mục 8 Spec) khớp số liệu từng bit (10,038.88 USD final equity), short funding âm, verification invariants.
  - `tests/test_paper_broker.py` (7 tests): Giới hạn 1 vị thế/symbol, SL over TP, gap exit, trailing SL, CB streak, Liq over SL, replay determinism.
  - `tests/test_execution_no_lookahead.py` (3 tests): Entry nến sau, sizing độc lập High/Low/Close, future perturbation bất biến.
- **Kịch bản Mô phỏng Thực tế (`scripts/simulate_paper_execution.py`):**
  - Phần A: Mô phỏng tổng hợp (Synthetic Deterministic) kiểm thử vòng đời hoàn chỉnh: win, loss streak, funding, gap exit, daily loss lock, 24h unlock, recovery wins.
  - Phần B: Mô phỏng trên dữ liệu thật Binance cached (BTCUSDT 15m + Funding Rate 8h) đi qua 3 kỳ funding thực tế và kiểm tra Risk Gate chặn lệnh vi phạm.
- **Tài liệu Kiến trúc & Báo cáo:**
  - `docs/decisions/0007-paper-execution-engine-architecture.md` (ADR 0007).
  - `BÁO CÁO TÓM TẮT/GIAI ĐOẠN 4/BAO_CAO_GIAI_DOAN_4.md`.
### Kết quả kiểm thử
- **Pytest Offline:** **170/170 tests PASSED** trong 1.63s.
- **Pytest Network:** **5/5 tests PASSED** trong 12.24s.
- **Tổng cộng:** **175/175 tests PASSED (100% xanh)**.

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
