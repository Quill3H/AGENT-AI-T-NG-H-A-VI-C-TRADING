# Báo Cáo Sửa Đổi Theo GPT Review 06 — Giai Đoạn 4: Paper Execution Engine

> **Ngày thực hiện:** 19/09/2026  
> **Người thực hiện:** Antigravity (Pair Programming Assistant)  
> **Tham chiếu đối chiếu:**  
> - `crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_06.md`  
> - `crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_05.md`  
> - `crypto-paper-agent/docs/planning/ANTIGRAVITY_STAGE_04_TASK.md`  
> - `PLANNER_HANDOVER.md`  
> **Trạng thái:** HOÀN TẤT TOÀN BỘ YÊU CẦU SỬA ĐỔI H1–H6. DỪNG CHỜ GPT REVIEW 07.

---

## 1. Tổng Quan & Đối Chiếu Tiêu Chí Nghiệm Thu Review 07

| Mục | Yêu cầu Review 06 | Hiện trạng thực hiện | Kết quả thực tế |
| :--- | :--- | :--- | :--- |
| **H1** | Entry fee, funding, exit cashflow ghi nhận đúng 1 lần; không double-count; entry fee lock không tăng streak | Đã sửa `paper_broker.py`, `circuit_breakers.py` | 3/3 probes H1 PASS; demo rolling loss -687.09$ khớp chính xác delta ví |
| **H2** | Solver thanh lý nhất quán theo tier tại nghiệm ($Q \times P_{liq}$); không fallback hardcode | Đã áp dụng solver tier-consistent theo $Q \times P$; ném `(ValueError, TypeError)` khi hỏng bracket | 2/2 probes H2 PASS |
| **H3** | Event clock hỗ trợ multi-symbol cùng timestamp; batch sequence watermark; chống nến trùng theo symbol | Đã thêm `last_candle_open_time_per_symbol`, batch watermark; gỡ `advance_time(close_time)` sớm | 2/2 probes H3 PASS |
| **H4** | Transactional `close_all_positions` và config fail-closed | Prevalidate toàn bộ tham số/thời gian trước mutation; validate subconfig type là `dict` | 3/3 probes H4 PASS |
| **H5** | Lifecycle `finalize/end-of-data`, idempotent, chặn thao tác sau kết thúc | Thêm `finalize(timestamp, force_close)`; chặn `process_candle` và `submit_order` | 1/1 probe H5 PASS |
| **H6** | Funding provenance/readiness; thêm `scripts/fetch_market_data.py`; phục hồi Giai đoạn 3 checklist; phân định author vs reviewer | Đã thêm kiểm tra `funding_time` & readiness; tạo `scripts/fetch_market_data.py`; phục hồi checklist `PROJECT_STATE.md` | Đạt đầy đủ tiêu chí |

---

## 2. Chi Tiết Các Thay Đổi Kỹ Thuật

### H1 — Ghi Nhận Dòng Tiền Exactly-Once & Chống Cộng Trùng
- **Lúc Entry (Phase 3):** Ghi nhận ngay `-entry_fee` vào rolling cashflow ledger thông qua `self.circuit_breaker.record_cashflow(amount=-entry_fee, timestamp=open_time, equity=self.equity)`. Nếu phí vào lệnh kích hoạt khóa 24h, gọi `_handle_circuit_breaker_lock(open_time)` để đóng cưỡng chế vị thế vừa mở mà không tính vào chuỗi lệnh thua (`consecutive_losses == 0`).
- **Lúc Funding (Phase 2):** Ghi nhận `cashflow` của funding rate đúng một lần tại thời điểm thanh toán (00:00, 08:00, 16:00 UTC).
- **Lúc Thoát Vị Thế (`_execute_exit`):**
  - Tính `exit_cashflow = gross_pnl - exit_fee`.
  - Gọi `record_trade_result(pnl=net_trade_pnl, timestamp=exit_time, equity=post_close_equity, cashflow=exit_cashflow)`: rolling cashflows chỉ nhận `exit_cashflow` thay vì `net_trade_pnl` (vốn đã bao gồm entry fee và funding).
  - Tương thích ngược: Bọc `try/except TypeError` khi gọi `record_trade_result` để hỗ trợ các test mock `Spy` chỉ nhận 3 tham số `(pnl, timestamp, equity)`.
  - Nếu thoát do ngắt mạch (`CIRCUIT_BREAKER_LOCK`), chỉ ghi nhận `exit_cashflow` vào `record_cashflow`, không gọi `record_trade_outcome`.

