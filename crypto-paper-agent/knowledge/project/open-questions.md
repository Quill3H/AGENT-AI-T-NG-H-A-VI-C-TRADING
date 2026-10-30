<!-- wiki-meta {"id": "open-questions", "type": "project", "title": "Câu hỏi còn mở", "updated_at": "2026-10-30", "source_ids": ["state", "lab-review", "orb", "repair-review"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Câu hỏi còn mở

1. Bằng chứng forward/untouched tiếp theo nào được định trước và chưa bị dùng chọn phương án?
2. Các hạn chế fill/quantity và lịch sử exchange filters tác động bao nhiêu đến kết quả?
3. ORB/broker đã được commit tại 05a396f; kiểm kết quả review/test trên đúng bản hợp nhất trong docs/reviews/MAIN_INTEGRATION_2026_10_29.md. Việc merge không tự xác nhận kinh tế hoặc vận hành.
4. Tài liệu nào cần cập nhật để checkpoint và bàn giao phản ánh cùng trạng thái?
5. Có thể tái hiện báo cáo trên đúng dữ liệu/config/code hay chỉ còn văn bản?

Không tự chạy tải dữ liệu hay thí nghiệm dài để trả lời. Dùng [[experiment-register]] lập phạm vi bước tiếp theo.

## Nguồn

- [state](<../../PROJECT_STATE.md>), mục `ETH–BTC cointegration v1 — 2026-10-22`; đã tracked ở snapshot; xem SHA trong manifest.
- [lab-review](<../../docs/reviews/BACKTEST_LAB_2026_10_27.md>), mục `Author verification on final code`; đã tracked ở snapshot; xem SHA trong manifest.
- [orb](<../../docs/research/crypto-orb-portfolio.md>), mục `Execution and input limits`; chưa commit hoặc đang sửa; xem SHA trong manifest.

## Checkpoint sửa lỗi ngày 30/10/2026

Bảy artifact cũ đã đối soát và được xác định synthetic; câu hỏi tiếp theo là chuẩn bị nguồn thị trường có thể truy vết cùng hợp đồng đánh giá, không phải ép bộ mô phỏng cũ thành backtest thật. Chưa xác minh prospective paper/reboot/soak. Xem [[synthesized-repair]].

- [repair-review](../../docs/reviews/CAUSAL_RECOVERY_EVIDENCE_REPAIR_2026_10_30.md), các mục correction, implemented behavior và verification.
