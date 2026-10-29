# Bổ sung từ ba đánh giá repo (QuantDinger, CCXT, Freqtrade) — 2026-10-23

Trạng thái: AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Paper-only, không có đường đặt lệnh, không key.
Nhánh `claude/project-thread-jrmpfx`, gốc `claude/project-thread-ryvuyt` @ `fd466ac`.
Không đổi chiến lược, không đổi tham số v1, không chạy lại ma trận, không làm v2. Kết luận vòng 18 vẫn là NO_TRADES / chưa đủ bằng chứng.

## Đã làm

| Việc | Commit | Nội dung |
|---|---|---|
| Ledger + execution_assumptions | `569224a` | `ledger.record(..., variants_tried=, fold_scores=)` có kiểm tra đầu vào; `variants_tried_by_round`, `fold_matrix` (đầu vào cho DSR và PBO/CSCV sau này). `persist_research_run` thêm khối `execution_assumptions` (phí, trượt giá cố định, khớp ở open nến sau, mark = open nến, funding theo sự kiện, thanh lý theo bracket, những gì chưa mô hình hoá). Bản ghi cũ không đổi. |
| Ghim ccxt + test public-only | `44be762` | `ccxt==4.5.82` (khớp `requirements-repair-lock.txt`). Test: `_get_exchange()` không có apiKey/secret/... kể cả khi có biến môi trường giống key, sandbox tắt, endpoint là `fapi.binance.com`. |
| Test recursive cho ewm | `389d3d8` | So giá trị chỉ báo tính trên cửa sổ của chiến lược với giá trị trên 3000 nến; và quyết định vào lệnh chỉ phụ thuộc cửa sổ cuối (backtest và forward paper quyết định như nhau). |
| Hook order book forward paper | `d970fdf` | `src/execution/book_slippage.py`: đi qua sổ lệnh L2 để ra giá khớp trung bình, so với giá khớp giả (bps), ghi JSONL mỗi lần khớp giả. Chưa nối vào broker, không đổi luật khớp. |

Test offline: 723 passed, 2 skipped, 5 network deselected (Python 3.13, môi trường từ `requirements-repair-lock.txt`). Trước khi sửa: 693 passed.

## Phát hiện từ test recursive (không sửa, chỉ ghi lại)

Đo trên BTCUSDT perp 4h 2021–2026 (dữ liệu Binance Vision của dự án):

- `ADXDonchian` tính ADX(14) trên 80 nến 4h: lệch so với ADX hội tụ trung vị 2,7%, tối đa 10%. Cổng ADX > 25 đổi kết quả ở khoảng 2,7% số lần kiểm tra.
- `MultiTimeframeTrend` tính EMA(200) ngày trong 1400 nến 4h (khoảng 233 ngày): lệch trung vị 1,4%, tối đa 8,9%. Điều kiện EMA50 > EMA200 ngày đổi kết quả ở khoảng 5% số lần kiểm tra.
- Các chỉ báo còn lại hội tụ (EMA20/160, RSI2/260, ATR, Supertrend/200, ADX/130, EMA50 ngày) hoặc lệch nhỏ (EMA50 trên 80 nến: tối đa 0,75%).

Vì chiến lược luôn tính trên đúng `window` nến cuối, backtest và forward paper vẫn nhất quán với nhau; chỉ là giá trị khác với chỉ báo "chuẩn" (ví dụ TradingView). Cửa sổ thuộc kết quả vòng 3 nên giữ nguyên; test chỉ đặt trần để khoảng lệch không tăng mà không ai biết.

## Bảng leverage bracket BTC: chưa xác minh được, không đổi

- Trang công khai `binance.com/en/futures/trading-rules/perpetual/leverage-margin` render bằng JavaScript; bản tải về chỉ có tiêu đề cột và "No Data".
- Từ container, mọi kết nối tới `binance.com` / `fapi.binance.com` bị proxy chặn (403); endpoint `leverageBracket` của Binance là USER_DATA, cần key, nên không dùng.
- Trang FAQ 360033162192 (cập nhật 2026-03-27) không có bảng BTC.
- Nguồn thứ cấp duy nhất là file JSON của Freqtrade (GPLv3, CI của họ lấy bằng API key) cho tầng đầu khác bảng dự án (300k/0,4% so với 50k/0,4%). Không dùng làm nguồn.

Kết luận: không đoán số, `config/default_config.yaml` giữ nguyên. Với tài khoản 10k và trần danh nghĩa 2 lần vốn, lệnh luôn nằm ở tầng đầu (MMR 0,4% ở cả hai bảng), nên kết quả hiện tại không bị ảnh hưởng. Muốn cập nhật: người dùng mở trang trên trình duyệt, chụp hoặc chép bảng BTCUSDT kèm ngày, rồi thêm vào config cùng một test.

## Thiết kế ghi order book cho forward paper

- Khi broker khớp giả một lệnh market, gọi `OrderBookRecorder.on_simulated_fill(symbol, side, qty, giá_khớp_giả, giá_open, thời_điểm, event_id)`.
- Recorder lấy sổ lệnh công khai qua `fetch_public_order_book` (ccxt không key, `fetch_order_book`, 20 mức), so chi phí theo sổ với chi phí theo 0,03%, ghi một dòng JSONL. Lỗi mạng ghi `SNAPSHOT_FAILED`, không làm dừng phiên paper.
- Sổ lệnh được chụp lúc hook chạy, không đúng lúc khớp; cả hai thời điểm đều được ghi để đánh giá độ trễ.
- Backtest không có sổ lệnh lịch sử, nên recorder không có nguồn và không làm gì.
- Việc còn lại khi bắt đầu forward paper: nối hook vào vòng lặp paper (nhánh paper stream chưa merge vào nhánh này), và chọn ngưỡng để quyết định có thay 0,03% hay không. Chưa đổi luật khớp.
