# Vòng 10: Wyckoff và Ichimoku trên BTC/ETH/SOL (2026-10-18)

Đây là **giao dịch giấy**: tài khoản 10.000$, đòn bẩy 2x, lệnh nào cũng có stop-loss. Phí là 0,05% mỗi chiều, cộng thêm 0,03% trượt giá. Mọi con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Nhật ký nằm ở `crypto-paper-agent/docs/research/2026-10-18-wyckoff-ichimoku.md`, trong PR nháp #7.

**Lưu ý trước:** toàn bộ dữ liệu BTC/ETH/SOL đến 17/10/2026 đã được dùng cho kiểm tra cuối ở các vòng trước. Vì vậy, kết quả kiểm tra sau khi khoá ở vòng này chỉ để tham khảo. Bằng chứng thật phải đến từ chạy giấy với dữ liệu từ 18/10 trở đi.

## 1. Kết luận ngắn

- **Chưa đạt bậc 10% mỗi tháng.**
- **Mọi cách Wyckoff đều lỗ** trên dữ liệu chạy thử 2021–2023, ở cả nến 4h và 1h.
- Hai cách cải tiến Ichimoku đều kém hơn cách cũ của vòng 9:
  - thêm lọc theo mây khung ngày;
  - kéo stop theo đường Kijun.
- Cách được chọn là **bộ gộp M1**: chia đều vốn cho swing EMA chỉ mua (vòng 8), Ichimoku Tenkan/Kijun 4h (vòng 9) và Wyckoff SOS/LPS 4h, rủi ro 5% mỗi lệnh.
  - Chạy thử 2021–2023: khoảng **+2,1% mỗi tháng**.
  - Tham khảo 2024–2026: khoảng **+0,6% mỗi tháng**, sụt sâu nhất 15%. Đây là mức sụt thấp nhất trong các cách được chọn gần đây.

## 2. Luật Wyckoff đã thử

Vùng tích luỹ được định nghĩa là 40 nến trước đó, có biên độ không quá 8 lần ATR và ADX dưới 25, tức là giá đi ngang yên lặng. Khi đã vào lệnh, cả hai cách đều giữ lệnh cho đến khi giá đóng cửa cắt EMA50 (hoặc tối đa 60 nến), để lệnh có thể ăn trọn một con sóng lớn.

- **WY1, Spring/Upthrust:** một nến có khối lượng lớn đâm thủng đáy vùng rồi đóng cửa quay lại trong vùng thì vào lệnh mua. Chiều ngược lại ở đỉnh vùng thì vào lệnh bán.
- **WY2, SOS rồi LPS:**
  - SOS là nến có khối lượng lớn đóng cửa vượt lên trên vùng.
  - Trong 10 nến sau đó, giá không được đóng cửa quay lại trong vùng.
  - LPS là lúc giá lùi về gần đỉnh vùng cũ nhưng vẫn đóng cửa trên đó. Khi đó vào lệnh mua.
  - Chiều bán làm ngược lại (SOW rồi LPSY).

## 3. Kết quả chạy thử (BTC/ETH/SOL 2021–2023)

| Cách | Rủi ro | Lãi/lỗ 3 năm | TB mỗi tháng | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|---|
| **M1 gộp 3 cách (được chọn)** | **5%** | **+108%** | **+2,06%** | 24,8% | 777 | 27% |
| M1 | 2% | +27,5% | +0,68% | 10,7% | 871 | 26% |
| Ichimoku Tenkan/Kijun 4h (vòng 9, tham khảo) | 5% | +32,9% | +0,79% | 22,8% | 274 | 32% |
| Ichimoku + lọc mây ngày | 5% | +28,0% (lỗ năm 2023) | +0,69% | 23,3% | 146 | 34% |
| Ichimoku + kéo stop theo Kijun | 5% | +24,0% | +0,60% | 18,4% | 274 | 33% |
| Wyckoff Spring vòng 5 (tham khảo) | 5% | +8,8% | +0,24% | 15,2% | 102 | 40% |
| WY1 Spring, 4h | 5% | −6,0% | −0,17% | 14,4% | 139 | 38% |
| WY1 Spring, 1h | 2% | −40,7% | −1,44% | 41,1% | 918 | 38% |
| WY2 SOS/LPS, 4h | 5% | −26,3% | −0,84% | 44,8% | 146 | 18% |
| WY2 SOS/LPS, 1h | 2% | −33,9% | −1,14% | 41,1% | 789 | 16% |

- WY2 chỉ thắng 15–22% số lệnh: phần lớn các lần giá vượt ra khỏi vùng đi ngang rồi lại rơi về.
- M1 thắng theo luật chọn chủ yếu nhờ phần swing EMA. Nếu chạy riêng, swing EMA cho +4,05% mỗi tháng (vòng 8). Phần Wyckoff trong M1 làm lãi chung thấp đi. Tôi giữ đúng luật đã ghi trước, không đổi lựa chọn sau khi đã thấy kết quả.

## 4. Kiểm tra M1 sau khi khoá (dữ liệu đã dùng, chỉ tham khảo)

| Bài kiểm tra | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|
| BTC/ETH/SOL 2024-01 → 2026-09 | 12.171$ | +21,7% | 15,3% | 694 | 27% |
| Như trên, phí ×2 | 10.726$ | +7,3% | 15,7% | 707 | 26% |
| BTC/ETH/SOL 01–17/10/2026 | 10.009$ | +0,1% | 1,1% | 5 | 20% |

- Lãi theo năm: 2024 +8,6%, 2025 +11,1%, 2026 (đến tháng 9) +0,9%.
- Có 16 trên 33 tháng bị lỗ. Tháng tốt nhất +13%, tháng tệ nhất −6,4%.
- Lãi của từng phần (mỗi phần giữ 1/3 vốn): swing EMA +17,8%, Ichimoku +34,0%, Wyckoff SOS/LPS +13,3%.
- Wyckoff lỗ ở giai đoạn 2021–2023 nhưng lại lãi ở 2024–2026. Kết quả đảo chiều như vậy cho thấy không nên tin vào một giai đoạn đơn lẻ.

## 5. Bài học ghi vào sổ

- Wyckoff viết thành luật cố định từ dữ liệu giá và khối lượng không có lãi ổn định trên BTC/ETH/SOL.
- Gộp nhiều cách giúp đường vốn mượt hơn (sụt ít hơn), nhưng không làm lãi mỗi tháng cao hơn.

## 6. Bước tiếp theo

- Ngày 25/10, tôi sẽ chạy giấy tuần đầu (dữ liệu từ 18/10) cho cả ba cách: swing EMA, Ichimoku 4h và M1. Kết quả sẽ được ghi vào sổ học hỏi.
