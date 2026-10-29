# ETH–BTC cointegration v1 — kết quả hồi cứu ngày 22/10/2026

**Kết luận: chưa đủ bằng chứng về lợi thế; v1 thất bại sau chi phí trong giai đoạn có giao dịch.** 2021–2023 chỉ có một cặp hoàn tất và bị lỗ. 01/2024–30/09/2026 không có tín hiệu vào lệnh. Không đạt mục tiêu tìm được phương pháp sinh lời; không thay ngưỡng, tìm cặp khác hoặc tăng đòn bẩy để cải thiện kết quả.

Báo cáo do người triển khai chạy: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED về hiệu quả kinh tế. Rà soát mã độc lập đã hoàn tất trong phạm vi bên dưới; không đồng nghĩa nghiệm thu toàn dự án.

## 1. Phiên bản, dữ liệu và phạm vi

- Nhánh gốc `claude/project-thread-uiqlsn`, SHA `a3a1681c4762a88bfa2dc9adced07be64f4f6ee6`; mã chạy cuối `dc418d307aae987874415676d84ff5eb5728c259`.
- Đã đối chiếu phương pháp cũ: `src/strategies/pairs.py` chọn cặp theo khoảng cách giá chuẩn hóa; v1 bổ sung Engle–Granger cố định ETH trên BTC, I(1), AR(1)/half-life và một tài khoản chung vốn.
- 438 ZIP Binance Vision khớp SHA-256 với CHECKSUM chính thức, ETH/BTC perpetual, 4h/15m/funding từ 09/2020 đến 09/2026. Mỗi đồng có 213.216 nến 15m, 13.326 nến 4h và 6.663 sự kiện funding.
- Đủ lịch sử khởi tạo 90 ngày trước tuần đầu. Tín hiệu 4h được ghép từ đúng 16 nến 15m liên tục đã đóng. Thiếu nến hoặc funding thì dừng, không điền giả.
- Hai giai đoạn là hồi cứu trên dữ liệu dự án đã xem; không gọi là dữ liệu mới hoặc kiểm chứng cuối cùng.
- Mỗi kịch bản bắt đầu độc lập 10.000 USDT, tổng notional tối đa equity, ký quỹ 1x; một cặp có chung vốn và một mã vòng đời.

## 2. Kết quả cả 12 kịch bản

Funding “đầy đủ” ghi nhận thực tế; “không nhận” bỏ từng khoản dương nhưng vẫn trả từng khoản âm. Hai tài khoản tự tính lại vốn, khối lượng và bộ ngắt. Chậm chân BTC = một nến 15 phút.

| Giai đoạn | Funding | Chi phí | BTC chậm | Vốn cuối USDT | Lãi/lỗ USDT | Lãi/lỗ % | Sụt vốn % | Cặp |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2021-2023 | đầy đủ | 1x | 0 | 9975.384912 | -24.615088 | -0.246151 | 0.256826 | 1 |
| 2021-2023 | không nhận | 1x | 0 | 9975.241289 | -24.758711 | -0.247587 | 0.258262 | 1 |
| 2021-2023 | đầy đủ | 2x | 0 | 10000.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |
| 2021-2023 | không nhận | 2x | 0 | 10000.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |
| 2021-2023 | đầy đủ | 1x | 1 | 9975.185252 | -24.814748 | -0.248147 | 0.256831 | 1 |
| 2021-2023 | không nhận | 1x | 1 | 9975.041629 | -24.958371 | -0.249584 | 0.258267 | 1 |
| 2024-2026 | đầy đủ | 1x | 0 | 10000.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |
| 2024-2026 | không nhận | 1x | 0 | 10000.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |
| 2024-2026 | đầy đủ | 2x | 0 | 10000.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |
| 2024-2026 | không nhận | 2x | 0 | 10000.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |
| 2024-2026 | đầy đủ | 1x | 1 | 10000.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |
| 2024-2026 | không nhận | 1x | 1 | 10000.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |

