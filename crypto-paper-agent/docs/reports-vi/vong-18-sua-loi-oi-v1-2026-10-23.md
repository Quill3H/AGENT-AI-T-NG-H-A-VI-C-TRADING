# Vòng 18 (sửa lỗi): btc_oi_contraction_reclaim_v1 sau review của Codex (23/10/2026)

Chỉ giao dịch giấy. Bản sửa cho 4 lỗi Codex nêu (F1–F4) khi review hai commit `5fdda7c` (code) và
`ab1ad81` (kết quả). Kết quả do mình tự chạy, **chưa có người kiểm tra độc lập**
(AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED). Cần Codex review lại.

- Nhánh: `claude/project-thread-ryvuyt` (nối tiếp `claude/project-thread-uiqlsn`, gốc `ab1ad81`).
- Commit sửa code (khóa trước khi chạy lại): **`ff64ed7`** (`ff64ed7d9a432cc972c72359ebae17ecbd648400`).
- Commit kết quả, ledger và tài liệu: commit ngay sau `ff64ed7` trên cùng nhánh.
- **Không đổi tham số v1 nào**, file cấu hình không bị sửa: cú giảm 2 ATR, OI −1%, hồi 25%,
  lãi/rủi ro 1,5, cắt lỗ/chốt lời, thời gian nghỉ 24 giờ, xác nhận 2 nến 1 giờ, rủi ro 0,5%, 1x, phí.
- **Không làm v2, không chọn bản vào chậm** dựa trên hai lệnh thắng.

## Đã sửa gì

### F1 – Giảm rủi ro và ngắt giao dịch
- Bộ mô phỏng giờ dùng đúng bộ ngắt mạch của dự án (`CircuitBreakerState`) và bộ kiểm tra luật cứng
  (`check_all_invariants`), giống broker và bộ mô phỏng carry. Bộ đếm lỗ theo ngày lịch tự viết đã bỏ.
- Mỗi dòng tiền được ghi **đúng lúc nó xảy ra**: phí và trượt giá lúc vào, từng lần trả funding,
  dòng tiền lúc đóng lệnh. Lỗ ròng trong 24 giờ trượt chạm 5% vốn thì khóa 24 giờ.
- Nếu bị khóa khi đang giữ lệnh (ví dụ do một khoản funding lớn), lệnh bị **đóng ngay** ở giá mở
  của nến đó (lý do `CIRCUIT_BREAKER_LOCK`). Lệnh đóng cưỡng bức này không tính vào chuỗi thua, giống broker.
- Chuỗi thua chỉ tính theo lãi/lỗ ròng của lệnh đã đóng: thua 3 lệnh liên tiếp thì rủi ro còn
  một nửa (0,25%); thắng 3 lệnh liên tiếp mới trở lại 0,5%. Không cộng trùng phí hay funding.
- Mỗi lệnh vào phải qua luật cứng: cắt lỗ đúng chiều, đòn bẩy 1x, trần rủi ro bậc "normal" 2%,
  rủi ro thật tới cắt lỗ không vượt ngân sách, đủ ký quỹ, danh nghĩa ≤ 1x vốn, khoảng cách thanh lý.

### F2 – Thiếu nến hoặc funding thì dừng, không mô phỏng tiếp
- Trước khi chạy, kiểm tra **mọi nến 15 phút** từ dữ liệu ATR (16 giờ trước đầu cửa sổ) tới cuối
  cửa sổ, và **mọi mốc funding 00/08/16 UTC** trong cửa sổ. Thiếu, lệch lưới hoặc giá trị không hợp lệ
  thì lượt chạy thất bại với `DataQualityError`.
- Thiếu funding không còn bị coi là funding = 0; mất nến không còn bị coi là "chưa chạm cắt lỗ".
- Lượt nào lỗi dữ liệu được đánh dấu `DATA_QUALITY_FAILED`, **không có số liệu được chấm**.
  Lượt có cú giảm thiếu OI vẫn giữ con số, nhưng chỉ trong mục `diagnostic_not_scored`. Ledger ghi các
  lượt này với giai đoạn `data-quality-failed`, không còn ghi là lượt validation hợp lệ.

