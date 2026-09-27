# ADR 0003: Cơ chế chống Lookahead Bias trong xác nhận Swing Point & CVD Divergence

## Trạng thái
Đã chấp thuận (Accepted) — Triển khai tại Giai đoạn 2.

## Bối cảnh
- Phân kỳ CVD (CVD Divergence) yêu cầu so sánh các đỉnh (Swing High) hoặc đáy (Swing Low) giữa đường giá và đường CVD tích lũy.
- Theo định nghĩa hình học, một nến tại chỉ số $i$ chỉ được coi là đỉnh/đáy cục bộ nếu nó cao hơn/thấp hơn $k$ nến lân cận trước và sau ($k = \text{swing\_n} = 3$).
- Rủi ro lớn nhất trong backtest là "Lookahead Bias": nếu thuật toán phát hiện nến $i$ là đỉnh rồi gán tín hiệu phân kỳ ngay tại nến $i$, hệ thống đã vô tình sử dụng dữ liệu của các nến $i+1, i+2, i+3$ trong tương lai mà ở thời gian thực trader chưa thể biết được.

## Quyết định
1. **Độ trễ xác nhận (Confirmation Lag):** Nến $i$ chỉ được xác nhận là Swing Point tại thời điểm nến $t = i + k$ đóng cửa.
2. **Tuyệt đối không Backfilling:** Tín hiệu phân kỳ (`BULLISH` hoặc `BEARISH`) **chỉ được ghi nhận tại nến $t$**, không bao giờ được ghi ngược về nến $i$ trong quá khứ.
3. **Causal Streaming Loop:** Duyệt tuần tự theo thời gian $t = 0 \to N-1$, sử dụng cấu trúc hàng đợi `deque` để theo dõi các đỉnh/đáy đã được xác nhận trong cửa sổ $[t - \text{lookback} + 1, t]$.
4. **Bảo chứng kiểm thử:** Thiết kế test case `tests/test_no_lookahead.py` xáo trộn ngẫu nhiên dữ liệu sau điểm $T$, chứng minh mọi feature tại $t \le T$ không đổi.

## Lý do
- Đảm bảo kết quả backtest phản ánh chính xác 100% điều kiện giao dịch thực tế, không có "lợi nhuận ảo" do nhìn trộm tương lai.

## Hệ quả
- Tín hiệu phân kỳ sẽ có độ trễ tự nhiên đúng bằng $k = 3$ nến so với thời điểm đỉnh/đáy hình thành. Đây là sự thật khách quan của phân tích kỹ thuật thời gian thực.
