# GPT REVIEW 03 — Giai đoạn 3: ba điểm còn lại
**Verdict: FIX REQUIRED (đợt sửa nhỏ).** Chưa đóng giai đoạn 3, chưa triển khai giai đoạn 4.
Bản được review: 2f3bc30709fa3e24ccb0a0ebbc7823f0ef779522.
Các yêu cầu dưới đây là phần còn lại của F2/F3 trong Review 02, không mở rộng thêm strategy hoặc engine.

## Bằng chứng đã kiểm tra
Đã đọc diff commit, ba module risk, news_calendar, ADR 0006/phụ lục, PROJECT_STATE/CHANGELOG và báo cáo REVIEW_02.
Chạy offline trên Linux/Python 3.12.14: **128 passed, 2 skipped, 5 deselected**, tổng 135 collected.
Hai skip: test đối chiếu pandas-ta chưa cài trong môi trường reviewer. Năm network thuộc Data Layer chưa chạy lại; 135/135 là kết quả Antigravity báo, reviewer không xác nhận lại toàn bộ.
Riêng 82 test giai đoạn 3 (sizing 21, liquidation 15, breaker 16, invariants 30) đều đạt.
Script mô phỏng: 13 dòng minh bạch; vốn cuối 9470 USD, multiplier 1.0, assertion đối soát vốn đạt.
Reviewer tạo 9 tests độc lập ngoài repo: **4 passed, 5 failed**.
Bốn pass xác nhận đã sửa: khai 1% nhưng risk thực 4% bị chặn; NaN available margin bị chặn; khoản lỗ mới sau expiry khóa lại đúng; liquidation ngoài snapshot cap bị chặn.

## Tình huống gốc cho các regression
T=2026-09-01T10:00:00Z.
Order: LONG BTCUSDT, entry=50000, stop=49000, leverage=3, risk_percent=.02,
conviction_tier=normal, position_size_usd=10000, timestamp=T.
Account: equity=10000, available_margin=10000, CircuitBreakerState mới hợp lệ,
current_time=T, news_filter=None.
Config=default_config.yaml hiện có.

## G1 — P1: Config/state lỗi bị bỏ qua hoặc fallback làm mất bảo vệ
Vị trí: invariant_checks.py phần raw_cb_mult, raw_max_lev, raw_taker, min_buffer_pct.
1. Set config.risk.min_liquidation_buffer_pct=NaN, order leverage=5: gate trả (True, []). Buffer thực khoảng 17.68%, thấp hơn 30%, nhưng NaN vô hiệu hóa comparison.
2. Set cb.risk_multiplier=NaN: gate fallback 1.0 và chấp nhận full-risk order. Một state lỗi không được hiểu thành phục hồi risk.
3. Set min_liquidation_buffer_pct="bad": unhandled ValueError tại dòng 644.
Sửa đúng phạm vi:
- Validate config/state trước arithmetic, trả INVARIANT_FAIL_CONFIG_ERROR hoặc INVALID_CIRCUIT_BREAKER_STATE; không im lặng lấy full risk/default khi trường đã có nhưng lỗi.
- Default chỉ áp dụng cho field tùy chọn thực sự thiếu theo contract đã công bố, không áp dụng cho field có giá trị NaN/bool/chuỗi sai.
- risk config và subconfig phải đúng cấu trúc; max_leverage hữu hạn >=1, min_buffer hữu hạn và trong miền chính sách, tier limits hữu hạn dương, fees hữu hạn không âm. Giữ default project 5x/30% và recovery 3 thắng, không giảm yêu cầu để lấy test xanh.
- Circuit breaker đúng class/contract; multiplier phải hữu hạn và thuộc state hợp lệ (1.0 hoặc risk_reduction_on_streak cấu hình). Không chỉ kiểm tra một callable rồi mặc định các field còn lại.
- Tests từng NaN/Inf/bool/chuỗi sai và nhiều lỗi độc lập, không crash hoặc pass.
- Không thêm broad catch che lỗi lập trình; validate cấu trúc/giá trị và bắt các lỗi dữ liệu đã định nghĩa.

