# Vòng 15: dùng funding để đo độ "đông đúc" của thị trường (2026-10-19)

Đây là **giao dịch giấy** trên futures perpetual Binance:
- Tài khoản 10.000$, chia đều cho 10 đồng top.
- Đòn bẩy 2x, có bán khống, có tính funding. Lệnh nào cũng có stop-loss.
- Phí 0,05% mỗi chiều, cộng 0,03% trượt giá.

Các con số do tôi tự chạy và **chưa có người kiểm tra độc lập**.

## 1. Copy từ đâu

- **Nguồn:** Schmeling, Schrimpf và Todorov, *Crypto carry*, bài nghiên cứu số 1087 của Ngân hàng Thanh toán Quốc tế (BIS) ([nguồn](https://bis.org/publ/work1087.htm)).
- **Phát hiện chính:**
  - Chênh lệch giữa giá futures và giá spot (carry, đi cùng với funding) trung bình trên 10% mỗi năm.
  - Chênh lệch này đến từ người chơi nhỏ đuổi theo xu hướng và dùng đòn bẩy cao.
  - **Khi carry cao bất thường, giá dễ sập sau đó.**

## 2. Ba cách đã thử

| Cách | Luật |
|---|---|
| F1 | C1 cũ, nhưng không mở lệnh mua khi funding 7 ngày của đồng đó cao hơn mức 90% trong 180 ngày qua (tức là phe mua đang quá đông) |
| F2 | Mỗi tuần: mua 3 đồng có funding thấp nhất, bán khống 3 đồng có funding cao nhất |
| F3 | Mỗi tuần: chỉ bán khống 3 đồng có funding cao nhất, và chỉ khi funding đang dương |

## 3. Kết quả chạy thử (10 đồng, 2021–2023, rủi ro 5%)

| Cách | Lãi/lỗ 3 năm | TB mỗi tháng | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng | Năm lỗ |
|---|---|---|---|---|---|---|
| C1 cũ (tham khảo) | +174% | +2,84% | 21,3% | 1.269 | 24,4% | 2022 |
| **F1: C1 + lọc funding** | **+128%** | **+2,31%** | 21,3% | 1.050 | 24,1% | 2022 |
| F2: xếp hạng funding | +24% | +0,60% | 7,1% | 344 | 46,2% | 2022 |
| F3: bán khống đồng quá đông | −7,2% | −0,21% | 8,1% | 194 | 46,4% | 2021, 2023 |

Theo luật chọn đã ghi trước, F1 được chọn vì có lãi trung bình mỗi tháng cao nhất mà sụt vốn dưới 35%.

## 4. Kiểm tra F1 sau khi khoá (dữ liệu đã dùng, chỉ tham khảo)

| Bài kiểm tra | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Tỷ lệ thắng |
|---|---|---|---|---|
| 10 đồng 2024-01 → 2026-09 | 11.488$ | +14,9% | 17,3% | 21,7% |
| Như trên, phí ×2 | 10.146$ | +1,5% | 23,7% | 19,3% |
| C1 cũ, cùng 10 đồng | 12.501$ | +25,0% | 19,6% | 22,1% |
| 10 đồng 01–17/10/2026 | 9.572$ | −4,3% | 4,4% | 12% |

## 5. Đánh giá thật

**Thất bại: F1 kém hơn C1 ở cả hai giai đoạn.**

- Khi thị trường tăng, funding cao kéo dài nhiều tuần mà giá vẫn tiếp tục lên. Vì vậy, bộ lọc chặn mất nhiều lệnh thắng.
- Phát hiện của BIS có thể đúng ở quy mô cả thị trường và trong nhiều tháng. Nhưng nó không giúp chọn thời điểm vào lệnh khung 4h hay chọn đồng hằng tuần.
- F1 không được thêm vào lần chạy giấy.

**P1 với rủi ro 10%** (bạn đã chọn thử): 2021–2023 lãi +32%, sụt sâu nhất 7,1%. Giai đoạn 2024–2026 lãi +16,8%, sụt sâu nhất 8,5%. Năm 2025 lỗ nhẹ 0,2%.
