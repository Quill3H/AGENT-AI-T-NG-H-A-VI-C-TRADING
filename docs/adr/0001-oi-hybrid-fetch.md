# ADR 0001: Cơ chế Hybrid Fetch dữ liệu Open Interest (Binance Vision + REST API)

## Trạng thái
Đã chấp thuận (Accepted) — Triển khai tại Giai đoạn 1.

## Bối cảnh
- Binance Futures REST API (`/fapi/v1/openInterestHist`) chỉ lưu trữ tối đa 30 ngày dữ liệu Open Interest (OI) gần nhất. Khi backtest chiến lược từ 2021 đến nay (~5.5 năm), gọi REST API cho các mốc lịch sử xa sẽ trả về rỗng hoặc lỗi.
- Nguồn Binance Data Vision (`data.binance.vision`) lưu trữ toàn bộ dữ liệu daily metrics lịch sử từ năm 2019, nhưng các file nén theo ngày thường có độ trễ phát hành từ 1 đến 2 ngày so với thời điểm hiện tại. Nếu chỉ dùng Binance Vision, phần đuôi (1-2 ngày gần nhất) sẽ bị thiếu (`NaN`).

## Quyết định
Áp dụng cơ chế **Hybrid Fetch** chia khoảng thời gian $[since, until]$ thành 2 phần:
1. **Phần lịch sử sâu ($[since, boundary]$):** Lấy từ Binance Data Vision thông qua module `binance_vision_downloader.py`. Điểm $boundary = now - 2\text{ ngày}$ nhằm chừa khoảng đệm an toàn cho độ trễ phát hành file. Dữ liệu nến 5m được downsample về 4h/15m/1m bằng forward-fill (không nội suy để tránh lookahead).
2. **Phần thời gian thực ($[boundary, until]$):** Lấy trực tiếp từ Binance Futures REST API qua `ccxt`.
3. Ghép nối hai tập dữ liệu, sort index theo thời gian và deduplicate.

## Lý do
- Đảm bảo có đầy đủ dữ liệu OI xuyên suốt toàn bộ khoảng backtest nhiều năm mà không bị thiếu hụt dữ liệu ở những ngày giao dịch gần nhất.
- Hoàn toàn tự động, trong suốt đối với các module tầng trên (Feature Engine, Strategies).

## Hệ quả
- Khi fetch dữ liệu lịch sử > 28 ngày, hệ thống sẽ thực hiện tải các file zip từ Binance Vision, giải nén và lưu cache Parquet local.
- Cần duy trì kết nối Internet khi tải lần đầu. Các lần chạy tiếp theo được đọc từ cache Parquet local siêu tốc.
