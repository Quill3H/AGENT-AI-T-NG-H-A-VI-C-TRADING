# Kiểm tra cách tính phí trong bản chạy thử (2026-10-21)

## Đang tính những gì
| Khoản | Cách tính trong code | So với Binance USDⓈ-M |
|---|---|---|
| Phí khớp lệnh | **0,05% × giá trị lệnh (notional)**, tính cả lúc vào lẫn lúc ra. Mọi lệnh, kể cả chốt lời, đều tính phí taker (`paper_broker.py`) | Tài khoản thường (VIP 0): taker 0,05%, maker 0,02%. Trả phí bằng BNB được giảm 10%. Mình **không** tính giảm giá BNB hay VIP |
| Trượt giá | 0,03% mỗi chiều: mua đắt hơn, bán rẻ hơn giá mở nến. Lệnh cắt lỗ khớp ở giá cắt lỗ trừ thêm 0,03%. Nếu giá nhảy qua cắt lỗ thì khớp ở giá mở nến (còn xấu hơn) | Chênh lệch mua bán của BTC/ETH thường nhỏ hơn 0,01%. Nhưng khi thị trường chạy mạnh, lệnh cắt lỗ có thể trượt hơn 0,03% |
| Funding | Lấy đúng mức funding thật của từng đợt từ dữ liệu Binance. Tiền = khối lượng × giá × mức funding. Bên long trả khi mức dương, bên short trả khi mức âm | Đúng cách Binance tính, chỉ khác là mình dùng giá mở nến thay cho giá mark (sai lệch rất nhỏ) |
| Phép thử "phí gấp đôi" | Nhân đôi cả phí lẫn trượt giá | Để xem kết quả có còn đứng vững khi chi phí xấu hơn |

**Tổng chi phí một lệnh vào rồi ra:** khoảng 0,16% giá trị lệnh, chưa kể funding. Với đòn bẩy 2x, mỗi lệnh tốn khoảng 0,32% vốn đặt vào lệnh đó.

## Chỗ thận trọng hơn thực tế (làm kết quả xấu đi một chút)
- Lệnh chốt lời và lệnh chờ đều tính phí taker 0,05%. Thực tế, lệnh chờ chỉ tốn phí maker 0,02%.
- Không tính giảm 10% khi trả phí bằng BNB.

## Chỗ có thể lạc quan hơn thực tế
- Trượt giá 0,03% có thể là ít khi thị trường sập hoặc khi giao dịch coin nhỏ.
- Không mô phỏng việc lệnh lớn làm giá chạy (không quan trọng với vốn 10.000$).

## Lỗi tìm thấy và đã sửa
- **Lỗi:** code chỉ thu funding vào 0h, 8h và 16h UTC. Khi thị trường căng thẳng, Binance rút chu kỳ funding xuống 4 giờ hoặc 2 giờ. Trong 10 đồng mình dùng, việc này chỉ xảy ra với **SOL từ 9 đến 18/11/2022** (sau vụ FTX sập): 75 đợt funding bị bỏ sót, cộng lại −21,5%. Nghĩa là ai giữ lệnh short SOL lúc đó đã không bị trừ khoản phí này.
- **Đã sửa:** bây giờ cứ có đợt funding nào là thu đợt đó, kể cả trong phần mô phỏng ăn funding. Đã thêm 2 test; toàn bộ 639 test đều đạt.
- **Ảnh hưởng (đo lại trên SOL quý 4/2022):**
  - Ichimoku I1 (vòng 9): phần vốn SOL giảm 2,9%. Phần SOL chỉ chiếm 1/3 tài khoản (khi chạy BTC/ETH/SOL) hoặc 1/10 (khi chạy 10 đồng), nên kết quả cả tài khoản thấp hơn khoảng 0,3–1%.
  - Bản chạy cả kế hoạch Reddit (vòng 17) lãi thêm 1$.
  - C1, A2, S1, P1, X3, R2 và phần ăn funding không đổi.
  - Không kết luận nào trước đây bị thay đổi.

## Kết luận
Cách tính phí, trượt giá và funding nhìn chung đúng và hơi thận trọng: tính hai chiều, theo giá trị lệnh, dùng funding thật. Sai sót duy nhất tìm thấy là funding của SOL trong 9 ngày năm 2022. Đã sửa, và ảnh hưởng dưới 1% tài khoản.

Nguồn biểu phí: [Finder, cập nhật 01/2024](https://www.finder.com/binance-futures-fees). Mình không mở được trang phí của chính Binance để kiểm tra lại mức hiện hành.
