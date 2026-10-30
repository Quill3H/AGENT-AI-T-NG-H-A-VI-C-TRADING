<!-- wiki-meta {"id": "synthesized-repair", "type": "experiments", "title": "Đính chính synthetic và sửa broker/recovery", "updated_at": "2026-10-30", "source_ids": ["repair-review", "broker", "state"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Đính chính synthetic và sửa broker/recovery

Bộ artifact tổng hợp cũ có 6.455 completed lifecycles, 10.892 realization slices,
WR 49,20%, nhưng lỗ ròng 91.280,33 USDT và DD 92,6019%. Audit đối chiếu giá vào
với seed-42 synthetic và funding giả định: không được gọi là backtest thị trường
hợp lệ. Giữ nguyên artifact, báo cáo ngày 29/10 và sáu probe cũ để truy vết.

Sửa ngày 30/10 chặn fallback ngầm; historical cần cache có manifest SHA và funding
có thời điểm nguồn/khả dụng; synthetic phải chọn rõ và ghi nhãn trong JSON/MD/HTML.
Broker đồng bộ pha cho các symbol, không lấy funding đến sau để quyết định tại
open; giữ cap, gap, kill switch và accounting. Recovery/API được tích hợp có chọn
lọc; funding mô phỏng và nghiên cứu hồi cứu không tự cấp vốn thay thế.

Review độc lập đã phát hiện và kiểm lại lỗi funding khả dụng trễ, rồi lỗi UI
không gửi được Pause/Stop lúc writer bận hoặc chart chậm/lỗi. Kết quả kiểm thử
chính xác, phạm vi người kiểm chứng và phần chưa xác minh nằm trong báo cáo nguồn.
Test kỹ thuật và graph không tự nghiệm thu kinh tế. Chưa có lượt dữ liệu thị trường
mới hoặc prospective paper được xác nhận trong sửa lỗi này.

Giảm phí tại cùng fill từ taker 0,05% sang maker 0,02% chỉ tiết kiệm 26.950,18
USDT; net vẫn khoảng -64.330,16. Không phải maker execution replay, không phải
phương pháp sinh lời. Không chỉnh tham số để ép mẫu/lợi nhuận.

## Nguồn

- [repair-review](../../docs/reviews/CAUSAL_RECOVERY_EVIDENCE_REPAIR_2026_10_30.md), mục `Original synthesized evidence: correction` và `Verification and limitations`.
- [broker](../../src/execution/paper_broker.py), `PaperBroker.process_batch`, các preflight và breaker phase.
- [state](../../PROJECT_STATE.md), checkpoint broker/recovery ngày 30/10/2026.
