# TradingAgents — nghiên cứu và đánh giá mức độ phù hợp

Ngày: 29/10/2026. Repo: TauricResearch/TradingAgents. Mã nguồn được neo tại commit [c4544913a14ed3df5f1ed7b9e8483270ce20682a](https://github.com/TauricResearch/TradingAgents/commit/c4544913a14ed3df5f1ed7b9e8483270ce20682a), merge release v0.7.1 ngày 27/10/2026.

## Kết luận

Đáng tham khảo và có thể thử như lớp trợ lý nghiên cứu tin tức/vĩ mô, lập luận phản biện và ghi nhận quyết định. Chưa phù hợp để thay crypto-paper-agent hoặc Backtest Lab trong nhiệm vụ mô phỏng crypto futures có phí, funding, margin, thanh lý và quy tắc rủi ro cứng. Đánh giá này dựa trên đọc mã nguồn, tài liệu và bài nghiên cứu; chưa cài chạy, gọi mô hình trả phí, tái lập hiệu quả hoặc kiểm toán toàn repo.

## 1. Repo thực sự làm gì?

Luồng chính: các analyst kỹ thuật/tin tức/tâm lý/cơ bản hoạt động song song → Bull/Bear tranh luận → Research Manager → Trader → các quan điểm rủi ro aggressive/neutral/conservative → Portfolio Manager. LangGraph điều phối luồng; có checkpoint SQLite tùy chọn và báo cáo Markdown/HTML. Nguồn: [graph/setup.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/graph/setup.py#L109-L187), [trading_graph.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/graph/trading_graph.py).

Đầu ra propagate là trạng thái cùng một rating Buy / Overweight / Hold / Underweight / Sell, hoặc REVIEW khi không đọc được rating. Đây là ý kiến/quyết định nghiên cứu; tự nó không phải lệnh khớp trên sàn. Nguồn: [propagate](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/graph/trading_graph.py#L167-L190).

PortfolioContext nhận cash và vị thế do bên gọi cung cấp. Nó không tự lấy tài khoản, không đóng vai trò sổ tiền và không tạo đường thực thi broker. Nguồn: [portfolio.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/portfolio.py).

Có crypto mode và ticker BTC-USD/ETH-USD, dùng các đường dữ liệu Yahoo cùng logic phân biệt crypto/công ty. CLI loại analyst báo cáo tài chính doanh nghiệp khi chạy crypto. Điều này không chứng minh hỗ trợ dữ liệu Binance perpetual, funding, OI hay CVD. Nguồn: [crypto tests](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tests/test_crypto_asset_mode.py), [context](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/agents/context.py#L164-L168), [default config](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/default_config.py).

## 2. Khác biệt quyết định: backtest ở đây chấm nhận định

backtest.py tuyên bố rõ phạm vi đánh giá chất lượng quyết định, không phải bộ mô phỏng danh mục. Mỗi ô ticker/ngày độc lập; một portfolio đầu vào được giữ nguyên cho từng ô. Không có quantity/fill/cash ledger phục vụ mô phỏng giao dịch nối tiếp. Nguồn: [backtest.py, phần đầu](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/backtest.py#L1-L15).

Điểm số được nhóm theo rating, đo hit rate và alpha so với benchmark. Alpha trong memory log được đọc từ phần trăm làm tròn 0,1 điểm phần trăm; không phải PnL chính xác của tài khoản có giao dịch. Khoảng đo bắt đầu tại close đầu tiên sau ngày phân tích; holding_period_days mặc định 5. Nguồn: [backtest.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/backtest.py), [settlement.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/memory/settlement.py#L60-L125), [default config](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/default_config.py).

Hệ quả đối với dự án: không suy hit rate/alpha của rating thành lợi nhuận ròng, Sharpe danh mục, drawdown, thời gian nằm dưới đỉnh, margin usage hoặc nguy cơ thanh lý. Những chỉ số này cần engine và sổ tiền theo thời gian mà dự án đang phát triển.

Cũng không ánh xạ máy móc Sell thành mở SHORT futures: prompt Portfolio Manager định nghĩa Sell là thoát vị thế hoặc tránh vào; Underweight là giảm tỷ trọng. Nguồn: [portfolio_manager.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/agents/managers/portfolio_manager.py).

## 3. Có Risk Manager nhưng chưa phải hard risk gate

TraderProposal có entry_price và stop_loss tùy chọn; position_sizing là hướng dẫn bằng chuỗi văn bản. Portfolio Manager tổng hợp lập luận bằng LLM và xuất rating/thesis. Các schema giúp dữ liệu có cấu trúc, nhưng không thay thế kiểm tra xác định như không cho mở lệnh thiếu SL, giới hạn vốn, leverage cap và circuit breaker. Nguồn: [schemas.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/agents/schemas.py#L146-L188), [Portfolio Manager](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/agents/managers/portfolio_manager.py).

Đây là giới hạn về mục tiêu sản phẩm, không tự động là bug của repo. Khi tích hợp, hard rules của engine riêng phải tiếp tục có quyền từ chối.

## 4. Các phần đáng học hỏi

| Thành phần | Lợi ích cụ thể | Giới hạn |
|---|---|---|
| Analyst tách vai trò + Bull/Bear | Buộc ghi cả bằng chứng thuận/nghịch và điều kiện bác bỏ | Nhiều agent đồng thuận không tạo thành nhiều bằng chứng độc lập |
| Structured output | Lưu rating/reasoning/giá đề xuất có schema thay vì đọc văn bản bằng regex | Có fallback văn bản; JSON hợp lệ không chứng minh luận điểm đúng |
| Khóa ngày dữ liệu trong tool | Ngày và tài sản lấy từ graph state; model hỏi ngày tương lai bị chặn xuống ngày chạy | Chống lộ dữ liệu qua tool không loại bỏ tri thức tương lai có sẵn trong trọng số LLM |
| Snapshot thị trường xác định | Giá/indicator lấy từ công cụ trước khi AI trình bày | Snapshot Yahoo không thay nguồn dữ liệu Binance được xác minh |
| Memory có thời điểm kết quả | Chỉ dùng bài học đã biết tại ngày phân tích lịch sử | Đây là đưa bài học vào prompt, không phải huấn luyện RL hoặc cập nhật trọng số |
| Giới hạn vòng gọi tool/debate | Giảm vòng lặp dài và hỗ trợ kiểm soát chi phí | Chưa phải trần tổng USD cho mỗi đợt |
| Tách mô hình nhanh/sâu | Có thể dùng mô hình khác nhau cho analyst và manager | Chi phí, chất lượng và độ trễ phải đo thực tế |

Nguồn tương ứng: [graph setup](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/graph/setup.py), [schema](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/agents/schemas.py), [tools](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/agents/tools.py), [memory cutoff](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/memory/log.py#L93-L107), [reflection](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/memory/reflection.py), [config](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/default_config.py).

## 5. Chống nhìn trước và tái lập: đã có tiến bộ, còn giới hạn

Tool lấy trade_date từ trạng thái thay vì cho LLM tự đặt; as_of/as_of_window chặn ngày tương lai. Có test cho trường hợp model hỏi ngày vượt ngày chạy hoặc bỏ ngày khi gọi công cụ. Nguồn: [tools](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/agents/tools.py), [date_window](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/dataflows/date_window.py), [tests](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tests/test_tool_date_enforcement.py).

Yahoo news lấy feed/search hiện có rồi lọc theo ngày công bố. Có phân biệt không có dữ liệu với không có tin. Bộ lọc này không khôi phục toàn bộ kho tin đã có tại một ngày trong quá khứ. README thừa nhận nguồn văn bản thay đổi và LLM không bảo đảm trả cùng kết quả. Nguồn: [news.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/dataflows/vendors/yahoo/news.py#L87-L134), [reproducibility](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/README.md#L385-L405).

Đường OHLCV Yahoo tải cửa sổ 5 năm tính từ hiện tại rồi lọc theo ngày yêu cầu. Đây không phải kho dữ liệu lịch sử cố định nhiều năm có checksum như yêu cầu dự án. Giá được auto_adjust; không dùng trực tiếp thay series perpetual của Binance. Nguồn: [ohlcv.py](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/tradingagents/dataflows/vendors/yahoo/ohlcv.py#L161-L230).

Release 0.7.1 sửa thêm lỗi ngày model có thể đọc filing sau ngày chạy và lỗi chấm kết quả khi phiên chưa đóng. 0.7.0 đổi thời điểm chấm từ close cùng ngày sang close sau ngày quyết định; changelog yêu cầu bắt đầu run mới để không trộn kết quả cũ/mới. Những sửa đổi này không xác nhận ngược lại kết quả bài nghiên cứu cũ. Nguồn: [changelog](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/CHANGELOG.md#L9-L57).

Để kiểm chứng lịch sử đáng tin hơn cần lưu nguyên input trả về, thời điểm công bố/truy cập, snapshot dữ liệu, prompt, model ID, cấu hình và output. Để giảm ảnh hưởng tri thức tương lai trong LLM, ưu tiên paper forward trên dữ liệu phát sinh sau khi khóa thiết kế. Đây là đề xuất đánh giá của người review, không phải tính năng repo đã xác nhận.

## 6. Bằng chứng lợi nhuận

Xem [báo cáo đối chiếu bài nghiên cứu](BAO_CAO_BANG_CHUNG.md). Paper arXiv v7 được sửa ngày 03/06/2025; repo khảo sát là release tháng 10/2026. Không coi kết quả paper là kết quả đã tái lập của code hiện tại. Thử nghiệm được công bố trên một cửa sổ cổ phiếu ngắn đầu năm 2024; chưa xác minh bằng chứng nhiều năm trên crypto futures sau toàn bộ chi phí. Nguồn: [paper](https://arxiv.org/abs/2412.20138), [PDF v7](https://arxiv.org/pdf/2412.20138v7).

README hiện tại cũng ghi kết quả backtest không được bảo đảm khớp số đã công bố. Nguồn: [README](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/README.md#L385-L405).

## 7. Chi phí và cài đặt

Python >=3.11; có CLI, Docker tùy chọn, nhiều provider LLM và Ollama/local endpoint. Repo dùng Apache 2.0. Dependencies chính gồm LangGraph/LangChain, pandas, yfinance, stockstats và thư viện CLI; chưa thấy dependency ccxt trong pyproject. Nguồn: [pyproject](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/pyproject.toml), [license](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/LICENSE), [README](https://github.com/TauricResearch/TradingAgents/blob/c4544913a14ed3df5f1ed7b9e8483270ce20682a/README.md).

Các lượt phân tích/debate/tool/reflection gọi LLM; thử nhiều coin và nhiều ngày nhân số lần phân tích. Không báo một con số USD cố định vì phụ thuộc mô hình, độ dài nội dung và số vòng. Sử dụng mô hình local giảm phí API nhưng vẫn cần thời gian, tài nguyên và kiểm chứng chất lượng. Không cần đăng nhập/kết nối tài khoản hoặc trả phí để hoàn thành nghiên cứu repo này.

## 8. Khuyến nghị cho dự án của bạn

Cơ sở đối chiếu đọc trực tiếp: sources/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md và eth-btc-research/crypto-paper-agent/docs/operations/BACKTEST_LAB.md. Tài liệu Backtest Lab hiện có mô tả chạy offline, cache theo nội dung, đọc dữ liệu Binance Vision và giữ cơ chế PaperBroker/funding. Chưa kiểm chứng lại code/branch/kết quả của dự án trong lượt này.

- Giữ engine + hard risk rules + Backtest Lab làm lớp mô phỏng/đối soát.
- Học trước cách khóa ngày công cụ, snapshot số liệu, báo thiếu dữ liệu và schema đầu ra. Các phần này có giá trị ngay cả khi không dùng toàn bộ kiến trúc nhiều agent.
- Nếu muốn thí nghiệm LLM, dùng một lớp nghiên cứu tin tức/vĩ mô tạo báo cáo có nguồn; không để nó tự đặt lệnh hoặc ghi đè risk.
- Bắt đầu với một analyst tin tức và một lượt phản biện, chưa cần toàn bộ đội ngũ.
- Chỉ sau khi khóa thiết kế và có mẫu paper forward mới so bản engine hiện tại với bản có lớp tin tức, dùng cùng điều kiện giao dịch; tính thêm phí API, độ trễ, phí/slippage/funding và đo drawdown/underwater/recovery.
- Nếu lớp LLM không tạo cải thiện ngoài mẫu sau chi phí thì không đưa vào luồng quyết định.

Đây là hướng đề xuất, không phải triển khai được cho phép ngầm. Chưa sửa chiến lược, cấu hình, ledger, dữ liệu hoặc kết luận nghiên cứu hiện có.

## 9. Phạm vi xác minh

- Đã đọc cây repo và các file về graph, backtest, portfolio/schema, ngày dữ liệu, Yahoo price/news, memory/reflection, crypto tests, config, CI và dependency.
- GitHub Actions CI ở commit khảo sát báo success: [run](https://github.com/TauricResearch/TradingAgents/actions/runs/40474943713). CI cấu hình Python 3.11–3.14 và test bổ sung múi giờ; pytest mặc định loại integration. CI xanh không chứng minh lợi nhuận.
- Chưa tự chạy pytest hoặc gọi data provider/LLM; chưa xác nhận hiệu quả, chi phí hoặc latency.
- Không làm audit bảo mật toàn repo, không đánh giá các provider login, không xác nhận mọi prompt/chức năng.