Không có cặp nào còn mở cuối kỳ. Các tài khoản không nhận funding đều chưa tạo lợi nhuận. Kịch bản chi phí gấp đôi không có lệnh được nhận; số 0 không phải bằng chứng chiến lược chịu được chi phí cao.

## 3. Tuần kiểm định, tín hiệu và lý do từ chối

| Giai đoạn | Tuần xét | Tuần đạt | Tín hiệu mỗi kịch bản | Loại tuần thống kê | Mô hình không hợp lệ |
|---|---:|---:|---:|---:|---:|
| 2021-2023 | 157 | 1 | 1 | 150 | 6 |
| 2024-2026 | 144 | 5 | 0 | 138 | 1 |

Lý do từ chối vào lệnh theo kịch bản:

- `2021-2023-actual-cost2-delay0`: HEDGE_ROUNDING_ERROR = 1.
- `2021-2023-no_positive-cost2-delay0`: HEDGE_ROUNDING_ERROR = 1.

Các kịch bản khác không có lệnh bị từ chối; giai đoạn 2024–2026 không phát tín hiệu. Không cộng 12 lượt chạy thành 12 bộ bằng chứng độc lập; chúng dùng cùng lịch sử.

## 4. Phân rã lãi/lỗ

Lợi nhuận giá dưới đây chưa trừ trượt giá; phí và trượt giá là số tiền chi phí dương. Lãi/lỗ ròng = giá − phí − trượt giá + funding đã ghi nhận. Đơn vị USDT.

| Kịch bản 2021–2023 | Giá | Phí | Trượt giá | Funding | Bỏ funding dương | Ròng |
|---|---:|---:|---:|---:|---:|---:|
| actual-cost1-delay0 | -22.820923 | 1.182597 | 0.709556 | 0.097989 | 0.000000 | -24.615088 |
| no_positive-cost1-delay0 | -22.820923 | 1.182597 | 0.709556 | -0.045634 | 0.143623 | -24.758711 |
| actual-cost2-delay0 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| no_positive-cost2-delay0 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| actual-cost1-delay1 | -23.020423 | 1.182697 | 0.709616 | 0.097989 | 0.000000 | -24.814748 |
| no_positive-cost1-delay1 | -23.020423 | 1.182697 | 0.709616 | -0.045634 | 0.143623 | -24.958371 |

Toàn bộ khoản trên bằng 0 trong 2024–2026. Sai số đối chiếu vốn với cashflow trong cả 12 kịch bản dưới 0,000001 USDT.

## 5. Kết quả từng năm và tập trung lợi nhuận

| Kịch bản | 2021 % | 2022 % | 2023 % | 2024 % | 2025 % | 01–09/2026 % |
|---|---:|---:|---:|---:|---:|---:|
| actual, 1x, chậm 0 | 0.000000 | 0.000000 | -0.246151 | 0.000000 | 0.000000 | 0.000000 |
| no_positive, 1x, chậm 0 | 0.000000 | 0.000000 | -0.247587 | 0.000000 | 0.000000 | 0.000000 |
| actual, 2x, chậm 0 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| no_positive, 2x, chậm 0 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| actual, 1x, chậm 1 | 0.000000 | 0.000000 | -0.248147 | 0.000000 | 0.000000 | 0.000000 |
| no_positive, 1x, chậm 1 | 0.000000 | 0.000000 | -0.249584 | 0.000000 | 0.000000 | 0.000000 |

Các năm sau 2023 thuộc tài khoản khởi đầu lại 10.000 USDT ở 01/2024, không phải nối vốn từ tài khoản trước. Không có cặp thắng; tỷ trọng lợi nhuận của một/hai cặp thắng lớn không xác định. Toàn bộ lỗ giao dịch của mỗi kịch bản có lệnh đến từ duy nhất một cặp, nên không thể suy ra tính ổn định.

