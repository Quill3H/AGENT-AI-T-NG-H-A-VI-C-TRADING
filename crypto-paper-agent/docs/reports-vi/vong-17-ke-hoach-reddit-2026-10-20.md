# Vòng 17: thử "kế hoạch futures đơn giản" của bài r/Daytrading (2026-10-20)

Chỉ giao dịch giấy trên perp BTC/ETH/SOL, nến 5 phút, đòn bẩy 2x, có phí, trượt giá và funding. Kết quả do mình tự chạy, chưa có người kiểm tra độc lập (AUTHOR_REPORTED).

## Luật lấy từ bài và phần bình luận
- Chỉ giao dịch quanh giờ mở cửa Mỹ, tối đa 2 lệnh mỗi ngày rồi nghỉ.
- **R1:** vùng giá 6:00–7:00 sáng giờ New York; lệnh vào khi nến đóng ra ngoài vùng trong 7:00–7:30. Cắt lỗ ở phía bên kia vùng.
- **R2:** xem hướng chạy từ 9:30 đến 9:45; sau 9:45, gặp nến búa, sao băng hoặc nến nhấn chìm ngược hướng thì vào lệnh ngược lại. Cắt lỗ ngay ngoài nến đó.
- **R3:** cả hai cách trên, mỗi cách tối đa một lệnh mỗi ngày.
- Chốt lời ở 2 lần mức rủi ro. Bỏ qua lệnh khi điểm cắt lỗ quá sát (dưới 0,3% giá), vì phí sẽ ăn hết lãi.
- Phần mình đơn giản hoá: bài vào lệnh trên nến 1 phút, mình vào ở đầu nến 5 phút kế tiếp.

## Kết quả 2021–2023
| Cách | Rủi ro | Lãi/lỗ 3 năm | Sụt vốn sâu nhất | Số lệnh | Tỉ lệ thắng | Trung bình/tháng |
|---|---|---|---|---|---|---|
| R1 | 2% | −50,5% | 54,7% | 1.195 | 35,2% | −1,93% |
| R2 | 2% | −12,5% | 23,4% | 397 | 37,5% | −0,37% |
| R3 (cả kế hoạch) | 2% | −68,3% | 69,6% | 1.638 | 35,3% | −3,14% |
| R2 (được chọn) | 5% | −10,6% | 12,5% | 27 | 33,3% | −0,31% |
| C1 (để so sánh) | 5% | +317,9% | 31,4% | 357 | 26,6% | +4,05% |

## Kiểm tra lại R2 rủi ro 5% (dữ liệu đã từng xem)
- 01/2024 – 09/2026: −0,2%, chỉ 2 lệnh. Khi phí gấp đôi: −2,2%. Tháng 10/2026: không có lệnh.
- C1 cùng giai đoạn: +17,8%, sụt vốn 24,3%.

## Kết luận thật
- **Thất bại.** Cả ba bản đều lỗ sau phí. Tỉ lệ thắng 35–39% với chốt lời 2R chỉ gần hoà trước phí. Cắt lỗ trên nến 5 phút rất sát nên phí ăn hết phần còn lại.
- Ở rủi ro 5%, bot gần như không vào lệnh. Một lệnh thua trọn cộng phí đã có thể chạm mức khoá lỗ 5% mỗi ngày, và luật thua liên tiếp còn giảm khối lượng. Mình chưa tách rõ nguyên nhân nào chiếm bao nhiêu.
- Không đưa vào chạy giấy tuần tới.

## Bài học quản lý rủi ro và hành vi đáng đưa vào luật bot
Bot đã có sẵn: lệnh nào cũng có cắt lỗ, khoá khi lỗ quá mức trong ngày, giới hạn khối lượng và số lệnh.

Đề xuất thêm (chờ bạn đồng ý, chưa làm):
1. **Không bao giờ nới cắt lỗ:** chỉ được dời cắt lỗ về phía có lãi. (Đính chính 21/10: code đã có sẵn luật chặn nới cắt lỗ khi bot dời stop, lần trước mình tìm sót. Nay bot còn dừng hẳn nếu phát hiện cắt lỗ bị nới bằng bất kỳ cách nào.)
2. **Nhật ký từng lệnh:** ghi điểm vào, cắt lỗ, chốt lời và lý do thoát cho mỗi lệnh giấy, để xem lại từng tuần.
3. **Bỏ lệnh khi cắt lỗ quá sát so với phí:** như luật 0,3% ở vòng này.

**Cập nhật 21/10:** bạn đã đồng ý, cả hai luật đã được đưa vào code.
