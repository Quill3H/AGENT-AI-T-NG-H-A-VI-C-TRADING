# Vòng 11: học IncomeSharks, Nebraskangooner, Big Cheds để tăng tỷ lệ thắng (2026-10-18)

Đây là **giao dịch giấy**: tài khoản 10.000$, đòn bẩy 2x, lệnh nào cũng có stop-loss. Phí là 0,05% mỗi chiều, cộng 0,03% trượt giá. Mọi con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Nhật ký nằm ở `crypto-paper-agent/docs/research/2026-10-18-round11-traders.md`, trong PR nháp #7.

## 1. Kết luận ngắn

- **Chưa đạt bậc 10% mỗi tháng.**
- Trên dữ liệu chạy thử 2021–2023, cách tốt nhất là **S1**: swing EMA cũ (C1) cộng bộ lọc của IncomeSharks (hai Supertrend khung ngày cùng đi lên và OBV đi lên).
  - Ở rủi ro 5%, S1 lãi **+4,38% mỗi tháng**, sụt sâu nhất 26%. C1 cũ lãi +4,05% mỗi tháng, sụt 31%.
  - Số tháng lỗ giảm từ 18 xuống 10 trên 36 tháng.
- **Nhưng trên dữ liệu 2024–2026, S1 lỗ 3,3%**, trong khi C1 cũ lãi 17,8%. Bộ lọc giúp ở giai đoạn trước nhưng lại cắt mất các lệnh thắng của giai đoạn sau.
- Bán bớt sớm (chốt một nửa ở mức lãi bằng rủi ro, tức 1R) làm tỷ lệ thắng tăng từ khoảng 27% lên 38%, nhưng lãi mỗi tháng giảm từ 1/4 đến 1/2.
- **C1 cũ vẫn là cách chính.** S1 sẽ chạy giấy song song với C1 từ tuần này để so sánh trên dữ liệu mới.

## 2. Luật công khai của ba trader

Tôi chỉ dùng phần luật viết được thành quy tắc cố định. Tôi không dùng số lãi họ tự công bố.

- **IncomeSharks:** dùng hai Supertrend trên khung ngày, cài đặt (10, 3) và (10, 2), và cần OBV xác nhận xu hướng. Khi OBV không đi theo giá thì giảm vị thế.
- **Nebraskangooner:** giao dịch phá vỡ vùng kháng cự ngang có khối lượng xác nhận. Lãi tiềm năng phải ít nhất gấp 2 lần rủi ro. Dùng đòn bẩy thấp và nghỉ sau 4–5 lệnh thua liên tiếp.
- **Big Cheds:** xác định xu hướng trên khung ngày. Trong xu hướng tăng rõ, mua khi giá lùi về EMA8. Chốt lời từng phần khi giá đi lên. Không bỏ quá 5% vốn vào một lệnh.
- **Không kiểm tra được:** vẽ mô hình bằng mắt (tam giác, cờ, đường xu hướng), quản lý lệnh theo cảm nhận, xoay vòng altcoin theo BTC dominance, tin tức.
- Luật nghỉ sau chuỗi thua đã có sẵn trong hệ thống: giảm nửa rủi ro sau 3 lệnh thua. Tôi giữ nguyên luật này.

## 3. Kết quả chạy thử (BTC/ETH/SOL 2021–2023, rủi ro 5%)

