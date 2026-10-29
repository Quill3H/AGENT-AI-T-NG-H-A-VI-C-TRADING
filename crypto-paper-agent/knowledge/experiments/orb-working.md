<!-- wiki-meta {"id": "orb-working", "type": "experiments", "title": "Thí nghiệm ORB: trạng thái chưa xác minh", "updated_at": "2026-10-29", "source_ids": ["orb"], "verification": "NOT_VERIFIED", "page_ids": []} -->

# Thí nghiệm ORB: trạng thái chưa xác minh

Nguồn rulebook đang untracked/dirty, chưa có code commit khóa thí nghiệm được xác nhận trong wiki. Hash rulebook ở manifest chỉ cố định bản đã đọc. Không có performance metrics hoặc verdict được nhập.

Trước chạy: xác định frozen config, code identity cả dirty bytes, universe, window, chi phí, target đủ mẫu và audit dữ liệu. Sau chạy: ghi đầy đủ rejections/trades/cost2x và tách partial windows. Không xóa thất bại hoặc tối ưu để đủ số lệnh. Xem [[orb-fvg]] và [[experiment-register]].

## Nguồn

- [orb](<../../docs/research/crypto-orb-portfolio.md>), mục `Execution and input limits`; chưa commit hoặc đang sửa; xem SHA trong manifest.
