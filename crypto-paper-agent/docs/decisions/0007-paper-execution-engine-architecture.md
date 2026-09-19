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

---

## 4. Phụ lục: Bổ sung & Chuẩn hóa Kiến trúc theo GPT Review 05 (E1–E8)

Ngày cập nhật: 2026-09-19  
Phạm vi giải quyết: 8 nhóm vấn đề kỹ thuật E1–E8 phát hiện bởi GPT Review 05.

### 4.1 Cấu hình Settlement Hours, Tính Toàn Vẹn & Khóa Trùng Funding (E1)
- **Settlement Hours động:** Đọc từ `config['execution']['settlement_hours_utc']` (mặc định `[0, 8, 16]`). Toàn bộ giờ phải thuộc $[0, 23]$, không trùng lặp và được sắp xếp tăng dần.
- **Idempotency Key:** Mỗi sự kiện thanh toán funding được định danh duy nhất bằng cặp khóa `(symbol, candle.open_time)`, đảm bảo không bao giờ thanh toán trùng lặp tại cùng một nến.
- **Xác thực Funding Rate:** Khi nến rơi vào giờ thanh toán, nếu `funding_rate` bị khuyết (`None`) hoặc không hữu hạn (`NaN`, `Inf`) thì động cơ lập tức từ chối xử lý nến trước khi bất kỳ trạng thái nào bị đột biến.
- **Phát hiện Gap bỏ qua Settlement:** Khi vị thế đang mở, nếu bước nhảy thời gian giữa hai nến liên tiếp vượt qua một hoặc nhiều mốc settlement hours mà không có dữ liệu nến tương ứng, động cơ ném ngoại lệ từ chối để ngăn chặn việc lẩn tránh nghĩa vụ ký quỹ/phí funding.

### 4.2 Cập nhật Giá Thanh lý Theo Ký quỹ Thực tế (Collateral-Aware Liquidation) (E2)
- Khi dòng tiền funding được cộng/trừ vào `isolated_collateral`, tỷ lệ đòn bẩy thực tế và khoảng đệm an toàn thay đổi.
- Động cơ tự động gọi lại bộ giải thanh lý chuẩn `calculate_estimated_liquidation_price` với `isolated_collateral` mới và `get_mmr_tier(position_size_usd, symbol, leverage_brackets)`, cập nhật lại `position.liquidation_price` theo thời gian thực.

### 4.3 Dòng Tiền Độc Lập cho Circuit Breaker & Cưỡng Chế Đóng Khi Khóa (E3)
- Bổ sung phương thức `record_cashflow(amount, timestamp, equity)` vào `CircuitBreakerState`: ghi nhận ngay lập tức phí giao dịch và funding cashflow vào cửa sổ trượt lỗ 24h mà không làm biến dạng chuỗi thắng/thua (trade streak) hay làm méo mó `risk_multiplier`.
- Tự động kích hoạt cơ chế thoát hiểm khẩn cấp `_handle_circuit_breaker_lock`: khi tổng lỗ chạm trần khiến Breaker kích hoạt khóa (`is_locked = True`), Paper Broker tự động hủy toàn bộ lệnh chờ (`pending_orders`) và cưỡng chế đóng toàn bộ vị thế đang mở còn lại theo giá thị trường (có áp dụng exit slippage) với mã lý do `CIRCUIT_BREAKER_LOCK`.

### 4.4 Hạch toán Vốn Sau Khi Đóng Vị Thế (Post-Close Equity) (E4)
- Khi đóng một vị thế, vị thế đó được gỡ bỏ khỏi danh mục `self.positions` trước khi tính toán lại `post_close_equity` để gửi vào Circuit Breaker.
- Loại bỏ hoàn toàn lỗi cộng hai lần (double counting) lãi/lỗ chưa thực hiện cũ của vị thế vừa đóng vào số dư equity mới.

### 4.5 Tái Kiểm Soát Cổng Duyệt Lệnh & Xử Lý Lỗi Solver (E5)
- Tái kiểm tra khoảng cách Stop Loss và Take Profit sau khi tính toán giá khớp có trượt giá (`fill_price`):
  - Nếu thị trường nhảy Gap khiến `fill_price` chạm hoặc vượt qua `stop_loss_price`, lệnh bị từ chối sạch sẽ với trạng thái `ORDER_REJECTED` (`REASON: Fill price crossed stop loss`).
  - Nếu khoảng cách TP không hợp lệ so với giá fill thực tế, lệnh bị từ chối với trạng thái `ORDER_REJECTED`.
