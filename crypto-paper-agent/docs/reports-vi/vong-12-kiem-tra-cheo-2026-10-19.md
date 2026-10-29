# Kiểm tra chéo vòng 12: A2 và C1 (2026-10-19)

Có ba bên kiểm tra độc lập, đều là phiên Claude riêng biệt và không dùng lại code của tôi:

- **Bên 1 và bên 2:** mỗi bên tự viết lại A2 và C1 chỉ từ mô tả luật bằng lời, rồi chạy lại trên cùng dữ liệu. Hai bên chỉ được xem các số cần đối chiếu sau khi đã có số của riêng mình.
- **Bên 3:** soát code của tôi, đồng thời tự tính tay hai lệnh đầu tiên từ dữ liệu thô.

## 1. Kết quả chính

- **Số liệu khớp.** Cả hai bên độc lập ra cùng kết quả với tôi, chênh tối đa khoảng 1%, ở cả 7 lần chạy. Điều kiện là luật "lỗ quá 5% trong 24 giờ thì dừng" chỉ tính **lỗ đã chốt**, đúng như hệ thống đang làm.
- **Không tìm thấy lỗi** nhìn trước dữ liệu tương lai, và không có lỗi về phí hay funding. Bên 3 tính tay lệnh đầu tiên khớp từng xu.
- **Có một điểm quan trọng.** Nếu luật dừng 5% tính cả lỗ chưa chốt (cách hiểu chặt hơn), kết quả giảm mạnh:

| Lần chạy | Như hệ thống (chỉ lỗ đã chốt) | Nếu tính cả lỗ chưa chốt |
|---|---|---|
| A2 rủi ro 5%, 2021–2023 | +488% | +225% |
| C1 rủi ro 5%, 2021–2023 | +318% | +176% |
| A2 rủi ro 5%, 2024–2026 | +18,6% | +14,5% |
| C1 rủi ro 5%, 2024–2026 | +17,8% | +26,6% |

  Theo cách tính chặt hơn này, A2 thua C1 ở giai đoạn 2024–2026. Vì vậy, lợi thế của A2 so với C1 **chưa chắc chắn**.

## 2. Ba điều bên soát code phát hiện

1. **Mức rủi ro thật thấp hơn tên gọi.** Sau 3 lệnh thua liên tiếp, hệ thống tự giảm rủi ro còn một nửa. Muốn quay lại mức cũ thì phải thắng 3 lệnh liên tiếp, mà điều này hiếm khi xảy ra khi tỷ lệ thắng chỉ khoảng 27%. Kết quả là khoảng 95% lệnh của bản "5%" thật ra chỉ rủi ro 2,5%, và bản "2%" chỉ rủi ro 1%.
2. **Lãi dồn vào rất ít lệnh.** Một lệnh SOL (15/10 đến 17/11/2023, giá từ 21,9$ lên 58,2$) mang lại khoảng 57% toàn bộ lãi của A2 ở giai đoạn 2021–2023. Hai lệnh lớn nhất chiếm khoảng 78%.
3. **Sụt vốn có thể bị tính thấp hơn thực tế.** Sụt vốn được đo theo giá đóng cửa nến 15 phút, không tính giá thấp nhất trong nến. Ngoài ra, khoảng 19–20 tín hiệu SOL bị bỏ vì stop quá xa giá thanh lý. Đây là một bộ lọc ngầm.

## 3. Ý nghĩa

- Các con số tôi đã báo là **đúng với cách hệ thống đang tính**, và có hai bên độc lập xác nhận.
- Nhưng kết quả **phụ thuộc nhiều vào cách tính luật dừng lỗ trong ngày và vào vài lệnh rất lớn**. Đây không phải bằng chứng là có lãi ổn định.
- Bằng chứng thật vẫn phải đến từ chạy giấy trên dữ liệu mới (từ 18/10).

Đã ghi vào sổ học hỏi. File mô tả luật đã được bổ sung phần sửa: [codex-kiem-tra-cheo-vong-12.md](/mnt/project-files/repo-analysis/codex-kiem-tra-cheo-vong-12.md).