### F3 – Đường vốn và drawdown trên nến 15 phút
- Đường vốn dựng lại từ **sổ dòng tiền** tại mỗi lần đóng nến 15 phút, cộng lãi/lỗ tạm tính của
  lệnh đang mở. Funding xuất hiện trong đường vốn **ngay ở nến nó được trả**, không đợi tới lúc đóng lệnh.
- Drawdown tính trên chuỗi 15 phút, lấy vốn ban đầu làm đỉnh đầu tiên. Không còn gộp về 1 giờ.
  Lưu ý: vẫn chưa thấy giá thấp nhất bên trong nến, nên đây vẫn là mức tối thiểu.
- Lệnh thoát giữa nến (chạm cắt lỗ/chốt lời) giờ ghi thời điểm là **lúc đóng nến** (khi mới biết
  được), kèm cột `exit_bar` là giờ mở của nến đó.

### F4 – Đối chiếu vốn khi đóng lệnh cuối kỳ
- Báo cáo giờ giữ lại khoản tất toán cuối kỳ, và không tạo ra năm hoặc tháng giả tại ngày 01/01 hay ngày 01.
- Cả bộ mô phỏng và báo cáo đều **dừng với lỗi** nếu vốn cuối khác vốn đầu + tổng lãi/lỗ ròng các
  lệnh, hoặc khác vốn đầu + tổng dòng tiền (sai số 1e-6).

## Kiểm thử
- 12 kiểm thử mới (`test_f1_*` … `test_f4_*`), **đều đỏ trên `ab1ad81`, đều xanh trên `ff64ed7`**.
  - 5 kiểm thử đỏ vì hành vi sai, ra đúng số Codex đã tái hiện:
    - giữ lệnh tới TIME_STOP thay vì đóng khi bị khóa;
    - nhận lệnh rủi ro 3%;
    - funding không vào đường vốn lúc lệnh còn mở (0 so với −3,362865);
    - báo cáo 9.997,31 trong khi tiền mặt là 9.994,62 (2 trường hợp).
  - 7 kiểm thử đỏ vì thiếu các tên mà bản sửa thêm vào. Hành vi cũ của các trường hợp này đã được
    probe của Codex chỉ ra: lệnh thứ 4 vẫn 0,5%, mất nến thì ra TIME_STOP, funding rỗng thì ra 0.
  - (Commit message của `ff64ed7` ghi nhầm là 13 kiểm thử, đúng là 12.)
- Toàn bộ kiểm thử offline tại `ff64ed7`: **680 passed, 2 skipped, 5 network deselected**.
- Trên `ab1ad81`, chạy cả bộ ra 668 passed, 3 skipped; 4 kiểm thử cần mạng lỗi vì máy không có mạng.

## Chạy lại (cùng dữ liệu, cùng sha256 với lần đầu)

| Giai đoạn | Kịch bản | Trạng thái | Số lệnh | Lãi % | Sụt vốn 15m % | Lãi ròng $ |
|---|---|---|---|---|---|---|
| 2021–2023 | 6 kịch bản có OI + OI trễ 60 phút | DATA_QUALITY_FAILED (3 cú giảm thiếu OI) | không chấm | | | |
| 2021–2023 | Bỏ điều kiện OI | OK | 0 | 0 | 0 | 0 |
| 2024 – 09/2026 | Cơ sở, phí ×2, OI trễ 60 phút, bỏ điều kiện OI | OK | 0 | 0 | 0 | 0 |
| 2024 – 09/2026 | Vào chậm 1 nến (chỉ là phép thử nhạy) | OK | 2 | +1,24 | **0,43** (trước ghi 0,31) | +123,59 |

