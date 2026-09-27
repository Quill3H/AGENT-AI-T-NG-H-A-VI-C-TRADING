# ADR 0008: Kiến Trúc Chiến Lược Trend Following & Cỗ Máy Backtest Đa Khung Thời Gian

**Trạng thái:** PENDING REVIEW (Chờ nghiệm thu theo GPT Review 10)  
**Ngày đề xuất:** 2026-09-19  
**Người đề xuất:** Quill3H & Antigravity (theo đặc tả kỹ thuật Giai đoạn 5 — ANTIGRAVITY_STAGE_05_TASK.md)

---

## 1. Bối cảnh
Sau khi hoàn thành và nghiệm thu Giai đoạn 4 (Paper Execution Engine với chu trình 5 pha chống nhìn trước và kiểm toán sổ cái kế toán tự động), hệ thống bước vào Giai đoạn 5: Xây dựng chiến lược bám đuổi xu hướng đầu tiên (**Trend Following**) và cỗ máy kiểm thử lịch sử (**BacktestEngine**) tối thiểu.

Mục tiêu cốt lõi của Giai đoạn 5:
1. Thiết lập hợp đồng giao tiếp chuẩn giữa Chiến lược (`BaseStrategy`) và Động cơ khớp lệnh (`PaperBroker`).
2. Hiện thực hóa Rulebook Trend Following thuần nhân quả (causal) trên khung thời gian đa tầng: **4h cho Signal/Regime** và **15m cho Thực thi (Execution)**.
3. Loại bỏ 100% rủi ro nhìn trước (Lookahead Bias) trong đồng bộ đa khung: chiến lược chỉ nhìn thấy nến 4h đã đóng hoàn toàn, lệnh được khớp tại giá Open (+ trượt giá) của nến 15m kế tiếp.
4. Đóng mắt xích nguồn gốc dữ liệu tài trợ vốn (Funding Provenance Seam) từ Data Layer sang PaperBroker: bảo toàn `funding_time` thực và cờ sẵn sàng `funding_readiness`.
5. Đảm bảo tính tái lập 100% (deterministic replay) trên dữ liệu thực 3 năm BTCUSDT (2021-01-01 đến 2023-12-31).

---

## 2. Quyết định Kiến trúc & Thiết kế

### 2.1 Hợp đồng Chiến lược Tối thiểu (`BaseStrategy`)
- Giao diện trừu tượng (`ABC`) định nghĩa 2 phương thức bắt buộc:
  - `on_candle_close(candle_4h, history_4h, broker_state) -> Optional[OrderRequest]`: Được gọi tại mỗi mốc nến 4h đóng hoàn toàn. Nhận dữ liệu nến 4h vừa đóng và toàn bộ lịch sử 4h causal tính đến nến đó.
  - `update_trailing_stop(candle_4h, broker) -> None`: Cập nhật trailing stop loss bám EMA50 cho vị thế đang mở.
- Chiến lược không tự ý sửa đổi trạng thái tài khoản, không tự tính toán số dư hay can thiệp vào `Position`. Mọi hành động mở vị thế đều thông qua `OrderRequest` gửi tới `PaperBroker.submit_order()`.

### 2.2 Máy Trạng Thái Trend Following (Causal State Machine)
- Trạng thái quản lý theo cặp (symbol, direction): `IDLE` hoặc `ARMED`.
- **Crossover Trigger:**
  - LONG: `ema20[t-1] <= ema50[t-1]` và `ema20[t] > ema50[t]` đồng thời `close[t] > ema200[t]`.
  - SHORT: `ema20[t-1] >= ema50[t-1]` và `ema20[t] < ema50[t]` đồng thời `close[t] < ema200[t]`.
  - Khi xuất hiện giao cắt: setup chuyển sang `ARMED`, lưu `trigger_time = close_time[t]`, đặt `setup_age_bars = 0`. **Tuyệt đối không vào lệnh tại nến crossover!**
- **Pullback / Retest Confirmation (trên nến 4h kế tiếp sau trigger):**
  - Tuổi setup `setup_age_bars` tăng thêm 1 mỗi nến 4h.
  - **Hết hạn (Expiry):** Nếu `setup_age_bars > max_setup_age_bars` (mặc định 12 nến 4h = 48 giờ) mà chưa có điểm vào -> reset về `IDLE`.
  - **Vô hiệu hóa (Invalidation):** Nếu xu hướng đảo chiều (`close <= ema200` hoặc `ema20 < ema50` cho LONG) -> reset về `IDLE`.
  - **Retest thỏa mãn:**
    - LONG: Biên nến giao với vùng giữa EMA20 và EMA50 (`low <= ema20` và `high >= ema50`), đồng thời nến đóng giữ vững phía thuận xu hướng (`close >= ema20`).
    - SHORT: Biên nến giao với vùng giữa EMA20 và EMA50 (`high >= ema20` và `low <= ema50`), đồng thời nến đóng giữ vững phía thuận xu hướng (`close <= ema20`).
- **Bộ lọc Xung lượng (Momentum Gate):**
  - LONG: `rsi_14 > 50.0` (nghiêm ngặt, tại biên 50.0 từ chối).
  - SHORT: `rsi_14 < 50.0` (nghiêm ngặt, tại biên 50.0 từ chối).