- Bắt toàn bộ ngoại lệ định cỡ/thanh lý (`ValueError` từ solver hoặc position sizing) và chuyển thành `ORDER_REJECTED` với mô tả lỗi cụ thể, tuyệt đối không để unhandled exception làm sập tiến trình nến.
- Kiểm tra khớp đúng giữa ngân sách rủi ro khai báo (`order_declared_budget_usd`) và `risk_percent` cấu hình.

### 4.6 Giao Dịch Nguyên Khối (Transactional Preflight Validation) (E6)
- Trước khi thực hiện bất kỳ thay đổi trạng thái nào trong `process_candle`, Broker kiểm tra toàn diện:
  - Quan hệ hình thái nến: $High \ge \max(Open, Close)$ và $Low \le \min(Open, Close)$, $High \ge Low > 0$.
  - Định dạng khung thời gian (`timeframe`): regex hợp lệ (ví dụ `15m`, `1h`, `4h`) và có thời lượng dương $> 0$.
  - Thời gian mở nến đơn điệu tăng nghiêm ngặt: $open\_time > last\_candle\_open\_time$.
  - Thời gian đóng nến nhất quán: $close\_time > open\_time$ và đúng thời lượng nến.
- Nếu bất kỳ điều kiện nào không thỏa mãn, ném ngoại lệ và bảo toàn 100% trạng thái của Broker và Circuit Breaker (Zero Financial Mutation).

### 4.7 Nâng Cao Độ Trung Thực Khớp Lệnh (Execution Fidelity) (E7)
- Cưỡng chế đóng lệnh khẩn cấp (`close_all_positions`) phải áp dụng trượt giá thoát lệnh (`slippage_pct`).
- Thắt chặt Stop Loss (`update_stop_loss`) không được phép vượt qua giá thị trường hiện tại (Mark Price).
- Tại Pha 1, nếu nến mở cửa nhảy Gap qua giá Take Profit, vị thế được ưu tiên chốt lời ngay tại giá mở cửa trước khi thực hiện thanh toán Funding ở Pha 2.

### 4.8 Xác Thực Miền Cấu Hình & Bất Biến Số Học (E8)
- Xác thực khởi tạo Engine: `initial_equity_usd` phải hữu hạn và $> 0$; các tham số phí (`taker_pct`, `slippage_pct`) phải là số thực hữu hạn trong $[0, 1.0]$.
- Gia cố `verify_accounting_invariants`: kiểm tra `math.isfinite` trên toàn bộ số dư ví, ký quỹ khả dụng, ký quỹ cô lập và tổng unrealized PnL trước khi thực hiện các phép so sánh dung sai, chặn đứng hoàn toàn việc lọt lỗi do giá trị không hữu hạn.

---

## 5. Phụ Lục 2: Hoàn Thiện Cơ Chế Thực Thi Theo GPT Review 06 (H1–H6)

### 5.1 Ghi Nhận Dòng Tiền Chính Xác & Chống Cộng Trùng (H1)
- **Entry Fee**: Ghi nhận `-entry_fee` vào rolling cashflow ledger của Circuit Breaker ngay tại thời điểm mở vị thế (Phase 3). Nếu khoản phí này kích hoạt khóa 24h, vị thế lập tức bị đóng cưỡng chế mà không làm tăng chuỗi lệnh thua (`consecutive_losses`).
- **Funding Cashflow**: Ghi nhận đúng một lần tại thời điểm thanh toán (Phase 2).
- **Exit Cashflow**: Khi đóng vị thế, chỉ ghi nhận `gross_price_pnl - exit_fee` vào rolling cashflow ledger; đồng thời gọi `record_trade_outcome(net_trade_pnl)` để cập nhật chuỗi thắng/thua.
- **Tính nhất quán**: Toàn bộ dòng tiền cấu thành lợi nhuận của vị thế (Entry fee, Funding, Realized price PnL, Exit fee) được ghi nhận chính xác 1 lần tại đúng mốc thời gian phát sinh, loại bỏ hoàn toàn hiện tượng tính trùng (double-counting) trong cửa sổ 24h.

