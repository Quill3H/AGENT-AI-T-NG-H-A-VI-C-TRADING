# Trạng thái hiện tại — 29/10/2026

## Phạm vi và mức bằng chứng

Đây là **tổng hợp tài liệu và đối chiếu mã nguồn**, không chạy lại backtest/test suite và không nghiệm thu một gate. Snapshot main được đọc tại `65960bff7341637557d8158c2440dcc087ce1a41`; nhánh nghiên cứu cục bộ được đọc tại `05a396f` trước khi checkout thay đổi bởi công việc tích hợp đang diễn ra.

Không dùng câu “100% suite pass” để bao gồm các bài skipped/deselected hoặc để suy ra sinh lời. Không coi nhãn TESTER_VERIFIED do một báo cáo ghi sẵn là kết quả kiểm tra độc lập của lượt tài liệu này.

## 1. Năng lực đã có bằng chứng triển khai

| Thành phần | Hiện trạng ở snapshot main | Giới hạn |
| --- | --- | --- |
| Data / features | Public Binance, cache, feature và căn chỉnh nhiều timeframe | Coverage và provenance phải kiểm tra từng runner; không phải mọi đường nạp dữ liệu đều fail closed |
| Risk / PaperBroker | Sizing, stops, breaker, funding, ledger và force close | Phải áp dụng ADR theo scope; không suy một cấu hình thử nghiệm thành mặc định toàn dự án |
| Baseline | Trend, Breakout/Retest, SMC, Funding | Có mã không đồng nghĩa đã có kết quả thị trường đầy đủ/được nghiệm thu |
| PPO | Có triển khai train/evaluate/save/load và báo cáo smoke lịch sử | Chưa chứng minh chính sách có lợi thế kinh tế |
| SynthesizedStrategy | Regime 4h, tín hiệu 15m, funding filter, partial exits, runner đa coin | Báo cáo/config khác nhau; nguồn dữ liệu lần chạy chưa được xác minh |
| Nghiên cứu và đối chứng | Preregistration, ledger, matched random, drawdown/underwater, concentration | Công cụ không tự làm thí nghiệm hợp lệ nếu runner bỏ qua hợp đồng |
| Giao diện/báo cáo | Bộ sinh journal/report và dashboard trong hồ sơ | Artifact của lượt tổng hợp được chỉ tới đường dẫn máy khác, chưa có bytes trên main đã đọc |
| Backtest Lab / ETH–BTC / ORB / wiki | Có ở nhánh nghiên cứu cục bộ; không có trong cây main snapshot trên | Đang có công việc tích hợp; phải xác minh lại commit sau tích hợp |

## 2. Kết quả nghiên cứu cần giữ

| Hướng | Khoảng dữ liệu / mẫu | Kết quả trong nguồn | Diễn giải hiện tại |
| --- | --- | --- | --- |
| Funding carry | 2021–2025, 10 baskets | +28,25%; max DD 1,74%; riêng final check 2024–2025 +6,91%, 3 baskets | AUTHOR_REPORTED; mẫu nhỏ, lợi nhuận tập trung, 2021–2023 đã dùng chọn phương pháp |
| BTC OI reclaim v1 | Các cửa sổ W1/W2 của vòng 18 | W1 DATA_QUALITY_FAILED; W2 base/2x NO_TRADES | Không đủ bằng chứng; hai lệnh ở delay stress không biến thành ứng viên được chọn |
| ETH–BTC v1, nhánh riêng | 2021–2023: 1 cặp hoàn tất; 2024–09/2026: 0 tín hiệu | Actual -24,615088 USDT; no-positive-funding -24,758711 USDT | Hồi cứu trên dữ liệu đã xem; v1 thất bại sau chi phí trong khoảng có giao dịch |
| Crypto ORB/FVG, nhánh riêng | 10 coin, 09/2026, vốn 10.000 USD, tối đa 4 vị thế | Base: 1.140 lệnh, -3.315,11 USD, DD 33,59%, PF 0,350. Stress: 1.101 lệnh, -5.207,41 USD, DD 52,07%, PF 0,127 | Đạt mục tiêu số lệnh của đề cương nhưng lỗ; không phải OOS/forward mới |
| Synthesized 4h/15m trên main | Báo cáo cửa sổ 2025-01-01 → 2026-01-01, 10 coin | 6.455 lifecycles, 10.892 slices; WR 49,20%; 100.000 → 8.719,67 USDT | Khoảng -91,28% vốn theo số báo cáo; chưa xác minh dataset/artifact hoặc nghiệm thu kinh tế |

