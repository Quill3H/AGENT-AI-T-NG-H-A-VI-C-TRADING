<!-- wiki-meta {"id": "project-map", "type": "project", "title": "Bản đồ dự án", "updated_at": "2026-10-30", "source_ids": ["spec", "state", "planner", "repair-review"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Bản đồ dự án

Dự án nghiên cứu crypto futures bằng paper simulation. Các phần chính: dữ liệu, features, strategies, risk, execution, backtest và báo cáo. Các luồng shared-account ETH/BTC, funding carry và ORB cần đọc hướng dẫn riêng; không mặc định mọi chiến lược đi qua cùng runner.

Main tại 65960bf đã có checkpoint Synthesized ngày 29/10, research QA và các báo cáo repo ngoài; bản hợp nhất giữ thêm checkpoint ETH/BTC ngày 22/10. Các nhãn nghiệm thu và số test cũ là lời công bố trong nguồn, không phải kết quả kiểm chứng của lượt merge. Đối chiếu Git hiện hành và [[latest]] trước khi tiếp tục; xem [[evidence-standard]] và [[strategy-comparison]].

Chưa có nghiệm thu kinh tế toàn dự án được xác minh trong tác vụ wiki.

## Nguồn

- [spec](<../../../Project%20spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md>), mục `1.2 Nguyên tắc thiết kế cốt lõi`; đã tracked ở snapshot; xem SHA trong manifest.
- [state](<../../PROJECT_STATE.md>), mục `ETH–BTC cointegration v1 — 2026-10-22`; đã tracked ở snapshot; xem SHA trong manifest.
- [planner](<../../../PLANNER_HANDOVER.md>), mục `Current single-main integration — 2026-09-23`; đã tracked ở snapshot; xem SHA trong manifest.

## Đọc lại đặc tả ngày 30/10/2026

Đã đọc phần U1–U7 mới từ main 460ed37; baseline kỹ thuật được giữ lịch sử. Thẩm quyền, paper-only, dữ liệu thật/giả lập và phân biệt software/protocol/economic verdict không cho phép tự mở gate hoặc nâng mức kiểm chứng. Các mô tả chưa tích hợp trong nguồn là snapshot 65960bf; trạng thái tích hợp mới xem docs/reviews/MAIN_INTEGRATION_2026_10_29.md từ package.

## Checkpoint sửa lỗi ngày 30/10/2026

Main tích hợp bản sửa broker/data/recovery có chọn lọc sau review. Checkpoint tổng hợp cũ không phải nghiệm thu: artifact synthetic, lỗ và provenance cũ không hợp lệ. Xem [[synthesized-repair]] và báo cáo repair-review; đối chiếu Git hiện hành trước khi tiếp tục.

- [repair-review](../../docs/reviews/CAUSAL_RECOVERY_EVIDENCE_REPAIR_2026_10_30.md), các mục correction, implemented behavior và verification.