Ở kịch bản chuẩn, tín hiệu 13/04/2023 12:00 UTC khớp lúc 12:15 UTC: short 0,357 ETH, long 0,015 BTC. Chân ETH chạm stop và đóng BTC ở giá mở khả dụng kế tiếp; cặp kết thúc 14/04/2023 00:45 UTC, giữ 12,5 giờ. Chi tiết khớp, funding, model_id và nguyên nhân thoát trong trade-audit.json.

## 6. Kiểm tra và giới hạn

- Bộ kiểm thử mới: 44 đạt; toàn bộ ngoại tuyến trên mã khóa: 686 đạt, 4 bỏ qua, 5 kiểm thử mạng không chạy. Có hồi quy kiểm tra mô hình tổng hợp, không đồng liên kết, thay đổi tương lai, hai chiều, làm tròn, thiếu vốn, lỗi/chậm một chân, kế toán tính tay, stop, tái ước lượng tuần, giữ lệnh và thiếu dữ liệu.
- Rà soát độc lập sửa bốn vấn đề trước khi khóa mã: sở hữu lệnh thoát cũ; tính nhầm cặp mở dở vào mẫu hoàn tất; trễ giới hạn giữ lệnh; vốn tại biên năm. Người rà soát chạy riêng 24 kiểm thử và không còn P1/P2 trong phạm vi mã đã xem.
- Bộ rủi ro hiện hành được tái sử dụng; không nới giới hạn để tạo lệnh. Stop có thể lỗ vượt ngân sách khi gap hoặc chân còn lại đóng chậm.
- Lot hiện tại lấy từ exchangeInfo ngày 22/10/2026 là giả định cho lịch sử, chưa tái dựng filter/bracket theo từng ngày. Chặn lệch hedge do làm tròn >1% tổng notional là quy tắc thận trọng đã ghi trước khi xem kết quả; ở chi phí 2x, nó loại tín hiệu duy nhất.
- Funding dùng giá mở nến thanh toán làm xấp xỉ giá mark; sự kiện trễ không quá 1 giây được đưa về mốc danh nghĩa theo ADR0013 và giữ timestamp nguồn. Vì vậy “funding thực tế” là rate/lịch thanh toán từ nguồn thật, còn giá trị tiền vẫn có xấp xỉ giá.
- Nến 15 phút không cho biết thứ tự đường giá trong nến hay thanh khoản sổ lệnh. Stop có nhãn cuối nến; giá khớp là giả định có trượt giá, không phải bằng chứng khớp thực tế.
- Mốc 30 cặp chỉ là ngưỡng tối thiểu gắn nhãn ít mẫu của báo cáo, không phải kiểm định ý nghĩa thống kê. Với 0–1 cặp, kết luận phải là “chưa đủ bằng chứng”. Riêng kết quả đã quan sát bị lỗ sau chi phí nên ghi nhận thất bại v1 trong giai đoạn có lệnh.

## 7. Tái lập và bàn giao

Hướng dẫn và câu lệnh: [ETH_BTC_COINTEGRATION.md](../operations/ETH_BTC_COINTEGRATION.md). Hồ sơ: [manifest](../reviews/evidence/eth-btc-2026-10-22/manifest.json), [tóm tắt 12 kịch bản](../reviews/evidence/eth-btc-2026-10-22/summary.json), [khớp lệnh và funding](../reviews/evidence/eth-btc-2026-10-22/trade-audit.json), [mô hình tuần](../reviews/evidence/eth-btc-2026-10-22/weekly-models.json).

Nguồn thô, Parquet và chuỗi vốn đầy đủ được giữ cục bộ dưới market-data/ và artifacts/eth-btc-v1-final/; không đưa các tệp lớn vào Git. Manifest lưu mã băm của đầu vào, mã chạy, cấu hình, phiên bản thư viện và toàn bộ đầu ra. Nhật ký nghiên cứu ghi đủ 12 lượt là retrospective. Đây là bàn giao mã và kết quả thử nghiệm, không phải chỉ dẫn giao dịch tiền thật.