- **Phễu lọc và lý do từ chối không đổi** ở mọi kịch bản: bản sửa thay đổi kế toán và rủi ro, không đổi luật.
- Bộ ngắt mạch không lần nào khóa, cả 2 lệnh đều chạy ở mức rủi ro đầy đủ.
- Hai lệnh vào chậm giữ nguyên giá vào/ra và lãi ròng (123,590892, khớp bản Codex tự dựng lại).
  Giờ thoát lệnh lùi 15 phút vì giờ ghi theo lúc đóng nến.
- Sụt vốn 0,4299% khớp đúng con số Codex tính khi có funding và dùng chuỗi 15 phút.
- Kiểm tra nến 15 phút và funding đều đạt: cả hai giai đoạn không thiếu nến hay mốc funding nào.

## Đính chính báo cáo trước
- Giai đoạn 2021–2023 bị DATA_QUALITY_FAILED, nên câu "69 tháng không có lệnh" chỉ đúng cho
  2024–09/2026 và bản đối chứng bỏ OI của 2021–2023. Các kịch bản có OI của 2021–2023 không phải bằng chứng.
- Giai đoạn 2024–2026 có **460 mốc OI 5 phút bị thiếu (41 mốc đúng giờ)**. Điều đúng là không cú giảm
  nào trong giai đoạn này thiếu hai mốc OI cần dùng, chứ không phải dữ liệu OI đầy đủ.
- Hai điều kiện "hồi 25%" và "lãi/rủi ro ≥ 1,5" **không mâu thuẫn nhau** như mình đã viết.
  - Có vùng giá vào hợp lệ khi phần râu dưới cộng 0,25 ATR không quá 25% cú giảm.
  - Codex đếm (có tính tick và trượt giá): 30/111 và 28/87 sự kiện được nhận có vùng giá vào khả thi,
    nhưng chỉ 1/21 và 3/19 tín hiệu còn vùng đó khi xác nhận xong.
  - Lý do không có lệnh là vùng giá vào hẹp sau 1 giờ xác nhận, không phải luật tự mâu thuẫn.

## Giới hạn còn lại
- Drawdown vẫn chỉ nhìn giá đóng nến 15 phút, chưa thấy giá thấp nhất trong nến.
- Giá thanh lý ước tính cho lệnh long 1x là 0, nên chỉ kiểm tra ở bước vào lệnh; không mô phỏng thanh lý trong lúc giữ lệnh.
- Lịch funding được giả định là 8 giờ cho BTCUSDT (dữ liệu xác nhận không có mốc lệch lịch).
  Nếu có mốc ngoài lịch thì vẫn được dùng.
- Luật lọc lệnh 0,001 BTC và tick 0,1 vẫn lấy theo mức hiện tại, chưa kiểm chứng cho quá khứ.

## File
- Code: `src/strategies/oi_reclaim.py`, `scripts/reproduce_oi_reclaim.py`, `tests/test_oi_reclaim.py`.
- Kết quả: `docs/research/runs/oi-reclaim-v1-ff64ed7/`
  - `summary.json`, `data_check.json`;
  - sự kiện / lệnh / dòng tiền của từng kịch bản;
  - đường vốn 15 phút của kịch bản vào chậm;
  - `logs/`: log đỏ trên `ab1ad81`, log xanh trên `ff64ed7`, log toàn bộ kiểm thử.
- Đường vốn 15 phút của mọi kịch bản: `/mnt/project-files/research-runs/oi-reclaim-v1-ff64ed7/equity-15m/`.
- Ledger: 16 dòng của `5fdda7c` được đánh dấu void (vẫn giữ lại, không xóa); 16 dòng mới ở `ff64ed7`,
  gồm 9 dòng validation và 7 dòng data-quality-failed; thêm 1 bài học. LEARNING_LOG đã sinh lại.
- Tài liệu kỹ thuật: `docs/research/2026-10-22-btc-oi-reclaim-v1.md`, mục "Fix and rerun at ff64ed7".
