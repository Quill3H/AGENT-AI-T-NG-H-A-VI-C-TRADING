# ADR 0007: Kiến Trúc Paper Execution Engine (Mô Phỏng Khớp Lệnh Isolated Margin & Chống Nhìn Trước)

**Trạng thái:** ACCEPTED  
**Ngày quyết định:** 2026-09-19  
**Người quyết định:** Quill3H & Antigravity (theo đặc tả kỹ thuật và yêu cầu nghiệm thu Giai đoạn 4)

---

## 1. Bối cảnh
Sau khi hoàn thành và nghiệm thu Giai đoạn 3 (Risk Manager), hệ thống cần một động cơ khớp lệnh mô phỏng (Paper Execution Engine) để kiểm thử các chiến lược giao dịch trong tương lai (Giai đoạn 5+).

Để đảm bảo kết quả backtest và paper trading phản ánh trung thực thực tế thị trường tiền mã hóa phái sinh (Binance USDT-Margined Futures), động cơ thực thi phải loại bỏ hoàn toàn các lỗi thiên lệch (bias) thường gặp:
1. **Thiên lệch nhìn trước (Lookahead Bias):** Dùng dữ liệu High, Low hoặc Close của nến hiện tại để tính toán kích thước vị thế hoặc quyết định vào lệnh ngay tại Open.
2. **Khớp lệnh phi thực tế:** Khớp tại giá tín hiệu thay vì giá Open nến sau, bỏ qua trượt giá (slippage) và phí giao dịch (taker fee).
3. **Bỏ qua hiện tượng nhảy Gap:** Khi thị trường biến động mạnh vượt qua giá Stop Loss hoặc giá Thanh lý tại thời điểm mở nến, lệnh vẫn được khớp ở giá SL cũ thay vì giá Open thực tế.
4. **Mâu thuẫn intrabar:** Khi trong 1 nến cả TP và SL đều nằm trong biên độ [Low, High], việc giả định chạm TP trước là lạc quan tếu (optimistic bias).
5. **Sai lệch kế toán & Funding Rate:** Không tính phí tài trợ vốn (Funding Rate) 8 tiếng/lần, không hạch toán ký quỹ cô lập (isolated margin) chuẩn, hoặc trừ phí hai lần.

---

## 2. Quyết định Kiến trúc & Nguyên tắc Thiết kế

### 2.1 Mô hình Tài khoản & Ký quỹ Cô lập (Isolated Margin Futures)
- Hệ thống mô phỏng hợp đồng tương lai ký quỹ bằng USDT (Linear USDT-margined futures).
- Chế độ ký quỹ: **Isolated Margin** (Ký quỹ cô lập) cho từng symbol.
  - Mỗi vị thế chỉ được sử dụng số tiền ký quỹ được bảo lưu riêng cho nó (`isolated_collateral`).
  - Tiền ký quỹ ban đầu: $M_{initial} = \frac{\text{notional}}{\text{leverage}} = \frac{Q \times \text{fill\_price}}{\text{leverage}}$.
  - Số dư ký quỹ khả dụng: $\text{available\_margin} = \text{wallet\_balance} - \text{reserved\_collateral}$.
  - Phí vào lệnh (`entry_fee`) được trừ trực tiếp từ số dư ví tự do (`wallet_balance`), không tính vào ký quỹ ban đầu.
  - Phí funding được cộng/trừ trực tiếp vào cả `wallet_balance` và `isolated_collateral` của vị thế tại thời điểm settlement.

### 2.2 Quy trình 5 Pha Xử lý Nến Chống Nhìn Trước Tuyệt Đối (5-Phase Pipeline)
Mỗi cây nến OHLCV được xử lý tuần tự qua 5 pha bất biến theo trục thời gian thực:

```
[Open Time] ────────────────────────────────────────────────────────► [Close Time]
 │                                                                       │
 ├─ Pha 1: Open Time & Gap Exits (quét gap qua SL / Liq)                 │
 ├─ Pha 2: Funding Settlement (00:00, 08:00, 16:00 UTC)                  │
 ├─ Pha 3: Pending Market Entry & Risk Gate (khớp tại Open + Slippage)   │
 ├─ Pha 4: Intrabar Protection [Low, High] (Ưu tiên Liq > SL > TP)       │
 └───────────────────────────────────────────────────────────────────────┴─ Pha 5: Close Time & Mark-to-Market
```

1. **Pha 1 (Open Time & Gap Exits):**
   - Đồng hồ hệ thống tiến tới `candle.open_time`.
   - Với vị thế đang mở mang từ nến trước: kiểm tra nếu giá `open` nhảy khoảng trống vượt qua `stop_loss_price` hoặc `liquidation_price`.
   - Nếu xảy ra Gap: lệnh bị cưỡng chế thoát ngay tại giá `open` (có áp dụng slippage bán/mua), không được thoát ở mức giá SL cũ.

2. **Pha 2 (Funding Settlement):**
   - Chỉ kích hoạt tại các mốc giờ quy định trong config (mặc định 00:00, 08:00, 16:00 UTC).
   - Chỉ áp dụng cho các vị thế đã tồn tại trước mốc này và sống sót qua Pha 1. Lệnh mới mở ở Pha 3 không phải chịu funding ở mốc này.
   - Giá tính funding: giá `open` tại mốc settlement (đã xác định tại thời điểm nến mở).
   - Dòng tiền funding:
     $$\text{cashflow} = -\text{direction\_sign} \times Q \times \text{mark\_price} \times \text{funding\_rate}$$
     (LONG: sign = +1, rate dương $\implies$ trả phí; SHORT: sign = -1, rate dương $\implies$ nhận tiền).

