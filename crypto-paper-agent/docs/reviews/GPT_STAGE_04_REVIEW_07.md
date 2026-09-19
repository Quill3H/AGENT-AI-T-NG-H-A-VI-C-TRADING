# GPT Review 07 — Giai đoạn 4 chưa đạt nghiệm thu

> [!NOTE]
> **Tài liệu Lịch sử — Đã được thay thế (Superseded):**  
> Các phát hiện J1–J3 tại Review 07 đã được khắc phục tại Review 08 và chính thức nghiệm thu tại [GPT_STAGE_04_REVIEW_09.md](file:///D:/Ta%CC%80i%20lie%CC%A3%CC%82u/Default%20Project/crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_09.md).

## 1. Kết luận

**CHƯA NGHIỆM THU GIAI ĐOẠN 4. KHÔNG BẮT ĐẦU GIAI ĐOẠN 5.**

Antigravity đã sửa được các probe Review 05–06, nhưng kiểm tra độc lập sâu hơn tại commit `b0af6b199973f17a7bd1b9690a450f015403ef68` tái hiện ba lỗi còn lại trực tiếp thuộc H2, H5 và H6.

## 2. Bằng chứng đã chạy độc lập

- `python -m pytest tests -m 'not network' -q`: **179 passed, 2 skipped, 5 deselected**. Hai skip do môi trường reviewer thiếu `pandas-ta`.
- `python -m pytest docs/reviews/test_stage_04_review_05.py -q`: **26 passed**.
- `python -m pytest docs/reviews/test_stage_04_review_06.py -q`: **11 passed**.
- `python scripts/simulate_paper_execution.py`: Phần A đạt đối soát, wallet cuối 9.440,94 USD. Phần B **SKIPPED / NOT_VERIFIED** vì checkout reviewer không có cache dữ liệu thật.
- Probe mới: `docs/reviews/test_stage_04_review_07.py`.

Con số 181/181 và Phần B pass là kết quả tác giả báo cáo; reviewer không đổi hai skip thành pass và không coi dữ liệu cache không có trong checkout là đã tự xác minh.

## 3. Phát hiện còn lại

### J1 — Funding provenance/readiness vẫn không bắt buộc (P1)

Tại settlement, broker từ chối `funding_readiness=False` và kiểm tra future/stale khi `funding_time` được cung cấp. Tuy nhiên, candle chỉ có `funding_rate` nhưng thiếu hoàn toàn `funding_time` và readiness vẫn được chấp nhận và settlement được ghi sổ.

Điều này chưa hoàn thành H6 Review 06: contract nguồn funding phải phân biệt dữ liệu sẵn sàng, thiếu, tương lai và quá cũ; không được âm thầm coi metadata vắng mặt là hợp lệ.

**Sửa bắt buộc:** khi một vị thế sống qua Pha 1 tại settlement, yêu cầu rõ `funding_readiness is True` và source timestamp hợp lệ. Thiếu key, `None`, sai kiểu, future hoặc stale phải fail-closed trước mọi mutation. Rate 0 hữu hạn phải được phép khi metadata hợp lệ. Bổ sung test missing/None/wrong-type/zero.

### J2 — Funding settlement không transactional khi solver lỗi (P1)

`_apply_funding_settlement` hiện thay đổi wallet, isolated collateral, cumulative funding và append `FundingEvent` trước khi tính lại liquidation price. Nếu leverage bracket hỏng hoặc solver không có nghiệm, hàm ném lỗi sau khi tài khoản đã bị thay đổi dở dang.

Điều này trái H2 Review 06: bracket sai/không có nghiệm phải lỗi tường minh **trước mutation**.

**Sửa bắt buộc:** precompute toàn bộ cashflow, collateral mới và liquidation price mới trên state tạm; chỉ commit wallet/position/history/ledger sau khi tất cả validation và solver thành công. Nếu bất kỳ bước nào lỗi, snapshot tài khoản, position, funding history, settled keys và breaker phải bất biến.

### J3 — `finalize(force_close=True)` có thể đóng xong nhưng văng KeyError và không terminal (P1)

Với hai vị thế mở, lần đóng thứ nhất trong finalize có thể kích hoạt circuit breaker; `_handle_circuit_breaker_lock` đóng vị thế còn lại. Vòng lặp finalize sau đó truy cập symbol đã bị xóa và văng `KeyError`.

Probe thực tế cho thấy: positions đã về 0, có 2 trades, nhưng `is_finalized=False`. Đây là partial lifecycle mutation và vi phạm H5 transactional/idempotent.

**Sửa bắt buộc:** finalize/close-all phải chịu được nested breaker closure, không double-close, không KeyError và luôn đạt trạng thái terminal nhất quán khi thành công. Duyệt symbol an toàn hoặc tách preflight/commit; kiểm thử hai chiều LONG/SHORT, nhiều symbol, breaker kích hoạt ở lần đóng thứ nhất và lần giữa.

## 4. Tiêu chí nghiệm thu Review 08

1. Không sửa, xóa hoặc né assertion trong các probe Review 05–07.
2. Review 05: 26/26 pass; Review 06: 11/11 pass; Review 07: 3/3 pass.
3. Bộ offline mặc định không hồi quy; báo riêng pass/skip/deselected.
4. Thêm coverage cho missing/None/wrong-type/zero funding metadata, settlement rollback toàn state và finalize multi-position khi breaker đóng lồng nhau.
5. Phần dữ liệu thật chỉ được gọi reviewer-verified khi artifact cache và lệnh tái hiện có trong checkout reviewer; nếu không thì ghi SKIPPED/NOT_VERIFIED.
6. Cập nhật ADR 0007, báo cáo sửa Review 07, PROJECT_STATE, CHANGELOG và PLANNER_HANDOVER.
7. Commit/push `main`, gửi full SHA rồi dừng. Không bắt đầu Giai đoạn 5.

## 5. Prompt ngắn cho Antigravity

Đọc `PLANNER_HANDOVER.md` và `crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_07.md`. Sửa đúng J1–J3, chạy toàn bộ tiêu chí Review 08, cập nhật hồ sơ, commit/push main và báo full SHA. Không sửa probe để che lỗi. Dừng chờ GPT Review 08; chưa bắt đầu Giai đoạn 5.
