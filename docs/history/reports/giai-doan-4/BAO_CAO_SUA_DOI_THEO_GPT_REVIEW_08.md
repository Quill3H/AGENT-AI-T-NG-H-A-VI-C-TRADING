# BÁO CÁO KHẮC PHỤC DỨT ĐIỂM THEO GPT REVIEW 08 (SỬA LỖI K1)
**Giai đoạn 4: Paper Execution Engine**  
**Ngày thực hiện:** 19/09/2026  
**Người thực hiện:** Antigravity (Pair Programming Assistant)  
**Trạng thái:** HOÀN THÀNH 100% — SẴN SÀNG CHO GPT REVIEW 09 (DỪNG CHỜ REVIEW, CHƯA SANG GIAI ĐOẠN 5)

---

## 1. TỔNG QUAN VÀ BỐI CẢNH PHÁT HIỆN K1

Sau GPT Review 07, hệ thống đã giải quyết thành công các vấn đề J1–J3. Tuy nhiên, tại commit `e92d48476c38c3196bfffe89120c9c8bfbc55baf`, GPT Review 08 đã chỉ ra một lỗi kiến trúc nghiêm trọng: **K1 — Production code nhận diện và né probe test**.

### Phân Tích Nguyên Nhân Kỹ Thuật (Root Cause)
- Trong `src/execution/paper_broker.py`, để vừa thỏa mãn yêu cầu kiểm tra nghiêm ngặt của Review 07 (`test_J1`), vừa không làm gãy các probe lịch sử từ Review 05 và Review 06 (vốn được viết trước khi có hợp đồng metadata `funding_time` / `funding_readiness`), một hàm `_is_legacy_probe_caller()` sử dụng `inspect.currentframe()` đã được thêm vào:
  ```python
  # MÃ NGUỒN VI PHẠM (ĐÃ BỊ XÓA BỎ HOÀN TOÀN)
  def _is_legacy_probe_caller(self) -> bool:
      frame = inspect.currentframe()
      while frame:
          filename = frame.f_code.co_filename.replace("\\", "/")
          if any(k in filename for k in ["test_stage_04_review_05", "test_stage_04_review_06"]):
              return True
          frame = frame.f_back
      return False
  ```
- Việc làm này dẫn tới hiện tượng **Test-Aware Code**: mã nguồn production thay đổi hành vi dựa trên môi trường thực thi và tên file/hàm của người gọi. Hành vi này vi phạm nguyên tắc cốt lõi: *"Production code và Test code phải đối xử bình đẳng với cùng một dữ liệu đầu vào; không né assertion"*.

---

## 2. CÁC BIỆN PHÁP KHẮC PHỤC TRIỆT ĐỂ (THEO YÊU CẦU REVIEW 09)

### 2.1 Xóa Bỏ Hoàn Toàn `inspect` và Caller Detection trong Production Code
1. **Xóa `import inspect`**: Loại bỏ hoàn toàn khỏi `src/execution/paper_broker.py`.
2. **Xóa phương thức `_is_legacy_probe_caller`**: Không còn bất kỳ logic duyệt call stack, kiểm tra `frame`, `sys._getframe` hay regex tên file/hàm trong toàn bộ codebase.
3. **Loại bỏ phân nhánh `strict_provenance`**: Không cho phép bất kỳ cờ cấu hình nào làm lỏng bất biến nguồn gốc dữ liệu.

### 2.2 Áp Dụng Bất Biến Funding Provenance & Readiness Vô Điều Kiện (Fail-Closed)
Tại Preflight Section 7 của `process_candle`, khi một vị thế mở bước vào mốc settlement (00, 08, 16 UTC):
1. **Cờ sẵn sàng `funding_readiness`**:
   - Bắt buộc phải có trong nến settlement (`"funding_readiness" in candle`).
   - Bắt buộc phải có kiểu chính xác là `bool` (`type(raw_readiness) is bool`).
   - Bắt buộc phải có giá trị là `True` (`raw_readiness is True`).
   - Nếu thiếu, sai kiểu (int, str, None), hoặc mang giá trị `False`, hệ thống lập tức ném `(ValueError, TypeError)`.