3. **Pha 3 (Pending Market Entry & Risk Gate Admission):**
   - Lọc các lệnh chờ (`pending_orders`) có $\text{signal\_time} \le \text{open\_time}$ cho symbol hiện tại.
   - Tính giá khớp giả định có trượt giá:
     - LONG: $\text{fill\_price} = \text{open} \times (1 + \text{slippage\_pct})$
     - SHORT: $\text{fill\_price} = \text{open} \times (1 - \text{slippage\_pct})$
   - Tính toán kích thước vị thế qua `calculate_position_size` và giá thanh lý qua `calculate_estimated_liquidation_price`.
   - Chụp snapshot tài khoản và đưa lệnh qua cổng kiểm soát rủi ro toàn diện: `check_all_invariants(...)` (Giai đoạn 3).
   - Nếu từ chối: chuyển trạng thái `ORDER_REJECTED` kèm lý do chi tiết, không biến động tài sản.
   - Nếu chấp thuận: trừ phí `entry_fee`, bảo lưu `initial_margin`, mở vị thế chính thức.

4. **Pha 4 (Intrabar Protection):**
   - Đánh giá khoảng giá biến động trong nến $[Low, High]$.
   - Áp dụng triệt để quy tắc bảo vệ thận trọng tối cao (Conservative Priority):
     $$\mathbf{Liquidation} \succ \mathbf{Stop\ Loss} \succ \mathbf{Take\ Profit}$$
   - Nếu cả SL và TP đều nằm trong biên độ của nến: hệ thống bắt buộc coi là dính Stop Loss trước.
   - Nếu cả Liquidation và SL đều bị xuyên thủng: hệ thống bắt buộc coi là dính Thanh lý.

5. **Pha 5 (Close Time & Mark-to-Market):**
   - Đồng hồ hệ thống tiến tới `candle.close_time`.
   - Đánh giá lại lãi/lỗ chưa thực hiện (`unrealized_pnl`) theo giá `close`.
   - Cập nhật số dư vốn tức thời: $\text{equity} = \text{wallet\_balance} + \text{unrealized\_pnl}$.
   - Chụp ảnh snapshot tài khoản cuối nến và đối soát các bất biến kế toán.
   - Cho phép các chiến lược (Giai đoạn 5+) quan sát giá `close` để sinh tín hiệu mới cho nến kế tiếp.

### 2.3 Quản lý Ràng buộc Vị thế & Đơn lệnh (Single Position Policy)
- **Tối đa 1 vị thế hoạt động trên mỗi symbol:** Tuyệt đối không cho phép nhồi lệnh (no pyramiding), không phòng hộ 2 chiều (no hedging).
- **Không tự động đảo chiều (No Auto-reversal):** Nếu đang có vị thế LONG, tín hiệu SHORT mới sẽ bị từ chối ngay tại Pha 3 cho đến khi vị thế LONG được đóng hoàn toàn.
- **Thắt chặt Stop Loss một chiều (Tightening Only):** Khi vị thế đang mở, chỉ chấp nhận dịch chuyển Stop Loss theo hướng giảm rủi ro (dịch lên đối với LONG, dịch xuống đối với SHORT). Mọi yêu cầu nới rộng khoảng cách Stop Loss đều bị từ chối.

### 2.4 Hạch toán Kế toán & Tích hợp Hai chiều với Circuit Breaker
- **Các phương trình bất biến kế toán:**
  $$\text{wallet\_balance} = \text{initial\_equity} + \sum \text{net\_pnl}_{\text{closed}} + \sum \text{funding\_cashflow}_{\text{open}} - \sum \text{entry\_fee}_{\text{open}}$$
  $$\text{equity} = \text{wallet\_balance} + \sum \text{unrealized\_pnl}_{\text{open}}$$
  $$\text{available\_margin} = \text{wallet\_balance} - \sum \text{isolated\_collateral}_{\text{open}}$$
- **Tích hợp Circuit Breaker:**
  - Khi một trade đóng hoàn tất, net PnL (đã trừ phí entry, exit và funding) được gửi vào `record_trade_result`.
  - Nếu xảy ra 3 trận thua liên tiếp $\implies$ giảm `risk_multiplier` xuống 0.5.
  - Khi ở chế độ giảm rủi ro, nếu đạt đủ 3 trận thắng liên tiếp $\implies$ tự động phục hồi `risk_multiplier` về 1.0.
  - Khi tổng lỗ rolling 24h chạm ngưỡng 5% equity $\implies$ kích hoạt khóa 24 giờ (`is_locked = True`), cưỡng chế đóng toàn bộ vị thế đang mở và từ chối mọi lệnh vào mới cho đến khi hết hạn khóa.

---

## 3. Hệ quả & Tác động
- Động cơ thực thi độc lập hoàn toàn với việc sinh tín hiệu: không chứa bất kỳ logic chỉ báo hay chiến lược giao dịch nào.
- 100% tuân thủ các bất biến rủi ro đã được nghiệm thu ở Giai đoạn 3 mà không cần nới lỏng hay sửa đổi logic gốc.
- Đảm bảo tính tất định (Determinism): hai lần chạy với cùng chuỗi nến và lệnh cho ra cùng một bảng lịch sử giao dịch và số dư ví chính xác từng bit.
- Sẵn sàng cung cấp interface khớp lệnh chuẩn xác cho Giai đoạn 5 (Alpha Discovery & Strategy Development).
