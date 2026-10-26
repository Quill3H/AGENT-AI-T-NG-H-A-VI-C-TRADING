# Review: ba phương pháp còn sống sau phép thử Reddit

Nguồn đầu vào là số liệu do tác giả bài viết tự báo cáo; dự án chưa có trade list, equity curve hoặc mã chạy để tái lập. Vì vậy đây là đánh giá thiết kế bằng chứng, không xác nhận các con số.

## Kết luận nhanh

1. **SPY dip rule** là ứng viên có tín hiệu ổn định nhất theo các giai đoạn, nhưng bằng chứng so với random còn yếu và thời gian hồi phục có thể tới khoảng 3,5 năm.
2. **Month-end SPY** đứng thứ hai: dương ở mọi giai đoạn nhưng suy yếu gần đây; thiếu đối chứng random cùng thời gian giữ nên chưa tách được calendar effect khỏi market drift.
3. **Residual momentum + SPY** đáng tin ít nhất: beta 1,26, giảm ngang SPY trong tháng SPY giảm, lợi nhuận tập trung vào 2020 và 2024–2026, đồng thời nhạy với survivorship bias.

Không phương pháp nào nên được chuyển nguyên xi sang perpetual crypto. Phần có giá trị cho dự án là chuẩn kiểm tra, vì cấu trúc phiên, overnight gap, universe và nguồn lợi nhuận của cổ phiếu khác thị trường crypto 24/7.

## Đọc đúng các con số

### Momentum + SPY

- Cú giảm COVID khoảng 34% hồi phục nhanh, nhưng thời gian dài nhất dưới đỉnh cũ là 1.028 ngày. Đây là rủi ro vốn và tâm lý khác hẳn một drawdown sâu nhưng ngắn.
- Thắng 50/50 danh mục random cho xác suất vượt ngẫu nhiên nhỏ nhất khoảng `1 / 51 = 1,96%` trước khi điều chỉnh số lượng ý tưởng đã thử. Với hàng trăm lần thử, kết quả này chưa đủ mạnh.
- Lợi nhuận tăng thêm xuất hiện trong tháng thị trường tăng; tháng SPY giảm thì chiến lược giảm ngang SPY. Đây là bằng chứng phần lớn lợi thế có thể là beta và mức phơi nhiễm rủi ro cao hơn.
- Kết quả giảm rõ khi đưa cổ phiếu hủy niêm yết trở lại và tập trung vào vài giai đoạn mạnh. Không chọn làm mẫu phương pháp mới.

### SPY dip rule

- Drawdown khoảng 12,7% nhìn nhẹ, nhưng có thể mất khoảng 3,5 năm mới lập đỉnh mới. Báo cáo chỉ max drawdown sẽ che mất đặc tính này.
- Thắng 78/100 lượt random chưa phải bằng chứng thống kê mạnh. Nếu 22 lượt random bằng hoặc tốt hơn, xác suất vượt một phía có hiệu chỉnh hữu hạn xấp xỉ `(1 + 22) / 101 = 22,8%`.
- Tỷ lệ thắng và lợi nhuận trung bình mỗi lệnh khá ổn định theo bốn giai đoạn là điểm tốt nhất. Tuy nhiên, luật chỉ giao dịch trên MA200 chủ yếu né bear market; cần báo cáo riêng hiệu quả khi benchmark tăng/giảm.
- 84% lợi thế đến từ overnight là đặc điểm thực thi cổ phiếu, không chuyển trực tiếp sang crypto giao dịch liên tục.

### Month-end SPY

- Drawdown khoảng 15%, bốn năm lỗ trên 34 năm và dương ở từng giai đoạn là dấu hiệu đáng nghiên cứu.
- Lợi nhuận mỗi lệnh giảm sau 2010 cho thấy edge có thể suy yếu.
- Chưa có phân phối random-entry tương ứng và chưa có thời gian hồi phục/underwater, nên bằng chứng còn thiếu hai kiểm tra quan trọng.

## Cải tiến đã đưa vào dự án

- Báo cáo peak, trough, ngày hồi phục, số ngày từ đỉnh đến đáy, số ngày hồi phục và longest underwater; episode chưa hồi phục được đánh dấu mở.
- Báo cáo tỷ trọng gross positive equity change đến từ top 1/top 3 tháng và năm.
- So sánh candidate với toàn bộ kết quả matched-random bằng empirical percentile và finite-sample exceedance probability.
- Tách return khi benchmark tăng/giảm, beta và correlation.
- Tổng hợp cùng một chuỗi return theo regime causal đã khóa trước.

Các kiểm tra này mô tả độ bền của kết quả. Chúng không thay thế dữ liệu untouched, chi phí thực tế, điều chỉnh multiple testing hoặc forward paper record.
