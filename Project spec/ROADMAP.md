# Lộ trình từ checkpoint 29/10/2026

Đây là backlog được sắp theo phụ thuộc, không tuyên bố các gate đã đạt và không tự cho phép bắt đầu việc ngoài yêu cầu cập nhật tài liệu. G0–G6 giữ nghĩa trong [charter](../crypto-paper-agent/docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md).

## 1. Công việc và điều kiện ra

| Ưu tiên | Việc cần làm | Đầu ra có thể kiểm tra | Điều kiện kết thúc |
| --- | --- | --- | --- |
| P0 | Chốt main và nhánh nghiên cứu; bảo toàn merge conflicts/công việc khác | Commit map và danh sách phạm vi đã tích hợp | Không còn nhầm local với GitHub; không tự nâng trạng thái nghiệm thu |
| P0 | Kiểm tra provenance Synthesized và đồng nhất báo cáo/config | Manifest dataset thật/giả lập, hash code/config, artifact và log chính lần chạy | Nếu thiếu thì giữ NOT_VERIFIED; synthetic chỉ là engineering demo |
| P0 | Kiểm tra funding và tính đúng của accounting/replay | Tái hiện ca thiếu/sai/nhân đôi funding; đối soát ledger/equity; reviewer riêng | Fail closed theo ADR; không tự gán readiness hoặc coi số nhỏ là đúng |
| P1 | Tái lập một baseline cố định bằng cache đã kiểm | Lệnh chạy, runtime, hash và kết quả từ đầu đến cuối | Tester tái hiện; Reviewer đánh giá; người dùng quyết định gate |
| P1 | Chuẩn hóa sổ thí nghiệm và báo cáo cả thất bại | Registry mọi phương án, dữ liệu đã xem, costs, controls và selection history | Không có “ứng viên thắng” được chọn từ holdout đã mở |
| P2 | Nghiên cứu lợi thế sau chi phí | Một giả thuyết/vòng; baseline, placebo/matched random, stress và sensitivity | Theo protocol kinh tế được duyệt trước, không theo win rate |
| P2 | Holdout và walk-forward hợp lệ | Candidate khóa; ranh giới thời gian; model/scaler train-only; kết quả từng regime | Không tune sau khi thấy holdout; đổi phiên bản cần kỳ đánh giá khác |
| P3 | Prospective paper trên dữ liệu công khai | Phiên khóa version; clocks, faults, reconnect, kill switch và daily reconciliation | Theo hợp đồng phiên; không gọi replay hồi cứu là forward |
| Sau đó | Lựa chọn sản phẩm tương lai | Quyết định riêng: trợ lý tín hiệu hay tiếp tục nghiên cứu | Giao dịch thật cần yêu cầu, kế hoạch và phê duyệt mới |

## 2. Quy tắc chọn việc

Hoàn tất một câu hỏi có thể bác bỏ trước khi mở thêm chiến lược. Dùng cache/fixture hiện có cho kiểm tra chức năng; chỉ mở rộng dữ liệu khi câu hỏi nghiên cứu cần. Không yêu cầu dữ liệu “hoàn hảo” để chứng minh phần mềm chạy được, nhưng cũng không dùng fixture để chứng minh hiệu suất thị trường.

Với Synthesized, ưu tiên xác minh và phân rã PnL theo từng nhánh tín hiệu/regime trước tối ưu exits, hạ phí hoặc thêm AI. So sánh bản tổng hợp với từng baseline cùng dataset, vốn, rủi ro và chi phí.

Với ORB hoặc ETH–BTC, giữ nguyên kết quả âm/no-trade. Thay tham số sau khi đọc kết quả là thí nghiệm mới trên dữ liệu đã xem; phải ghi selection history.

## 3. Hợp đồng tối thiểu của một task tiếp theo

- Một mục tiêu, một phạm vi file và một người chịu trách nhiệm; ghi dependency và giới hạn runtime/network.
- Base SHA, branch, config/data/model identity, giả thuyết và điều kiện dừng.
- Test/câu lệnh tái hiện, đầu ra cần giữ và reviewer/tester độc lập nếu là gate.
- Kết quả tách phần mềm, tính hợp lệ thí nghiệm và kinh tế; ghi failures/skips/network chưa chạy.
- Sau push kiểm main trên GitHub và checkout chính; không reset công việc chưa commit của chat khác.

Lượt cập nhật tài liệu này không chạy thêm backtest, không sửa strategy/risk, không kích hoạt automation hoặc paper session.
