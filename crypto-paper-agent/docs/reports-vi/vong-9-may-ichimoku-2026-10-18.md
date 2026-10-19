# Vòng 9: mây Ichimoku (2026-10-18)

Đây là **giao dịch giấy**: tài khoản 10.000$, đòn bẩy 2x, lệnh nào cũng có stop-loss. Phí 0,05% mỗi chiều cộng trượt giá 0,03%. Mọi con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Nhật ký chi tiết ở `crypto-paper-agent/docs/research/2026-10-19-ichimoku.md`, PR nháp #7.

## 1. Kết luận ngắn

- **Chưa đạt bậc 10% mỗi tháng.**
- Cách Ichimoku tốt nhất là **Tenkan cắt Kijun trên nến 4h, rủi ro 5% mỗi lệnh**. Trên dữ liệu chạy thử 2021–2023, cách này lãi khoảng +0,8% mỗi tháng và không có năm nào lỗ. Mức này vẫn thấp hơn cách swing EMA của vòng 8 (+4%).
- Trên 17 ngày tháng 10/2026 của 7 đồng chưa từng dùng, cách này **lỗ 2,3%** sau phí. Chỉ có 6 lệnh, quá ít để kết luận.

## 2. Luật đã dùng

Tôi dùng thông số chuẩn của Ichimoku (9/26/52) và chỉ đọc nến đã đóng, không nhìn trước:
- **Cách 1 (I1), Tenkan cắt Kijun:** Tenkan cắt lên Kijun, giá đóng cửa trên mây, và Chikou cao hơn giá 26 nến trước thì vào lệnh mua. Stop đặt dưới Kijun nửa ATR. Thoát khi giá đóng cửa quay lại dưới Kijun. Lệnh bán làm ngược lại.
- **Cách 2 (I2), phá mây:** giá đóng cửa vượt lên trên mây, đồng thời mây phía trước là mây tăng. Stop đặt dưới đáy mây.

Mỗi cách được thử trên 3 khung nến (4h, 1h, 15m). Ngoài ra có thêm bản chỉ mua trên nến 4h cho cả hai cách. Tổng cộng 8 phiên bản.

## 3. Chạy thử (BTC/ETH/SOL 2021–2023)

| Cách | Rủi ro | Lãi/lỗ 3 năm | TB mỗi tháng | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|---|
| **I1 Tenkan cắt Kijun, 4h (được chọn)** | **5%** | **+32,9%** | **+0,79%** | 22,8% | 274 | 32% |
| I1, 4h | 2% | +23,0% | +0,58% | 9,1% | 301 | 32% |
| I1, 1h | 5% | +50,0% | +1,13% | 29,9% (lỗ năm 2022) | 751 | 36% |
| I1, 4h, chỉ mua | 5% | +35,1% | +0,84% | 22,7% (lỗ năm 2022) | 151 | 38% |
| I2 phá mây, 4h | 5% | +4,9% | +0,13% | 18,4% | 251 | 33% |
| I2 phá mây, 1h | 5% | −29,4% | −0,96% | 46,6% | 872 | 31% |
| I1, 15m | 2% | −63,9% | −2,79% | 75,8% | 3.577 | 30% |
| I2, 15m | 2% | −77,0% | −4,0% | 78,0% | 4.196 | 27% |

- Luật chọn được ghi trước khi chạy: không có năm nào lỗ, sụt tối đa 35%, và lấy cách có trung bình tháng cao nhất. Bản 1h có trung bình tháng cao hơn nhưng lỗ năm 2022, nên bị loại.
- Mọi bản chạy trên nến 15m đều lỗ nặng vì phí, giống kết quả của các vòng trước.

## 4. Kiểm tra sau khi khoá (I1 4h, rủi ro 5%)

| Bài kiểm tra | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|
| **XRP/BNB/DOGE/TRX/ADA/LINK/AVAX, 01–17/10/2026 (chưa dùng)** | **9.769$** | **−2,3%** | 3,0% | 6 | 17% |
| Như trên, phí ×2 | 9.754$ | −2,5% | 3,1% | 6 | 17% |
| BTC/ETH/SOL, 01–17/10/2026 (đã dùng ở vòng 8) | 10.166$ | +1,7% | 2,7% | 1 | 100% |
| BTC/ETH/SOL 2024-01 → 2026-09 (đã dùng) | 13.404$ | +34,0% | 21,6% | 225 | 35% |
| 10 đồng top, 2021-01 → 2026-09 (đã dùng) | 25.358$ | +153,6% | 18,1% | 1.643 | 33% |

- Giai đoạn 2024–2026 có lãi, nhưng gần như toàn bộ lãi đến từ SOL (+124% trên phần vốn của SOL). Phần BTC lỗ 5%, phần ETH lỗ 16%.
- Trên 10 đồng top, năm 2021 lãi +80%, các năm sau chỉ từ −1% đến +19%. Có 31 trên 69 tháng bị lỗ, và 4 đồng bị lỗ (BTC, XRP, DOGE, TRX).
- Đây là cách sụt sâu ít nhất trong các cách đã chọn ở những vòng gần đây (18% trên 10 đồng). Tuy vậy, lãi vẫn tập trung ở vài đồng và năm 2021, đúng kiểu các vòng trước đã cảnh báo là dễ do may mắn.

## 5. Ghi chú trung thực

- Trước khi ghi luật, tôi chạy thử một lần để kiểm tra dữ liệu tải đúng, và đã thấy kết quả bản 1h trên XRP/DOGE tháng 10 (+6%, 12 lệnh). Tôi đã ghi rõ việc này trong nhật ký. Bản 1h không được chọn, nên kết quả đó không ảnh hưởng đến lựa chọn.
- Đến nay, toàn bộ dữ liệu của 10 đồng top đến hết 17/10/2026 đã được dùng cho kiểm tra cuối. Bằng chứng mới chỉ còn đến từ việc chạy giấy với dữ liệu từ giờ trở đi.

## 6. Bước tiếp theo

- Ngày 25/10, tôi sẽ chạy giấy tuần đầu cho cả swing EMA (vòng 8) và Ichimoku 4h (vòng 9) trên dữ liệu mới, rồi ghi kết quả vào sổ học hỏi.
