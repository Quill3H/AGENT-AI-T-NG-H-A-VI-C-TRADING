<!-- wiki-meta {"id": "experiment-register", "type": "project", "title": "Sổ thí nghiệm và bước tiếp theo", "updated_at": "2026-10-30", "source_ids": ["method-search", "pair-report", "orb", "repair-review"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Sổ thí nghiệm và bước tiếp theo

| Hồ sơ | Phạm vi | Trạng thái |
|---|---|---|
| [[funding-2026-10-16]] | Dev + final historical check được tác giả mô tả | AUTHOR_REPORTED |
| [[pair-v1-2026-10-22]] | Seen-data retrospective | AUTHOR_REPORTED, không đạt |
| [[orb-working]] | Working rulebook | NOT_VERIFIED, chưa có PnL nạp |

Bước tiếp theo đề xuất: kiểm tra snapshot ORB đang làm và bằng chứng đã có trước khi quyết định thí nghiệm tiếp theo. Chủ dự án chọn ưu tiên; wiki không tự thay đề cương. Ghi run ID, tham số, data/code/config hashes và cả lượt thất bại. Số lần thử chưa biết ghi unknown.

## Nguồn

- [method-search](<../../docs/research/2026-10-16-method-search.md>), mục `Result of the frozen candidate`; đã tracked ở snapshot; xem SHA trong manifest.
- [pair-report](<../../docs/reports-vi/2026-10-22-eth-btc-cointegration-v1.md>), mục `Kết quả cả 12 kịch bản`; đã tracked ở snapshot; xem SHA trong manifest.
- [orb](<../../docs/research/crypto-orb-portfolio.md>), mục `Execution and input limits`; chưa commit hoặc đang sửa; xem SHA trong manifest.

## Checkpoint sửa lỗi ngày 30/10/2026

Đã lưu hồ sơ [[synthesized-repair]] và giữ nguyên artifact/probe thất bại cũ. Không có lần tuning, dữ liệu thị trường mới hoặc prospective paper mới; E2E explicit synthetic chỉ kiểm luồng phần mềm. Xem báo cáo nguồn để lấy lệnh và kết quả chính xác.

- [repair-review](../../docs/reviews/CAUSAL_RECOVERY_EVIDENCE_REPAIR_2026_10_30.md), các mục correction, implemented behavior và verification.
