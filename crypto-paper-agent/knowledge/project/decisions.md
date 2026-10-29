<!-- wiki-meta {"id": "decisions", "type": "project", "title": "Quyết định và ranh giới", "updated_at": "2026-10-29", "source_ids": ["spec", "pair-adr", "planner"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Quyết định và ranh giới

Paper-only tiếp tục có hiệu lực. Quyền xây wiki không mở rộng sang đặt lệnh thật/testnet hoặc đổi risk. ADR0015 cho phép thí nghiệm ETH/BTC cố định, không biến kết quả mã thành lợi thế kinh tế.

Quy định tích hợp main trong hồ sơ bàn giao và checkout feature hiện tại phải được đối chiếu trước commit/push. Wiki không tự giải quyết bằng checkout/reset/merge. Xem [[open-questions]] và [[project-map]].

## Nguồn

- [spec](<../../../Project%20spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md>), mục `1.2 Nguyên tắc thiết kế cốt lõi`; đã tracked ở snapshot; xem SHA trong manifest.
- [pair-adr](<../../docs/decisions/0015-eth-btc-cointegration-v1.md>), mục `Decision`; đã tracked ở snapshot; xem SHA trong manifest.
- [planner](<../../../PLANNER_HANDOVER.md>), mục `Current single-main integration — 2026-09-23`; đã tracked ở snapshot; xem SHA trong manifest.

## Đối chiếu khi hợp nhất ngày 29/10/2026

Nguồn planner trên main có thêm checkpoint Synthesized; quy định single-main và paper-only vẫn còn nguyên. Chủ dự án yêu cầu merge phần đủ điều kiện; lượt tích hợp không mở rộng quyền đặt lệnh hoặc tự chấp nhận các gate còn thiếu bằng chứng.

## Đọc lại đặc tả ngày 30/10/2026

Đã đọc phần U1–U7 mới từ main 460ed37; baseline kỹ thuật được giữ lịch sử. Thẩm quyền, paper-only, dữ liệu thật/giả lập và phân biệt software/protocol/economic verdict không cho phép tự mở gate hoặc nâng mức kiểm chứng. Các mô tả chưa tích hợp trong nguồn là snapshot 65960bf; trạng thái tích hợp mới xem docs/reviews/MAIN_INTEGRATION_2026_10_29.md từ package.
