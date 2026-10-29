<!-- wiki-meta {"id": "external-comparison", "type": "reference", "title": "Đối chiếu repo ngoài và phần có thể tận dụng", "updated_at": "2026-10-29", "source_ids": ["quantdinger-review", "tradingagents-review", "tradingagents-paper-review"], "page_ids": ["external-quantdinger", "external-tradingagents"], "verification": "AUTHOR_REPORTED"} -->

# Đối chiếu repo ngoài và phần có thể tận dụng

Hai nghiên cứu đã được nhập theo yêu cầu của chủ dự án. Việc nhập tài liệu không chấp nhận lợi nhuận, chọn chiến lược mới hoặc triển khai các repo ngoài.

| Nhu cầu | QuantDinger (khảo sát 23/10) | TradingAgents (khảo sát 29/10) | Hướng cho dự án |
| --- | --- | --- | --- |
| Nghiên cứu chiến lược | Quản lý thí nghiệm, walk-forward, stress chi phí | Analyst và tranh luận có cấu trúc | Học từng cơ chế còn thiếu |
| Mô phỏng futures | Thiếu funding trong backtest; thanh lý đã đọc còn đơn giản | Chấm rating; không có engine danh mục nối tiếp | Giữ bộ mô phỏng và kế toán riêng |
| Rủi ro | Chưa xác nhận tương đương hard rules, AI filter fail-open | Risk bằng lập luận; SL/sizing đề xuất chưa bắt buộc | Hard rules có quyền từ chối |
| Tái lập | Cần kiểm dữ liệu/code/config và ledger | LLM/text feeds không tất định | Lưu snapshot và phân biệt hồi cứu/forward |
| Vận hành | Nhiều dịch vụ và worker | Nhiều lượt LLM/tool | Không thêm hạ tầng khi chưa có nhu cầu đã đo |

## Thứ tự ưu tiên tham khảo

1. Khóa nguồn/ngày dữ liệu và lưu giả định/đầu ra để kiểm tra.
2. Bổ sung kiểm tra độ bền/đối chứng phù hợp nếu dự án còn thiếu; không dùng thống kê để thay bằng chứng giao dịch.
3. Chỉ khi được yêu cầu thử LLM: một analyst tin tức và một lượt phản biện, chạy chế độ ghi nhận. Đánh giá ngoài mẫu, phí API, latency, phí/slippage/funding, drawdown, underwater/recovery.
4. Chỉ tích hợp chức năng sau một phạm vi triển khai riêng. Không tự thay engine, risk, cấu hình hoặc kết luận NO_TRADES.

Nhiều agent đồng thuận không tạo nhiều nguồn chứng cứ độc lập. Kết quả paper/repo ngoài không nâng mức xác minh của nghiên cứu trong dự án. Đây là tổng hợp/đề xuất của người nghiên cứu, không phải ADR đã phê duyệt.

## Nguồn và hồ sơ

- [[external-quantdinger]]: [quantdinger-review](<../../docs/research/external-repos/quantdinger/DANH_GIA_QUANTDINGER.md>), mục ma trận và kết luận.
- [[external-tradingagents]]: [tradingagents-review](<../../docs/research/external-repos/tradingagents/DANH_GIA_TRADINGAGENTS.md>), mục 2–8; [tradingagents-paper-review](<../../docs/research/external-repos/tradingagents/BAO_CAO_BANG_CHUNG.md>), mục 2–6.
- Các báo cáo là nguồn nghiên cứu thứ cấp có trích primary sources; hash chỉ chứng minh bytes đúng bản nhập, không xác minh nội dung upstream hoặc hiệu quả kinh tế.
