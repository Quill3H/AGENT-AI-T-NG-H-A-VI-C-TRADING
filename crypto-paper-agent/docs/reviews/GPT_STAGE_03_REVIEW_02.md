# GPT REVIEW LẦN 2 — GIAI ĐOẠN 3
Verdict: FIX REQUIRED. Chưa chuyển giai đoạn 4.

## Bằng chứng
Review commit d121cf6449599c71867dfbe3db5b7808094587f4 trên main. Đã đọc diff, toàn bộ module risk, news filter, test sửa, ADR 0006, báo cáo mới và chạy chương trình.
- Test offline: 106 passed, 2 skipped, 5 deselected (113 collected). Hai skip là đối chiếu pandas-ta thiếu trong môi trường review; năm deselected là test network Data Layer. Không xác nhận lại 113/113.
- 60 test giai đoạn 3 trong suite offline đều đạt (sizing 21, liquidation 10, breaker 10, invariant 19).
- Mô phỏng 13 dòng mới chạy, vốn cuối 9470 USD, multiplier 1.0; đối soát vốn đạt, không còn hai thắng ẩn.
- NaN đầu vào order phổ biến, direction sai, tier thiếu, thiếu breaker, thiếu timestamp, hai benchmark thanh lý xuyên tier đã được cải thiện.
- Không sửa code chương trình trong review này.

## Lỗi còn lại, tái hiện và prompt sửa
Antigravity: đọc file này và PROJECT_STATE.md/ADR 0006, sửa đúng các điểm dưới đây, thêm regression tests chứng minh và dừng ở giai đoạn 3. Bản hiện tại chưa nghiệm thu. Không làm giai đoạn 4.

Fixture gốc dùng cho tái hiện:
entry=50000, stop=49000, leverage=3, symbol=BTCUSDT, direction=LONG,
risk_percent=.02, conviction_tier=normal, position_size_usd=10000;
account equity=10000, available_margin=10000, CircuitBreakerState hợp lệ;
timestamp/current_time T=2026-09-01 10:00 UTC; default_config.yaml hiện có.

### F1 — P1: Đối soát theo trần tier thay vì ngân sách risk lệnh
invariant_checks.py phần Actual Risk:
quantity=N/entry; actual risk=q*abs(entry-stop).
Thay tier=high, risk_percent=.01, N=20000: q=.4, risk thực=400 USD=4%, khai 100 USD=1%. Hàm trả (True, []) vì so với trần high 5%.
Sửa: risk_percent phải có nghĩa tường minh là effective risk của lệnh; ngân sách lệnh=equity*risk_percent, đồng thời risk_percent <= tier_limit*breaker_multiplier. Actual risk phải <= ngân sách lệnh, không chỉ trần tier. Nếu thêm base_risk_percent, validate quan hệ base/effective và không nhân reduction hai lần. Cập nhật ADR 0006 và contract cho execution. Thêm test high tier nhưng chọn risk thấp, actual vượt khai báo; effective đã giảm không bị nhân hai lần.

### F2 — P1: Available margin chưa validate; component/timestamp sai vẫn crash
- Đổi N=60000, stop=49900 (risk thực 120 USD), account available_margin=NaN: required margin=20000 > equity=10000 nhưng hàm trả True vì so sánh NaN bỏ qua.
- breaker=object(): AttributeError ở is_trading_allowed dù đã thêm lý do missing component.
- conviction_tier=[]: TypeError unhashable list.
- timestamp=1e100: OverflowError từ datetime.fromtimestamp.
Sửa: validate available_margin hữu hạn, >=0, không bool, không chuỗi; required margin đối chiếu khoản entry-fee dự phòng được định nghĩa rõ. Không ngầm lấy equity làm free margin khi chưa xác nhận account không có margin đang dùng; fixture account trống phải khai available_margin tường minh.
Validate component đúng contract/callable và chỉ gọi nếu hợp lệ; mọi order/account lỗi phải trả False cùng các lý do độc lập, không crash. Parse timestamp bắt ValueError/OverflowError/OSError. Validate tier type trước membership. Validate cấu hình số/limits và multiplier để NaN không vô hiệu hóa các check. Regression tests với dữ liệu lỗi từng trường, nhiều lỗi cùng lúc và state không bị phá bởi input lỗi.

### F3 — P1: Admission time lấy signal time; flag news object ghi đè config
- admission_time=order_ts or account_ts ưu tiên timestamp cũ của tín hiệu.
- Config news enabled=true, object NewsCalendarFilter enabled=false có event CPI tại T: hàm trả True. Flag object làm bypass config.
- Cho object enabled=true, event CPI tại T, account current_time=T, order timestamp=T-1h: hàm trả True vì kiểm tra ở giờ cũ, tránh blackout tại giờ duyệt.
Sửa: account current_time là admission time bắt buộc/nguồn thẩm quyền; order timestamp là signal time <= admission. Check breaker/news tại admission, không dùng signal time để quyết định quyền mở lệnh. Missing admission không lấy đồng hồ thật hoặc để order tự quyết. Nếu config news bật mà filter disabled/không sẵn sàng, từ chối lỗi cấu hình rõ; config tắt thì bypass chủ đích. Không coi enabled với lịch không nạp được là bảo vệ đang hoạt động mà không có trạng thái readiness/giả định rõ.
Test signal cũ vào blackout hiện tại; signal cũ nhưng lock đã hết hạn hiện tại; signal tương lai phải reject mà không mở khóa; config/object bất nhất.