### H2 — Solver Thanh Lý Nhất Quán Theo Tier Tại Điểm Nghiệm
- Loại bỏ hoàn toàn phương pháp lấy tier MMR từ `notional = quantity * entry_price`.
- Duyệt qua từng tier của leverage brackets, giải phương trình:
  - LONG: $P_{liq} = \frac{Q \cdot Entry - C - cum}{Q \cdot (1 - mmr)}$
  - SHORT: $P_{liq} = \frac{Q \cdot Entry + C + cum}{Q \cdot (1 + mmr)}$
- Nghiệm hợp lệ khi và chỉ khi $Q \times P_{liq} \in (\text{lower\_bound}, \text{upper\_bound}]$.
- Loại bỏ hoàn toàn fallback sang `mmr=0.004, cum=0.0`. Nếu bracket bị hỏng hoặc không có tier thỏa mãn, ném `(ValueError, TypeError)` ngay lập tức trước khi xảy ra bất kỳ đột biến tài khoản nào.

### H3 — Event Clock Hỗ Trợ Multi-Symbol Cùng Mốc Thời Gian
- Bổ sung cấu trúc theo dõi nến:
  - `last_candle_open_time_per_symbol: Dict[str, datetime]`: theo dõi tính đơn điệu riêng cho từng cặp giao dịch.
  - `current_batch_open_time: Optional[datetime]`: watermark mốc nến đang xử lý.
  - `symbols_in_current_batch: Set[str]`: tập hợp các symbol đã xuất hiện tại `current_batch_open_time`.
- Cho phép nhiều symbol xuất hiện tại cùng một `open_time`, nhưng từ chối nếu cùng một symbol xuất hiện lặp lại trong cùng batch hoặc có hiện tượng lùi thời gian.
- Gỡ bỏ lệnh gọi `self.circuit_breaker.advance_time(close_time)` tại Pha 5 để đồng hồ ngắt mạch không bị đẩy vội lên `close_time`, gây lỗi lùi thời gian cho các symbol đến sau trong cùng batch.

### H4 — Transactional Public Operations & Config Fail-Closed
- **`close_all_positions`:** Kiểm tra giá hợp lệ hữu hạn, kiểm tra time reversal so với `current_time`, `circuit_breaker.last_event_time` và `pos.opened_at`, kiểm tra kiểu `ExitReason` enum trước khi đóng bất kỳ vị thế nào. Nếu gặp lỗi, ném ngoại lệ và không để lại bất kỳ đột biến nào trong danh sách vị thế hay lịch sử giao dịch.
- **`_validate_config`:** Kiểm tra tất cả các phân vùng cấu hình phụ (`funding_rate`, `account`, `fees`, `leverage_brackets`, `circuit_breakers`, `risk`). Nếu có mặt mà không phải kiểu `dict`, ném `TypeError` ngay lập tức, không âm thầm fallback sang default.

### H5 — Vòng Đời Kết Thúc Dữ Liệu (`finalize`)
- Bổ sung phương thức `finalize(timestamp=None, force_close=False) -> Dict[str, Any]`:
  - Mang tính idempotent: gọi nhiều lần trả về cùng bản tóm tắt phiên mà không gây lỗi hoặc double close.
  - Chuyển broker sang trạng thái terminal `is_finalized = True`.
  - Hủy sạch toàn bộ `pending_orders`.
  - Nếu `force_close=True`: đóng toàn bộ vị thế mở với `ExitReason.END_OF_DATA`, áp dụng phí taker và trượt giá thoát lệnh.
  - Nếu `force_close=False`: giữ nguyên các vị thế mở, trả về chi tiết số dư ví, ký quỹ, unrealized PnL và equity.
  - Sau khi finalize: `process_candle` ném `RuntimeError`, `submit_order` trả về bản ghi lệnh bị từ chối với lý do `EXECUTION_REJECT_FINALIZED`.

### H6 — Funding Provenance, Script Tải Dữ Liệu & Minh Bạch Hồ Sơ
- **Provenance & Readiness:**
  - Kiểm tra `funding_time`: ném `ValueError` nếu `funding_time > open_time` (Lookahead bias) hoặc `funding_time < open_time - 24h` (quá cũ).
  - Kiểm tra `funding_readiness`: ném `ValueError` nếu cờ này là `False` tại mốc thanh toán funding khi đang mở vị thế.
- **Tạo Script `scripts/fetch_market_data.py`:** Tải dữ liệu nến 15m và funding rate 8h từ Binance USD-M Futures REST API và lưu vào `data/raw/binance/{symbol}/`.
- **Khôi phục Checklist `PROJECT_STATE.md`:** Khôi phục đầy đủ dòng trạng thái đã nghiệm thu của Giai đoạn 3 (theo Review 04) và cập nhật tiến độ Giai đoạn 4.
- **Tính Minh Bạch Báo Cáo:** Phân biệt rõ kết quả chạy trong môi trường tác giả (181 passed offline, 5 deselected network tests) và môi trường reviewer (168 passed nếu không cài `pandas-ta`).

