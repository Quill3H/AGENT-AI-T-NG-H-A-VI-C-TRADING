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
