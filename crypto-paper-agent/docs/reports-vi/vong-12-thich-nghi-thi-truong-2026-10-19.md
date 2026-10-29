# Vòng 12: các cách tự thích nghi với thị trường (2026-10-19)

Đây là **giao dịch giấy**: tài khoản 10.000$, đòn bẩy 2x, lệnh nào cũng có stop-loss. Phí là 0,05% mỗi chiều, cộng 0,03% trượt giá. Mọi con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Nhật ký nằm ở `crypto-paper-agent/docs/research/2026-10-19-round12-adaptive.md`, trong PR nháp #7.

## 1. Kết luận ngắn

- **Chưa đạt bậc 10% mỗi tháng.**
- Cách được chọn là **A2**: swing EMA cũ (C1), nhưng cách thoát lệnh thay đổi theo độ mạnh của xu hướng.
  - Khi xu hướng yếu (ADX từ 25 trở xuống), thoát sớm khi giá đóng cửa dưới EMA20.
  - Khi xu hướng mạnh (ADX trên 25), giữ lệnh đến khi giá đóng cửa dưới EMA50, như C1.
- Đây là **cải tiến đầu tiên tốt hơn C1 ở cả hai giai đoạn**:
  - 2021–2023: **+5,0% mỗi tháng** (C1 +4,05%), sụt sâu nhất 25,7% (C1 31,4%).
  - 2024–2026: **+18,6%** (C1 +17,8%), sụt sâu nhất 22,0% (C1 24,3%), 13 tháng lỗ (C1 17).
- Lợi thế ở 2024–2026 còn mỏng: khi tính phí gấp đôi, lãi chỉ còn +1,5%.

## 2. Sáu cách đã thử

1. **A1:** đường trung bình thích nghi Kaufman (KAMA 10, 2, 30), tự chậm lại khi thị trường nhiễu và nhanh lên khi giá chạy thẳng.
2. **A2:** C1, thoát lệnh theo độ mạnh xu hướng như mô tả ở trên.
3. **A3:** C1, dời stop theo biến động (Chandelier): đỉnh 22 nến trừ 3 lần ATR.
4. **A4:** C1, chỉ vào lệnh khi lực mua chủ động (taker buy) lớn hơn lực bán trong 20 nến gần nhất.
5. **A5:** tự đổi cách theo trạng thái thị trường. Khi thị trường có xu hướng (ADX ngày từ 20 trở lên) thì dùng C1. Khi thị trường đi ngang thì mua lúc giá bật lại từ dải Bollinger dưới.
6. **A6:** C1, chỉ vào lệnh khi biến động đang tăng.

## 3. Kết quả chạy thử (BTC/ETH/SOL 2021–2023, rủi ro 5%)

| Cách | Lãi/lỗ 3 năm | TB mỗi tháng | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng | Tháng lỗ / 36 |
|---|---|---|---|---|---|---|
| **A2: thoát theo độ mạnh xu hướng** | **+488%** | **+5,04%** | 25,7% | 461 | 28,4% | 15 |
| C1: swing EMA cũ | +318% | +4,05% | 31,4% | 357 | 26,6% | 18 |
| A5: đổi cách xu hướng/đi ngang | +167% (lỗ năm 2022) | +2,77% | 28,4% | 375 | 30,1% | 19 |
| A4: lọc lực mua chủ động | +131% | +2,36% | 12,8% | 79 | 29,1% | 16 |
| A3: stop Chandelier | +127% | +2,30% | 24,2% | 495 | 29,1% | 14 |
| A6: lọc biến động tăng | +74% | +1,56% | 16,2% | 164 | 28,7% | 15 |
| A1: KAMA | −0,5% | −0,01% | 12,5% | 180 | 26,7% | 19 |

- Luật chọn được ghi trước khi chạy: không năm nào lỗ, sụt tối đa 35%, và lấy cách có lãi trung bình mỗi tháng cao nhất. Theo luật này, cách được chọn là A2 ở rủi ro 5%.

## 4. Kiểm tra A2 sau khi khoá (dữ liệu đã dùng, chỉ tham khảo)

| Bài kiểm tra | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng | Tháng lỗ |
|---|---|---|---|---|---|---|
| BTC/ETH/SOL 2024-01 → 2026-09 | 11.860$ | +18,6% | 22,0% | 468 | 23,9% | 13/33 |
| Như trên, phí ×2 | 10.154$ | +1,5% | 28,1% | 469 | 22,6% | 16/33 |
| C1 cũ, cùng giai đoạn | 11.778$ | +17,8% | 24,3% | 375 | 22,9% | 17/33 |
| BTC/ETH/SOL 01–17/10/2026 | 9.864$ | −1,4% | 2,0% | 3 | 0% | |
| 10 đồng top 2021-01 → 2026-09 | 32.241$ | +222% | 24,0% | 3.117 | 24,0% | 41/69 |

- Lãi theo năm trên BTC/ETH/SOL: 2024 +16,5%, 2025 +5,6%, 2026 (đến tháng 9) −3,6%.

## 5. Bài học ghi vào sổ

- Cắt lỗ nhanh hơn khi xu hướng yếu, nhưng vẫn để lệnh chạy khi xu hướng mạnh, là cách thích nghi hiệu quả hơn so với thêm bộ lọc lúc vào lệnh.
- Các bộ lọc lúc vào lệnh (lực mua chủ động, biến động) và stop kéo sát làm sụt vốn ít hơn, nhưng cắt mất vài con sóng lớn, nên lãi mỗi tháng giảm.

## 6. Bước tiếp theo

- Ngày 25/10, tôi sẽ chạy giấy tuần đầu (dữ liệu từ 18/10) cho C1, A2, S1 và bản C1 rủi ro 10% để tham khảo, đặt cạnh nhau. Kết quả sẽ được ghi vào sổ học hỏi.
