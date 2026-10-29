# Vòng 14: giao dịch cặp, copy luật Gatev–Goetzmann–Rouwenhorst (2026-10-19)

Đây là **giao dịch giấy** trên futures perpetual Binance:
- Tài khoản 10.000$, chia đều cho 10 đồng top, mỗi đồng 1.000$.
- Đòn bẩy 2x, có bán khống, có tính funding. Lệnh nào cũng có stop-loss.
- Phí 0,05% mỗi chiều, cộng 0,03% trượt giá.

Các con số do tôi tự chạy và **chưa có người kiểm tra độc lập**.

## 1. Copy từ đâu

- **Nguồn gốc:** Gatev, Goetzmann và Rouwenhorst, *Pairs Trading: Performance of a Relative-Value Arbitrage Rule* (Review of Financial Studies, 2006). Trên cổ phiếu Mỹ giai đoạn 1962–2002, cách này lãi vượt thị trường tới khoảng 11% mỗi năm ([tóm tắt](https://alphaarchitect.com/pairs-trading-kicks-butt/)).
- **Trên crypto:** một luận văn của Đại học Charles dùng dữ liệu Binance năm 2018. Cách này lãi khoảng 3% mỗi tháng trong điều kiện có phí, nhưng phần lớn các bộ thông số lỗ sau phí ([nguồn](https://dspace.cuni.cz/handle/20.500.11956/109634)).

## 2. Luật

**Bước 1: tìm cặp.**
- Lấy 12 tháng giá của 10 đồng và quy về cùng mốc 1.
- Chọn ra 5 cặp có giá đi sát nhau nhất trong 45 cặp có thể ghép.

**Bước 2: vào lệnh.** Trong 6 tháng tiếp theo, khi hai đồng trong một cặp lệch nhau quá 2 lần độ lệch chuẩn:
- bán khống đồng đang cao;
- mua đồng đang thấp.

**Bước 3: thoát lệnh.** Khi hai đường giá cắt nhau lại, hoặc khi hết 6 tháng.

**Phần tôi phải điều chỉnh cho futures:**
- Mỗi lệnh có stop cách giá 3 lần ATR ngày.
- Hai chân của cặp được cân theo rủi ro, không cân theo số tiền.

**Ba bản đã thử:**
- P1: đúng luật gốc, 12 tháng tìm cặp và 6 tháng giao dịch.
- P2: nhanh hơn, 3 tháng tìm cặp và 1 tháng giao dịch.
- P3: như P2 nhưng lấy 10 cặp.

## 3. Kết quả chạy thử (10 đồng, 2021–2023, rủi ro 5%)

| Cách | Lãi/lỗ 3 năm | TB mỗi tháng | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|
| C1 cũ (tham khảo) | +174% | +2,84% | 21,3% | 1.269 | 24,4% |
| **P1: luật gốc** | **+14,7%** | **+0,38%** | **3,8%** | 24 | 50% |
| P3: 3 tháng, 10 cặp | +1,5% | +0,04% | 5,2% | 172 | 51,7% |
| P2: 3 tháng, 5 cặp | −1,0% | −0,03% | 2,6% | 126 | 46% |

- Không bản nào có lãi ở cả 3 năm.
- Theo luật chọn đã ghi trước, P1 được chọn vì có lãi trung bình mỗi tháng cao nhất mà sụt vốn dưới 35%.
- Bản nhanh vào nhiều lệnh hơn, và phí ăn hết lãi.

## 4. Kiểm tra P1 sau khi khoá (dữ liệu đã dùng, chỉ tham khảo)

| Bài kiểm tra | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng | Tháng lỗ |
|---|---|---|---|---|---|---|
| 10 đồng 2024-01 → 2026-09 | **10.860$** | **+8,6%** | **3,7%** | 34 | 50% | 12/33 |
| Như trên, phí ×2 | 10.833$ | +8,3% | 3,7% | 34 | 50% | 12/33 |
| C1 cũ, cùng 10 đồng | 12.501$ | +25,0% | 19,6% | 1.162 | 22,1% | 23/33 |
| 10 đồng 01–17/10/2026 | 10.000$ | 0% | 0% | 0 | | |

- Lãi theo năm của P1: 2024 +3,9%, 2025 +0,7%, 2026 (đến tháng 9) +3,8%.

## 5. Đánh giá thật

- **Chưa đạt bậc 10% mỗi tháng.** P1 chỉ lãi khoảng +0,25% mỗi tháng.
- **Điểm mới đáng chú ý:**
  - Sau 14 vòng, đây là cách đầu tiên **có lãi ở mọi năm** của giai đoạn kiểm tra 2024–2026, trong khi sụt vốn **dưới 4%**.
  - Khi phí tăng gấp đôi, kết quả gần như không đổi.
  - Cách này không phụ thuộc thị trường lên hay xuống.
- **Điểm yếu:**
  - Chỉ có 34 lệnh, quá ít để chắc chắn.
  - Lãi nhỏ.
  - Năm 2022 lỗ nhẹ.
- **Hướng có thể tăng lãi:** sụt vốn rất thấp, nên có thể đặt lệnh lớn hơn. Nhưng việc tăng rủi ro cần bạn quyết định, và chỉ chạy như một bản thử "nếu như" có ghi nhãn.
- P1 đã được thêm vào lần chạy giấy hằng tuần, bắt đầu từ ngày 25/10.

## 6. Bài học ghi vào sổ

- Giao dịch cặp chậm (12 tháng) giữ được lợi thế. Giao dịch cặp nhanh (3 tháng) bị phí ăn hết.
- Cách trung lập với thị trường giúp làm mượt và đa dạng hoá danh mục. Nó không phải cỗ máy lãi 10% mỗi tháng.
