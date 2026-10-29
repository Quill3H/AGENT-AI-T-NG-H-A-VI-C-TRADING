# Báo cáo bổ sung kiểm tra độ bền chiến lược

Ngày: 2026-10-26

Nhánh: `codex/research-qa-hardening`

Mã tính năng: `e51dcd8`

Mã sửa sau review: `58a8370`, `2d931ea`

## Mục tiêu

Bổ sung các câu hỏi mà tổng lợi nhuận và max drawdown không trả lời được: chiến lược nằm dưới đỉnh bao lâu, hồi phục mất bao lâu, có thắng random entry không, có chỉ hưởng lợi từ chiều chung của thị trường không, và lợi nhuận có tập trung vào vài giai đoạn hay không.

## Thay đổi

- Báo cáo drawdown sâu nhất: đỉnh, đáy, ngày hồi phục, số ngày giảm, số ngày từ đáy tới hồi phục và tổng thời gian underwater.
- Báo cáo episode underwater dài nhất, kể cả episode vẫn chưa hồi phục ở cuối dữ liệu.
- Giữ riêng đường equity đầy đủ để tính drawdown cuối kỳ; không thay đỉnh trước đó bằng equity quyết toán.
- Tính mức tập trung gross positive equity change vào top 1 và top 3 tháng/năm.
- So sánh candidate với phân phối random bằng empirical percentile và finite-sample exceedance probability; bắt buộc khai báo metric cao hơn hay thấp hơn là tốt hơn.
- Báo cáo beta, correlation và return của chiến lược trong kỳ benchmark tăng, giảm và đi ngang.
- Báo cáo return, mean return và win rate cho từng regime causal do runner cung cấp.

## Kiểm thử và review

- Bộ kiểm thử trọng tâm robustness/report: 30 đạt.
- Toàn bộ kiểm thử offline: 726 đạt, 4 bỏ qua, 5 test mạng không chạy.
- Review độc lập đã tái hiện và dẫn tới sửa: headline drawdown bỏ qua vốn đầu kỳ; placebo đảo kết luận với metric lower-is-better; bỏ mất kỳ benchmark đi ngang; và xóa nhầm peak trước settlement.
- Review độc lập cuối cùng trên `edb6104..2d931ea`: không còn lỗi chặn; xác nhận settlement path và toàn bộ lỗi toán học/báo cáo trước đó đã đóng.

## Giới hạn

Các run cũ chưa tự có thêm bằng chứng kinh tế. Chúng phải được chạy lại từ dữ liệu và cấu hình đã khóa để sinh drawdown duration, concentration, placebo, benchmark và regime blocks. Random entry vẫn phải dùng cùng universe, thời gian giữ, sizing, stop, target, phí, trượt giá, funding và risk gates. Regime phải được biết tại thời điểm quan sát; nhãn tạo từ tương lai không hợp lệ.
