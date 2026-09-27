# BÁO CÁO SỬA ĐỔI THEO GPT REVIEW 05 — GIAI ĐOẠN 4 (PAPER EXECUTION ENGINE)

**Ngày thực hiện:** 2026-09-19  
**Người thực hiện:** Antigravity  
**Tham chiếu:** `crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_05.md`  
**Hồ sơ tiếp nối:** `PLANNER_HANDOVER.md`, `PROJECT_STATE.md`  

---

## 1. TỔNG QUAN

Sau khi nhận kết quả đánh giá độc lập từ GPT Review 05 đối với mã nguồn tại commit `e4cb87b975d3404fbe73b31281d1d9697522cce0` (trong đó reviewer chỉ ra 8 nhóm thiếu sót kỹ thuật E1–E8 kèm bộ 26 probe tests độc lập `test_stage_04_review_05.py`), Antigravity đã hoàn thành việc rà soát và khắc phục toàn diện 100% các vấn đề được nêu.

Toàn bộ nguyên tắc thiết kế bất biến được giữ vững tuyệt đối:
1. **Chống nhìn trước 100% (No Lookahead Bias):** Signal trên nến trước $\to$ Admission & Fill trên Open nến sau.
2. **Bảo tồn tính toán rủi ro (Risk Invariants):** Không nới lỏng bất kỳ ngưỡng rủi ro hay bypass bất biến nào.
3. **Kế toán chính xác từng bit (Bit-exact Accounting):** Toàn bộ phí, funding và PnL được đối soát tự động sau mỗi nến và sau mỗi giao dịch.

---

## 2. CHI TIẾT SỬA ĐỔI THEO 8 NHÓM PHÁT HIỆN E1–E8

### 2.1 E1 — Cấu hình Settlement Hours, Tính Toàn Vẹn & Khóa Trùng Funding
- **Đọc mốc thanh toán từ cấu hình:** Đọc `settlement_hours_utc` từ `config['execution']['settlement_hours_utc']` (mặc định `[0, 8, 16]`). Toàn bộ giờ được kiểm tra thuộc $[0, 23]$, không trùng lặp và được sắp xếp tăng dần.
- **Khóa thanh toán đơn nhất (Idempotency Key):** Sử dụng tập hợp `self.settled_funding_keys` lưu trữ cặp `(symbol, candle.open_time)`. Mỗi cây nến chỉ được thanh toán funding tối đa một lần cho mỗi symbol.
- **Xác thực dữ liệu Funding Rate trước đột biến:** Khi nến rơi vào mốc thanh toán funding, nếu `funding_rate` bị khuyết (`None`) hoặc không hữu hạn (`NaN`, `Inf`), Broker lập tức từ chối và ném `ValueError` ngay tại bước kiểm tra đầu vào, không làm thay đổi bất kỳ trạng thái tài chính nào.
- **Bắt hiện tượng nhảy Gap bỏ qua Settlement:** Khi vị thế đang mở, nếu bước nhảy thời gian giữa hai nến liên tiếp vượt qua một hoặc nhiều mốc settlement hours mà không có dữ liệu nến tương ứng, Broker phát hiện và từ chối xử lý nến để ngăn chặn việc lẩn tránh phí funding.

### 2.2 E2 — Cập nhật Giá Thanh lý Theo Ký quỹ Thực tế (Collateral-Aware Liquidation)
- **Tái tính toán động:** Khi dòng tiền funding được ghi nhận vào `isolated_collateral`, tỷ lệ đòn bẩy thực tế thay đổi.
- Động cơ tự động gọi lại hàm giải thanh lý `calculate_estimated_liquidation_price` với `isolated_collateral` cập nhật và tra cứu đúng MMR tier qua `get_mmr_tier(position_size_usd, symbol, leverage_brackets)`, đảm bảo `position.liquidation_price` luôn phản ánh chính xác rủi ro phá sản thực tế theo thời gian thực.

