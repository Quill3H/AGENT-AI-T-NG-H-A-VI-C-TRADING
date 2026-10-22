# Vòng 18: BTC hồi phục sau cú giảm có OI co lại (btc_oi_contraction_reclaim_v1, 2026-10-22)

Chỉ giao dịch giấy, BTCUSDT perpetual, chỉ long hoặc đứng ngoài, ký quỹ 1x. Làm đúng đặc tả bạn gửi, chờ Codex review.
- Kết quả do mình tự chạy, chưa có người kiểm tra độc lập (AUTHOR_REPORTED).
- Cả hai giai đoạn đều là dữ liệu đã từng xem (SEEN_DATA_RETROSPECTIVE), không phải phép thử cuối.

## Dữ liệu OI
- Tải 2.130/2.130 ngày metrics của Binance Vision (12/2020 – 09/2026) qua máy của bạn. Mọi file đều khớp checksum.
- **Vấn đề dữ liệu:**
  - Dòng trong file không xếp theo thời gian.
  - 150 ngày có mọi dòng bị lặp đúng 2 lần.
  - 473 dòng có OI = 0, nằm rải trên 23 ngày.
  - Mình chỉ sắp lại thứ tự, gộp các dòng trùng y hệt và bỏ các dòng OI = 0. Không điền hay nội suy chỗ nào.
- **2021–2023 bị đánh dấu DATA_QUALITY_FAILED:** 3 cú giảm không có số OI đúng giờ, vì Binance không có dòng đó (07/09/2021, 26/11/2021, 04/12/2021).
- 2024 – 09/2026 không có cú giảm nào bị thiếu OI.

## Kết quả
| Giai đoạn | Kịch bản | Số lệnh | Lãi/lỗ |
|---|---|---|---|
| 2021–2023 | Mọi kịch bản | 0 | 0 |
| 2024 – 09/2026 | Cơ sở, phí gấp đôi, OI trễ 60 phút, bỏ điều kiện OI | 0 | 0 |
| 2024 – 09/2026 | Vào chậm thêm 1 nến 15 phút (phép thử nhạy, không phải ứng viên) | 2 (cả 2 chạm chốt lời) | +123,6$ (+1,24%), sụt vốn 0,31% |

Không có lệnh nào trong 69 tháng thì không được tính là thành công. Kết quả với từng kịch bản đều như nhau dù funding tính theo thực tế hay bỏ hết khoản funding được nhận.

## Vì sao không có lệnh (2021–2023 / 2024–2026)
1. **Các cú giảm:**
   - Có 271 / 289 cú giảm giá lớn.
   - Trong đó 128 / 96 cú đi kèm OI giảm từ 1% trở lên.
   - Sau khi bỏ các cú rơi vào thời gian nghỉ 24 giờ, còn lại 111 / 87 sự kiện.
2. **Bị hủy hoặc hết hạn:**
   - 64 / 56 sự kiện bị hủy vì giá làm đáy mới trong 2 giờ sau đó.
   - 26 / 12 sự kiện hết hạn vì không có nến xác nhận.
3. **Có tín hiệu nhưng bị từ chối:**
   - 21 / 19 sự kiện có tín hiệu vào lệnh, nhưng đều bị từ chối tại giá khớp.
   - Lý do chính là tỉ lệ lãi/rủi ro chưa đạt 1,5 (15 / 11 lần).
   - Các lý do còn lại: giá mở đã tụt dưới mức hồi phục 25% (4 / 6 lần), hoặc thứ tự cắt lỗ < giá vào < chốt lời không đúng (2 / 2 lần).
4. **Mâu thuẫn trong luật:**
   - Phải mua trên mức hồi phục 25%, nên phần lãi tối đa còn khoảng 75% cú giảm.
   - Còn rủi ro thì ít nhất bằng 25% cú giảm, cộng 0,25 ATR, cộng phần râu dưới của nến giảm.
   - Vì vậy hai điều kiện "phải hồi phục 25%" và "lãi/rủi ro ≥ 1,5" gần như loại trừ nhau, trừ khi cú giảm gần như không có râu.

## Kết luận thật
- **Bản v1 như đặc tả gần như không bao giờ vào lệnh.** Đây là kết quả "không có lệnh", không phải lãi, cũng không phải lỗ.
- **Chưa đo được OI có giúp gì không:** bản bỏ điều kiện OI cũng không có lệnh nào.
- **Bản vào chậm 1 nến** chỉ có 2 lệnh, quá ít để kết luận (dưới mức sàn 30 lệnh). Theo đặc tả, không được chọn nó thay cho v1.
- **Mình không chỉnh ngưỡng nào sau khi chạy.** Nếu muốn có bản v2 (ví dụ đổi cách đặt cắt lỗ/chốt lời), bạn cần viết đặc tả mới và đăng ký trước.

## File
- Code và cấu hình khóa ở commit 5fdda7c (nhánh `claude/project-thread-uiqlsn`).
- Kết quả từng kịch bản và nhật ký từng sự kiện: `crypto-paper-agent/docs/research/runs/oi-reclaim-v1-5fdda7c/`.
- Tài liệu kỹ thuật: `crypto-paper-agent/docs/research/2026-10-22-btc-oi-reclaim-v1.md`.
- Dữ liệu OI thô: `/mnt/project-files/market-data/binance-vision-metrics-btcusdt/`.
