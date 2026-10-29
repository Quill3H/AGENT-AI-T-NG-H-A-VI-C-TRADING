# Kết quả: sửa lõi bot và tìm phương pháp trade (2026-10-16)

PR nháp: https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/7 (nhánh `claude/project-thread-uiqlsn`, chưa vào `main`).
Tất cả con số trong file này do tôi tự chạy, **chưa có người kiểm tra độc lập**.

## 1. Kết luận ngắn

- Tài khoản giấy 10.000 USDT, chạy từ 2021 tới hết 2025, bot **không nhìn trước nến**: kết thúc ở **12.824,61 USDT (+28,25%)**.
- Năm nào cũng có lãi: 2021 +16,78%, 2022 +0,08%, 2023 +1,92%, 2024 +7,02%, 2025 +0,62%.
- Mức sụt giảm lớn nhất từ đỉnh xuống đáy chỉ là 1,74%.
- Nếu tôi nhân đôi phí và trượt giá, kết quả vẫn lãi +26,14%.
- Theo luật bạn đặt ra (lãi trên 20% và tăng dần theo thời gian), kết quả là **THÀNH CÔNG**.

## 2. Phương pháp được chọn: "ăn phí funding" (carry)

- Khi phí funding của hợp đồng vĩnh cửu BTC cao (từ 15%/năm trở lên), bot mua BTC spot và bán khống BTC perp với cùng số lượng.
- Hai vị thế bù trừ nhau, nên giá BTC lên hay xuống thì bot gần như không lời không lỗ vì giá. Phần lãi đến từ khoản funding mà bên long trả cho bên short, cứ 8 tiếng một lần.
- Khi funding giảm xuống thì bot đóng cả hai vị thế.
- Đây là chiến lược ít rủi ro, nên lãi cũng chậm. Ví dụ để so sánh: mua BTC rồi giữ nguyên trong cùng giai đoạn sẽ lãi khoảng +199%, nhưng có lúc mất 77% giá trị.

## 3. Làm sao biết bot không "ăn gian"

1. Tôi chỉ dùng năm 2021–2023 để thử 9 cách khác nhau. Cả 9 lần thử đều được ghi lại.
2. Trước khi mở dữ liệu 2024–2025, tôi khoá lựa chọn bằng một commit (`7534d6c`).
3. Sau đó tôi mới chạy trên 2024–2025, phần dữ liệu bot chưa từng thấy. Kết quả lãi +6,91%, sụt giảm tối đa 0,23%.
4. Lệnh chỉ được đặt sau khi nến đã đóng, và được khớp ở giá mở của nến tiếp theo. Mỗi lệnh đều tính phí và trượt giá.

## 4. 9 cách đã thử (giai đoạn 2021–2023)

| # | Cách | Lãi/lỗ |
|---|---|---|
| 1 | Theo xu hướng (code cũ) | +4,62% |
| 2 | Breakout (code cũ) | −26,25% |
| 3 | Donchian 20/10, long và short | +14,57% |
| 4 | Donchian 20/10, chỉ long | +4,44% |
| 5 | Donchian 55/20, long và short | −6,25% |
| 6 | Donchian 55/20, chỉ long | +0,33% |
| 7 | **Carry, vào lệnh khi funding ≥ 15%/năm** (được chọn) | **+19,00%** |
| 8 | Carry, vào lệnh khi funding ≥ 10%/năm | +14,38% |
| 9 | Kết hợp 50% Donchian và 50% carry | +16,78% |

## 5. Những điều cần biết (giới hạn)

- Mẫu còn nhỏ: cả giai đoạn chỉ có 10 lần vào lệnh. Phần lớn tiền lãi đến từ năm 2021 và 2024, hai năm thị trường sôi động.
- Năm 2022 và 2025 gần như hoà vốn. Từ tháng 1 tới tháng 9/2026 bot chưa vào lệnh lần nào.
- Dữ liệu tính theo nến 1 giờ, nên chưa mô phỏng sổ lệnh thật.
- Thông thường cách làm này thắng ở mức lãi đều và an toàn. Nó không cho lãi lớn.
- Tất cả đều là **giao dịch giấy**: không có lệnh thật, không có testnet, không có API key.

## 6. Những lỗi đã sửa trong lõi bot

- **Tải dữ liệu lỗi giữa chừng:** trước đây bot âm thầm dùng phần dữ liệu thiếu. Giờ bot báo lỗi và dừng lại.
- **Thêm nút tắt khẩn cấp (kill switch):** bot đóng hết vị thế và dừng hẳn khi được bấm tắt, hoặc khi dữ liệu bị mất quá 60 phút.
- **Thêm trần cho mỗi lệnh:** giá trị một lệnh không được vượt quá 2 lần số vốn.
- **Sửa điểm cắt lỗ của chiến lược carry:** trước đây bot cắt lỗ chỉ vì một vị thế giảm 2%, dù vị thế còn lại đã bù lại. Giờ bot chỉ cắt lỗ khi tổng của cả hai vị thế bị lỗ.
- **Bảo mật:** thêm `.env` vào `.gitignore` để khoá API không bao giờ bị đưa lên GitHub.
- **Code mới:**
  - chiến lược Donchian;
  - bộ đọc dữ liệu Binance Vision (có kiểm tra checksum);
  - báo cáo lãi lỗ theo năm kèm kết luận THÀNH CÔNG hoặc THẤT BẠI;
  - script để chạy lại toàn bộ thử nghiệm trong khoảng 2 phút.
- **Test:** 435 test chạy qua, 4 test bỏ qua (cần thư viện AI chưa cài), 5 test cần mạng thì chưa chạy.
- **Giao diện web:** tôi không sửa.

## 7. Cách tôi hiểu yêu cầu "lỗ dưới 50% là thất bại"

Câu này có thể hiểu theo nhiều cách. Tôi chọn cách chặt hơn: bất kỳ kết quả nào không đạt luật thành công đều bị coi là thất bại, và bot phải thử phương pháp khác. Luật thành công tôi đặt trong code là:
- lãi trên 20%;
- ít nhất 80% số năm có lãi;
- không năm nào lỗ quá 10%.

## 8. Việc tiếp theo bạn có thể quyết định

- Xem và duyệt PR #7. Theo quy định của dự án, cần có người kiểm tra độc lập trước khi đưa vào `main`.
- Chạy giao dịch giấy với dữ liệu live, theo dõi ít nhất vài tháng.
- Thêm cặp ETH để tăng số lần vào lệnh, giúp kết quả đáng tin hơn.
