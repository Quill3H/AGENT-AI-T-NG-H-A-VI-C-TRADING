<!-- wiki-meta {"id": "external-tradingagents", "type": "reference", "title": "TradingAgents: trợ lý phân tích, chưa phải engine futures", "updated_at": "2026-10-29", "source_ids": ["tradingagents-review", "tradingagents-paper-review"], "page_ids": [], "verification": "AUTHOR_REPORTED"} -->

# TradingAgents: trợ lý phân tích, chưa phải engine futures

Khảo sát 29/10/2026 tại commit `c4544913a14ed3df5f1ed7b9e8483270ce20682a` (v0.7.1). Đọc tài liệu/mã và bài nghiên cứu, chưa tự chạy repo, gọi LLM trả phí hoặc xác nhận hiệu quả kinh tế.

## Có thể học

Analyst tách vai trò, phản biện Bull/Bear, schema đầu ra, snapshot số liệu và khóa ngày trong công cụ. Memory chỉ dùng bài học đã biết tại ngày phân tích; đó là đưa văn bản vào prompt, không phải huấn luyện RL. Giới hạn vòng tool/debate và tách mô hình nhanh/sâu hỗ trợ kiểm soát chi phí.

## Giới hạn

Backtest hiện tại chấm từng nhận định ticker/ngày độc lập, không có mô phỏng danh mục nối tiếp bằng lượng khớp/giá khớp/sổ tiền. Stop-loss trong đề xuất có thể trống; sizing là hướng dẫn văn bản. Crypto mode BTC/ETH không tương đương Binance perpetual có funding/thanh lý/OI/CVD. Sell không tự động có nghĩa mở SHORT futures.

LLM và feed tin tức thay đổi khiến khó tái lập. Khóa ngày công cụ không loại trừ tri thức tương lai trong trọng số mô hình. Paper v7 thử cổ phiếu giai đoạn 01/01–29/03/2024; số lợi nhuận là tác giả báo, chưa tái lập độc lập và chưa xác nhận đủ giả định chi phí. Paper năm 2025 không phải kết quả kiểm chứng release tháng 10/2026.

## Ứng dụng đề xuất

Nếu có yêu cầu thử tiếp, dùng lớp tin tức/vĩ mô và phản biện chạy ngoài engine; lưu input, output, nguồn, thời điểm biết được và chi phí. So với đối chứng không LLM trên paper forward sau khi khóa thiết kế. Không để rating AI ghi đè hard risk rules. Xem [[external-comparison]], [[evidence-standard]].

## Nguồn

- [tradingagents-review](<../../docs/research/external-repos/tradingagents/DANH_GIA_TRADINGAGENTS.md>), mục 2–8; liên kết mã nguồn neo commit trong báo cáo.
- [tradingagents-paper-review](<../../docs/research/external-repos/tradingagents/BAO_CAO_BANG_CHUNG.md>), mục 2–5; báo cáo phân biệt paper/current code và các giới hạn tái lập.
