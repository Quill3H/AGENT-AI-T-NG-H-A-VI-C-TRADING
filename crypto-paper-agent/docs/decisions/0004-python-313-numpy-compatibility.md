# ADR 0004: Tương thích môi trường Python 3.13 và thư viện NumPy / Pandas-TA

## Trạng thái
Đã chấp thuận (Accepted) — Triển khai tại Giai đoạn 1.

## Bối cảnh
- Môi trường thực thi của máy là Python 3.13.14.
- Ban đầu `requirements.txt` pin cứng `numpy==1.26.4`. Bản NumPy 1.x này không có wheel binary biên dịch sẵn cho Python 3.13 trên Windows, gây lỗi khi cài đặt hoặc xung đột C-extensions.
- Thư viện `pandas-ta` chưa có bản phát hành chính thức cập nhật hoàn toàn cho Python 3.13 và pandas >= 2.2.

## Quyết định
1. Nâng cấp cấu hình phụ thuộc trong `requirements.txt`:
   - `numpy>=2.1.0` (hỗ trợ chính thức Python 3.13).
   - `pandas>=2.2.3`.
2. Trong module `src/features/indicators.py`:
   - Ưu tiên import và sử dụng `pandas-ta`.
   - Xây dựng sẵn tầng **Pure Pandas Fallback** (`_ema_presma`, Wilder's smoothing RMA, True Range) tương thích 100% chuẩn TA-Lib nếu `pandas-ta` gặp trục trặc hoặc không khả dụng.

## Lý do
- Duy trì môi trường chạy ổn định trên Python 3.13 hiện đại mà không cần hạ phiên bản Python hệ thống.
- Dự án không bị phụ thuộc chết cứng vào một thư viện bên ngoài duy nhất.

## Hệ quả
- Toàn bộ 53 bài test unit và integration test đều chạy mượt mà trên môi trường ảo Python 3.13.
- Cả 2 tầng (pandas-ta và pure pandas fallback) đều được kiểm thử chéo và cho kết quả đồng nhất.
