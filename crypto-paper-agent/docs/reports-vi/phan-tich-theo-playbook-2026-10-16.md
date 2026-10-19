# Phân tích repo theo Skills Playbook (bản 2)

Ngày: 2026-10-16 · Commit được đọc: `fe1c133` (`main`) · Chỉ đọc, không sửa repo.
Bản này bổ sung cho [bản 1](phan-tich-repo-2026-10-16.md). Kiến trúc, kết quả test và lộ trình ở bản 1 vẫn đúng, nên ở đây tôi không nhắc lại.

## 1. Skill đã dùng theo playbook

| Playbook yêu cầu | Có trong phiên? | Đã dùng thay bằng |
| --- | --- | --- |
| Nguyên tắc an toàn (mục đầu playbook) | Không phải skill | Đối chiếu từng mục với code, xem mục 2 |
| `ecc:llm-trading-agent-security`, `ecc:prediction-market-risk-review` | **Không có** | Tự rà phần key, gửi lệnh và giới hạn rủi ro theo checklist của playbook |
| `ecc:error-handling`, `ecc:api-connector-builder` | **Không có** | Đọc trực tiếp retry/backoff trong `fetcher.py` và các script tải dữ liệu |
| `statistical-analysis` | Có (`data:statistical-analysis`) | Đã dùng cho mục 4 (ý nghĩa thống kê của backtest) |
| `superpowers:test-driven-development`, `ecc:python-testing` | **Không có** | Dùng kết quả test tự chạy ở bản 1 |
| `superpowers:verification-before-completion` | **Không có** | Mọi kết luận đều ghi rõ là tôi tự kiểm chứng hay chỉ trích từ tài liệu |
| `ecc:latency-critical-systems` (websocket, realtime) | Không có | Không áp dụng, vì repo chưa có luồng giá realtime |
| `claude-mem`, `context-mode`, `caveman` | Không có | Không cần cho việc chỉ đọc |

## 2. Đối chiếu nguyên tắc an toàn của playbook

| Nguyên tắc | Trạng thái trong repo | Bằng chứng |
| --- | --- | --- |
| Mặc định paper/testnet, không tự bật tiền thật | **Đạt, chặt hơn playbook.** `AGENTS.md` cấm cả testnet | `AGENTS.md`; `fetcher.py:57-67` khởi tạo ccxt không có key; trong `src/` và `scripts/` không có `create_order` |
| Key chỉ ở `.env`, `.env` nằm trong `.gitignore` | **Thiếu một phần.** Hiện không có key nào, nhưng `.gitignore` **không có dòng `.env`** | `.gitignore`; quét `git grep` toàn repo không thấy key/secret, chỉ thấy URL công khai của Binance Vision |
| Key không có quyền rút tiền | Không áp dụng (không có key) | — |
| Backtest có phí và trượt giá | **Đạt nhưng đơn giản.** Taker 0,05%, maker 0,02%, slippage cố định 0,03% | `default_config.yaml:33-36`; `paper_broker.py:158`, `:525-567` |
| OOS / walk-forward trước khi paper | **Có code, chưa có kết quả.** Walk-forward 4 tài khoản dùng luật cố định, không dò tham số | `research/workflow.py:186` ("no parameter search") |
| Paper trading với dữ liệu live | **Chưa có** (gate G5 mới ở dạng kế hoạch) | Charter mục 4 |
| Giới hạn lỗ theo ngày | **Đạt.** 5% trong 24h trượt thì đóng toàn bộ và khoá 24h | `default_config.yaml:24`, `circuit_breakers.py` |
| Giới hạn khối lượng mỗi lệnh | **Chỉ gián tiếp.** Lệnh bị giới hạn bởi % rủi ro, đòn bẩy tối đa 5x và ký quỹ khả dụng. Không có trần tuyệt đối theo notional hay số lượng | `invariant_checks.py`; không có `max_notional`/`max_qty` trong config |
| Stop-loss bắt buộc | **Đạt** cho lệnh định hướng | Web evidence "Directional stop-loss: Required"; risk gate kiểm tra khoảng SL |
| Circuit breaker khi lỗi API hoặc mất kết nối | **Chưa có cho chạy live.** Mới có kiểm tra dữ liệu cũ (`validation.source_time`, tối đa 24h). Khi tải dữ liệu lỗi thì xem mục 3.1 | `research/validation.py:47-58` |
| Kill switch (nút tắt khẩn cấp) | **Chưa có nút tắt thủ công.** Chỉ có breaker tự động (`is_locked`, `is_halted`) và `EMERGENCY_STOP` riêng trong Funding Arbitrage | `circuit_breakers.py:106-197`, `funding_arbitrage.py:242` |
| Cảnh giác look-ahead | **Mạnh.** Có test riêng và ADR 0003, 0007 | `test_no_lookahead.py`, `test_execution_no_lookahead.py` |
| Survivorship bias | **Rủi ro thấp.** Chỉ có BTCUSDT, một cặp sống suốt giai đoạn | config |
| Overfitting | **Kiểm soát tốt về quy trình.** Luật cố định, OOS phải đóng băng trước, cấm tinh chỉnh trên holdout | Charter mục 2, 5 |

