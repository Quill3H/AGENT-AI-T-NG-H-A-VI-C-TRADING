<!-- wiki-meta {"id": "source-catalog", "type": "sources", "title": "Danh mục nguồn đã đọc", "updated_at": "2026-10-29", "source_ids": ["spec", "state", "planner", "lab", "lab-review", "method-search", "pair-adr", "pair-report", "pair-ops", "orb", "broker", "quantdinger-review", "tradingagents-review", "tradingagents-paper-review"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Danh mục nguồn đã đọc

Các nguồn dự án bên dưới trỏ tới file gốc. Mục repo ngoài trỏ tới bản sao báo cáo được nhập nguyên bytes; chúng là nghiên cứu thứ cấp có trích nguồn upstream. `manifests/sources.json` ghi SHA-256, tracked/dirty, HEAD khi đọc và locator. Đổi file khiến trang phụ thuộc cần tái tổng hợp; không tự cập nhật hash để che sự thay đổi.

Ngày tiếp nhận nguồn: 29/10/2026. Kết quả cũ được giữ nguyên trạng thái báo cáo lịch sử. Xem [[project-map]] và [[evidence-standard]].

## Nguồn

- [spec](<../../../Project%20spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md>), mục `1.2 Nguyên tắc thiết kế cốt lõi`; đã tracked ở snapshot; xem SHA trong manifest.
- [state](<../../PROJECT_STATE.md>), mục `ETH–BTC cointegration v1 — 2026-10-22`; đã tracked ở snapshot; xem SHA trong manifest.
- [planner](<../../../PLANNER_HANDOVER.md>), mục `Current single-main integration — 2026-09-23`; đã tracked ở snapshot; xem SHA trong manifest.
- [lab](<../../docs/operations/BACKTEST_LAB.md>), mục `Chế độ batch hiện có`; chưa commit hoặc đang sửa; xem SHA trong manifest.
- [lab-review](<../../docs/reviews/BACKTEST_LAB_2026_10_27.md>), mục `Author verification on final code`; đã tracked ở snapshot; xem SHA trong manifest.
- [method-search](<../../docs/research/2026-10-16-method-search.md>), mục `Result of the frozen candidate`; đã tracked ở snapshot; xem SHA trong manifest.
- [pair-adr](<../../docs/decisions/0015-eth-btc-cointegration-v1.md>), mục `Decision`; đã tracked ở snapshot; xem SHA trong manifest.
- [pair-report](<../../docs/reports-vi/2026-10-22-eth-btc-cointegration-v1.md>), mục `Kết quả cả 12 kịch bản`; đã tracked ở snapshot; xem SHA trong manifest.
- [pair-ops](<../../docs/operations/ETH_BTC_COINTEGRATION.md>), mục `Reproduce`; đã tracked ở snapshot; xem SHA trong manifest.
- [orb](<../../docs/research/crypto-orb-portfolio.md>), mục `Execution and input limits`; chưa commit hoặc đang sửa; xem SHA trong manifest.
- [broker](<../../src/execution/paper_broker.py>), mục `PaperBroker`; chưa commit hoặc đang sửa; xem SHA trong manifest.

## Nghiên cứu repo ngoài đã nhập

- [quantdinger-review](<../../docs/research/external-repos/quantdinger/DANH_GIA_QUANTDINGER.md>), mục `Kết luận`; bản sao báo cáo được giữ nguyên bytes, khảo sát 2026-10-23, nhập 2026-10-29; chưa tracked, chưa kiểm chứng thực thi/lợi nhuận. SHA trong manifest.
- [tradingagents-review](<../../docs/research/external-repos/tradingagents/DANH_GIA_TRADINGAGENTS.md>), mục `Kết luận`; bản sao báo cáo được giữ nguyên bytes, khảo sát 2026-10-29, nhập 2026-10-29; chưa tracked, chưa kiểm chứng thực thi/lợi nhuận. SHA trong manifest.
- [tradingagents-paper-review](<../../docs/research/external-repos/tradingagents/BAO_CAO_BANG_CHUNG.md>), mục `Kết quả tác giả công bố`; bản sao báo cáo được giữ nguyên bytes, khảo sát 2026-10-29, nhập 2026-10-29; chưa tracked, chưa kiểm chứng thực thi/lợi nhuận. SHA trong manifest.

## Đọc lại nguồn khi tích hợp main

Ngày 29/10/2026 đã đối chiếu state/planner với main 65960bf và các mục lịch sử đã dẫn; đọc broker sau hợp nhất để kiểm guard thời gian và phase barrier; pair-ops đổi hướng dẫn --append-ledger sang từ chối sớm theo governance. Các thay đổi không thay kết luận kinh tế trong wiki. Manifest lưu previous_versions của bốn nguồn; đây là tác giả rà soát nguồn, không nâng mức kiểm chứng hay coi các công bố cũ trên main đã được nghiệm thu lại.

## Đọc lại đặc tả ngày 30/10/2026

Đã đọc phần U1–U7 mới từ main 460ed37; baseline kỹ thuật được giữ lịch sử. Thẩm quyền, paper-only, dữ liệu thật/giả lập và phân biệt software/protocol/economic verdict không cho phép tự mở gate hoặc nâng mức kiểm chứng. Các mô tả chưa tích hợp trong nguồn là snapshot 65960bf; trạng thái tích hợp mới xem docs/reviews/MAIN_INTEGRATION_2026_10_29.md từ package.