### 2.3 E3 — Tích Hợp Dòng Tiền Circuit Breaker & Cưỡng Chế Đóng Khi Khóa
- **Tách biệt Dòng tiền và Chuỗi giao dịch trong `CircuitBreakerState`:**
  - Bổ sung phương thức `record_cashflow(amount, timestamp, equity)`: ghi nhận ngay lập tức phí giao dịch và funding cashflow vào cửa sổ trượt lỗ 24h mà không làm biến dạng chuỗi thắng/thua (`consecutive_wins`, `consecutive_losses`) và không thay đổi `risk_multiplier`.
  - Bổ sung `record_trade_outcome(net_pnl, timestamp)`: cập nhật chuỗi thắng/thua sau khi đóng lệnh mà không cộng trùng dòng tiền.
  - Duy trì tương thích ngược 100% cho `record_trade_result(pnl, timestamp, equity)`.
- **Cơ chế thoát hiểm khẩn cấp (`_handle_circuit_breaker_lock`):**
  - Khi tổng lỗ rolling 24h chạm ngưỡng 5% khiến Circuit Breaker kích hoạt khóa (`is_locked = True`), Paper Broker tự động hủy toàn bộ lệnh chờ (`pending_orders`) và cưỡng chế đóng toàn bộ vị thế đang mở còn lại theo giá thị trường (có áp dụng exit slippage) với mã lý do `CIRCUIT_BREAKER_LOCK`.
  - Bổ sung cờ `_is_handling_cb_lock` chống đệ quy khi các lệnh đóng cưỡng chế báo cáo kết quả về Breaker.

### 2.4 E4 — Hạch toán Vốn Sau Khi Đóng Vị Thế (Post-Close Equity)
- **Loại bỏ Double Counting:** Khi thực hiện đóng một vị thế (`_close_position`), vị thế đó được gỡ bỏ khỏi danh mục `self.positions` trước khi tính toán `post_close_equity` để chuyển tới Circuit Breaker.
- Nhờ vậy, số dư `post_close_equity` gửi vào Circuit Breaker phản ánh chính xác 100% tài sản ròng thực tế của ví, không bị cộng dồn trùng lặp với `unrealized_pnl` cũ của chính vị thế vừa đóng.

### 2.5 E5 — Tái Kiểm Soát Cổng Duyệt Lệnh & Xử Lý Lỗi Solver
- **Tái kiểm tra khoảng cách Stop Loss / Take Profit sau trượt giá (`fill_price`):**
  - Nếu thị trường nhảy Gap khiến `fill_price` chạm hoặc vượt qua `stop_loss_price`, lệnh bị từ chối sạch sẽ với trạng thái `ORDER_REJECTED` (`REASON: Fill price crossed stop loss`).
  - Nếu Take Profit nằm sai phía so với `fill_price` thực tế, lệnh bị từ chối với trạng thái `ORDER_REJECTED`.
- **Bắt trọn ngoại lệ toán học:** Toàn bộ ngoại lệ `ValueError` phát sinh từ bài toán định cỡ vị thế (`calculate_position_size`) hoặc giải giá thanh lý (`calculate_estimated_liquidation_price`) được bắt trọn và chuyển hóa thành `OrderStatus.REJECTED` kèm mô tả chi tiết, không làm crash nến.
- **Kiểm soát ngân sách khai báo:** Kiểm tra khớp đúng giữa `order_declared_budget_usd` và `risk_percent` cấu hình, ngăn chặn việc khai báo sai lệch.

### 2.6 E6 — Giao Dịch Nguyên Khối (Transactional Preflight Validation)
- **Zero-Mutation Guard:** Trước khi thay đổi bất kỳ biến trạng thái nào trong `process_candle`, Broker kiểm tra toàn diện:
  - Tính hợp lệ hình học OHLC: $High \ge \max(Open, Close)$ và $Low \le \min(Open, Close)$, $High \ge Low > 0$.
  - Định dạng chuỗi timeframe: khớp regex chuẩn (ví dụ `15m`, `1h`, `4h`) và có thời lượng dương $> 0$.
  - Tính đơn điệu nghiêm ngặt: $open\_time > last\_candle\_open\_time$.
  - Tính nhất quán thời gian đóng: $close\_time > open\_time$ và đúng thời lượng nến.
