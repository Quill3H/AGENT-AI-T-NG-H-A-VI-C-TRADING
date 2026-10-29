# TradingAgents — kiểm tra bằng chứng hiệu quả

Ngày: 29/10/2026. Phạm vi: bài nghiên cứu chính thức và cách tài liệu/mã hiện tại mô tả đánh giá. Không cài phần mềm, không chạy LLM hoặc tái lập kết quả.

## 1. Định danh nguồn

- Yijia Xiao, Edward Sun, Di Luo, Wei Wang. *TradingAgents: Multi-Agents LLM Financial Trading Framework*. arXiv:2412.20138, bản v7 ngày 03/06/2025; bản đầu 28/12/2024. [Metadata arXiv](https://arxiv.org/abs/2412.20138), [PDF v7](https://arxiv.org/pdf/2412.20138v7).
- Mã hiện tại được đọc ở commit `c4544913a14ed3df5f1ed7b9e8483270ce20682a`, merge phát hành v0.7.1 ngày 27/10/2026. Đây là mốc khác với bài nghiên cứu năm 2025. [Commit](https://github.com/TauricResearch/TradingAgents/commit/c4544913a14ed3df5f1ed7b9e8483270ce20682a).

## 2. Kết quả tác giả công bố — chưa xác minh độc lập

Bài v7 mô tả thử nghiệm 01/01–29/03/2024, tín hiệu theo ngày, so với Buy & Hold, MACD, KDJ+RSI, ZMR, SMA. Bảng 1 báo cáo:

| Mã | Lợi nhuận tích lũy | Sharpe | Drawdown tối đa |
|---|---:|---:|---:|
| AAPL | 26,62% | 8,21 | 0,91% |
| GOOGL | 24,36% | 6,39 | 1,69% |
| AMZN | 23,21% | 5,60 | 2,11% |

Chú thích cho biết mỗi dự đoán dùng 11 lượt LLM và hơn 20 lượt công cụ; chi phí tính toán giới hạn thử nghiệm trong ba tháng. Tác giả nói chỉ dùng dữ liệu sẵn có vào ngày quyết định. [PDF v7, mục 5, Bảng 1 và chú thích trang 12](https://arxiv.org/pdf/2412.20138v7#page=10).

**Nhận định:** đây là kết quả hồi cứu ngắn trên cổ phiếu, chưa chứng minh độ bền nhiều chế độ thị trường hoặc hiệu quả futures crypto. Nghiên cứu này chưa tự chạy lại số liệu.

## 3. Chi phí và tính có thể kiểm chứng

Không tìm thấy thông số commission/slippage/fee đủ rõ trong PDF v7 và phần mô tả mô phỏng/metrics đã đọc để xác nhận số liệu là lợi nhuận ròng sau chi phí giao dịch. Không diễn giải điều này thành bằng chứng chắc chắn phí bằng 0. Chú thích chỉ nêu lượng gọi mô hình/công cụ, không phải mức USD hiện nay hoặc chứng cứ đã trừ phí API vào PnL. [PDF v7, mục 5–6 và phụ lục metrics](https://arxiv.org/pdf/2412.20138v7).

Do đó không dùng headline lợi nhuận để cam kết lợi nhuận của bản cài hiện nay. Cần dữ liệu đầu vào đã lưu, toàn bộ quyết định, mô hình/prompt/version, quy tắc khớp và kế toán chi phí mới có thể đối soát kết quả.

## 4. Điểm giới hạn mà mã hiện tại thừa nhận

`tradingagents/backtest.py` tự xác định đây là đánh giá **chất lượng quyết định**, không phải mô phỏng danh mục. Mỗi ô ticker/ngày độc lập; không có đủ quantity, fill price, cash ledger; portfolio nếu truyền vào là cùng một danh mục đứng yên, không phải vị thế chạy nối tiếp. [backtest.py, dòng 1–14](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/backtest.py#L1-L14).

Phần render kết quả còn ghi chỉ lấy một mẫu LLM cho mỗi ô và không lưu trữ nguyên bản các nguồn văn bản, nên số liệu chỉ mang tính chỉ báo, không thể tái lập đầy đủ. [backtest.py, dòng 124–125](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/backtest.py#L124-L125).

README mô tả riêng hai nguồn thay đổi: việc lấy mẫu LLM và tin tức/mạng xã hội thay đổi theo thời gian. README cũng nói kết quả không được bảo đảm trùng số đã công bố. [README, mục Reproducibility](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/README.md#L385-L405).

**Suy luận phục vụ dự án:** khóa ngày phân tích và giảm temperature chưa đủ đáp ứng yêu cầu chạy lại ra cùng kết quả của engine rule-based. Cần lưu và phát lại bộ dữ liệu văn bản cùng phản hồi LLM; tính ngẫu nhiên phải được đo qua nhiều lần thử, không chỉ chọn một kết quả tốt.

## 5. Point-in-time: có sửa chữa, vẫn cần kiểm thử

Changelog v0.7.0 cho biết đã chuyển giá chấm điểm từ close cùng ngày sang close đầu tiên sau ngày quyết định, vì một lượt phân tích có thể đọc tin phát hành sau close. Kết quả đã settle trước đó giữ cách cũ; nối tiếp bằng cùng run_id có thể trộn hai cách, nên tác giả yêu cầu bắt đầu run mới để so sánh nhất quán. [CHANGELOG, dòng 50–57](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/CHANGELOG.md#L50-L57).

v0.7.1 tiếp tục sửa giá close chưa kết thúc, lịch nghỉ dài và ngày mô hình có thể đọc filing sau ngày chạy. [CHANGELOG, bản v0.7.1](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/CHANGELOG.md#L7-L31).

README hiện mô tả SEC fundamentals theo ngày filing và giữ lại số liệu as-filed; các fundamentals Yahoo không có publication date bị giữ lại khi chạy quá khứ. [README, Fundamentals as filed](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/README.md#L300-L315).

**Suy luận:** các sửa chữa này là điểm tích cực để học cách chặn dữ liệu tương lai. Chúng không tự xác minh lại thí nghiệm năm 2024 trong bài báo, cũng không loại trừ rủi ro kiến thức tương lai nằm trong trọng số LLM. Cần kiểm thử trực tiếp việc cách ly dữ liệu và dùng forward paper nếu muốn đánh giá thực dụng.

## 6. Áp dụng cho dự án

Phù hợp nhất là lớp đọc/tóm tắt tin và tạo hồ sơ lập luận có nguồn, chạy riêng với engine. Có thể học phản biện bull/bear và báo cáo theo vai trò. Không coi lời đồng thuận của nhiều LLM là bằng chứng độc lập, lợi nhuận đã xác minh hoặc hard risk rule.

Nếu thử: giữ engine định lượng hiện tại; bắt đầu ở chế độ chỉ ghi nhận; lưu nguồn cùng thời điểm biết được, phản hồi, cấu hình, thời gian và chi phí thực tế; so cùng kỳ với phương án không dùng LLM. Chỉ đánh giá tác động sau chi phí và trên dữ liệu chưa dùng chọn thiết kế.

Đây là đề xuất đánh giá, không phải yêu cầu tự triển khai hoặc thay đổi kết luận nghiên cứu hiện có.

