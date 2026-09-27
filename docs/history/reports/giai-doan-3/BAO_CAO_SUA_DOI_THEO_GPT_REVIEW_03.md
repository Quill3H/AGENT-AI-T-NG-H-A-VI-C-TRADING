# BÁO CÁO SỬA ĐỔI THEO GPT REVIEW LẦN 3 (STAGE 3: RISK MANAGER)

**Thời điểm thực hiện:** 2026-09-19  
**Tài liệu đánh giá đầu vào:** `crypto-paper-agent/docs/reviews/GPT_STAGE_03_REVIEW_03.md`  
**Bản commit gốc được review:** `2f3bc30709fa3e24ccb0a0ebbc7823f0ef779522`  
**Trạng thái:** HOÀN THÀNH TOÀN BỘ 3 HẠNG MỤC (G1, G2, G3) | TEST SUITE 158/158 PASS 100%  

---

## 1. TỔNG QUAN KẾT QUẢ XỬ LÝ (G1 – G3)

Đợt phản biện kỹ thuật độc lập lần 3 của GPT đã chỉ ra 3 điểm còn lại trong cơ chế bảo vệ của cổng duyệt lệnh (Risk Admission Gate). Cả 3 hạng mục đã được xử lý triệt để, có kiểm chứng hồi quy độc lập:

| Mã | Hạng mục | Vấn đề phát hiện | Giải pháp kỹ thuật đã triển khai | File / Hàm xử lý | Trạng thái |
|---|---|---|---|---|---|
| **G1** | Xác thực Cấu hình & Trạng thái | `min_liquidation_buffer_pct` bằng `NaN` làm tê liệt phép so sánh buffer; `min_liquidation_buffer_pct = "bad"` văng `ValueError`; `cb.risk_multiplier = NaN` ngầm fallback 1.0 (nhận full risk); `max_leverage`, `conviction_tiers`, `taker_pct` thiếu validate miền giá trị hữu hạn. | 1. Validate `math.isfinite` và kiểu số thực nghiêm ngặt cho toàn bộ `config.risk` (`max_leverage >= 1.0`, `min_liquidation_buffer_pct in (0, 1)`, `conviction_tiers > 0`) và `config.fees.taker_pct >= 0`. Nếu sai kiểu/NaN/Inf/chuỗi sai, trả `INVARIANT_FAIL_CONFIG_ERROR`.<br>2. Bỏ qua so sánh buffer nếu `min_buffer_valid` là False (chống NaN bypass).<br>3. Validate `cb_state.risk_multiplier` phải là số hữu hạn trong (0, 1.0] và khớp với trạng thái hợp lệ (1.0 hoặc `risk_reduction_on_streak`). Nếu sai, trả `INVARIANT_FAIL_INVALID_CIRCUIT_BREAKER_STATE`, tuyệt đối không fallback 1.0.<br>4. Validate `cb_state.is_locked` phải là boolean. | `src/risk/invariant_checks.py`<br>(hàm `check_all_invariants`) | **ĐÃ XỬ LÝ XONG** |
| **G2** | Cổng Duyệt & Lùi Thời gian Breaker | `cb.advance_time(T+1h)` sau đó gate nhận `account.current_time = T` làm văng unhandled `ValueError` từ `CircuitBreakerState` thay vì trả về `(False, reasons)` theo hợp đồng của gate. | 1. Tại cổng duyệt lệnh, so sánh `admission_time < cb_state.current_timestamp`. Nếu có lùi thời gian, ghi nhận `INVARIANT_FAIL_TIME_REVERSAL` vào danh sách lý do từ chối.<br>2. **Không gọi** `cb_state.is_trading_allowed(admission_time)` khi lùi thời gian, giúp bảo toàn nguyên vẹn đồng hồ, lịch sử giao dịch và trạng thái khóa của Breaker.<br>3. Bọc try/except `ValueError` phòng hộ cho component call.<br>4. Tiếp tục chạy các kiểm tra invariant độc lập khác để gom đủ lý do vi phạm.<br>5. Giữ nguyên vẹn hợp đồng toán học trực tiếp của `CircuitBreakerState` (ném `ValueError` khi lùi thời gian). | `src/risk/invariant_checks.py`<br>(hàm `check_all_invariants`) | **ĐÃ XỬ LÝ XONG** |
| **G3** | Trạng thái Sẵn sàng của Bộ lọc Tin tức | Khi `news_filter.enabled = True` nhưng file CSV lịch không tồn tại hoặc lỗi, `NewsCalendarFilter` log warning nhưng vẫn để `events = []`, khiến gate trả về `(True, [])` coi như filter đang hoạt động bình thường. | 1. Thêm thuộc tính `is_ready: bool` và `load_error: Optional[str]` vào `NewsCalendarFilter`.<br>2. Quy ước rõ: `enabled = False` => bypass (`is_ready = True`). Khi `enabled = True`, bắt buộc nạp lịch thành công (`is_ready = True`).<br>3. Nếu file thiếu, không đọc được, sai schema (thiếu cột time/event), hoặc có dòng chứa timestamp/sự kiện hỏng (`NaT`, rác) -> đánh dấu `is_ready = False` và ghi nhận `load_error = "CALENDAR_LOAD_ERROR: ..."` (không nuốt lỗi).<br>4. Tại gate, nếu `news_filter` chưa ready -> chặn lệnh với `INVARIANT_FAIL_NEWS_FILTER_NOT_READY`.<br>5. File CSV có header hợp lệ nhưng 0 dòng sự kiện được xác nhận là hợp lệ (`is_ready = True`, `events = []`).<br>6. Cung cấp API `set_events` và phục hồi khi reload lịch. | `src/features/news_calendar.py`<br>`src/risk/invariant_checks.py` | **ĐÃ XỬ LÝ XONG** |