Kết luận phần an toàn: với một hệ thống backtest thuần, repo đạt hầu hết các mục. Phần còn thiếu (kill switch, breaker khi mất kết nối, trần khối lượng tuyệt đối) đều thuộc giai đoạn chạy live và **phải có trước khi làm G5**.

## 3. Phát hiện mới so với bản 1

### 3.1 Required: tải dữ liệu lỗi giữa chừng thì âm thầm trả về dữ liệu thiếu
Trong `src/data_layer/fetcher.py:109-112` và `:149-195`, nếu một chunk thất bại hết `MAX_RETRIES` lần (lỗi mạng, rate limit) hoặc gặp `ExchangeError`, hàm `_fetch_ohlcv_chunk` trả về `[]`. Vòng lặp ngoài coi đó là "hết dữ liệu", `break`, rồi trả về DataFrame **chỉ có phần đã tải được**. Hàm `detect_gaps` chỉ ghi log, không chặn. OI và funding (`:421-445`, `:521-558`) cũng theo cùng mẫu này.
Hệ quả: một lần mất mạng khi tải 5 năm dữ liệu có thể tạo ra bộ dữ liệu bị cắt đuôi mà backtest vẫn chạy bình thường. Điều này trái với nguyên tắc fail-closed của chính dự án.
Đề xuất: ném lỗi (ví dụ `DATASET_UNAVAILABLE`) khi hết retry hoặc khi khoảng thời gian trả về ngắn hơn khoảng được yêu cầu.
Lưu ý: đường tải mới (`prepare_public_research_sample.py`, Binance Vision kèm checksum) có kiểm soát tốt hơn. Lỗi này ảnh hưởng chủ yếu tới đường `run_backtest.py --allow-network` dùng ccxt. Tôi kết luận dựa trên đọc code, chưa tái hiện bằng cách ngắt mạng.

### 3.2 Required: `.gitignore` thiếu `.env`
Hiện chưa có key nào nên chưa có rủi ro thực. Nhưng playbook yêu cầu `.env` phải nằm trong `.gitignore` từ đầu, trước khi ai đó lỡ tạo file `.env`. Sửa bằng một dòng.

### 3.3 Required trước G5: thiếu kill switch thủ công và breaker khi mất kết nối
Breaker hiện chỉ phản ứng với lỗ. Playbook yêu cầu bot dừng nhận lệnh khi API lỗi hoặc mất kết nối, và có một nút tắt mà người vận hành bấm được. Với backtest offline thì không cần, nhưng đây phải là hạng mục bắt buộc trong kế hoạch G5. Charter đã nêu "quarantine stale/disconnected data and stop admission" nhưng chưa có code.

### 3.4 Optional: không có trần khối lượng tuyệt đối cho mỗi lệnh
Kích thước lệnh = rủi ro% ÷ khoảng stop, bị chặn bởi 5x đòn bẩy và ký quỹ. Khi stop rất sát giá, notional sẽ tiến tới mức 5x vốn. Thêm `max_notional_per_order` sẽ khớp với yêu cầu của playbook. Đây là thay đổi ngữ nghĩa rủi ro, nên cần bạn duyệt.