- Nếu bất kỳ điều kiện nào không thỏa mãn, ném ngoại lệ và bảo toàn 100% trạng thái của Broker và Breaker.

### 2.7 E7 — Nâng Cao Độ Trung Thực Khớp Lệnh (Execution Fidelity)
- **Exit Slippage khi Force Close:** Hàm `close_all_positions` áp dụng trượt giá thoát lệnh (`slippage_pct`) theo đúng hướng đóng vị thế (bán giá thấp hơn cho LONG, mua giá cao hơn cho SHORT).
- **Mark Price Guard khi Tighten Stop Loss:** Hàm `update_stop_loss` kiểm tra giá dừng mới không được phép vượt qua giá thị trường hiện tại (Mark Price).
- **Gap Take Profit Priority tại Pha 1:** Nếu nến mở cửa nhảy Gap qua giá Take Profit, vị thế được chốt lời ngay tại giá Open trước khi tính toán phí Funding ở Pha 2.

### 2.8 E8 — Xác Thực Miền Cấu Hình & Bất Biến Số Học
- **Xác thực cấu hình khởi tạo:** `initial_equity_usd` phải là số thực hữu hạn $> 0$; các tham số phí (`taker_pct`, `slippage_pct`) phải là số thực hữu hạn thuộc $[0, 1.0]$.
- **Gia cố kiểm tra bất biến (`verify_accounting_invariants`):** Bổ sung kiểm tra `math.isfinite` trên toàn bộ số dư ví, ký quỹ khả dụng, ký quỹ cô lập và tổng unrealized PnL trước khi so sánh dung sai sai số.

---

## 3. KẾT QUẢ KIỂM THỬ THỰC TẾ

### 3.1 Bộ Kiểm Thử Độc Lập GPT Review 05 (`docs/reviews/test_stage_04_review_05.py`)
- **Kết quả:** **26/26 tests PASSED (100% xanh)** trong 0.67s.
```text
collected 26 items

docs/reviews/test_stage_04_review_05.py::test_control_flat_oracle_without_funding PASSED [  3%]
docs/reviews/test_stage_04_review_05.py::test_control_stop_tightening_refuses_widening PASSED [  7%]
docs/reviews/test_stage_04_review_05.py::test_E1_missing_or_nonfinite_funding_fails_before_state_mutation[None] PASSED [ 11%]
docs/reviews/test_stage_04_review_05.py::test_E1_missing_or_nonfinite_funding_fails_before_state_mutation[nan] PASSED [ 15%]
docs/reviews/test_stage_04_review_05.py::test_E1_configured_settlement_hours_are_used PASSED [ 19%]
docs/reviews/test_stage_04_review_05.py::test_E1_gap_skipping_settlement_is_rejected PASSED [ 23%]
docs/reviews/test_stage_04_review_05.py::test_E2_liquidation_tracks_actual_funded_collateral PASSED [ 26%]
docs/reviews/test_stage_04_review_05.py::test_E3_funding_updates_rolling_cashflow_immediately_without_trade_streak PASSED [ 30%]
docs/reviews/test_stage_04_review_05.py::test_E3_lock_closes_all_other_active_positions PASSED [ 34%]
docs/reviews/test_stage_04_review_05.py::test_E4_breaker_receives_post_close_equity_without_closed_unrealized PASSED [ 38%]
docs/reviews/test_stage_04_review_05.py::test_E5_gap_fill_equal_stop_is_clean_order_rejection PASSED [ 42%]
docs/reviews/test_stage_04_review_05.py::test_E5_take_profit_revalidated_against_actual_fill PASSED [ 46%]
docs/reviews/test_stage_04_review_05.py::test_E5_unsupported_entry_type_is_rejected PASSED [ 50%]
docs/reviews/test_stage_04_review_05.py::test_E5_explicit_declared_risk_not_silently_ignored PASSED [ 53%]
docs/reviews/test_stage_04_review_05.py::test_E6_invalid_close_time_has_no_financial_mutation PASSED [ 57%]
docs/reviews/test_stage_04_review_05.py::test_E6_invalid_duration_rejected_without_mutation[0m] PASSED [ 61%]
docs/reviews/test_stage_04_review_05.py::test_E6_invalid_duration_rejected_without_mutation[-1m] PASSED [ 65%]
docs/reviews/test_stage_04_review_05.py::test_E6_invalid_duration_rejected_without_mutation[nonsense] PASSED [ 69%]
docs/reviews/test_stage_04_review_05.py::test_E7_force_close_applies_exit_slippage PASSED [ 73%]
docs/reviews/test_stage_04_review_05.py::test_E7_stop_update_cannot_cross_current_mark PASSED [ 76%]
docs/reviews/test_stage_04_review_05.py::test_E7_gap_take_profit_exits_at_open_phase_before_funding PASSED [ 80%]
docs/reviews/test_stage_04_review_05.py::test_E8_invalid_engine_configuration_is_rejected[fees-slippage_pct-nan] PASSED [ 84%]
docs/reviews/test_stage_04_review_05.py::test_E8_invalid_engine_configuration_is_rejected[fees-slippage_pct--0.01] PASSED [ 88%]
docs/reviews/test_stage_04_review_05.py::test_E8_invalid_engine_configuration_is_rejected[fees-slippage_pct-1.1] PASSED [ 92%]
docs/reviews/test_stage_04_review_05.py::test_E8_invalid_engine_configuration_is_rejected[account-initial_equity_usd-nan] PASSED [ 96%]
docs/reviews/test_stage_04_review_05.py::test_E8_invalid_engine_configuration_is_rejected[account-initial_equity_usd--100.0] PASSED [100%]

======================== 26 passed, 1 warning in 0.67s ========================
```