---

## 3. Kết Quả Kiểm Thử Thực Tế

### 3.1 Bộ Probe Độc Lập Review 06 (`docs/reviews/test_stage_04_review_06.py`)
```text
python -m pytest docs/reviews/test_stage_04_review_06.py -q --tb=short
11 passed, 1 warning in 0.58s [100%]
```
- `test_H1_entry_fee_hits_daily_guard_at_entry_without_counting_a_trade`: PASSED
- `test_H1_funding_is_not_double_counted_when_trade_later_closes`: PASSED
- `test_H1_closed_trade_records_gross_price_pnl_and_exit_fee_as_cashflows`: PASSED
- `test_H2_collateral_solver_uses_tier_at_liquidation_not_entry`: PASSED
- `test_H2_invalid_brackets_never_fall_back_to_hardcoded_tier`: PASSED
- `test_H3_two_symbols_can_advance_at_the_same_market_timestamp`: PASSED
- `test_H3_all_open_symbols_are_funded_once_at_same_settlement`: PASSED
- `test_H4_close_all_time_reversal_is_transactional`: PASSED
- `test_H4_malformed_funding_config_is_rejected`: PASSED
- `test_H4_mutated_pending_request_is_cleanly_rejected`: PASSED
- `test_H5_finalize_prevents_future_entries`: PASSED

### 3.2 Bộ Probe Độc Lập Review 05 (`docs/reviews/test_stage_04_review_05.py`)
```text
python -m pytest docs/reviews/test_stage_04_review_05.py -q --tb=short
26 passed, 1 warning in 0.67s [100%]
```
Toàn bộ 26/26 tình huống kiểm tra độc lập của Review 05 tiếp tục đạt 100%, không bị hồi quy.

### 3.3 Bộ Kiểm Thử Bổ Sung Biên H1–H6 (`tests/test_stage_04_review_06_coverage.py`)
```text
python -m pytest tests/test_stage_04_review_06_coverage.py -q --tb=short
11 passed, 1 warning in 0.60s [100%]
```

### 3.4 Toàn Bộ Bộ Kiểm Thử Đơn Vị Offline Dự Án (`tests/`)
```text
python -m pytest tests -m "not network" -q
181 passed, 5 deselected, 1 warning in 1.66s [100%]
```
*(Ghi chú: 5 test liên quan đến mạng ngoài `test_fetcher_integration_network` được deselect bằng marker `not network` theo đúng chuẩn kiểm thử offline)*.

### 3.5 Chạy Thực Tế Kịch Bản Mô Phỏng (`scripts/simulate_paper_execution.py`)
```text
python scripts/simulate_paper_execution.py
Phần A (Synthetic Simulation):
- Thoát lệnh Gap Down tại 44,986.50 USD.
- Khóa ngắt mạch 24h: Rolling 24h PnL = -687.09 USD (vượt ngưỡng -465.65 USD).
  => Khớp chính xác 100% với delta ví tại lúc lock (10,000 - 9,312.91 = -687.09 USD).
- Phục hồi Risk Multiplier về 1.00 sau 3 trận thắng liên tiếp.
- Vốn cuối: 9,440.94 USD = Vốn ban đầu (10,000.00) + Tổng Net PnL (-559.06).
- Đối soát kế toán: HOÀN TOÀN KHỚP (PASS).

Phần B (Real Data Simulation trên 120 nến 15m cached):
- 1 lệnh đóng có lãi (Take Profit tại 63,580.92 USD).
- Số dư ví cuối: 10,015.79 USD | Vốn: 10,015.79 USD.
- Đối soát bất biến kế toán: HOÀN TOÀN KHỚP (PASS).
Exit code: 0.
```

---

## 4. Kết Luận & Điểm Dừng Bắt Buộc

1. Toàn bộ 6 phát hiện H1–H6 của Review 06 đã được khắc phục triệt để.
2. Không chỉnh sửa, xóa hoặc né tránh bất kỳ assertion nào trong 2 bộ probe của Review 05 và Review 06.
3. Hồ sơ tài liệu (`PROJECT_STATE.md`, `ADR 0007`, `CHANGELOG.md`, `PLANNER_HANDOVER.md`) đã được cập nhật đầy đủ và đồng bộ.
4. **DỪNG CHỜ GPT REVIEW 07. TUYỆT ĐỐI KHÔNG BẮT ĐẦU GIAI ĐOẠN 5.**
