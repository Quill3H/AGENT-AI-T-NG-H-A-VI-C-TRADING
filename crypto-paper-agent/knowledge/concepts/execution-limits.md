<!-- wiki-meta {"id": "execution-limits", "type": "concepts", "title": "Giới hạn mô phỏng và khả năng khớp", "updated_at": "2026-10-30", "source_ids": ["orb", "pair-report", "broker", "repair-review"], "verification": "AUTHOR_REPORTED", "page_ids": []} -->

# Giới hạn mô phỏng và khả năng khớp

Nguồn ORB ở commit 05a396f mô tả OHLC approximation, không tái tạo queue/spread/partial fills, lot step/minimum notional và bộ lọc sàn lịch sử. Tick increment suy từ opening range là giả định, không phải exchange tick đã xác minh.

Báo cáo ETH/BTC cũng công bố exchange metadata hiện tại dùng như giả định lịch sử, và trade-bar open là proxy cho funding mark. Không áp kết quả cặp có kiểm lot sang mọi runner khác.

Đã đối chiếu broker 05a396f với main 65960bf và bản hợp nhất: giữ các guard thời gian đơn điệu, ghi cashflow và thay snapshot cùng timestamp của main; thêm barrier giữa các pha cho process_batch. Các caller vẫn dùng process_candle tuần tự không tự được chuyển sang batch. Review/test tích hợp không xác minh lợi nhuận hay lịch sử khớp lệnh. Xem [[orb-fvg]] và [[eth-btc]].

## Đọc lại broker ngày 30/10/2026

Đã đọc lại mã và review bản sửa: process_candle chuyển qua batch một phần tử,
preflight từ chối nến chồng lấn; lock chặn entry ngay nhưng peer flatten chờ đúng
barrier, giữ funding/open marks và stop đã chạm. Runner tổng hợp nay dùng batch
đồng bộ. Giữ giới hạn full-fill/OHLC, lot/tick và khả năng khớp chưa xác minh;
fork/recovery và funding mô phỏng không biến broker thành venue execution thật.
Xem [[synthesized-repair]] và báo cáo repair-review trong manifest. Đoạn mô tả
05a396f/65960bf phía trên là lịch sử trước lần sửa này.

## Nguồn

- [orb](<../../docs/research/crypto-orb-portfolio.md>), mục `Execution and input limits`; chưa commit hoặc đang sửa; xem SHA trong manifest.
- [pair-report](<../../docs/reports-vi/2026-10-22-eth-btc-cointegration-v1.md>), mục `Kết quả cả 12 kịch bản`; đã tracked ở snapshot; xem SHA trong manifest.
- [broker](<../../src/execution/paper_broker.py>), mục `PaperBroker`; chưa commit hoặc đang sửa; xem SHA trong manifest.

- [repair-review](../../docs/reviews/CAUSAL_RECOVERY_EVIDENCE_REPAIR_2026_10_30.md), các mục correction, implemented behavior và verification.
