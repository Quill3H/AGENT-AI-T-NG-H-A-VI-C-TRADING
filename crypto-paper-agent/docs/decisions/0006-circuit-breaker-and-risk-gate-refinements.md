# ADR 0006: Chuẩn Hóa Cổng Duyệt Rủi Ro, Tính Toán Thanh Lý Theo Tier Nhất Quán và Trạng Thái Circuit Breaker

**Trạng thái:** ACCEPTED  
**Ngày quyết định:** 2026-09-19  
**Người quyết định:** Quill3H & Antigravity (theo phản biện kỹ thuật độc lập của GPT)

---

## 1. Bối cảnh
Sau đợt triển khai ban đầu của Giai đoạn 3 (Risk Manager), đợt review độc lập của GPT đã phát hiện 6 nhóm vấn đề cần chuẩn hóa về mặt toán học và bảo vệ hệ thống:
1. Xác thực dữ liệu đầu vào chưa chặt chẽ (`NaN`, `Inf`, `bool`, số âm, sai tier không bị từ chối).
2. Chưa đối soát rủi ro biến động giá thực tế ($Q \times |Entry - Stop|$) với ngân sách rủi ro hiệu lực, chưa kiểm tra ký quỹ khả dụng và chưa ép buộc mức giảm risk khi `risk_multiplier = 0.5`.
3. Thiếu thành phần bảo vệ trong `account_state` (ví dụ thiếu breaker hoặc thiếu news filter khi đang bật) vẫn được duyệt lệnh; dùng `datetime.now()` fallback.
4. `CircuitBreakerState` có thể nhiễm `NaN`, chấp nhận sự kiện lùi thời gian, và không tự dọn dẹp các lệnh ngoài cửa sổ 24h khi thời gian trôi qua.
5. Công thức tính giá thanh lý bị lệch khi quy mô vị thế danh nghĩa thay đổi vượt ranh giới tier tại giá thanh lý ($q \times P$ khác tier với $q \times Entry$).
6. Kịch bản mô phỏng chứa lệnh ẩn không hiển thị trên bảng.

---

## 2. Quyết định Kiến trúc & Quy ước Nghiệp vụ

### 2.1 Cổng duyệt lệnh (Admission Gate) & Đối soát Rủi ro Thực tế
- **Xác thực dữ liệu:** Mọi số liệu tài chính (`entry`, `stop`, `quantity`, `leverage`, `risk_percent`, `equity`) bắt buộc phải là số thực hữu hạn dương (loại trừ `bool`, `NaN`, `+/-Inf`). Lỗi đầu vào phải trả mã lỗi ổn định `INVARIANT_FAIL_*`, không văng exception unhandled.
- **Không tự giả định:** Account thiếu `equity` hoặc sai tier sẽ bị từ chối ngay lập tức; không tự sinh vốn mặc định 10,000 USD và không fallback lên trần tier cao nhất.
- **Rủi ro thực tế:** Cổng duyệt tính toán tổn thất giá thực tế khi chạm Stop-Loss:
  $$\text{actual\_risk\_usd} = \text{quantity} \times |\text{entry\_price} - \text{stop\_loss\_price}|$$
  và đối soát với ngân sách rủi ro hiệu lực:
  $$\text{max\_allowed\_risk\_usd} = \text{equity} \times (\text{base\_risk\_percent} \times \text{risk\_multiplier})$$
  Nếu $\text{actual\_risk\_usd} > \text{max\_allowed\_risk\_usd} + 10^{-4} \implies$ Từ chối.
- **Ký quỹ khả dụng:** Tiền ký quỹ ban đầu yêu cầu ($\text{position\_size\_usd} / \text{leverage}$) không được vượt quá số dư ký quỹ khả dụng (`available_margin`, mặc định bằng `equity` nếu chưa có vị thế mở khác).

### 2.2 Tính toán Giá Thanh lý Nhất quán theo Tier (Tier-Consistent Liquidation Price)
- Trong mô hình Isolated Margin chuẩn Binance Futures:
  - Long: $M + q(P - \text{entry}) = q \cdot P \cdot \text{mmr} - \text{cum}$
  - Short: $M + q(\text{entry} - P) = q \cdot P \cdot \text{mmr} - \text{cum}$