- **Hợp lưu Open Interest (OI Confluence - ADR 0005):**
  - Yêu cầu `oi_delta_pct > 0` xác nhận dòng tiền mới gia nhập xu hướng.
  - Chế độ `optional`: nếu OI là NaN do dữ liệu lịch sử thiếu, cho phép bypass kèm ghi chú `OI_BYPASSED_HISTORICAL`.
  - Chế độ `strict`: chặn vào lệnh nếu OI là NaN/thiếu.
  - Các giá trị sai kiểu (string, bool) hoặc không hữu hạn (Inf/-Inf) đều fail-closed.
- **Nguyên tắc One-shot:** Một crossover chỉ phát sinh tối đa một lệnh; phát lệnh thành công lập tức reset về `IDLE`.

### 2.3 Quản Lý Cắt Lỗ Causal & Trailing Stop Thắt Chặt Một Chiều
- **Cắt lỗ ban đầu (Swing Causal Stop Loss):**
  - LONG: Sử dụng đáy thấp nhất (`min(low)`) trong cửa sổ `swing_lookback_bars` (mặc định 5 nến 4h đã đóng gần nhất). Bắt buộc `stop_loss_price < signal_price`.
  - SHORT: Sử dụng đỉnh cao nhất (`max(high)`) trong cửa sổ `swing_lookback_bars`. Bắt buộc `stop_loss_price > signal_price`.
  - Yêu cầu đủ warm-up lịch sử (tối thiểu 5 nến). Nếu stop sai phía hoặc không hợp lệ -> từ chối phát lệnh.
- **Chốt lời (Take Profit):** Không sử dụng take-profit cố định hay partial TP (`take_profit_price = None`). Vị thế để ngỏ cho xu hướng chạy và đóng theo trailing stop.
- **Trailing Stop Loss (Bám EMA50 nến 4h đóng):**
  - Đánh giá tại mỗi nến 4h đóng khi có vị thế mở.
  - Chỉ gọi `PaperBroker.update_stop_loss()` khi mức stop mới thắt chặt rủi ro (tightening-only):
    - LONG: `candidate_stop > current_stop` và `candidate_stop < mark_price`.
    - SHORT: `candidate_stop < current_stop` và `candidate_stop > mark_price`.
  - Tuyệt đối không nới rộng stop loss và không sửa trực tiếp trường dữ liệu của `Position`.

### 2.4 Cỗ Máy Backtest Đa Khung Thời Gian (`BacktestEngine`)
- **Nguyên tắc Đồng hồ Sự kiện (Event-Driven Clock):**
  - Trục thời gian chính được dẫn dắt bởi nến thực thi 15m: `broker.process_candle(candle_15m)`.
  - Funding settlement được kích hoạt đúng mốc 00:00, 08:00, 16:00 UTC trên nến 15m.
  - Tại mỗi mốc nến 15m kết thúc, động cơ kiểm tra nếu `close_time_15m == close_time_4h`:
    - Trích xuất lát cắt nến 4h hoàn tất tại thời điểm đó: `data_4h.loc[:open_4h]`.
    - Cập nhật trailing stop trước.
    - Đánh giá tín hiệu và submit lệnh vào `broker.pending_orders`.
  - Lệnh có trạng thái `PENDING` sẽ được khớp tại Pha 3 của nến 15m kế tiếp ở giá `Open + Slippage`.
- **Thẩm định Schema Fail-closed:**
  - Kiểm tra tính đơn điệu tăng dần, không trùng lặp timestamp, DatetimeIndex UTC, các trường OHLCV hữu hạn và dương, tính hợp lệ hình học nến (`high >= max(open, close)`...). Bất kỳ lỗi dữ liệu nào đều fail-closed trước khi mutate broker.
- **Tất toán Phiên (Finalize):**
  - Gọi `broker.finalize(force_close=True/False)`.
  - Bắt buộc chạy kiểm toán sổ cái kế toán tự động (`verify_accounting_invariants`) với dung sai $10^{-4}$ USDT.

### 2.5 Đóng Mắt Xích Funding Provenance (`fetcher.py`)
- Trong `merge_ohlcv_with_oi_and_funding`:
  - Lưu giữ timestamp thực của bản ghi funding nguồn thành `funding_time`.
  - Đặt `funding_readiness = True` chỉ khi: `funding_rate` hữu hạn, `funding_time` hợp lệ, không nằm ở tương lai (`<= df.index`), và không bị cũ/stale (`>= df.index - 24h`).
  - Khi thiếu dữ liệu nguồn, giữ nguyên `funding_readiness = False` để hệ thống fail-closed tại mốc settlement nếu có vị thế mở.

---

## 3. Hệ quả & Đánh giá
1. **Loại bỏ Lookahead Bias:** Được chứng minh qua probe kiểm thử `test_future_perturbation_invariance`: làm biến dạng toàn bộ dữ liệu tương lai sau thời điểm $T$ không làm thay đổi bất kỳ lệnh, giao dịch hay trạng thái tài khoản nào trước hoặc tại $T$.
2. **Tính Tái lập 100%:** Seed ngẫu nhiên cố định (`random.seed(42)`, `np.random.seed(42)`), ID giao dịch sinh tất định theo thời gian và số thứ tự (`ORD_...`, `TRD_...`).
3. **Toàn vẹn Kế toán:** Kiểm toán sổ cái luôn khớp từng cent:
   $$\text{wallet\_balance} = \text{initial\_balance} + \sum \text{gross\_pnl} - \sum \text{fees} + \sum \text{funding}$$
4. **Phạm vi Giới hạn:** Không mở rộng sang Giai đoạn 6 (không tạo SQLite trade logger tổng quát, không tạo metrics framework phức tạp, không dashboard).
