# Vòng 8: leo bậc 10% mỗi tháng, tìm lý do thua, học 5 trader nổi tiếng (2026-10-18)

Đây là **giao dịch giấy**: tài khoản 10.000$, đòn bẩy 2x, margin cô lập, lệnh nào cũng có stop-loss. Phí tính 0,05% mỗi chiều, cộng trượt giá 0,03%. Mọi con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Code ở [PR nháp #7](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/7), nhật ký ở `crypto-paper-agent/docs/research/2026-10-18-round8-plan.md`.

## 1. Kết luận ngắn

- **Chưa đạt bậc 1 (10% mỗi tháng).**
- Cách tốt nhất vòng này là **swing EMA 4h chỉ vào lệnh mua, rủi ro 5% mỗi lệnh**:
  - trên dữ liệu chạy thử 2021–2023: khoảng **+4% mỗi tháng**;
  - trên 2024–2026: chỉ còn **+0,5% mỗi tháng**;
  - trên 17 ngày tháng 10/2026 chưa ai dùng: **−1,4%**, mới có 4 lệnh, quá ít để kết luận.
- Hướng đi tiếp: cách này đã được đưa vào chạy giấy hằng tuần, tính từ 01/10/2026. Bài học lớn nhất của vòng này là gì quyết định lãi lỗ (mục 3).

## 2. Tìm lý do thua (phân tích từng lệnh, 2021–2023)

| Cách | Phát hiện | Đã sửa thế nào |
|---|---|---|
| Swing EMA 4h (W1) | Lệnh bán gần như hoà vốn sau phí (trung bình +0,02R), lãi nằm ở lệnh mua (+0,44R) | Bỏ lệnh bán (cách C1) |
| Swing EMA 4h (W1) | Lệnh ngược xu hướng 200 ngày lại tốt hơn lệnh thuận xu hướng | Không thêm bộ lọc xu hướng 200 ngày, vì bộ lọc này sẽ cắt mất các lệnh tốt nhất |
| Nến tiếp diễn 4h (K3) | Chỉ có 21 lệnh trong 3 năm | Quá ít để học |
| Phá biên độ Williams (T2) | Phí ăn mất **60% lãi gộp** (12.213$ trên 20.342$) | Rủi ro cao hơn làm T2 lỗ nặng hơn |

## 3. Học từ 5 trader nổi tiếng

Tôi chỉ lấy những gì đo được bằng giá, và không dùng số lãi họ tự công bố.

| Trader | Phần tôi thử được | Kết quả 2021–2023 |
|---|---|---|
| **GCR** | Bán ngược đỉnh khi giá tăng quá nóng (cách giá trung bình hơn 3 lần biên độ, RSI trên 80) | **Lỗ** ở mọi mức rủi ro: −10% đến −25%, chỉ 22–68 lệnh trong 3 năm |
| **Machi, James Wynn** | Mua sau một đợt xả mạnh | **Lỗ** nhẹ: −2% đến −12%, 10–21 lệnh |
| **Machi, James Wynn** | Đòn bẩy cao có kiểm soát thanh lý (x20 BTC/ETH, mức bạn đã cho chạy thử) | **Không giúp**: ít lệnh hơn, sụt sâu hơn (58% ở rủi ro 10%) |
| **Andrew Kang, Arthur Hayes** | Không thử được | Họ dựa vào tin vĩ mô, thanh khoản toàn cầu và dữ liệu on-chain, mà dự án chưa có các dữ liệu này |

## 4. Kết quả chạy thử (BTC/ETH/SOL 2021–2023, một tài khoản chung)

| Cách | Rủi ro | Lãi/lỗ 3 năm | TB mỗi tháng | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|---|
| **C1 Swing EMA chỉ mua (được chọn)** | **5%** | **+318%** | **+4,05%** | **31%** | 357 | 27% |
| C1 | 10% | +1.244% | +7,5% | 51% | 309 | 29% |
| W1 cả mua lẫn bán | 5% | +301% | +3,9% | 26% | 687 | 27% |
| C4 gộp C1 + K3 + T2 | 2% | +34% | +0,8% | 7% | 2.147 | 39% |
| C4 gộp C1 + K3 + T2 | 10% | +398% | +4,6% | 43% | 890 | 35% |
| C2 bán ngược đỉnh (GCR) | 5% | −25% | −0,8% | 25% | 47 | 32% |
| C3 mua sau xả | 5% | −10% | −0,3% | 17% | 17 | 35% |

Luật chọn được ghi trước khi chạy: không có năm lỗ, sụt tối đa 35%, rồi lấy cách có trung bình tháng cao nhất. Ở rủi ro 10%, C1 gần chạm 7,5% mỗi tháng, nhưng có lúc tài khoản sụt mất một nửa, nên luật loại ra.

**Điều quan trọng nhất:** ở mọi cách, tháng ở giữa (trung vị) đều quanh 0%. Lãi đến từ vài tháng thị trường chạy mạnh (tháng tốt nhất của C1 ở rủi ro 5%: +44%), còn phần lớn các tháng đi ngang hoặc lỗ nhẹ. Vì vậy, muốn có 10% đều đặn mỗi tháng thì phải có thêm nhiều cách kiếm tiền độc lập với nhau. Chỉ tăng rủi ro cho một cách thì không đủ.

## 5. Kiểm tra sau khi khoá (C1, rủi ro 5%)

| Bài kiểm tra | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng | TB mỗi tháng |
|---|---|---|---|---|---|---|
| BTC/ETH/SOL 2024-01 → 2026-09 (đã dùng ở vòng trước, chỉ tham khảo) | 11.778$ | +17,8% | 24,3% | 375 | 22,9% | +0,5% |
| **BTC/ETH/SOL 01–17/10/2026 (chưa từng dùng)** | **9.860$** | **−1,4%** | 2,1% | 4 | 0% | |
| Tháng 10, phí ×2 | 9.831$ | −1,7% | 2,3% | 4 | 0% | |
| Tham khảo tháng 10: W1 rủi ro 2% | 9.851$ | −1,5% | 4,6% | 15 | 20% | |
| Tham khảo tháng 10: K3 rủi ro 2% | 10.000$ | 0% | 0% | 0 | | |
| Tham khảo tháng 10: T2 rủi ro 2% | 9.644$ | −3,6% | 5,5% | 18 | 22% | |

- Năm 2024–2026 theo từng năm: 2024 +18,4%, 2025 +5,5%, 2026 (đến tháng 9) −5,7%.
- Có 17 trên 33 tháng bị lỗ. Tháng tốt nhất +18,4% (2/2024), tháng tệ nhất −6,9% (6/2025).
- Phần BTC lãi +34,8% và phần ETH lãi +35,6%. Phần SOL lỗ −17%.

## 6. Đã làm cho bot tự học

- Mọi lần chạy và 3 bài học của vòng này đã được ghi vào sổ học hỏi (`docs/research/ledger/LEARNING_LOG.md`).
- Dữ liệu tháng 10 đã được tải qua máy của bạn, có kiểm tra checksum, và không thiếu nến nào.
- Tiền funding của tháng hiện tại được lấy từ API công khai của Binance, không cần khoá.
- Đã có quy trình chạy giấy hằng tuần (mục "Forward paper" trong nhật ký). Cách đã khoá không được chỉnh theo kết quả chạy giấy.

## 7. Bước tiếp theo đề xuất

1. Chạy giấy mỗi tuần cho C1 (rủi ro 5%), W1, K3 và T2, rồi báo kết quả.
2. Tìm thêm cách kiếm tiền **độc lập** với swing EMA: phần BTC và ETH đang tốt hơn SOL. Hướng đáng thử nhất là funding carry, cách duy nhất từng có lãi đều ở vòng 1. Nó lãi khi funding cao và không phụ thuộc vào việc giá chạy mạnh.
3. Nếu bạn muốn thử theo kiểu Andrew Kang hoặc Arthur Hayes, cần thêm dữ liệu vĩ mô hoặc on-chain, ví dụ nguồn cung stablecoin hay lịch sự kiện kinh tế. Hãy cho tôi biết nguồn dữ liệu bạn có.
