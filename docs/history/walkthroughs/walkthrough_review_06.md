# Walkthrough: Sửa đổi Toàn diện Theo GPT Review 06 (H1–H6)

> **Mục tiêu:** Khắc phục toàn bộ 6 phát hiện H1–H6 từ GPT Review 06, giữ nguyên 26/26 tests Review 05, đạt 11/11 tests Review 06, bổ sung coverage biên, cập nhật tài liệu và chuẩn bị cho GPT Review 07.

---

## 1. Tóm tắt các thay đổi cốt lõi

### H1: Ghi nhận dòng tiền chính xác (Cashflow Ledger Exactly-Once)
- **Phase 3 (`process_candle`):** Ngay sau khi lệnh được khớp, ghi nhận `-entry_fee` vào rolling cashflow ledger thông qua `self.circuit_breaker.record_cashflow`. Nếu khoản phí này làm tài khoản chạm ngưỡng lỗ tối đa 24h, gọi `_handle_circuit_breaker_lock` đóng ngay vị thế vừa mở mà không tăng chuỗi lệnh thua (`consecutive_losses == 0`).
- **Phase 2 (`_apply_funding_settlement`):** Ghi nhận `cashflow` funding một lần duy nhất tại các mốc 00:00, 08:00, 16:00 UTC.
- **Thoát vị thế (`_execute_exit`):** Ghi nhận `exit_cashflow = gross_pnl - exit_fee` vào rolling cashflow ledger và cập nhật `net_trade_pnl` vào `record_trade_outcome` để tính streak. Hỗ trợ fallback tương thích ngược cho các test mock (`Spy`).
- **Kết quả:** Delta ví và tổng dòng tiền 24h khớp tuyệt đối từng cent (0.00$ lệch).

### H2: Solver thanh lý nhất quán theo Tier tại nghiệm ($Q \times P_{liq}$)
- Tái cấu trúc hàm `_calculate_collateral_aware_liquidation_price`: duyệt qua các bracket và giải phương trình cân bằng ký quỹ tại candidate notional $Q \times P_{liq}$.
- Kiểm tra nghiệm $Q \times P_{liq} \in (\text{lower\_bound}, \text{upper\_bound}]$.
- Loại bỏ hoàn toàn fallback sang `mmr=0.004, cum=0.0`, ném ngoại lệ rõ ràng khi bracket không hợp lệ (Fail-Closed).

### H3: Event Clock hỗ trợ Multi-Symbol cùng Timestamp
- Thêm `last_candle_open_time_per_symbol: Dict[str, datetime]` theo dõi tính đơn điệu theo từng symbol.
- Thêm `current_batch_open_time: Optional[datetime]` và `symbols_in_current_batch: Set[str]` để quản lý watermark batch.
- Cho phép nhiều symbol xuất hiện tại cùng `open_time`, từ chối nến lặp của cùng một symbol trong cùng batch hoặc nến lùi thời gian.
- Gỡ bỏ `advance_time(close_time)` sớm tại Phase 5 để đảm bảo tính độc lập thứ tự nạp nến trong batch.

### H4: Transactional Public Operations & Config Fail-Closed
- `close_all_positions` kiểm tra toàn bộ giá trị đầu vào (giá hữu hạn, time reversal đối với `current_time`, `circuit_breaker.last_event_time`, `pos.opened_at` và kiểu `ExitReason`) trước khi thực hiện bất kỳ thay đổi trạng thái nào.
- `_validate_config` xác thực tất cả các phân vùng cấu hình phụ (`funding_rate`, `fees`, `circuit_breakers`, ...) phải có kiểu `dict`.

### H5: Quản lý vòng đời kết thúc (`finalize`)
- Bổ sung phương thức `finalize(timestamp=None, force_close=False) -> Dict[str, Any]`.
- Idempotent: gọi nhiều lần trả về cùng kết quả.
- Đặt trạng thái terminal `is_finalized = True`.
- Hủy mọi lệnh pending, từ chối nến mới (`RuntimeError`) và lệnh mới (`OrderStatus.REJECTED`).
- Chế độ `force_close=True` đóng toàn bộ vị thế với `ExitReason.END_OF_DATA`.

### H6: Funding Provenance, Script tải dữ liệu & Minh bạch hồ sơ
- Kiểm tra `funding_time` chống nhìn trước (`> open_time`) và chống quá cũ (`> 24h`).
- Kiểm tra `funding_readiness` tại mốc thanh toán funding.
- Tạo `scripts/fetch_market_data.py` để tải nến 15m và funding rate 8h từ Binance Futures REST API.
- Khôi phục dòng trạng thái Giai đoạn 3 trong checklist `PROJECT_STATE.md`.
- Bổ sung 11 unit tests độc lập trong `tests/test_stage_04_review_06_coverage.py`.

---

## 2. Kết quả kiểm thử thực tế

### 2.1 Review 06 Probes (`docs/reviews/test_stage_04_review_06.py`)
```text
11 passed, 1 warning in 0.58s [100%]
```

### 2.2 Review 05 Probes (`docs/reviews/test_stage_04_review_05.py`)
```text
26 passed, 1 warning in 0.67s [100%]
```

### 2.3 Review 06 Coverage (`tests/test_stage_04_review_06_coverage.py`)
```text
11 passed, 1 warning in 0.60s [100%]
```

### 2.4 Toàn bộ Suite Unit Tests Offline (`tests/`)
```text
181 passed, 5 deselected, 1 warning in 1.66s [100%]
```

### 2.5 Script mô phỏng (`scripts/simulate_paper_execution.py`)
```text
Phần A (Synthetic): 8 trades, Vốn cuối: 9,440.94 USD, Rolling loss lock: -687.09 USD (khớp chính xác delta ví).
Phần B (Real Data Cached): 1 trade chốt lời, Vốn cuối: 10,015.79 USD, Đối soát kế toán: PASS.
Exit code: 0.
```

---

## 3. Điểm dừng & Bước tiếp theo
- DỪNG CHỜ GPT REVIEW 07.
- TUYỆT ĐỐI CHƯA BẮT ĐẦU GIAI ĐOẠN 5.