### 3.2 Toàn Bộ Test Suite Dự Án (`tests/`)
- **Kết quả:** **175/175 tests PASSED (100% xanh)** trong 14.96s (170 offline tests + 5 network integration tests).
```text
collected 175 items

tests\test_circuit_breakers.py ................                          [  9%]
tests\test_cvd.py ....                                                   [ 11%]
tests\test_data_layer.py .........................                       [ 25%]
tests\test_execution_accounting.py ...                                   [ 27%]
tests\test_execution_models.py ....                                      [ 29%]
tests\test_execution_no_lookahead.py ...                                 [ 31%]
tests\test_indicators.py .........                                       [ 36%]
tests\test_invariant_checks.py ......................................... [ 60%]
......                                                                   [ 63%]
tests\test_liquidation_calc.py ...............                           [ 72%]
tests\test_news_calendar.py .........                                    [ 77%]
tests\test_no_lookahead.py ......                                        [ 80%]
tests\test_oi_features.py ......                                         [ 84%]
tests\test_paper_broker.py .......                                       [ 88%]
tests\test_position_sizing.py .....................                      [100%]

======================= 175 passed, 1 warning in 14.96s =======================
```

### 3.3 Kịch Bản Mô Phỏng Khớp Lệnh (`scripts/simulate_paper_execution.py`)
- **Phần A (Synthetic Deterministic):** 100% các sự kiện mở lệnh, funding 3 kỳ, gap exit, 24h daily loss lock và unlock phục hồi sau 3 trận thắng hoạt động chuẩn xác; đối soát vốn `assert errors == 0`.
- **Phần B (Binance Real Cached Data):** Chạy thông suốt trên 100 nến BTCUSDT 15m thực tế; đối soát kế toán đạt 100% không phát sinh sai lệch; Risk Gate chặn đứng lệnh vi phạm khi đang có vị thế hoạt động.

---

## 4. KẾT LUẬN & TRẠNG THÁI TIẾP NỐI

1. **Tuân thủ kỷ luật nghiệm thu:** Toàn bộ 8 nhóm phát hiện E1–E8 đã được giải quyết triệt để và kiểm chứng bằng cả test suite hiện có lẫn bộ test probe độc lập của Review 05.
2. **Dừng chờ GPT Review 06:** Antigravity commit và push toàn bộ thay đổi lên `main`, dừng tại đây chờ GPT Review 06 kiểm tra và đánh giá lại.
3. **Tuyệt đối không tự ý chuyển sang Giai đoạn 5 (Alpha Discovery & Strategy Development)** khi chưa có quyết định chính thức từ người dùng.
