<!-- wiki-meta {"id": "external-quantdinger", "type": "reference", "title": "QuantDinger: tham khảo công cụ nghiên cứu", "updated_at": "2026-10-29", "source_ids": ["quantdinger-review"], "page_ids": [], "verification": "AUTHOR_REPORTED"} -->

# QuantDinger: tham khảo công cụ nghiên cứu

Khảo sát 23/10/2026, commit upstream `8c993764ada17e7b2299ec5f0fbb7eac1a508dca`. Đây là ảnh chụp nghiên cứu lịch sử; lượt nhập wiki 29/10 không xác nhận upstream vẫn như cũ. Chỉ đọc tài liệu và các đường mã quan trọng, chưa cài chạy hoặc tái lập hiệu quả.

## Có thể học

Quản lý phiên bản và thí nghiệm, walk-forward/holdout, stress phí/slippage, thống kê PBO/Deflated Sharpe/bootstrap; phân quyền agent, idempotency và audit log. Mỗi phần cần đối chiếu với chức năng dự án đã có trước khi đề xuất bổ sung.

## Giới hạn đã ghi nhận

Backtest Strategy API V2 ghi fundingMode = not_modeled. Đường thanh lý đã đọc xử lý khi equity <= 0, chưa tương đương maintenance margin theo bậc/mark price Binance. Bộ lọc AI có chính sách fail-open khi provider không dùng được. Backend và frontend có giấy phép khác nhau. Không suy việc có live funding reconciliation thành backtest đã hạch toán funding.

## Đối với dự án

Giữ engine/risk hiện có; không dùng repo này thay bộ kiểm chứng funding carry trước khi giải quyết khoảng thiếu và đối soát. Đây là nhận định nghiên cứu, chưa phải quyết định triển khai hoặc kết luận engine hiện tại đã đúng. Xem [[external-comparison]] và [[execution-limits]].

## Nguồn

[quantdinger-review](<../../docs/research/external-repos/quantdinger/DANH_GIA_QUANTDINGER.md>), mục Kết luận, ma trận phù hợp và các điểm kiểm tra sâu. Báo cáo chứa liên kết mã upstream neo commit. SHA-256 và bản gốc nhập trong manifest.