---

## 2. BẢNG MAPPING CHI TIẾT TỪNG TEST CASE HỒI QUY (REGRESSION SUITE)

Hệ thống bổ sung tổng cộng **15 unit tests mới** chuyên biệt để khóa chặt các tình huống reviewer đã kiểm thử độc lập:

| Nhóm | Tên Test Case | File | Mục đích kiểm chứng | Kết quả |
|---|---|---|---|---|
| **G1** | `test_g1_min_liquidation_buffer_nan_rejected` | `test_invariant_checks.py` | `min_liquidation_buffer_pct = NaN` bị chặn bởi `INVARIANT_FAIL_CONFIG_ERROR`, không bypass buffer check. | **PASSED** |
| **G1** | `test_g1_min_liquidation_buffer_string_rejected_no_crash` | `test_invariant_checks.py` | `min_liquidation_buffer_pct = 'bad'` bị chặn sạch sẽ, không crash unhandled ValueError. | **PASSED** |
| **G1** | `test_g1_circuit_breaker_multiplier_nan_rejected` | `test_invariant_checks.py` | `cb.risk_multiplier = NaN` bị chặn bởi `INVARIANT_FAIL_INVALID_CIRCUIT_BREAKER_STATE`, không fallback 1.0. | **PASSED** |
| **G1** | `test_g1_circuit_breaker_multiplier_invalid_values_rejected` | `test_invariant_checks.py` | Kiểm tra các giá trị bất thường: `0.0`, `-0.5`, `1.5`, `"0.5"`, `True`, `Inf` đều bị từ chối. | **PASSED** |
| **G1** | `test_g1_circuit_breaker_is_locked_non_bool_rejected` | `test_invariant_checks.py` | `cb.is_locked = "locked"` bị từ chối sạch sẽ. | **PASSED** |
| **G1** | `test_g1_max_leverage_invalid_rejected` | `test_invariant_checks.py` | `max_leverage` là `NaN`, `Inf`, `< 1.0`, string hoặc bool đều bị từ chối. | **PASSED** |
| **G1** | `test_g1_conviction_tiers_corrupted_rejected` | `test_invariant_checks.py` | `conviction_tiers` chứa giá trị `NaN` hoặc sai cấu trúc bị từ chối. | **PASSED** |
| **G1** | `test_g1_taker_fee_invalid_rejected` | `test_invariant_checks.py` | `fees.taker_pct` là `NaN`, âm, chuỗi hoặc bool đều bị từ chối. | **PASSED** |
| **G1** | `test_g1_multiple_independent_errors_all_collected` | `test_invariant_checks.py` | Kết hợp thiếu SL + config hỏng + cb state hỏng: thu thập đủ cả 3 mã lỗi, không crash. | **PASSED** |
| **G2** | `test_g2_time_reversal_rejected_cleanly_without_exception` | `test_invariant_checks.py` | Lùi thời gian qua gate trả `INVARIANT_FAIL_TIME_REVERSAL`, không văng exception; đồng hồ và trạng thái cb giữ nguyên. | **PASSED** |
| **G2** | `test_g2_time_reversal_accumulates_independent_errors` | `test_invariant_checks.py` | Lùi thời gian kết hợp thiếu Stop Loss: thu thập đủ cả 2 lỗi vi phạm độc lập. | **PASSED** |
| **G2** | `test_g2_direct_circuit_breaker_still_raises_value_error` | `test_invariant_checks.py` | Gọi trực tiếp `advance_time` hoặc `record_trade_result` lùi thời gian vẫn ném `ValueError` chuẩn. | **PASSED** |
| **G3** | `test_g3_news_filter_enabled_missing_file_rejected_at_gate` | `test_invariant_checks.py` | `enabled = True` nhưng file CSV không có -> gate từ chối với `INVARIANT_FAIL_NEWS_FILTER_NOT_READY`. | **PASSED** |
| **G3** | `test_g3_news_filter_enabled_malformed_csv_rejected_at_gate` | `test_invariant_checks.py` | `enabled = True` nhưng thiếu cột bắt buộc -> gate từ chối sạch sẽ. | **PASSED** |
| **G3** | `test_g3_news_filter_enabled_corrupted_rows_rejected_at_gate` | `test_invariant_checks.py` | `enabled = True` nhưng CSV có dòng timestamp hỏng -> gate từ chối, không nuốt lỗi. | **PASSED** |
| **G3** | `test_g3_news_filter_enabled_empty_valid_csv_passes` | `test_invariant_checks.py` | File CSV có header nhưng 0 dòng sự kiện -> `is_ready = True`, gate cho phép giao dịch. | **PASSED** |
| **G3** | `test_g3_news_filter_disabled_bypasses_even_if_unready` | `test_invariant_checks.py` | Mặc định `enabled = False` -> bypass hoàn toàn, không yêu cầu lịch. | **PASSED** |
| **G3** | `test_news_calendar_missing_file_marks_unready` | `test_news_calendar.py` | `NewsCalendarFilter` đánh dấu `is_ready = False` và lưu `load_error` khi thiếu file. | **PASSED** |
| **G3** | `test_news_calendar_missing_columns_marks_unready` | `test_news_calendar.py` | Đánh dấu `is_ready = False` khi file CSV thiếu cột thời gian hoặc tên sự kiện. | **PASSED** |
| **G3** | `test_news_calendar_corrupted_row_marks_unready` | `test_news_calendar.py` | Đánh dấu `is_ready = False` khi dòng CSV chứa timestamp NaT/rác. | **PASSED** |
| **G3** | `test_news_calendar_empty_valid_csv_marks_ready` | `test_news_calendar.py` | Đánh dấu `is_ready = True`, `events = []` khi file CSV rỗng nhưng đúng header. | **PASSED** |
| **G3** | `test_news_calendar_reload_after_error_recovers_readiness` | `test_news_calendar.py` | Cơ chế phục hồi nạp lại lịch hợp lệ chuyển `is_ready` từ `False` sang `True`. | **PASSED** |
| **G3** | `test_news_calendar_set_events_fixture_support` | `test_news_calendar.py` | Hỗ trợ inject events và cập nhật readiness tường minh cho test fixture. | **PASSED** |

