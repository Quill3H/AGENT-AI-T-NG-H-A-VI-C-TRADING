# Đánh giá QuantDinger cho dự án AGENT AI TỰ ĐỘNG HÓA VIỆC TRADING

Ngày nghiên cứu: 23/10/2026. Commit QuantDinger được đọc trực tiếp: 8c993764ada17e7b2299ec5f0fbb7eac1a508dca.

## Kết luận

Phù hợp để tham khảo hoặc thử riêng các công cụ nghiên cứu chiến lược, quản lý thí nghiệm và truy cập qua agent. Chưa phù hợp để thay toàn bộ crypto-paper-agent, đặc biệt với futures và funding carry. Đây là đánh giá mức độ phù hợp qua tài liệu và các đường mã nguồn quan trọng; chưa cài chạy, benchmark, hoặc kiểm toán toàn repo.

## Cơ sở đối chiếu của dự án

Đã đọc trực tiếp:
- sources/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md, mục 1–4: chạy local, paper-only, dữ liệu Binance public; funding, thanh lý, OI/CVD; quản trị rủi ro cứng; tái lập kết quả và không dùng dữ liệu tương lai.
- eth-btc-research/crypto-paper-agent/README.md.
- eth-btc-research/crypto-paper-agent/docs/research/2026-10-16-method-search.md: có hướng funding carry, nhưng báo cáo ghi AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Nghiên cứu này không xác nhận lại lợi nhuận hoặc trạng thái nghiệm thu.
- Các handover hiện có chỉ dùng làm bối cảnh; không xác nhận đây là HEAD hiện tại của repo người dùng.

## Ma trận phù hợp

| Nhu cầu | Bằng chứng QuantDinger | Đánh giá |
|---|---|---|
| Chiến lược Python, nhiều tài sản, nhiều khung thời gian | Strategy API V2, manifest, initialize/handle_data, dữ liệu nến đóng | Có khả năng đáp ứng; cần chuyển chiến lược sang hợp đồng API của họ |
| Funding futures/carry | service.py ghi fundingMode: not_modeled; hướng dẫn backtest xác nhận chưa mô hình hóa funding payments | Khoảng thiếu quyết định khi muốn thay engine |
| Thanh lý phù hợp sàn | runtime.py liquidate_if_insolvent chỉ kích hoạt khi equity <= 0, dùng close và hấp thụ thiếu hụt cuối cùng | Không thể coi là tương đương mô hình thanh lý theo maintenance margin/tier của Binance |
| OI, CVD, taker-buy volume và nguồn dữ liệu hiện có | Chưa xác nhận đầy đủ hợp đồng dữ liệu này ở các đường đã đọc | Cần kiểm tra adapter và kiểm thử dữ liệu trước khi chuyển |
| Hard risk rules riêng | Có protection/risk và kiểm soát agent; chưa xác nhận tương đương toàn bộ invariants dự án | Phải ánh xạ từng rule và đối soát, không suy từ tên tính năng |
| Chống overfit | Có mã walk-forward, thống kê PBO, Deflated Sharpe, bootstrap Monte Carlo | Đáng học hỏi; sự tồn tại của mã không xác nhận độ đúng hoặc hiệu quả |
| Agent/API | Token theo scope, paper-only restrictions, idempotency, job và source versions | Hữu ích nếu cần tự động hóa vòng nghiên cứu |
| Chạy cá nhân đơn giản | PostgreSQL, Kafka, hai Redis, nhiều worker và Docker Compose | Gánh vận hành lớn hơn Python/Parquet/SQLite hiện tại |
| Giao diện có thể tự sửa/phân phối | Web/mobile ở repo riêng; frontend dùng Source-Available License | Không áp dụng mặc định Apache 2.0 của backend cho toàn sản phẩm |

## Các điểm kiểm tra sâu

### Funding

backend_api_python/app/services/strategy_v2/service.py:443–459 xuất executionAssumptions, bao gồm fundingMode = not_modeled. docs/product/BACKTEST_CENTER.md và docs/trading/STRATEGY_DEV_GUIDE.md nói rõ funding payments chưa được mô hình hóa trong Strategy API V2 backtests.

Điều này khác với live funding reconciliation: có file xử lý funding live không có nghĩa backtest hạch toán funding. Một chiến lược kiếm tiền chủ yếu từ funding không thể được đánh giá đầy đủ bằng PnL bỏ qua khoản này.

### Thanh lý

backend_api_python/app/services/strategy_v2/runtime.py:1089–1135:
- mark_to_market;
- nếu equity > 0 thì không thanh lý;
- nếu không, đóng vị thế tại giá close có fallback;
- hấp thụ thiếu hụt còn lại để equity không âm và đánh dấu bankrupt.