## G2 — P2: Cổng duyệt chưa chuyển lỗi thời gian ngắt mạch thành rejection
Vị trí: invariant_checks.py:684; CircuitBreakerState.advance_time.
Thực chạy: cb.advance_time(T+1h), sau đó gate(account.current_time=T) ném ValueError time reversal.
Breaker từ chối đi lùi là ĐÚNG. Lỗi còn lại là gate hứa trả (False,reasons) nhưng không xử lý hợp đồng này, khiến backtest có thể dừng do order/account lỗi.
Sửa:
- Trước hoặc khi gọi breaker, phát hiện admission_time < breaker.current_timestamp và trả TIME_REVERSAL/INVALID_ADMISSION_TIME rõ.
- Bắt lỗi thời gian/data từ component theo contract khi cần; không sửa state để 'cho phép' đi lùi.
- Test gate không văng exception; cb history/clock/lock/counters giữ nguyên cho event lùi; vẫn thu thập các lỗi độc lập còn lại.
- Giữ test trực tiếp advance_time/record_trade_result ném ValueError, không đổi behavior API toán học/state trực tiếp này.

## G3 — P1 khi news được bật: Không nạp được lịch vẫn được coi như filter hoạt động
Vị trí: news_calendar.py load_calendar; invariant_checks.py news admission.
Thực chạy: config news enabled=True, calendar_file trỏ file không tồn tại;
NewsCalendarFilter giữ enabled=True, events=[], log warning; gate trả (True, []).
Review 02 đã yêu cầu readiness/giả định rõ; implementation mới chỉ xử lý enabled mismatch.
Sửa:
- Thêm trạng thái nạp lịch/readiness + lý do lỗi, phân biệt 'đã nạp lịch hợp lệ và không có sự kiện tại thời điểm này' với 'không nạp được lịch'.
- Khi news disabled=False? Quy ước chính xác: news_filter.enabled=false => bypass như hiện tại. enabled=true và missing/unreadable/malformed calendar => gate reject NOT_READY/CALENDAR_LOAD_ERROR.
- Không dùng events=[] đơn thuần làm readiness. Lịch hợp lệ rỗng cần policy tường minh; fixture unit test có events do test inject cần khởi tạo readiness hợp lệ qua giao diện/fixture rõ ràng, không chỉ bật enabled.
- File calendar thiếu cột/parse lỗi cần trạng thái chất lượng rõ. Không im lặng skip dòng HIGH lỗi rồi tuyên bố fully ready; tối thiểu reject lịch không đủ hợp lệ cho policy strict, ghi lý do.
- Ghi rõ coverage/giả định của lịch thủ công nếu cần; không yêu cầu nguồn tin API mới.
- Test enabled+missing file, malformed schema, bad timestamps, disabled bypass và lịch hợp lệ có/không có blackout, reload sau lỗi.
Phạm vi paper trading, news mặc định tắt vẫn giữ nguyên.

## Prompt thực hiện cho Antigravity
1. Đồng bộ repo và đọc file này, PROJECT_STATE, ADR 0006. Chỉ sửa G1–G3, không viết lại các phần đã pass hoặc làm giai đoạn 4.
2. Thêm regression tests phản ánh đúng các ca reviewer đã chạy trên 2f3bc30. Các tests phải fail trên bản cũ và pass sau sửa. Giữ các test F1–F5 và mô phỏng đang đạt.
3. Chạy python -m pytest -m "not network" -q, và nhóm network riêng nếu môi trường hỗ trợ; ghi số pass/fail/skip/deselected thật. Chạy script mô phỏng; lưu raw output, phiên bản môi trường, diff.
4. Cập nhật ADR 0006 bằng phụ lục bổ sung, PROJECT_STATE (đã sửa review 03, chờ nghiệm thu), CHANGELOG, báo cáo map G1–G3 -> file/hàm -> test -> kết quả. Không khẳng định đã triệt tiêu mọi rủi ro.
5. Commit và push code/test/tài liệu, không force push. Remote có commit review này, cần đồng bộ an toàn trước khi push. Trả mã commit và link, dừng chờ review.

Không cần sửa lại mô phỏng vốn/lệnh ẩn hoặc hai benchmark liquidation: đã được xác nhận đạt. Network và đối chiếu pandas-ta là giới hạn xác minh của reviewer, không phải lỗi code được phát hiện.
