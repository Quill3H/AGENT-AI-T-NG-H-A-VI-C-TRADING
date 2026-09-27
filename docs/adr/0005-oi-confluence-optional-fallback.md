# ADR 0005: Cơ chế OI Confluence và Fallback an toàn khi thiếu dữ liệu Open Interest

## Trạng thái
Đã chấp thuận (Accepted) — Triển khai tại Giai đoạn 1 & 2.

## Bối cảnh
- Một số chiến lược (như Trend Following) kiểm tra điều kiện đồng thuận Open Interest: `oi_delta_positive: true` (tăng OI = dòng tiền mới vào).
- Tuy nhiên, trong dữ liệu lịch sử hoặc khi chuyển sàn / chuyển cặp giao dịch, có những thời điểm Open Interest bị thiếu hoặc mang giá trị `NaN` (ví dụ do API giới hạn hoặc ngày sàn chưa ghi nhận metric).
- Nếu xử lý cứng nhắc (`strict`), hệ thống sẽ từ chối vào lệnh hoặc throw lỗi làm gãy cả chu trình backtest.

## Quyết định
1. Thêm khối cấu hình `oi_confluence` vào `default_config.yaml` và các file cấu hình chiến lược:
   ```yaml
   oi_confluence:
     mode: "optional"          # "strict" | "optional" | "disabled"
     fallback_when_nan: true
     nan_log_note: "OI_BYPASSED_HISTORICAL"
   ```
2. **Tại Feature Engine (`src/features/oi_features.py`):**
   - Nếu `open_interest` tại nến $t$ hoặc $t-N$ là `NaN`, `oi_delta_pct` tự động lan truyền giá trị `NaN` (không tự ý forward-fill che giấu).
   - Nếu không có cột `open_interest` hoặc toàn bộ cột là `NaN`, tạo cột `oi_delta_pct` chứa `NaN` và KHÔNG ném ngoại lệ.
3. **Tại Strategy / Rulebook (các giai đoạn sau):**
   - Khi `mode == "optional"` và `oi_delta_pct` là `NaN`: bỏ qua kiểm tra OI, cho phép lệnh tiếp tục nếu các điều kiện khác (EMA, RSI) thỏa mãn, đồng thời ghi log ghi chú `OI_BYPASSED_HISTORICAL`.

## Lý do
- Giữ cho chiến lược có thể backtest xuyên suốt nhiều năm trên các tập dữ liệu có khoảng khuyết OI mà không bị crash hay đình trệ.
- Vẫn kiểm tra chặt chẽ điều kiện OI khi dữ liệu có sẵn.

## Hệ quả
- Kết quả backtest tách bạch rõ ràng giữa các lệnh vào có sự hỗ trợ của OI và các lệnh vào trong vùng thiếu OI (thông qua trade log metadata).
