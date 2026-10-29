<!-- wiki-meta {"id": "eth-btc", "type": "strategies", "title": "ETH/BTC cointegration: v1 thất bại sau chi phí", "updated_at": "2026-10-29", "source_ids": ["pair-adr", "pair-report", "pair-ops"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# ETH/BTC cointegration: v1 thất bại sau chi phí

Luận điểm: hội tụ giá ETH trên BTC với mô hình weekly Engle–Granger cố định, vốn chung; funding dương không phải nguồn lợi nhuận luận điểm. Hai tài khoản actual và no-positive được chạy riêng.

Báo cáo: 2021–2023 có một cặp hoàn tất bị lỗ; 2024–09/2026 không có tín hiệu. Baseline actual -24,615088 USDT; no-positive -24,758711 USDT. Kịch bản cost2 từ chối tín hiệu duy nhất do hedge rounding, không phải bằng chứng chịu chi phí.

Kết luận tác giả: chưa đủ bằng chứng lợi thế, v1 thất bại sau chi phí trong giai đoạn có giao dịch. Review mã không đồng nghĩa nghiệm thu kinh tế. Không tự đổi ngưỡng/cặp/leverage. Xem [[pair-v1-2026-10-22]] và [[execution-limits]].

## Nguồn

- [pair-adr](<../../docs/decisions/0015-eth-btc-cointegration-v1.md>), mục `Decision`; đã tracked ở snapshot; xem SHA trong manifest.
- [pair-report](<../../docs/reports-vi/2026-10-22-eth-btc-cointegration-v1.md>), mục `Kết quả cả 12 kịch bản`; đã tracked ở snapshot; xem SHA trong manifest.
- [pair-ops](<../../docs/operations/ETH_BTC_COINTEGRATION.md>), mục `Reproduce`; đã tracked ở snapshot; xem SHA trong manifest.

## Tái hiện trên main sau tích hợp

Hướng dẫn pair-ops đã được đối chiếu: không dùng --append-ledger. Cờ cũ bị từ chối trước đọc dữ liệu/chạy replay vì quy tắc preregistration hiện hành. Không đổi kết luận hay số liệu hồi cứu ở trên.