- Các tham số $\text{mmr}$ và $\text{cum}$ **bắt buộc phải thuộc về tier của quy mô vị thế tại chính giá thanh lý $P$**, tức $q \times P \in (\text{tier\_min}, \text{tier\_max}]$.
- Giải thuật: Duyệt tìm nghiệm trên từng tier trong `leverage_brackets` và chỉ chấp nhận nghiệm khi $q \times P$ nằm trọn vẹn trong miền định nghĩa của tier đó.

### 2.3 Chuẩn hóa Trạng thái Circuit Breaker
1. **Cửa sổ trượt 24h:** Là khoảng nửa mở nửa đóng $(T - 24\text{h}, T]$. Các lệnh có timestamp $\le T - 24\text{h}$ tự động bị loại khỏi tổng rolling PnL khi thời gian tiến lên.
2. **Thời gian đơn điệu:** Chỉ chấp nhận các sự kiện có $t \ge t_{last}$. Tuyệt đối từ chối sự kiện lùi thời gian.
3. **Quy ước lệnh hòa ($PnL = 0$):** Lệnh hòa ngắt cả chuỗi thắng và chuỗi thua (`consecutive_losses = 0`, `consecutive_wins = 0`), nhưng giữ nguyên `risk_multiplier`.
4. **Thời gian khóa:** Khóa đúng 24 giờ kể từ thời điểm chạm ngưỡng lỗ 5%. Các lệnh đóng sau đó trong thời gian đang bị khóa không làm gia hạn thêm `locked_until`.
5. **Mẫu số tính lỗ:** Ngưỡng lỗ 5% được tính trên `equity` hiện tại sau khi đã cộng/trừ PnL của lệnh vừa đóng.

---

## 3. Hệ quả & Cam kết Tích hợp Giai đoạn 4
- Cổng Risk Manager ở Giai đoạn 3 chịu trách nhiệm chốt chặn rủi ro biến động giá và ký quỹ ban đầu.
- Chi phí giao dịch (phí taker/maker), trượt giá thực tế và funding rate theo diễn biến thị trường sẽ được tích hợp và trừ trực tiếp vào equity khi xây dựng Paper Broker ở Giai đoạn 4.

---

## 4. Phụ lục: Quyết định Bổ sung theo Review Lần 2 (F1 – F5)
Đợt phản biện kỹ thuật độc lập lần 2 (GPT Review 02) đã chỉ ra 5 lỗ hổng biên, dẫn đến các quyết định chuẩn hóa bổ sung:

### F1. Đối soát Ngân sách Lệnh Khai báo & Chống Double Reduction
- Lệnh có thể khai báo `risk_percent` nhỏ hơn trần tier (ví dụ tier 'high' cho phép 3%, nhưng lệnh chỉ dám chấp nhận 1%).
- Cổng duyệt tính ngân sách rủi ro khai báo: $\text{order\_risk\_budget\_usd} = \text{equity} \times \text{order\_effective\_risk\_pct}$. Bắt buộc tổn thất khi chạm SL không được vượt qua ngân sách này: $\text{actual\_price\_risk\_usd} \le \text{order\_risk\_budget\_usd} + 10^{-4}$.
- Nếu truyền cả `base_risk_percent` và `risk_percent`, hệ thống bắt buộc kiểm tra đẳng thức: $\text{risk\_percent} == \text{base\_risk\_percent} \times \text{cb\_multiplier}$ (dung sai $10^{-6}$), chống tình trạng người gọi tự giảm trước rồi hệ thống lại giảm thêm lần nữa (double reduction).

### F2. Cung ứng Ký quỹ Khả dụng & Tính Mạnh mẽ của Dữ liệu Đầu vào
- `available_margin` là bắt buộc, phải là số thực hữu hạn $\ge 0$. Không tự ý fallback dùng `equity`.
- Tổng vốn bắt buộc cung ứng trước khi mở lệnh bao gồm cả ký quỹ ban đầu và phí vào lệnh ước tính:
  $$\frac{\text{position\_size\_usd}}{\text{leverage}} + \text{position\_size\_usd} \times \text{taker\_fee\_pct} \le \text{available\_margin}$$