| Cách | Lãi/lỗ 3 năm | TB mỗi tháng | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng | Tháng lỗ / 36 |
|---|---|---|---|---|---|---|
| **S1: C1 + lọc IncomeSharks** | **+368%** | **+4,38%** | 26,0% | 209 | 26,8% | 10 |
| C1: swing EMA cũ (vòng 8) | +318% | +4,05% | 31,4% | 357 | 26,6% | 18 |
| P1: C1, chốt nửa ở 1R | +184% | +2,94% | 22,1% | 367 | 37,9% | 16 |
| X1: S1, chốt nửa ở 1R | +157% | +2,66% | 20,7% | 224 | 39,3% | 11 |
| K1: Cheds, mua khi giá về EMA8 | +147% (lỗ năm 2022) | +2,54% | 22,5% | 376 | 30,6% | 18 |
| P2: C1, chốt 1/3 ở 1R và 1/3 ở 2R | +119% | +2,20% | 20,2% | 367 | 37,9% | 16 |
| G1: Gooner phá đỉnh 30 nến, chốt 2R | +68% (lỗ năm 2022) | +1,45% | 10,4% | 139 | 42,4% | 12 |
| K2: K1, chốt từng phần | +45% (lỗ năm 2022) | +1,05% | 14,8% | 385 | 37,1% | 18 |
| S2: hai Supertrend + OBV | +35% | +0,84% | 18,8% | 128 | 40,6% | 19 |

- Luật chọn được ghi trước khi chạy: không năm nào lỗ, sụt tối đa 35%, lãi mỗi tháng không thấp hơn C1, và lấy cách có tỷ lệ thắng cao nhất.
- Theo luật này, cách được chọn là **S1 ở rủi ro 2%** (tỷ lệ thắng 27,4%, +1,6% mỗi tháng). S1 ở 5% có cùng luật giao dịch, nên tôi kiểm tra cả hai mức.

## 4. Kiểm tra S1 sau khi khoá (dữ liệu đã dùng, chỉ tham khảo)

| Bài kiểm tra | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|
| BTC/ETH/SOL 2024-01 → 2026-09, rủi ro 2% | 9.623$ | −3,8% | 10,8% | 212 | 23,6% |
| Như trên, rủi ro 5% | 9.668$ | −3,3% | 26,4% | 200 | 24,5% |
| Như trên, rủi ro 5%, phí ×2 | 9.003$ | −10,0% | 30,2% | 200 | 22,0% |
| C1 cũ, cùng giai đoạn, rủi ro 5% | 11.778$ | +17,8% | 24,3% | 375 | 22,9% |
| 10 đồng top 2021-01 → 2026-09, rủi ro 5% | 30.018$ | +200% | 16,1% | 1.290 | 24,6% |
| BTC/ETH/SOL 01–17/10/2026, rủi ro 5% | 9.871$ | −1,3% | 1,7% | 3 | 0% |

- Lãi trên 10 đồng top chủ yếu đến từ năm 2021 (+103%) và 2023 (+49%). Từ 2024 trở đi, mỗi năm chỉ khoảng −2% đến +4%.

## 5. Bài học ghi vào sổ

- Với cách đi theo xu hướng, tỷ lệ thắng cao và lãi cao kéo về hai phía ngược nhau. Lãi của C1 đến từ vài con sóng lớn, nên chốt sớm sẽ mất phần lãi đó.
- Một bộ lọc giúp ở một giai đoạn có thể cắt mất các lệnh thắng của giai đoạn sau. Cần dữ liệu mới để biết bộ lọc có thật sự tốt hay không.
- Cách phá vỡ của Gooner và Supertrend của IncomeSharks thắng trên 40% số lệnh, nhưng lãi nhỏ. Không cách nào vượt C1 về lãi mỗi tháng.

## 6. Bước tiếp theo

- Ngày 25/10, tôi sẽ chạy giấy tuần đầu (dữ liệu từ 18/10) cho C1, S1, Ichimoku 4h và M1, đặt C1 và S1 cạnh nhau để so sánh. Kết quả sẽ được ghi vào sổ học hỏi.
- Muốn tăng lãi mỗi tháng thì cần tăng rủi ro, và sụt sâu sẽ tăng theo. Ở rủi ro 10% (mức bạn đã chọn), C1 lãi +7,5% mỗi tháng trên dữ liệu chạy thử, nhưng sụt tới 51%, vượt giới hạn 35%. Việc này cần bạn quyết định riêng.