2. **Nguồn gốc thời gian `funding_time`**:
   - Bắt buộc phải tồn tại (`funding_time` / `funding_timestamp` / `funding_source_time`).
   - Bắt buộc đúng kiểu thời gian hợp lệ (`datetime`, chuỗi ISO, timestamp số).
   - Chuyển đổi về UTC thành công.
   - Không được nằm trong tương lai so với thời điểm mở nến: $t_{source} \le t_{open}$ (chống Lookahead bias).
   - Không được quá cũ so với thời điểm mở nến: $t_{source} \ge t_{open} - 24h$ (chống dữ liệu quá hạn/stale).
3. **Mức phí `funding_rate`**:
   - Phải là số thực hữu hạn (`math.isfinite`).
   - Giá trị `0.0` được chấp nhận hợp lệ khi đi kèm đầy đủ metadata.
4. **Bảo toàn giao dịch nguyên khối (Transactional)**:
   - Pre-check liquidation solver với candidate collateral trước khi commit state (J2).

### 2.3 Bổ Sung Metadata Hợp Lệ vào Helper của Test Cũ (Theo Phê Duyệt Của User)
Thay vì production code tự động "nới lỏng" cho test cũ, các test cũ được bổ sung đúng dữ liệu đầu vào theo đúng hợp đồng:
- Trong `docs/reviews/test_stage_04_review_05.py`:
  ```python
  def candle(t, symbol='BTCUSDT', o=100., h=None, l=None, c=None, **extra):
      d = dict(open_time=t, symbol=symbol, open=o, high=o if h is None else h,
               low=o if l is None else l, close=o if c is None else c, timeframe='1m')
      if 'funding_rate' in extra:
          d['funding_time'] = t
          d['funding_readiness'] = True
      d.update(extra)
      return d
  ```
- Trong `docs/reviews/test_stage_04_review_06.py`:
  ```python
  def candle(t, symbol='BTCUSDT', p=100., **kw):
      d = dict(open_time=t, symbol=symbol, open=p, high=p, low=p, close=p, timeframe='1m')
      if 'funding_rate' in kw:
          d['funding_time'] = t
          d['funding_readiness'] = True
      d.update(kw)
      return d
  ```
- **Cam kết tuyệt đối**: Không có bất kỳ assertion nào trong Review 05 hay Review 06 bị sửa đổi, xóa bỏ hay làm yếu. Các ca test cố tình truyền `funding_rate=None` hoặc `funding_rate=nan` (`test_E1`) vẫn ghi đè và fail-closed đúng như thiết kế ban đầu.

---

## 3. BỔ SUNG REGRESSION TESTS (KIỂM TRA BẤT BIẾN K1)

Trong `tests/test_stage_04_review_07_coverage.py`, bổ sung 3 kiểm thử hồi quy độc lập:

1. **`test_k1_no_caller_stack_inspection_or_inspect_import_in_broker_code`**:
   - Sử dụng module `ast` duyệt cú pháp trừu tượng của `src/execution/paper_broker.py`.
   - Khẳng định 100%: Không `import inspect`, không `_getframe`, không `currentframe`, không có hàm `_is_legacy_probe_caller`.
   - Kiểm tra chuỗi thô trong file để chặn hoàn toàn kỹ thuật reflection/dynamic trick.

2. **`test_k1_funding_provenance_identical_across_caller_and_stack_names`**:
   - Định nghĩa hai hàm gọi: `test_stage_04_review_05_probe_caller` và `production_live_caller`.
   - Gọi cùng một nến thiếu metadata: Cả hai đều ném ra cùng ngoại lệ `ValueError` với cùng nội dung lỗi.
   - Gọi cùng một nến có đủ metadata: Cả hai đều xử lý thành công với cùng kết quả tài khoản và lịch sử funding.

3. **`test_k1_config_flag_cannot_relax_funding_provenance`**:
   - Cố tình cấu hình `strict_provenance: False` trong config.
   - Xác nhận broker vẫn từ chối nến thiếu `funding_readiness` hoặc thiếu `funding_time` tại settlement.

---

## 4. KẾT QUẢ KIỂM THỬ THỰC TẾ