### F4 — P1: Đồng hồ breaker chưa thống nhất; khóa hết hạn bỏ sót khoản lỗ mới
A. cb.record_trade_result(-600,T,10000); cb.is_trading_allowed(T+25h); sau đó record_trade_result(+1,T+1h,10000) vẫn được chấp nhận: is_trading_allowed prune history nhưng không cập nhật last_event_time. Dữ liệu quá khứ lại sửa state đã tiến tương lai.
B. cb.record_trade_result(-600,T,10000); record_trade_result(-600,T+25h,10000) (chưa gọi is_trading_allowed giữa hai lần). Lần lỗ mới không khóa lại vì is_locked còn True với locked_until cũ T+24h. Gọi is_trading_allowed(T+25h) trả True dù rolling hiện tại -600.
Sửa: một hàm advance_time thống nhất dùng cả query/record; validate thời gian đơn điệu trước mutate, prune cửa sổ và hết hạn khóa trước đánh giá event mới. Khi lỗ mới đủ ngưỡng sau khóa hết hạn, tạo khóa mới tới thời điểm event+24h. Không gia hạn khóa còn hiệu lực. Query không được nhận giờ quá khứ hoặc xóa history rồi cho phép ghi event trước giờ query.
Thêm tests A/B; event/query đi lùi không thay state; đúng/sát ranh giới 24h; expiry+new breach; same timestamp nhiều event.
Validate recovery_mode bằng danh sách mode được hỗ trợ; mode bất kỳ hiện vẫn được constructor nhận. Đề xuất zero equity dùng trạng thái halted rõ thay khóa 'vô thời hạn' 3650 ngày; reset cho run mới.

### F5 — P2: Liquidation vẫn ngoại suy miền không hỗ trợ và fallback nghiệm không đúng tier
get_mmr_tier vẫn dùng tier cuối khi notional vượt cap. Solver cho phép candidate vượt cap tier cuối, cuối hàm còn fallback tier cuối nếu không có nghiệm.
Ví dụ SHORT entry=50000,N=1e9,lev=3 trả 47778.32111111111 (thanh lý dưới entry cho SHORT không được báo margin không đủ/miền không hỗ trợ). Không được gọi đây là solver tự nhất quán trong mọi trường hợp.
Sửa: reject entry notional vượt snapshot cap nếu contract không hỗ trợ; candidate vượt miền hoặc không có nghiệm thì lỗi rõ, không dùng fallback tier cuối. Nếu margin ngay entry đã <= maintenance thì báo already-liquidatable/insufficient initial margin, không trả giá trên phía sai mà khiến downstream dùng như nghiệm bình thường.
Validate bracket continuity/monotonic maintenance đủ để nghiệm có nghĩa, hoặc báo snapshot không nhất quán. Kiểm tra số trung gian q, candidate_p, candidate_notional hữu hạn dương; tránh underflow/overflow/NaN lọt.
Test phương trình margin_balance=maintenance độc lập bằng mmr/cum ở q*P, cả cùng tier, crossing, ranh giới, nhiều tier, long 1x, ngoài miền, bracket lỗi. Hai benchmark trước đã sửa đúng; giữ tests.
Ghi rõ bảng là snapshot/giả định mô hình isolated, không khẳng định chính xác toàn bộ lịch sử hoặc sàn thực tế. Không thêm API key.

## Trả bài
1. Thêm regression tests F1–F5, giữ tests đã đạt. Không chỉ sửa báo cáo.
2. Chạy offline và network riêng (network nếu môi trường hỗ trợ); lưu stdout/stderr thật và phiên bản Python/thư viện. Ghi pass/fail/skip/deselected đúng; không gọi network bị bỏ qua là passed.
3. Mô phỏng mới đã sửa vốn/lệnh ẩn: giữ kiểm chứng, hiển thị đủ PnL/vốn trước-sau/lý do từ chối; scenario stress ghi rõ PnL giả định.
4. Cập nhật ADR 0006 với phần bổ sung lịch sử, PROJECT_STATE.md: đã sửa review lần 2, chờ nghiệm thu; CHANGELOG và báo cáo F1–F5 -> diff -> test -> kết quả. Bỏ khẳng định “không còn bất kỳ rủi ro tiềm ẩn nào” khi bằng chứng chưa hỗ trợ.
5. Commit và push code/test/tài liệu lên main theo quy trình repo hiện có; không force push, không ghi đè thay đổi người dùng. Nếu remote có commit review này mà local thiếu, đồng bộ và bảo toàn thay đổi local trước khi push.
6. Báo mã commit/link sau push; dừng chờ GPT review, chưa chuyển giai đoạn 4.

## Lệnh xác minh hiện đã thực chạy
python -m pytest -m "not network" -q
python scripts/simulate_risk_manager_10_trades.py
Các tình huống F1–F5 ở trên đều đã được chạy độc lập trên commit d121cf6; không chỉ suy luận từ báo cáo.
