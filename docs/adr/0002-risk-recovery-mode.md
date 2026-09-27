# ADR 0002: Chế độ phục hồi rủi ro Circuit Breaker (Recovery Mode: after_3_wins)

## Trạng thái
Đã chấp thuận (Accepted) — Quyết định tại Giai đoạn 0 & 1.

## Bối cảnh
- Theo thiết kế Circuit Breakers (Mục 4.4 & 10.2 Spec), khi hệ thống gặp chuỗi 3 lệnh thua liên tiếp (`consecutive_losses_threshold = 3`), tỷ lệ rủi ro (`risk_percent`) sẽ tự động bị cắt giảm 50% (`risk_reduction_on_streak = 0.5`) để bảo vệ tài khoản khỏi chu kỳ sụt giảm vốn mạnh.
- Cần xác định điều kiện phục hồi `risk_percent` về lại mức tiêu chuẩn: Sau bao nhiêu lệnh thắng liên tiếp?

## Quyết định
- Chọn chế độ: `recovery_mode = "after_3_wins"` với `consecutive_wins_to_recover = 3`.
- Hệ thống chỉ khôi phục `risk_percent` về mức bình thường sau khi bot ghi nhận chuỗi **3 lệnh thắng liên tiếp**.

## Lý do
- Sau một chuỗi thua, thị trường thường đang rơi vào trạng thái nhiễu (choppy) hoặc chế độ thị trường (regime) không phù hợp với chiến lược. Một lệnh thắng đơn lẻ có thể chỉ là may mắn ngẫu nhiên.
- Đòi hỏi 3 lệnh thắng liên tiếp giúp đảm bảo thị trường đã thực sự quay lại pha thuận lợi trước khi mở rộng quy mô vốn trở lại.

## Hệ quả
- Khả năng bảo toàn vốn cao hơn trong các giai đoạn thị trường xấu kéo dài.
- Tốc độ gỡ lại drawdown có thể chậm hơn so với phục hồi ngay sau 1 lệnh thắng, nhưng giảm thiểu tối đa rủi ro cháy tài khoản.
