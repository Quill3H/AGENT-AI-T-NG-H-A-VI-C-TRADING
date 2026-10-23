# Vòng 18: BTC hồi phục sau cú giảm có OI co lại (btc_oi_contraction_reclaim_v1, 2026-10-22)

> **Cập nhật 23/10/2026:** Codex review yêu cầu sửa 4 lỗi trong bộ mô phỏng. Đã sửa và chạy lại
> (mục "Chạy lại sau review" ở cuối). Phần dưới đây là bản cũ, giữ lại để đối chiếu; con số
> sụt vốn 0,31% và hai câu "69 tháng" và "loại trừ nhau" ở bản cũ không còn đúng.

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

## Chạy lại sau review của Codex (23/10/2026, engine ce7ce67)
Luật v1, dữ liệu và các kịch bản giữ nguyên. Chỉ sửa bộ mô phỏng:
- **Rủi ro:** dùng đúng bộ ngắt mạch của dự án (lỗ 24 giờ trượt 5% thì khóa 24 giờ, thua 3 lệnh liền thì giảm rủi ro một nửa, thắng 3 lệnh liền thì trả lại). Phí, funding và lệnh đóng được ghi đúng thời điểm. Nếu một khoản funding làm chạm ngưỡng lỗ thì đóng lệnh ngay.
- **Dữ liệu:** thiếu nến 15 phút hoặc thiếu funding thì báo lỗi dữ liệu, không coi như "chưa chạm cắt lỗ" hay "funding bằng 0". Lượt lỗi dữ liệu không được chấm điểm và không ghi vào sổ.
- **Đường vốn:** tính lại từ sổ dòng tiền ở mọi nến 15 phút, có funding ngay khi trả. Sụt vốn đo trên 15 phút. Lệnh chạm chốt lời/cắt lỗ trong nến được ghi lúc nến đóng.
- **Báo cáo:** vốn cuối kỳ khớp đúng tổng dòng tiền, kể cả lệnh đóng ở cuối cửa sổ.

| Giai đoạn | Kịch bản | Trạng thái | Số lệnh | Lãi/lỗ | Sụt vốn (15 phút) |
|---|---|---|---|---|---|
| 2021–2023 | Mọi kịch bản có OI | Lỗi dữ liệu OI, không chấm | | | |
| 2021–2023 | Bỏ điều kiện OI | OK | 0 | 0 | 0 |
| 2024 – 09/2026 | Cơ sở, phí gấp đôi, OI trễ 60 phút, bỏ điều kiện OI | OK | 0 | 0 | 0 |
| 2024 – 09/2026 | Vào chậm 1 nến (phép thử nhạy) | OK | 2 | +123,59$ (+1,24%) | 0,43% |

**Đính chính:**
- 2021–2023 bị lỗi dữ liệu OI nên không được dùng làm bằng chứng. Bằng chứng hợp lệ chỉ có 2024 – 09/2026: **0 lệnh trong 33 tháng**, không phải 69 tháng.
- 2024–2026 vẫn thiếu 460 mốc OI 5 phút (41 mốc đúng giờ). Chỉ có thể nói là không thiếu mốc OI nào cần dùng tại các cú giảm.
- Hai điều kiện "hồi phục 25%" và "lãi/rủi ro ≥ 1,5" **không loại trừ nhau**. Có vùng giá vào hợp lệ khi râu dưới + 0,25 ATR ≤ 25% cú giảm. Vấn đề là vùng này hẹp, và khi nến 1 giờ xác nhận xong thì giá thường đã đi qua vùng đó. Cần phân tích kỹ trước khi làm v2. Không chỉnh ngưỡng v1.

**Kết luận không đổi:** v1 không vào lệnh nào ở kịch bản chính. Bản vào chậm 2 lệnh chỉ là phép thử nhạy, không phải ứng viên. Đang chờ Codex review lại.

File: `crypto-paper-agent/docs/research/runs/oi-reclaim-v1-ce7ce67/` (sự kiện, lệnh, dòng tiền, đường vốn 15 phút), hồ sơ bàn giao `crypto-paper-agent/docs/reviews/OI_RECLAIM_V1_FIX_HANDOFF_2026-10-23.md`.