---

## 3. KẾT QUẢ THỰC THI KIỂM THỬ THỰC TẾ (RAW EXECUTION OUTPUT)

### 3.1 Bộ kiểm thử Offline (Unit & Regression Tests)
- **Môi trường:** Windows, Python 3.13.14, pytest 9.1.1, pluggy 1.6.0
- **Lệnh thực thi:** `pytest -m "not network" -q`
- **Output:**
```text
tests\test_circuit_breakers.py ................                          [ 10%]
tests\test_cvd.py ....                                                   [ 13%]
tests\test_data_layer.py ....................                            [ 26%]
tests\test_indicators.py .........                                       [ 32%]
tests\test_invariant_checks.py ......................................... [ 58%]
......                                                                   [ 62%]
tests\test_liquidation_calc.py ...............                           [ 72%]
tests\test_news_calendar.py .........                                    [ 78%]
tests\test_no_lookahead.py ......                                        [ 82%]
tests\test_oi_features.py ......                                         [ 86%]
tests\test_position_sizing.py .....................                      [100%]

================ 153 passed, 5 deselected, 1 warning in 1.64s =================
```

### 3.2 Bộ kiểm thử Network (Live Exchange Data)
- **Lệnh thực thi:** `pytest -m "network" -q`
- **Output:**
```text
tests\test_data_layer.py .....                                           [100%]

================ 5 passed, 153 deselected, 1 warning in 11.62s ================
```

