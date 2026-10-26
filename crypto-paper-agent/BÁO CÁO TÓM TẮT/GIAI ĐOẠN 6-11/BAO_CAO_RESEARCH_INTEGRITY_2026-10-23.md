# Báo cáo tăng cường tính toàn vẹn nghiên cứu

Ngày: 2026-10-23

Nhánh: `codex/research-qa-hardening`

Nền: `fd466ac`

Mã tính năng: `3ac638d`

Mã sửa sau review: `efd935b` (vòng một: `d213462`)

## Mục tiêu

Giảm nguy cơ chọn phương pháp theo kết quả đẹp sau khi đã xem dữ liệu. Thay đổi này chỉ siết quy trình nghiên cứu; không sửa chiến lược, điều kiện vào/ra, quản trị rủi ro hoặc kết quả Round 18.

## Nội dung đã triển khai

- Từ Round 19, hệ thống từ chối ghi kết quả nếu chưa đăng ký giả thuyết trước.
- Bản đăng ký khóa danh sách biến thể, cấu hình đối chứng, các mức chi phí và commit dùng để chạy.
- Mỗi kết quả phải khớp tên ứng viên, biến thể, vai trò, cấu hình đối chứng, mức chi phí và commit đã đăng ký.
- Trạng thái hoàn tất chỉ đạt khi có đủ từng tổ hợp biến thể × chi phí × vai trò. Một kết quả đối chứng không thể đại diện cho nhiều biến thể hoặc nhiều mức chi phí.
- Đối chứng `matched_random` sử dụng seed và số lần lặp đã đăng ký, loại trừ tín hiệu thật và từ chối tập thời gian không hợp lệ.
- Mỗi lượt chạy mới có `run_id`. Nếu nhiều lượt trùng nhãn, yêu cầu vô hiệu hóa không chỉ rõ ID sẽ bị từ chối.
- Vai trò `candidate` và các stage metadata được giữ riêng, không thể dùng tên đối chứng hoặc hàm ghi kết quả chung để lách kiểm soát. Bản ghi cũ chưa có `run_id` có thể được chọn chính xác bằng thời điểm ghi.
- Các vòng 1–18 tiếp tục được ghi rõ là dữ liệu lịch sử chưa đăng ký trước; hệ thống không gắn nhãn đăng ký hồi tố.

## Kiểm thử và review

- Các ca hồi quy theo review vòng một: 8 ca thất bại trước khi sửa. Review vòng hai bổ sung 7 lỗi tái hiện thất bại trước khi sửa.
- Bộ kiểm thử trọng tâm ledger và đối chứng: 30 đạt.
- Toàn bộ kiểm thử offline tại `efd935b`: 713 đạt, 4 bỏ qua, 5 test mạng không chạy.
- Lượt chạy không loại test mạng: 706 test offline vẫn đạt; 4 test tải dữ liệu Binance lỗi do môi trường không phân giải được DNS. Không có lỗi này thuộc phần mã vừa thay đổi.
- Review độc lập cuối cùng trên `fd466ac..efd935b`: không còn lỗi chặn; toàn bộ lỗi P1/P2 trước đó đã được xác nhận đóng.

## Kết luận và giới hạn

Quy trình từ Round 19 đã khó bị lách bằng cách ghi kết quả trước, đổi commit, đổi cấu hình đối chứng hoặc dùng một đối chứng cho cả ma trận thử nghiệm. Đây là kiểm soát tính toàn vẹn nghiên cứu, không chứng minh phương pháp nào có lãi. Helper đối chứng vẫn phải được runner của từng chiến lược dùng với cùng sizing, stop, target, thời gian giữ, phí, trượt giá, funding và các bộ ngắt rủi ro trước khi có thể đánh giá lợi thế kinh tế.
