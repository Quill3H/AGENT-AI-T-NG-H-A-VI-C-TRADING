# Vòng 19: phương pháp ICT "quét thanh khoản + FVG" từ bài Reddit, thử trên BTC/ETH/SOL (2026-10-23)

Chỉ giao dịch giấy (paper). Kết quả do Claude tự chạy và tự báo cáo (AUTHOR_REPORTED), chưa có
người kiểm tra độc lập. Bản đầy đủ bằng tiếng Anh: `docs/research/2026-10-23-round19-ict-sweep-fvg.md`.

## Kết luận ngắn
**Không đạt.** Hai kiểu vào lệnh trong bài, khi viết thành quy tắc rõ ràng cho BTC/ETH/SOL, gần
như không xuất hiện (13 đến 28 lệnh trong 3 năm ở mức rủi ro 2%, chỉ 0 đến 4 lệnh ở 5%) và không
có lãi sau phí. Bản được chọn (L2, rủi ro 5%) thắng 4/4 lệnh trong 2021–2023 nhưng chỉ thắng 1/5
lệnh trong 2024–2026/09 (−2,9%). Không đưa vào danh sách forward ngày 2026-10-25. Kết luận nghiên
cứu vẫn là **NO_TRADES**.

Bài gốc chỉ có 2 lệnh thắng (+684$, 1,8R và 2R), không có lệnh thua, phí hay số lệnh, và tác giả có
liên kết quảng bá TradeZella, nên bản thân bài không phải bằng chứng.

## Đã làm gì (theo đúng quy trình)
1. Đọc LEARNING_LOG và ledger: vòng 7 và 17 (các quy tắc theo giờ phiên Mỹ trên 5m) đều lỗ sau phí.
2. Viết quy tắc bằng số và khóa trước khi chạy bất kỳ backtest nào: commit `3fc2e7e`.
3. Chạy giai đoạn dev 2021–2023, chọn theo luật đã định, khóa lựa chọn ở commit `9d94cd6`.
4. Chạy kiểm tra trên dữ liệu đã thấy (2024-01..2026-10-17). `check_untouched` xác nhận đây là dữ
   liệu đã dùng, nên chỉ ghi là `validation`, không phải bằng chứng mới.
5. Ghi mọi lần chạy (21 dòng, kèm `variants_tried = 7`) và bài học vào ledger.

## Phép dịch từ NQ/MNQ sang crypto (tự chọn, bài gốc không cho số)
- Phiên Asia = 00:00–06:00 UTC, London = 07:00–12:00 UTC, mở cửa New York = 09:30 giờ New York
  (13:30 hoặc 14:30 UTC tùy giờ mùa hè). Chỉ thứ Hai đến thứ Sáu. Lệnh bán đối xứng với lệnh mua.
- Bối cảnh trước giờ mở cửa New York: quét cả đáy Asia lẫn đáy London; giá chạm một FVG khung 1h
  hoặc 4h còn hiệu lực; một nến tăng mạnh (thân ≥ 1 ATR) đóng lại trên hai đáy đã quét; đỉnh Asia
  (mục tiêu) chưa bị chạm.
- **L1** (lệnh 1 trong bài): khoảng mở cửa 15 phút 09:30–09:45, rồi nến 5m tạo FVG và đóng vượt
  khoảng đó; dừng lỗ dưới nến 1 của FVG; chốt lời ở đỉnh Asia, phải cách ít nhất 1,5R.
- **L2** (lệnh 2, IRL → ERL): lần đầu giá hồi về FVG 30 phút hình thành sau cú quét; dừng lỗ dưới
  nến 1 của FVG; chốt lời cố định 2R.
- **L3**: cả hai, mỗi kiểu tối đa một lần một ngày. Mọi lệnh đóng trước 16:00 giờ New York.
- Vào lệnh 1 phút như bài gốc chỉ thử được trên 2023-01..03, vì dữ liệu 1m chỉ có 3 tháng đó.
- Phí, funding, trượt giá, đòn bẩy 2x, trần khối lượng 2x vốn, giới hạn lỗ ngày 5% đều giữ nguyên
  như engine hiện có. Không đổi cấu hình rủi ro, không đụng tham số v1. Không tải thêm dữ liệu,
  không dùng ALGO/VET/SAND.

## Kết quả dev 2021–2023 (vốn giấy 10.000$)