**Tổng cộng toàn repo:** **158 tests collected, 158/158 PASSED (100%)**.

### 3.3 Chạy Mô phỏng 10 Lệnh (`simulate_risk_manager_10_trades.py`)
- **Lệnh thực thi:** `python scripts/simulate_risk_manager_10_trades.py`
- **Kết quả xác thực vốn:**
  - Vốn đầu Phase 1: 10,000.00 USD | Vốn sau Phase 1: 9,170.00 USD (PnL: -830.00 USD)
  - Vốn đầu Phase 2: 9,170.00 USD | Vốn sau Phase 2: 9,470.00 USD (PnL: +300.00 USD)
  - Đối soát vốn: CHÍNH XÁC 100% (Vốn cuối = Vốn đầu + Tổng PnL các lệnh được duyệt)
  - Khóa 24h kích hoạt tại lệnh #8 khi lỗ rolling 24h đạt -830$ (vượt trần 5% = -458.50$).
  - Các lệnh #9, #10 trong thời gian khóa bị từ chối sạch sẽ với `INVARIANT_FAIL_CIRCUIT_BREAKER_LOCKED`.
  - Phục hồi risk từ 0.5 lên 1.0 sau đúng 3 lệnh thắng liên tiếp (#11, #12, #13) ở Phase 2.

---

## 4. GIỚI HẠN & CAM KẾT KỸ THUẬT

1. **Không tuyên bố triệt tiêu mọi rủi ro thị trường:**
   - Risk Manager đảm bảo tính toàn vẹn toán học và bảo vệ tài khoản trước các trạng thái dữ liệu lỗi, vi phạm tham số, trượt giá mô phỏng và biến động bất lợi trong phạm vi các quy tắc (invariants) đã định nghĩa.
   - Các rủi ro hệ thống ngoại vi (như sàn ngừng khớp lệnh hoàn toàn trong flash crash, thanh khoản cạn kiệt tuyệt đối khiến trượt giá vượt Stop-Loss thực tế) thuộc về rủi ro thị trường cơ sở của giao dịch phái sinh và cần được kiểm soát thêm ở tầng thực thi live.
2. **Quy ước về Lịch Tin tức (News Calendar):**
   - Chế độ mặc định của hệ thống vẫn là `news_filter.enabled = False` để phục vụ paper trading không phụ thuộc nguồn dữ liệu ngoài.
   - Khi người dùng chủ động bật `enabled = True`, hệ thống áp dụng chính sách nghiêm ngặt: lịch phải được cung cấp đầy đủ và hợp lệ; bất kỳ lỗi đọc lịch nào đều chuyển thành từ chối mở lệnh để đảm bảo nguyên tắc phòng vệ rủi ro.

---

## 5. KẾT LUẬN & BƯỚC TIẾP THEO

- **Giai đoạn 3 (Risk Manager):** Đã hoàn tất sửa đổi toàn bộ các phát hiện từ GPT Review 01, 02 và 03.
- **Trạng thái:** DỪNG CHỜ NGHIỆM THU. Tuyệt đối KHÔNG tự ý triển khai Giai đoạn 4 khi chưa có xác nhận từ người dùng.