ORB dùng DOTUSDT; universe tổng hợp dùng SUIUSDT. Không gộp hai thí nghiệm thành cùng universe/cùng vốn. Mục tiêu ORB 60 lệnh/tuần, 240/tháng và mục tiêu tổng hợp ≥2.000/năm là yêu cầu cỡ mẫu riêng; không được ép giao dịch để đạt chúng.

Nguồn chính xác ở [EVIDENCE_REGISTER](EVIDENCE_REGISTER.md). Số liệu trong bảng là trích từ nguồn, chưa chạy lại trong lượt này.

## 3. Vấn đề cần giải quyết trước khi tin kết quả tổng hợp

1. **Provenance dữ liệu:** `UniverseDataLoader.load_symbol` có thể tạo synthetic khi cache thiếu hoặc network lỗi, rồi lưu vào cache cùng tuyến. Chưa có manifest chứng minh lượt 6.455 vị thế dùng dữ liệu thị trường thật. Không khẳng định nó chắc chắn là synthetic; trạng thái đúng là **NOT_VERIFIED**.
2. **Funding:** runner điền funding thiếu bằng 0,0001 và đặt readiness/time trên candle. Đây chưa phải bằng chứng sự kiện funding nguồn duy nhất. Dòng tiền funding nhỏ không chứng minh filter loại bỏ rủi ro funding.
3. **Đồng nhất phiên bản:** báo cáo ghi ADX 25 và exits 1,5R/60% + 2,5R/25%; YAML hiện ghi ADX 20, exits 1R/50% + 2R/25%. YAML vốn 50.000 nhưng CLI mặc định 100.000 và ghi đè config. Phải tìm config của chính lần chạy; chưa chọn một bên làm sự thật.
4. **Artifact và kiểm thử:** báo cáo nêu 536 passed, 2 skipped, 5 deselected; adversarial 11/11, E2E 20/20. Đây là kết quả được báo cáo; lượt này chưa tái hiện. Các đường dẫn artifact `file:///d:/...` không cung cấp bytes để đối soát trên GitHub.
5. **Giải thích thất bại:** gross price PnL cũng âm khoảng 46.319,86 USDT, phí khoảng 44.916,96 USDT. Vì vậy giảm phí không tự đủ để sinh lời. Maker fills cần mô hình khả năng khớp, queue, adverse selection và kiểm tra riêng; không chỉ đổi con số phí.

Các mục trên là phát hiện từ đối chiếu tài liệu/mã, không phải kết quả audit toàn bộ engine. Giữ nguyên báo cáo gốc để truy vết; không truyền tiếp các lời khẳng định quá mức của nó thành đặc tả hiện tại.

## 4. Điều chưa được chốt

- Không có nghiệm thu lợi thế kinh tế toàn dự án trong bộ nguồn đã đọc.
- Không xác nhận hoàn tất prospective paper, khả năng chạy bền hoặc mọi gate G0–G5.
- Không chọn Synthesized, ORB, carry hay PPO làm phương pháp chính chỉ từ bảng này.
- Các ngưỡng kinh tế và thời gian paper forward phải theo quyết định người dùng/hợp đồng gate, không tự lấy ví dụ trong tài liệu cũ.
- Nhánh cục bộ đang được tích hợp ở checkout dùng chung; SHA/dirty state có thể đổi. Trang này là checkpoint có ngày và commit, không phải theo dõi nền.
