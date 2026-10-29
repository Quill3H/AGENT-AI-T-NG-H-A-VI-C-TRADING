# Vòng 4: thử hướng mới (2026-10-16)

Đây là **giao dịch giấy**, tài khoản 10.000$, rủi ro 10% mỗi lệnh, mọi giới hạn an toàn giữ nguyên. Bot không dùng chiến lược funding. Các con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Code ở [PR nháp #7](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/7), nhật ký ở `crypto-paper-agent/docs/research/2026-10-16-new-directions.md`.

## 1. Kết luận ngắn

- **Thất bại.** Cách được chọn lỗ trên BTC/ETH/SOL giai đoạn 2024–2026 (−6,1%). Trên 4 đồng mới, nó lãi +183%, nhưng gần như toàn bộ là nhờ AVAX, và vẫn lỗ 2 năm liền (2024, 2025).
- Không tháng nào trên BTC/ETH/SOL đạt +20%. Mục tiêu 20–50% mỗi tháng vẫn không được dữ liệu ủng hộ.

## 2. Bốn cách đã thử (chọn trên dữ liệu 2021–2023)

| Cách | Ý tưởng | Lãi/lỗ 2021–2023 | Sụt sâu nhất | Năm lỗ |
|---|---|---|---|---|
| N1 Xếp hạng động lượng | Mỗi tuần mua 1/3 đồng tăng mạnh nhất, bán khống 1/3 yếu nhất (7 đồng) | +38% | 9% | 2022 |
| **N2 Đổi chế độ (được chọn)** | Thị trường có xu hướng (ADX cao) thì đánh breakout, đi ngang thì đánh đảo chiều RSI(2) | **+643%** | **38%** | không |
| N3 Máy học chỉ dùng giá | Mô hình hồi quy logistic, học lại mỗi 30 ngày, chỉ dùng dữ liệu quá khứ | +2,5% | 41% | 2021, 2022 |
| N4 Máy học + open interest | N3 thêm open interest và tỷ lệ long/short | bỏ, theo lựa chọn của bạn | | |

Luật ghi trước: chọn cách có lãi/sụt tốt nhất trong số cách không có năm lỗ và có ít nhất 30 lệnh. Chỉ N2 qua được luật này. Máy học (N3) gần như không dự đoán được gì.

## 3. Kiểm tra cuối (chạy một lần sau khi đã khoá)

| Bài kiểm tra | Tiền cuối | Lãi/lỗ | Sụt sâu nhất | Tháng ≥20% | Tháng lỗ |
|---|---|---|---|---|---|
| A: LINK, AVAX, LTC, DOT, 2021-01 → 2026-09 (bot chưa từng thấy) | 28.336$ | +183% | 41,7% | 4/69 | 35/69 |
| A, phí ×2 | 27.020$ | +170% | 42,5% | 4/69 | 35/69 |
| B: BTC, ETH, SOL, 2024-01 → 2026-09 | 9.390$ | −6,1% | 39,7% | 0/33 | 21/33 |

Lãi/lỗ từng năm:
- A: 2021 +18%, 2022 +20%, 2023 +104%, 2024 −10%, 2025 −13%, 2026 (9 tháng) +25%.
- B: 2024 −2%, 2025 −3%, 2026 −1,5%.

Từng đồng trong bài A: AVAX +849%, LINK −33%, LTC −66%, DOT −16%. Riêng 2 tháng 11 và 12/2023 đã góp khoảng +115%.

Từng đồng trong bài B: BTC +38%, ETH −16%, SOL −40%.

Lãi/lỗ hằng tháng trên BTC/ETH/SOL (bài B, %):

| | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024 | +0,7 | +19,4 | −0,1 | −3,9 | −3,7 | +0,2 | −1,9 | −4,4 | −4,2 | −1,2 | +4,9 | −5,6 |
| 2025 | −0,6 | +3,6 | −0,8 | −2,2 | −0,2 | +1,0 | +2,5 | −3,2 | −0,2 | −0,3 | +2,5 | −4,5 |
| 2026 | +8,6 | +13,6 | −12,3 | −0,8 | −2,5 | +6,0 | +0,2 | −6,5 | −5,2 | | | |

## 4. Ý nghĩa

- Sau 4 vòng với hơn 20 cách khác nhau, cách nào cũng lãi tốt ở 2021–2023 rồi lỗ hoặc gần hoà từ 2024. Đó là dấu hiệu của việc may mắn trúng một giai đoạn thị trường, chứ chưa phải một lợi thế bền vững.
- Ở rủi ro 10%/lệnh, tài khoản thường xuyên sụt khoảng 40% so với đỉnh.
- Toàn bộ dữ liệu đến 2026-09 trên 11 đồng đã được dùng để kiểm tra. Muốn có bằng chứng mới thật sự thì cần chạy bot trên giấy với dữ liệu thời gian thực từ bây giờ (forward paper) trong vài tháng.

## 5. Ghi chú kỹ thuật

- Mới thêm: 8 chiến lược chỉ báo, mô hình máy học walk-forward viết bằng numpy (có test chứng minh không nhìn trước dữ liệu), và chạy được nhiều đồng cùng lúc.
- N4 chưa được chạy vì chưa lấy được file open interest từ máy bạn. Nó được ghi là "bỏ", chứ không phải "thất bại".