| Bản | Rủi ro | Lãi/lỗ | DD tối đa | Số lệnh | Tỉ lệ thắng | R ròng TB | Chi phí x2 |
|---|---|---|---|---|---|---|---|
| L1 | 2% | +2,4% | 3,3% | 13 | 46% | +0,29 | +1,9% |
| L1 | 5% | 0% | 0% | 0 | | | 0% |
| L2 | 2% | +0,1% | 3,3% | 16 | 63% | +0,02 | −1,6% |
| **L2 (chọn)** | **5%** | **+3,6%** | **2,0%** | **4** | **100%** | **+0,53** | **+3,3%** |
| L3 | 2% | +2,7% | 3,6% | 25 | 56% | +0,17 | −0,7% |
| L3 | 5% | +3,6% | 2,0% | 4 | 100% | +0,53 | +3,3% |
| C1 tham chiếu | 5% | +318% | 31,4% | 357 | 27% | +0,44 | |

Thử 1m (2023-01..03): 0 lệnh, bản 5m cùng tháng cũng 0 lệnh, nên câu hỏi "vào lệnh 1 phút có tốt
hơn không" chưa trả lời được với dữ liệu hiện có.

Vì sao ít lệnh: trong 100 ngày thường, khoảng 43–48 lần (tính riêng chiều mua và bán) có quét cả
hai đáy/đỉnh, 19–23 lần qua được điều kiện FVG khung lớn, 13–16 lần còn mục tiêu đỉnh Asia lúc mở
cửa. Sau đó điều kiện nến tăng mạnh, tín hiệu vào lệnh, dừng lỗ tối thiểu 0,3% và khoảng cách 1,5R
cắt gần hết. Ở rủi ro 5%, phần lớn lệnh còn lại biến mất, nhiều khả năng do trần khối lượng 2x vốn
(dừng lỗ hẹp + rủi ro 5% đòi khối lượng 5–16 lần vốn), giống vòng 5 và 17; chưa truy từng lệnh.

## Kiểm tra sau khi khóa (dữ liệu đã thấy, chỉ để tham khảo)

| Lần chạy | Lãi/lỗ | DD tối đa | Số lệnh | Tỉ lệ thắng | R ròng TB |
|---|---|---|---|---|---|
| L2 5%, 2024-01..2026-09 | −2,87% | 3,74% | 5 | 20% | −0,33 |
| Như trên, chi phí x2 | −3,27% | 3,99% | 5 | 20% | −0,40 |
| L2 5%, 2026-10-01..17 | 0% | 0% | 0 | | |
| C1 tham chiếu 5%, 2024-01..2026-09 | +17,8% | 24,3% | 375 | 23% | +0,09 |

## Cổng forward (đã định trước)

| Điều kiện | Kết quả |
|---|---|
| Lãi trung bình tháng dev ≥ 0,48% (lãi gửi ngân hàng 5,9%/năm) | 0,10%: **trượt** |
| DD dev ≤ 35% | 2,0%: đạt |
| Số lệnh dev ≥ 30 | 4: **trượt** |
| Chi phí x2 dev > 0 | +3,3%: đạt |
| Lãi trên 2024-01..2026-09 > 0 | −2,9%: **trượt** |

Trượt 3/5 điều kiện nên không đưa vào forward paper.

## Bài học
- Một setup ICT nhiều điều kiện, khi viết ra thành quy tắc cố định, hiếm đến mức không đo được: 4
  lệnh trong 3 năm thì tỉ lệ thắng 100% hay 20% đều là may rủi. Hai lệnh thắng trong bài gốc càng
  không nói được gì.
- Phần đáng giữ của bài là kỷ luật "không có setup thì không giao dịch", trùng với NO_TRADES hiện tại.
- Lần thứ ba (vòng 7, 17, 19) quy tắc theo giờ phiên chứng khoán Mỹ không chuyển được sang crypto
  perp. Không nên thử thêm biến thể giờ phiên trừ khi có dữ liệu mới.

## Tệp và commit
- Nhánh `claude/project-thread-hz26f3` (gốc `claude/project-thread-jrmpfx` @ 7bebd39), chưa mở PR.
- `3fc2e7e`: đăng ký trước, code `src/strategies/ict_liquidity.py`, test, cấu hình, script
  `scripts/reproduce_round19.py`. `9d94cd6`: kết quả dev và lựa chọn khóa. Commit sau: kiểm tra,
  ledger, báo cáo này.
- Số liệu thô: `docs/research/runs/round19-ict-3fc2e7e/` (dev.json, check.json, funnel_dev.json).
- Test offline: 733 passed, 2 skipped, 5 deselected (trước khi chạy dev).
