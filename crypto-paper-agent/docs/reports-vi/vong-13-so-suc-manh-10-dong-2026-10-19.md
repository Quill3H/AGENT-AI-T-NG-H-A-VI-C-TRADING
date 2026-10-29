# Vòng 13: so sức mạnh giữa 10 đồng top (2026-10-19)

Đây là **giao dịch giấy**: tài khoản 10.000$ chia đều cho 10 đồng, mỗi đồng 1.000$. Đòn bẩy 2x, lệnh nào cũng có stop-loss. Phí 0,05% mỗi chiều, cộng trượt giá 0,03% và funding. Các con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Nhật ký nằm ở `crypto-paper-agent/docs/research/2026-10-19-round13-cross-section.md`, trong PR nháp #7.

## 1. Kết luận ngắn

- **Không đạt bậc 10% mỗi tháng. Cách mới gần như hoà vốn.**
- Cách được chọn là **X3**. Mỗi tuần, X3 xếp hạng 10 đồng theo mức tăng giá 3 tuần qua:
  - mua tối đa 3 đồng mạnh nhất, nếu đồng đó đang tăng;
  - bán tối đa 3 đồng yếu nhất, nếu đồng đó đang giảm.
- **Ưu điểm:** thắng khoảng 40% số lệnh, và vốn sụt sâu nhất chỉ khoảng 10–13%.
- **Nhược điểm:** gần như không có lãi.
  - Giai đoạn 2024–2026: chỉ **+0,3%**.
  - Phí ×2: −1,7%.
  - Tháng 10/2026: −1,9%.
  - C1 cũ trên cùng 10 đồng, cùng giai đoạn 2024–2026: +25%.
- Hiệu ứng mà nghiên cứu học thuật tìm thấy (chênh lệch khoảng 4% mỗi tuần) **không còn** khi chỉ có 10 đồng lớn và phải tính đủ phí.

## 2. Kết quả chạy thử (10 đồng top 2021–2023, rủi ro 5%)

| Cách | Lãi/lỗ 3 năm | TB mỗi tháng | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng | Năm lỗ |
|---|---|---|---|---|---|---|
| C1 cũ (tham khảo) | +174% | +2,84% | 21,3% | 1.269 | 24,4% | 2022 −6,1% |
| **X3: mạnh và đang tăng / yếu và đang giảm** | **+29,5%** | **+0,72%** | 13,2% | 258 | 41,9% | không |
| X2: chỉ mua 3 đồng mạnh | +28,7% | +0,70% | 12,8% | 184 | 41,3% | 2022 −6,1% |
| X1: mua 3 mạnh, bán 3 yếu | +24,0% | +0,60% | 8,3% | 357 | 40,1% | không |
| X4: như X1 nhưng xét 1 tuần | +14,6% | +0,38% | 9,0% | 457 | 46,2% | không |

- Luật chọn được ghi trước khi chạy: không năm nào lỗ, sụt tối đa 35%, và lấy cách có lãi trung bình mỗi tháng cao nhất. Theo luật này, X3 được chọn.
- Ở rủi ro 2%, mọi bản chỉ lãi khoảng +0,2–0,3% mỗi tháng.

## 3. Kiểm tra X3 sau khi khoá (dữ liệu đã dùng, chỉ tham khảo)

| Bài kiểm tra | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng | Tháng lỗ |
|---|---|---|---|---|---|---|
| 10 đồng 2024-01 → 2026-09 | 10.031$ | +0,3% | 9,7% | 296 | 39,5% | 16/33 |
| Như trên, phí ×2 | 9.834$ | −1,7% | 10,2% | 296 | 39,2% | 16/33 |
| C1 cũ, cùng 10 đồng và cùng giai đoạn | 12.501$ | +25,0% | 19,6% | 1.162 | 22,1% | 23/33 |
| 10 đồng 01–17/10/2026 | 9.813$ | −1,9% | 2,4% | 8 | 12,5% | |

- Lãi theo năm của X3: 2024 +2,0%, 2025 +1,4%, 2026 (đến tháng 9) −3,0%.

## 4. Bài học ghi vào sổ

- So sức mạnh giữa các đồng làm vốn ổn định hơn: thắng nhiều lệnh hơn, sụt vốn ít hơn. Nhưng sau phí, lãi chỉ bằng khoảng 1/4 so với C1.
- Nghiên cứu học thuật dùng hàng trăm đồng và không tính phí. Với 10 đồng lớn có tính phí thì lợi thế gần như biến mất. Đừng tin một con số học thuật khi chưa thử trong điều kiện thật của mình.

## 5. Bước tiếp theo

- C1 và A2 vẫn là ứng viên chính.
- X3 được thêm vào lần chạy giấy hằng tuần (dữ liệu từ 18/10) làm đường so sánh ít rủi ro. Lần kiểm tra đầu tiên là ngày 25/10.