- Kiểm tra kiểu dữ liệu an toàn (`isinstance(tier, str)`, kiểm tra `callable` cho `is_trading_allowed`, bọc try/except `OverflowError`/`OSError` khi parse timestamp) để chống crash runtime do dữ liệu unhashable hoặc số quá lớn.

### F3. Phân lập Thời điểm Thẩm quyền Duyệt Lệnh (Admission Time vs Signal Time)
- `account_state['current_time']` là nguồn thời gian thẩm quyền duy nhất để duyệt lệnh tại cổng.
- Ràng buộc quan hệ nhân quả: $\text{order['timestamp']} \le \text{account\_state['current\_time']}$.
- Mọi điều kiện ngắt mạch (Circuit Breaker) và vùng cấm tin tức (News Blackout) được đánh giá nghiêm ngặt tại **thời điểm duyệt lệnh (Admission Time)**, ngăn chặn triệt để lỗ hổng dùng tín hiệu cũ ngoài giờ cấm để lách qua blackout hoặc lockout.
- Kiểm tra nhất quán cấu hình tin tức: Nếu `config.news_filter.enabled = True`, đối tượng `account_state['news_filter']` bắt buộc phải có `enabled = True`.

### F4. Mô hình Đồng hồ Đơn nhất (Unified Monotonic Clock via `advance_time`)
- Mọi phương thức truy vấn (`is_trading_allowed`) và ghi nhận sự kiện (`record_trade_result`) đều điều hướng qua hàm chuẩn hóa `advance_time(ts)`.
- Thời gian tiến đơn điệu $t \ge t_{last}$, ngăn chặn cả lùi thời gian khi ghi sự kiện lẫn khi query trạng thái.
- Giải quyết triệt để Scenario A (truy vấn thời gian mới khóa chặn sự kiện quá khứ) và Scenario B (tự động giải phóng khóa cũ và phát hiện vi phạm mới tại mốc thời gian sự kiện mà không cần gọi query thăm dò trước).
- Tài khoản cháy vốn (`equity <= 0`): kích hoạt cờ `is_halted = True` dừng giao dịch vĩnh viễn thay vì dùng số ngày tượng trưng.
- Danh mục `recovery_mode` kiểm soát chặt qua `SUPPORTED_RECOVERY_MODES = {"after_3_wins", "after_1_win"}`.

### F5. Giải thuật Giải Giá Thanh lý Nghiêm ngặt (Strict Liquidation Solver)
- Bảng `leverage_brackets` phải thỏa mãn tính liên tục của hàm ký quỹ duy trì tại các ranh giới tier:
  $$C_i \times \text{MMR}_i - \text{cum}_i = C_i \times \text{MMR}_{i+1} - \text{cum}_{i+1}$$
- Không cho phép ngoại suy ngoài bảng bracket: vị thế danh nghĩa vượt quá trần tối đa phải bị từ chối với `ValueError`.
- Phát hiện vị thế đã vi phạm thanh lý ngay tại giá vào lệnh: nếu $\text{initial\_margin} \le \text{maintenance\_margin}_{\text{entry}}$, từ chối với `ValueError("already liquidatable")`.
- Nghiệm giá thanh lý $P_{cand}$ phải thỏa mãn phương hướng: Long $P_{cand} < P_{entry}$, Short $P_{cand} > P_{entry}$.
- Loại bỏ hoàn toàn fallback sang tier cuối; nếu không tìm được nghiệm nhất quán theo tier trong miền bracket hợp lệ, solver ném `ValueError` minh bạch.
- Nghiệm được kiểm chứng toán học độc lập thỏa mãn phương trình cân bằng ký quỹ:
  $$\text{Initial Margin} \pm q \times (\Delta P) = q \times P_{liq} \times \text{MMR} - \text{cum}$$