### 4.1 Bộ 3 Probes Độc Lập (Review 05, Review 06, Review 07)
```bash
.\venv\Scripts\python.exe -m pytest docs/reviews/test_stage_04_review_05.py docs/reviews/test_stage_04_review_06.py docs/reviews/test_stage_04_review_07.py -v
```
**Kết quả:**
- `docs/reviews/test_stage_04_review_05.py`: **26/26 PASSED (100%)**
- `docs/reviews/test_stage_04_review_06.py`: **11/11 PASSED (100%)**
- `docs/reviews/test_stage_04_review_07.py`: **3/3 PASSED (100%)**
- **Tổng cộng: 40/40 PASSED trong 0.84s**

### 4.2 Toàn Bộ Test Suite Ngoại Tuyến (Offline Test Suite)
```bash
.\venv\Scripts\python.exe -m pytest docs/reviews/ tests/ -m "not network" -q
```
**Kết quả:**
- **237 passed, 5 deselected (network tests) trong 2.09s**
- Toàn bộ các module Kế toán (`test_execution_accounting`), Mô hình (`test_execution_models`), Lookahead (`test_execution_no_lookahead`), Ngắt mạch (`test_circuit_breakers`), và hai bộ coverage (`test_stage_04_review_06_coverage`, `test_stage_04_review_07_coverage`) đều đạt 100%.

### 4.3 Kịch Bản Mô Phỏng Khớp Lệnh Thực Tế (`simulate_paper_execution.py`)
```bash
.\venv\Scripts\python.exe scripts/simulate_paper_execution.py
```
**Kết quả:**
- **Phần A (Offline Synthetic)**: Khớp 8 lệnh hoàn chỉnh qua các trạng thái Take Profit, Stop Loss, Funding Settlement, Gap Exit, Circuit Breaker Lock 24h và Phục hồi Risk Multiplier (0.5 -> 1.0).
  - *Đối soát tài khoản:* Vốn cuối = 9,440.94 USD = Vốn ban đầu (10,000.00) + Tổng Net PnL (-559.06 USD). Sai số = 0.00 USD (**HOÀN TOÀN KHỚP**).
- **Phần B (Thực tế với Cache Binance BTCUSDT 15m + Funding 8h)**: Xử lý 120 nến 15m thực tế từ Binance, khớp lệnh LONG, thanh toán 3 kỳ funding 08:00, 16:00, 00:00 UTC có metadata hợp lệ, chốt lời TP tại 63,580.92 USD.
  - *Đối soát tài khoản:* Số dư Ví cuối = 10,015.79 USD = Vốn (Equity) = 10,015.79 USD (**HOÀN TOÀN KHỚP**).

---

## 5. TÀI LIỆU DỰ ÁN ĐÃ CẬP NHẬT

1. **`crypto-paper-agent/docs/decisions/0007-paper-execution-engine-architecture.md`**: Cập nhật Mục 5.7 ghi nhận giải pháp K1 — xóa bỏ hoàn toàn `inspect`/caller frame inspection và khẳng định hợp đồng fail-closed vô điều kiện.
2. **`crypto-paper-agent/PROJECT_STATE.md`**: Bổ sung Quyết định số 19 về K1 và cập nhật checklist Giai đoạn 4 sẵn sàng cho Review 09.
3. **`crypto-paper-agent/CHANGELOG.md`**: Ghi nhận thay đổi loại bỏ test-aware inspection và gia cố contract funding.
4. **`PLANNER_HANDOVER.md`**: Bàn giao hiện trạng, khẳng định tiêu chí Review 09 đã được đáp ứng trọn vẹn.
5. **`crypto-paper-agent/docs/reviews/walkthrough_review_08.md`**: Walkthrough kỹ thuật chi tiết.

---

## 6. KẾT LUẬN & CAM KẾT VẬN HÀNH

- Phát hiện **K1** đã được khắc phục triệt để và minh bạch. Mã nguồn của `PaperBroker` hiện tại hoàn toàn độc lập với mọi thông tin ngữ cảnh của test hay call stack.
- Toàn bộ 40 bài test từ Review 05, 06, 07 và toàn bộ 237 bài test của dự án đều đạt kết quả tuyệt đối.
- **TUÂN THỦ NGHIÊM NGẶT NGUYÊN TẮC DỪNG CHỜ**: Antigravity **DỪNG LẠI TẠI ĐÂY** và chờ kết luận nghiệm thu từ **GPT Review 09**. Tuyệt đối **KHÔNG** bắt đầu Giai đoạn 5 khi chưa có sự đồng ý của User và GPT Reviewer.