### 5.2 Solver Thanh Lý Nhất Quán Theo Tier Tại Điểm Nghiệm (H2)
- Thay thế việc tra cứu MMR tier dựa trên quy mô tại giá vào lệnh bằng solver giải nhất quán theo quy mô tại chính giá thanh lý ($Q \times P_{liq}$).
- Phương trình nghiệm:
  - LONG: $P = \frac{Q \cdot Entry - C - cum}{Q \cdot (1 - mmr)}$
  - SHORT: $P = \frac{Q \cdot Entry + C + cum}{Q \cdot (1 + mmr)}$
- Bắt buộc kiểm tra điều kiện tự nhất quán: $Q \times P \in (\text{lower\_bound}, \text{upper\_bound}]$.
- Loại bỏ hoàn toàn fallback sang tier mặc định `mmr=0.004, cum=0.0`; ném ngoại lệ rõ ràng khi cấu hình bracket hỏng hoặc không tìm thấy nghiệm hợp lệ (Fail-Closed).

### 5.3 Đồng Hồ Sự Kiện Hỗ Trợ Multi-Symbol Cùng Mốc Thời Gian (H3)
- Quản lý đồng hồ nến riêng biệt theo từng cặp giao dịch thông qua `last_candle_open_time_per_symbol` kết hợp watermark mốc nến của batch `current_batch_open_time` và tập hợp `symbols_in_current_batch`.
- Cho phép nhiều symbol cùng được nạp và xử lý tại cùng một `open_time`.
- Ngăn chặn nến lặp của cùng một symbol trong cùng một batch cũng như hiện tượng đảo ngược thời gian thực sự.
- Gỡ bỏ việc nâng sớm đồng hồ ngắt mạch lên `close_time` tại Phase 5 nhằm đảm bảo tính độc lập tuyệt đối với thứ tự nạp nến của các symbol trong cùng batch.

### 5.4 Giao Dịch Nguyên Khối & Cấu Hình Fail-Closed (H4)
- Hàm `close_all_positions` kiểm tra toàn bộ tính hợp lệ của tham số giá, kiểm tra đảo ngược thời gian so với `current_time`, `circuit_breaker.last_event_time` và `pos.opened_at`, cũng như xác thực kiểu enum `ExitReason` trước khi thực hiện bất kỳ thay đổi trạng thái nào.
- Trình kiểm tra cấu hình `_validate_config` bắt buộc mọi phân vùng cấu hình phụ (`funding_rate`, `leverage_brackets`, `circuit_breakers`, `risk`, ...) phải có kiểu `dict`, từ chối ngay lập tức các cấu hình sai kiểu mà không âm thầm dùng giá trị mặc định.

### 5.5 Quản Lý Vòng Đời Kết Thúc Dữ Liệu (Lifecycle Finalize) (H5)
- Bổ sung phương thức `finalize(timestamp=None, force_close=False)`:
  - Mang tính Idempotent: gọi lại nhiều lần trả về cùng một bản tóm tắt phiên giao dịch.
  - Chuyển Broker sang trạng thái kết thúc (`is_finalized = True`): từ chối mọi nến tiếp theo (`RuntimeError`) và tự động từ chối mọi lệnh mở mới (`OrderStatus.REJECTED`).
  - Chế độ mặc định (`force_close=False`): giữ nguyên vị thế mở, tính toán đầy đủ tài sản ròng và ký quỹ.
  - Chế độ cưỡng chế (`force_close=True`): đóng toàn bộ vị thế đang mở theo giá mark gần nhất kèm phí và trượt giá, ghi nhận lý do thoát `ExitReason.END_OF_DATA`.

### 5.6 Nguồn Gốc Dữ Liệu Funding & Tính Sẵn Sàng (H6)
- Xác thực nguồn gốc thời gian của dữ liệu funding (`funding_time`): từ chối nếu thời gian funding nằm trong tương lai so với nến hiện tại (Lookahead bias) hoặc quá cũ (>24 giờ).
- Kiểm tra cờ sẵn sàng của dữ liệu funding (`funding_readiness`): từ chối xử lý nến nếu dữ liệu funding chưa sẵn sàng tại mốc thanh toán khi đang có vị thế mở.
- Bổ sung script tải dữ liệu thị trường thực tế `scripts/fetch_market_data.py`.

