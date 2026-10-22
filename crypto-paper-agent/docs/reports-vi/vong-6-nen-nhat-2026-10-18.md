# Vòng 6: nến Nhật, các cách chốt lời và đòn bẩy x20/x5 (2026-10-18)

Đây là **giao dịch giấy**: tài khoản 10.000$, margin cô lập, luôn có stop-loss. Phí tính 0,05% mỗi chiều, cộng trượt giá 0,03%. Mọi con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Code nằm ở [PR nháp #7](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/7), nhật ký ở `crypto-paper-agent/docs/research/2026-10-18-candlesticks.md`.

## 1. Kết luận ngắn

- **Mục tiêu 20–50% mỗi tháng vẫn không đạt.** Không tháng nào lãi tới 20%, kể cả khi dùng x20/x5 và rủi ro 10%. Tháng tốt nhất là +12%.
- Cách được chọn: **mẫu nến tiếp diễn trên nến 4 giờ** (ba chàng lính / ba con quạ, mẫu "ba phương pháp"), chỉ vào lệnh theo xu hướng EMA50/EMA200, **chốt lời ở mức 1:2**.
- Trên 4 đồng bot chưa từng thấy (XLM, BCH, UNI, AAVE), cách này lãi ở mọi mức rủi ro và vẫn lãi khi phí tăng gấp đôi. Trên BTC/ETH/SOL 2024–2026 thì gần như hoà.
- Lệnh rất ít, chỉ khoảng 1 lệnh mỗi tháng, nên kết quả chưa chắc chắn.

## 2. Các cách vào lệnh và chốt lời đã thử (2021–2023, BTC/ETH/SOL, rủi ro 2%)

4 cách vào lệnh theo sách Nison, mỗi cách thử 7 cách chốt lời, tổng 28 tổ hợp:
- K1: nến đảo chiều khi giá hồi theo xu hướng, nến 4h.
- K2: nến đảo chiều ở đáy hoặc đỉnh 20 ngày, nến ngày.
- K3: nến tiếp diễn theo xu hướng, nến 4h.
- K4: giống K1 nhưng trên nến 1h.

Kết quả tốt nhất của từng cách vào lệnh:

| Cách vào lệnh | Cách chốt lời tốt nhất | Lãi/lỗ | Sụt sâu nhất | Tỷ lệ thắng | Số lệnh |
|---|---|---|---|---|---|
| K1 nến đảo chiều khi hồi, 4h | Thoát khi đóng dưới EMA50 | +71% | 24% | 29% | 883 (lỗ 2022) |
| K2 nến đảo chiều ở đáy/đỉnh 20 ngày | Chốt lời 1% | −4% | 7% | **86%** | 228 |
| **K3 nến tiếp diễn, 4h** | **Chốt lời 1:2 (được chọn)** | **+7%** | **2,3%** | 62% | 21 |
| K4 nến đảo chiều khi hồi, 1h | Thoát theo chỉ báo | −68% | 74% | 35% | 3.174 |

So sánh các cách chốt lời bạn gửi, ví dụ với K1:
- 1:1: −13%, thắng 53%.
- 1:2: +1%.
- Hỗ trợ/kháng cự gần nhất: −1%.
- Chốt 1%: −35%, thắng 73%.
- Trailing stop: −7%.
- Chỉ báo RSI/Bollinger/MACD: −14%.
- Giữ đến khi gãy EMA50: +71%.

**Chốt lời nhanh làm tỷ lệ thắng tăng nhưng tiền lại mất**, vì mỗi lần thắng nhỏ còn mỗi lần thua lớn, cộng thêm phí. Nến 1h (K4) lỗ nặng với mọi cách chốt lời.

Không tổ hợp nào đạt đủ luật chọn (không có năm lỗ và ít nhất 30 lệnh). Vì vậy tôi chọn tổ hợp có tỷ lệ lãi trên mức sụt tốt nhất là K3 + 1:2, và ghi chú rằng nó chưa đạt luật. Fibonacci không được thử riêng; cách chốt ở hỗ trợ/kháng cự đại diện cho ý "chốt ở vùng giá gần nhất".

## 3. Kiểm tra cuối (chạy một lần sau khi đã khoá)

| Bài kiểm tra | Đòn bẩy | Rủi ro/lệnh | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|---|---|
| A: XLM/BCH/UNI/AAVE, 2021-01 → 2026-09 | 2x | 1% | 10.365$ | +3,6% | 0,9% | 46 | 54% |
| A | 2x | 2% | 10.750$ | +7,5% | 1,8% | 46 | 54% |
| A | 2x | 10% | 12.943$ | +29,4% | 9,0% | 37 | 54% |
| A, phí ×2 | 2x | 2% | 10.691$ | +6,9% | 1,8% | 46 | 54% |
| **A** | **x5 (altcoin)** | **10%** | **14.580$** | **+45,8%** | **8,3%** | 46 | 54% |
| B: BTC/ETH/SOL, 2024-01 → 2026-09 | 2x | 1% | 10.030$ | +0,3% | 3,1% | 20 | 40% |
| B | 2x | 2% | 10.052$ | +0,5% | 6,0% | 20 | 40% |
| B | 2x | 10% | 9.634$ | −3,7% | 19,9% | 16 | 38% |
| B | x20 BTC/ETH, x5 SOL | 2% | 10.024$ | +0,2% | 4,2% | 7 | 43% |
| B | x20 BTC/ETH, x5 SOL | 10% | 10.105$ | +1,1% | 18,6% | 7 | 43% |

Số lãi trên là tổng của gần 6 năm (A) hoặc gần 3 năm (B), không phải mỗi tháng. Ví dụ +45,8% của A trải trên 69 tháng, trung bình khoảng 0,5% mỗi tháng.

Lãi/lỗ từng năm ở rủi ro 2%:
- **A:** 2021 +1,3%, 2022 +2,0%, 2023 −0,7%, 2024 −0,0%, 2025 +2,5%, 2026 +2,3%.
- **B:** 2024 +1,1%, 2025 +1,3%, 2026 −1,9%.

Lãi/lỗ hằng tháng ở bài B, rủi ro 2% (chỉ liệt kê các tháng có lệnh; các tháng còn lại không có lệnh, 0%):

| Tháng | 2024-01 | 2024-02 | 2024-11 | 2024-12 | 2025-06 | 2025-10 | 2025-11 | 2025-12 | 2026-01 | 2026-02 | 2026-05 | 2026-08 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| % | −0,7 | +1,3 | +1,0 | −0,4 | −0,7 | +0,8 | +2,6 | −1,4 | −1,2 | −1,6 | +0,3 | +0,6 |

Ở bản x5/rủi ro 10% của bài A, tháng tốt nhất là 2025-02 (+12,1%), tháng tệ nhất là 2023-01 (−6,3%).

## 4. Về đòn bẩy x20 / x5

- Bạn chọn "Chỉ chạy thử". Vì vậy tôi chỉ nới giới hạn trong một file thử riêng (`whatif_leverage_x20.yaml`). **Cài đặt mặc định không đổi.**
- Các giới hạn được nới trong bản thử:
  - đòn bẩy tối đa 5x lên 20x;
  - trần một lệnh 2 lần vốn lên 20 lần vốn;
  - khoảng cách tối thiểu giữa giá thanh lý và stop từ 30% xuống 0,5%.
- Stop vẫn phải nằm trước giá thanh lý. Giới hạn lỗ trong ngày, kill switch và mô phỏng thanh lý vẫn bật.
- **Đòn bẩy cao không tự làm lãi nhiều hơn.** Bot đặt cỡ lệnh theo rủi ro, ví dụ mất 2% vốn nếu chạm stop. Đòn bẩy chỉ đổi số tiền ký quỹ.
- **x20 trên BTC/ETH làm số lệnh giảm** từ 20 xuống 7. Ở x20, giá thanh lý chỉ cách giá vào khoảng 5%, nên những lệnh có stop xa hơn bị từ chối. Trên sàn thật, những lệnh đó sẽ bị thanh lý trước khi chạm stop.
- **x5 cho altcoin có ích ở rủi ro 10%.** Trần 2 lần vốn trước đây chặn một số lệnh; ở x5 các lệnh đó được vào (37 → 46 lệnh), nên bài A tăng từ +29% lên +46%.

## 5. Những điều cần biết

- Khoảng tin cậy của lãi trung bình mỗi lệnh vẫn chạm hoặc chứa 0 ở hầu hết các bài. Chưa thể nói cách này có lợi thế thật.
- 28 tổ hợp được thử trên cùng dữ liệu, nên cách thắng có thể chỉ là may. Chỉ bài A và B mới là bằng chứng.
- Đã sửa một lỗi: với stop rất xa trên nến ngày, mức chốt lời 1:2 của lệnh bán có thể ra giá âm. Bot giờ bỏ qua tín hiệu đó.

## 6. Bước tiếp theo tôi đề xuất

Chạy K3 + chốt lời 1:2 trên giấy với dữ liệu thời gian thực, ở rủi ro 1–2%, cùng với cách swing EMA của vòng 5. Hai cách này đều lãi nhẹ ở rủi ro thấp trên dữ liệu chưa thấy, nhưng còn quá ít lệnh để kết luận.
