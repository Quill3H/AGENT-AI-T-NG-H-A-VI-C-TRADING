# Nghiên cứu repo ngoài

Các báo cáo được nhập nguyên bytes vào dự án ngày 29/10/2026 theo yêu cầu của chủ dự án. Không phải mã/thư viện đã tích hợp, không phải xác nhận hiệu quả.

- [QuantDinger — khảo sát 23/10/2026](quantdinger/DANH_GIA_QUANTDINGER.md)
- [TradingAgents — khảo sát 29/10/2026](tradingagents/DANH_GIA_TRADINGAGENTS.md)
- [TradingAgents — bằng chứng bài nghiên cứu](tradingagents/BAO_CAO_BANG_CHUNG.md)

Manifest nguồn và SHA-256 ở knowledge/manifests/sources.json (tính từ package). Giữ ngày khảo sát và upstream commit của từng báo cáo; ngày nhập không có nghĩa đã kiểm tra lại upstream. Những nhánh hoặc kết quả dự án được nhắc trong báo cáo là bối cảnh tại lúc nghiên cứu, không xác nhận HEAD hiện tại.

Wiki/manifest hiện nằm trong bản làm việc local và chưa thuộc gói công bố này. Ba liên kết báo cáo ở trên cùng phần tổng hợp dưới đây là bộ tài liệu độc lập có thể đọc trên GitHub.

## Đối chiếu và hướng tận dụng

| Nhu cầu | QuantDinger (khảo sát 23/10/2026) | TradingAgents (khảo sát 29/10/2026) | Hướng cho dự án |
| --- | --- | --- | --- |
| Nghiên cứu chiến lược | Quản lý thí nghiệm, walk-forward, stress chi phí | Analyst và phản biện có cấu trúc | Học từng cơ chế còn thiếu |
| Mô phỏng futures | Backtest chưa tính funding; mô hình thanh lý đã đọc còn đơn giản | Chấm rating, không có sổ tiền và danh mục nối tiếp | Giữ engine và kế toán riêng |
| Quản trị rủi ro | Chưa xác nhận tương đương hard rules; AI filter fail-open | SL tùy chọn và sizing bằng văn bản | Hard rules phải có quyền từ chối |
| Tái lập | Cần đối soát dữ liệu, code, cấu hình và ledger | LLM và feed văn bản thay đổi | Lưu snapshot, phân biệt hồi cứu và forward |
| Vận hành | Nhiều dịch vụ và worker | Nhiều lượt gọi LLM/công cụ | Chỉ bổ sung khi có nhu cầu và chi phí đã đo |

Ưu tiên khóa ngày/nguồn dữ liệu, lưu giả định và đầu ra có cấu trúc trước. Nếu cần thử LLM, bắt đầu bằng một analyst tin tức/vĩ mô và một lượt phản biện ở chế độ ghi nhận; so với đối chứng không LLM trên paper forward sau khi khóa thiết kế. Tính phí API, độ trễ, phí/slippage/funding, drawdown và thời gian hồi phục.

Đây là tổng hợp từ ba báo cáo, chưa phải ADR hay quyền triển khai mới. Nhiều agent đồng thuận không tạo nhiều nguồn bằng chứng độc lập. Không tự thay engine, risk, chiến lược hoặc kết luận nghiên cứu hiện có.
