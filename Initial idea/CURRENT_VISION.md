# Định hướng hiện tại — 29/10/2026

## 1. Mục đích

Xây dựng trợ lý nghiên cứu crypto futures có thể biến một ý tưởng thành bộ quy tắc rõ ràng, chạy mô phỏng, giải thích vì sao vào/không vào lệnh và lưu bằng chứng để người dùng quyết định tiếp tục hay loại bỏ. Giao dịch tự động bằng tiền thật là lựa chọn tương lai cần phạm vi và phê duyệt riêng.

Thành công trước mắt là **hệ thống nghiên cứu dùng được, có thể kiểm tra và tiếp nối**. Lợi thế sau chi phí phải được đánh giá riêng; không mặc định rằng hệ thống nhiều chỉ báo hay có AI sẽ sinh lời.

## 2. Tư duy đã phát triển từ ý tưởng gốc

| Ý tưởng gốc | Cách hiểu hiện tại |
| --- | --- |
| Agent perception–decision–action | Dữ liệu có nguồn → feature nhân quả → chiến lược → risk gate → PaperBroker → journal/report |
| Bốn phương pháp giao dịch | Các baseline tách biệt để so sánh: Trend, Breakout/Retest, SMC, Funding; không mặc định cộng chúng là tốt hơn |
| RL/PPO có thể học | Có đường triển khai và smoke được thuật lại trong hồ sơ; chưa có bằng chứng chính sách học được lợi thế bền vững |
| Tỷ lệ thắng/thu nhập hấp dẫn | Giả thuyết cần kiểm tra bằng expectancy ròng, chi phí, drawdown và độ ổn định |
| Tự động hóa nghiên cứu | Tái sử dụng dữ liệu/cache, khóa config/code, lưu mọi lần thử và giảm làm lại giữa các chat |

Nguồn thẩm quyền: [charter](../crypto-paper-agent/docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md), [quyết định](../crypto-paper-agent/docs/decisions/) và [checkpoint hiện tại](<../Project spec/CURRENT_STATUS.md>). Nội dung này là tổng hợp tài liệu, không phải quyết định đổi risk hay chiến lược.

## 3. Các hướng nghiên cứu đang tồn tại

- **Baseline và chiến lược tổng hợp:** mã trên main có Trend, Breakout, SMC, Funding, PPO và SynthesizedStrategy 4h/15m. Kết quả tổng hợp được báo cáo gần nhất là âm; cần xác minh nguồn dữ liệu và khớp config với artifact trước khi đánh giá kinh tế.
- **Funding carry:** kết quả lịch sử được tác giả báo cáo dương, nhưng số basket ít và lợi nhuận tập trung. Không suy rộng thành lợi thế đã nghiệm thu.
- **BTC OI reclaim / ICT sweep–FVG:** giữ cả kết quả không có lệnh, thiếu dữ liệu và các vòng sửa lỗi. Không hạ điều kiện để tạo số lệnh đẹp.
- **ETH–BTC và ORB/FVG đa coin:** có mã và bằng chứng ở nhánh nghiên cứu cục bộ tại lúc kiểm tra; phải phân biệt với main. ETH–BTC v1 không đủ bằng chứng; ORB tháng 09/2026 lỗ sau chi phí.
- **QuantDinger / TradingAgents:** tài liệu tham khảo về cách tổ chức công cụ và phân tích; không nhập tín hiệu hoặc thay engine chỉ vì một repo có giao diện tốt.

Chi tiết số liệu, commit nguồn và mức kiểm chứng ở [CURRENT_STATUS](<../Project spec/CURRENT_STATUS.md>).

## 4. AI làm gì trong hệ thống?

AI hỗ trợ diễn đạt giả thuyết, tìm tài liệu, viết/kiểm tra mã và tổng hợp báo cáo. Tín hiệu phải đi qua luật đã khóa và ràng buộc rủi ro. PPO phải giữ riêng train/validation/test, model/scaler/config hash; không học tiếp trong phiên đang chấm điểm.

Chưa có bằng chứng để mô tả hệ thống hiện tại là “AI tự tìm được phương pháp sinh lời”. Hợp nhất các phương pháp là một ứng viên cần đối chứng với từng baseline, không phải một cải tiến mặc nhiên.

## 5. Thứ tự ưu tiên được đề xuất từ bằng chứng

1. Đồng bộ bản đồ tài liệu, phạm vi nhánh và danh mục thí nghiệm.
2. Làm rõ nguồn dữ liệu thật/giả lập, funding và các khác biệt giữa code/config/báo cáo.
3. Xác nhận pipeline đúng và tái lập được trước khi chạy thêm phương án.
4. Chỉ mở nghiên cứu mới với giả thuyết, đối chứng, chi phí và giới hạn nguồn lực đã khóa.
5. Chạy paper forward khi đủ điều kiện chức năng và có hợp đồng phiên cố định.

Đây là thứ tự đề xuất, chưa phải quyền tự bắt đầu một gate hoặc nghiệm thu kết quả. Xem [ROADMAP](<../Project spec/ROADMAP.md>).
