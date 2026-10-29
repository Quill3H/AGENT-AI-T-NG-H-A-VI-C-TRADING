<!-- wiki-meta {"id": "execution-limits", "type": "concepts", "title": "Giới hạn mô phỏng và khả năng khớp", "updated_at": "2026-10-29", "source_ids": ["orb", "pair-report", "broker"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Giới hạn mô phỏng và khả năng khớp

Nguồn ORB hiện đang chưa commit mô tả OHLC approximation, không tái tạo queue/spread/partial fills, lot step/minimum notional và bộ lọc sàn lịch sử. Tick increment suy từ opening range là giả định, không phải exchange tick đã xác minh.

Báo cáo ETH/BTC cũng công bố exchange metadata hiện tại dùng như giả định lịch sử, và trade-bar open là proxy cho funding mark. Không áp kết quả cặp có kiểm lot sang mọi runner khác.

Mã broker đang dirty: sự hiện diện của hàm không đồng nghĩa kiểm chứng thực thi. Trước kết luận khả năng giao dịch cần review/test độc lập trên đúng snapshot. Xem [[orb-fvg]] và [[eth-btc]].

## Nguồn

- [orb](<../../docs/research/crypto-orb-portfolio.md>), mục `Execution and input limits`; chưa commit hoặc đang sửa; xem SHA trong manifest.
- [pair-report](<../../docs/reports-vi/2026-10-22-eth-btc-cointegration-v1.md>), mục `Kết quả cả 12 kịch bản`; đã tracked ở snapshot; xem SHA trong manifest.
- [broker](<../../src/execution/paper_broker.py>), mục `PaperBroker`; chưa commit hoặc đang sửa; xem SHA trong manifest.