Đây là đường mô phỏng phá sản tài khoản đã kiểm tra, không phải bằng chứng có đầy đủ maintenance margin theo bậc, mark-price liquidation và cơ chế intrabar của sàn. Không nên gọi kết quả này tương đương engine riêng trước khi đối soát.

### Cổng quyết định AI

backend_api_python/app/services/ai_decision_filter.py cho phép entry tiếp tục khi không có provider/không dùng được provider. tests/test_ai_decision_filter.py:491–518 kiểm tra allowed == True sau lỗi provider.

Đây là chính sách có chủ đích, không tự động là lỗi. Nhưng nếu dự án yêu cầu AI duyệt bắt buộc thì chính sách này không đáp ứng. Cần phân biệt lớp AI tùy chọn với hard risk rules xác định.

### Giấy phép

README tại commit khảo sát phân biệt:
- backend: Apache 2.0;
- frontend web và mobile: repo riêng và giấy phép riêng;
- tên, logo, branding: quy định riêng.

LICENSE của QuantDinger-Vue được đọc từ main ngày khảo sát: cho phép nghiên cứu/thử nghiệm phi thương mại theo điều kiện; Commercial Use yêu cầu giấy phép riêng và phải giữ branding. Không mặc định rằng giao dịch vì lợi nhuận hoặc phát hành sản phẩm đều nằm trong phạm vi miễn phí. Đây là ghi nhận điều khoản, không phải kết luận pháp lý cho mô hình sử dụng cụ thể.

## Cách sử dụng phù hợp

1. Giữ crypto-paper-agent làm bộ máy nghiên cứu và đối soát theo spec hiện có; không ngụ ý engine hiện tại đã được nghiệm thu.
2. Ưu tiên học cách tổ chức walk-forward/holdout, stress chi phí và lưu lịch sử thử nghiệm.
3. Nếu cần thử ứng dụng, dựng riêng, dùng mô phỏng/signal, không đưa khóa giao dịch vào thử nghiệm.
4. Bắt đầu bằng một chiến lược giá đơn giản trên cùng OHLCV, cùng phí/slippage và thời điểm khớp; so từng lệnh và equity.
5. Chỉ cân nhắc chuyển core sau khi xử lý funding, thanh lý, dữ liệu OI/CVD, hard rules và tái lập kết quả.
6. Chưa có bằng chứng API của họ nhập trực tiếp nguyên bộ báo cáo hiện tại; tích hợp dashboard có thể cần adapter hoặc giao diện riêng.

## Tín hiệu bảo trì và giới hạn

Commit khảo sát có Backend CI và Security CI thành công theo GitHub Actions được truy vấn. Chưa tự chạy test. Không lấy CI xanh làm bằng chứng chiến lược có lợi nhuận, không có lỗi, hoặc an toàn giao dịch thật.

VERSION tại commit ghi 5.6.1, trong khi trang releases khi khảo sát hiển thị v5.6.5. Vì vậy đánh giá neo vào commit cụ thể, không gọi đây là bản release v5.6.5.

## Nguồn

- [Commit khảo sát](https://github.com/OpenByteInc/QuantDinger/commit/8c993764ada17e7b2299ec5f0fbb7eac1a508dca)
- [README](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/README.md)
- [Backtest assumptions](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/backend_api_python/app/services/strategy_v2/service.py#L443-L459)
- [Mô phỏng thanh lý](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/backend_api_python/app/services/strategy_v2/runtime.py#L1089-L1135)
- [Backtest guide](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/docs/product/BACKTEST_CENTER.md)
- [Strategy API guide](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/docs/trading/STRATEGY_DEV_GUIDE.md)
- [Walk-forward](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/backend_api_python/app/services/strategy_evolution/walk_forward.py)
- [Robustness statistics](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/backend_api_python/app/services/strategy_evolution/statistics.py)
- [Agent Gateway](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/docs/agent/AGENT_QUICKSTART.md)
- [AI decision policy](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/backend_api_python/app/services/ai_decision_filter.py)
- [Frontend license](https://github.com/OpenByteInc/QuantDinger-Vue/blob/main/LICENSE)
- [Compose](https://github.com/OpenByteInc/QuantDinger/blob/8c993764ada17e7b2299ec5f0fbb7eac1a508dca/docker-compose.yml)
- [Backend CI](https://github.com/OpenByteInc/QuantDinger/actions/runs/39925809607)
- [Security CI](https://github.com/OpenByteInc/QuantDinger/actions/runs/39925809618)

