# Walkthrough: Khắc Phục Dứt Điểm Phát Hiện K1 Theo GPT Review 08

> **Mục tiêu:** Xóa bỏ hoàn toàn cơ chế nhận diện caller/stack inspection (`inspect`, `_is_legacy_probe_caller`), thực thi hợp đồng funding provenance & readiness fail-closed vô điều kiện, bảo đảm 100% đồng nhất giữa môi trường test và production, đạt 40/40 tests Review 05–07, 237/237 tests toàn hệ thống và vượt qua kiểm thử mô phỏng thực tế.

---

## 1. Tóm Tắt Bản Chất Kỹ Thuật Của Thay Đổi

### 1.1 Xóa Bỏ Hoàn Toàn Caller Inspection (Anti-Cheat / Test Invariance)
- **Vấn đề (K1):** Ở bản sửa Review 07, `_is_legacy_probe_caller()` sử dụng `inspect.currentframe()` để dò call stack và tên file của các bộ test cũ (`test_stage_04_review_05`, `test_stage_04_review_06`) nhằm nới lỏng yêu cầu funding metadata. Đây là hành vi test-aware không thể chấp nhận trong production code.
- **Giải pháp:**
  - Xóa bỏ hoàn toàn `import inspect` và `_is_legacy_probe_caller` khỏi `src/execution/paper_broker.py`.
  - Loại bỏ hoàn toàn phân nhánh `strict_provenance`.
  - Cung cấp cùng một quy tắc xử lý cho mọi caller: bất kỳ lệnh gọi nào tại mốc settlement (00, 08, 16 UTC) cho vị thế mở đều phải đáp ứng đầy đủ hợp đồng funding provenance & readiness.

### 1.2 Thực Thi Hợp Đồng Funding Fail-Closed Vô Điều Kiện Tại Settlement
- **Kiểm tra cờ sẵn sàng `funding_readiness`:** Bắt buộc có mặt, bắt buộc kiểu `bool`, bắt buộc giá trị `True`. Thiếu key hoặc `None` ném `ValueError`, sai kiểu ném `TypeError`, mang giá trị `False` ném `ValueError`.
- **Kiểm tra timestamp nguồn `funding_time`:** Bắt buộc có mặt, đúng kiểu thời gian, chuyển đổi UTC thành công, không nằm trong tương lai ($t_{source} \le t_{open}$) và không quá cũ ($t_{source} \ge t_{open} - 24h$).
- **Kiểm tra mức phí `funding_rate`:** Bắt buộc là số thực hữu hạn; `0.0` được chấp nhận hợp lệ khi đi kèm đầy đủ metadata.
- **Không có ngoại lệ hay cờ cấu hình nới lỏng:** Kể cả khi cấu hình `config['funding_rate']['strict_provenance'] = False`, hệ thống vẫn kiên quyết fail-closed nếu thiếu metadata.

### 1.3 Bổ Sung Metadata Hợp Lệ Trong Helper Của Test Cũ
- Trong `docs/reviews/test_stage_04_review_05.py` và `docs/reviews/test_stage_04_review_06.py`, hàm helper `candle()` được bổ sung `d['funding_time'] = t` và `d['funding_readiness'] = True` khi `funding_rate` có mặt trong kwargs.
- **Tuyệt đối không sửa hay làm yếu assertion nào:** Các test cố tình kiểm tra đầu vào sai (`funding_rate=None`, `nan`) vẫn ghi đè và kích hoạt fail-closed đúng kỳ vọng của reviewer.

---

## 2. Bổ Sung Bộ Kiểm Thử Hồi Quy K1

Tại `tests/test_stage_04_review_07_coverage.py`:
1. `test_k1_no_caller_stack_inspection_or_inspect_import_in_broker_code`: Sử dụng module `ast` để duyệt toàn bộ cây cú pháp của `paper_broker.py`, khẳng định không có `import inspect`, không gọi `_getframe`/`currentframe`, không có hàm `_is_legacy_probe_caller`.
2. `test_k1_funding_provenance_identical_across_caller_and_stack_names`: Định nghĩa các hàm mang tên khác nhau (`test_stage_04_review_05_probe_caller` vs `production_live_caller`), chứng minh cùng một input thiếu metadata đều ném cùng ngoại lệ `ValueError`, và cùng một input hợp lệ đều cho kết quả trạng thái tài khoản giống hệt nhau.
3. `test_k1_config_flag_cannot_relax_funding_provenance`: Chứng minh việc gán `strict_provenance: False` trong config không thể vượt qua hàng rào fail-closed.

---

## 3. Bằng Chứng Kiểm Thử Thực Tế

### 3.1 Bộ 3 Probes Độc Lập
```text
docs/reviews/test_stage_04_review_05.py: 26 passed
docs/reviews/test_stage_04_review_06.py: 11 passed
docs/reviews/test_stage_04_review_07.py:  3 passed
======================== 40 passed in 0.84s ========================
```

### 3.2 Bộ Kiểm Thử Coverage Toàn Diện
```text
tests/test_stage_04_review_07_coverage.py: 16 passed in 0.64s
```

### 3.3 Toàn Bộ Offline Test Suite
```text
================ 237 passed, 5 deselected, 1 warning in 2.09s =================
```

### 3.4 Kịch Bản Mô Phỏng Giao Dịch Thực Tế
```text
scripts/simulate_paper_execution.py:
- Phần A: Đối soát Kế toán THÀNH CÔNG: Vốn cuối = 9,440.94 USD = Vốn ban đầu (10,000.00) + Tổng Net PnL (-559.06) (Pass 100%).
- Phần B: Chạy trên 120 nến 15m Binance BTCUSDT và 3 kỳ funding 8h thực tế, vốn cuối 10,015.79 USD, đối soát bất biến kế toán HOÀN TOÀN KHỚP (Pass 100%).
```