### 3.5 Optional: mô hình trượt giá cố định
Slippage 0,03% áp dụng như nhau cho mọi nến, kể cả nến gap hay lúc biến động mạnh. Trong `src/` và `tests/` tôi không tìm thấy phân tích độ nhạy theo chi phí (ví dụ chạy lại với slippage ×2, ×3), dù charter có nhắc "cost sensitivity". Nên thêm vào protocol đánh giá.

## 4. Ý nghĩa thống kê của kết quả backtest (skill `statistical-analysis`)

- **Cỡ mẫu hiện tại không đủ để kết luận bất cứ điều gì.** Trend và Breakout có 0 lệnh, Funding có 1 basket, PPO có một holdout. Với 0–1 quan sát, Sharpe, win rate và SQN đều vô nghĩa. Con số lỗ −25 USDT hay −477 USDT không chứng minh chiến lược tệ, cũng như một lần lãi sẽ không chứng minh chiến lược tốt.
- **Thiếu khoảng tin cậy.** `report/metrics.py` tính Sharpe (theo ngày, nhân √365), SQN và win rate dưới dạng **một con số duy nhất**, không có CI hay bootstrap. Khi đã có dữ liệu dài, nên báo cáo expectancy kèm CI 95% (bootstrap theo lệnh, hoặc block bootstrap theo ngày cho equity), và luôn ghi kèm số lệnh.
- **Vấn đề so sánh nhiều lần.** Có 4 chiến lược + PPO, thêm nhiều cửa sổ walk-forward. Nếu chọn "chiến lược tốt nhất" sau khi xem kết quả thì xác suất chọn nhầm rất cao. Charter đã cấm chọn sau khi mở holdout, rất tốt. Nên ghi thêm vào protocol: số phép thử đã chạy, và hiệu chỉnh (Bonferroni, hoặc deflated Sharpe) khi so sánh.
- **Ngưỡng số lệnh.** Hai phương án trong charter (60 lệnh, hoặc 24 lệnh với tối thiểu 8 lệnh mỗi năm) là hợp lý. Theo quy tắc kinh nghiệm cần khoảng 30 sự kiện trở lên, 24 lệnh là mức sàn và CI sẽ rất rộng. Tôi khuyên chọn phương án 60 lệnh nếu Trend + Breakout trên 5,5 năm đạt được mức đó.
- **Phân tích theo regime.** Kết quả gộp có thể đảo chiều khi tách theo giai đoạn bull 2021, bear 2022, hồi phục 2023–24 (Simpson's paradox). Báo cáo nên tách theo năm và theo regime như charter G2 yêu cầu.

## 5. Bước tiếp theo đã cập nhật

Thứ tự ở bản 1 giữ nguyên. Thêm hai việc nhỏ, rủi ro thấp, nên làm sớm:
1. Sửa fetcher để **fail-closed khi tải thiếu** (mục 3.1), kèm test giả lập lỗi mạng. Làm trước khi tải dữ liệu 2021–2026.
2. Thêm `.env` vào `.gitignore` (mục 3.2).

Thêm vào protocol đánh giá trước khi mở OOS: CI bootstrap, kiểm tra độ nhạy chi phí (slippage ×2, ×3), và đếm số phép thử đã chạy (mục 3.5 và 4).
Thêm vào kế hoạch G5: kill switch, breaker khi mất kết nối hoặc dữ liệu cũ, và trần khối lượng mỗi lệnh (mục 3.3, 3.4).

## 6. Mức độ tin cậy

- Tôi đọc trực tiếp: `.gitignore`, `fetcher.py` (đường retry), `fetch_market_data.py`, `validation.py`, `workflow.py`, `metrics.py` (phần Sharpe/SQN), các dòng slippage trong `paper_broker.py`, cùng kết quả quét key/secret bằng `git grep`.
- Phát hiện 3.1 là kết luận từ đọc code, tôi chưa tái hiện bằng cách ngắt mạng. Tôi chưa quét toàn bộ lịch sử git để tìm secret; mới quét cây hiện tại và tìm chuỗi `apiKey` trong lịch sử.
- Ghi chú: khi chạy test ở bản 1, Python tự sinh các thư mục `__pycache__` trong repo (đã bị `.gitignore` bỏ qua). Tôi đã xoá chúng, nên repo trở lại đúng trạng thái ban đầu.
