# Vòng 7: học từ video, cách của trader nổi tiếng, và vào 5–10 lệnh mỗi tuần (2026-10-18)

Đây là **giao dịch giấy**: tài khoản 10.000$, đòn bẩy 2x, margin cô lập, luôn có stop-loss. Phí tính 0,05% mỗi chiều, cộng trượt giá 0,03%. Mọi con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Code nằm ở [PR nháp #7](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/7), nhật ký ở `crypto-paper-agent/docs/research/2026-10-18-video-sessions.md`.

## 1. Kết luận ngắn

- **Vào nhiều lệnh hơn làm kết quả xấu đi.** Cả 8 cách đều vào được 5 lệnh mỗi tuần trở lên, nhưng sau khi trừ phí, gần như tất cả đều lỗ.
- **Các cách trong video đều lỗ** trên nến 5 phút của crypto: phá vùng London, scalp Heikin-Ashi, chạm vùng hỗ trợ/kháng cự rồi phá đỉnh gần nhất.
- Cách được khoá là swing EMA trên nến 1h, khoảng 20 lệnh mỗi tuần trên 3 đồng. Trên TRX, đồng duy nhất chưa từng dùng để kiểm tra, cách này lỗ 72% ở rủi ro 1%. Trên BTC/ETH/SOL 2024–2026, nó lỗ 26%.
- **Mục tiêu 20–50% mỗi tháng vẫn không đạt.**
- Cách duy nhất vừa vào nhiều lệnh vừa có lãi khi chạy thử là **phá biên độ của Larry Williams**: +24% trong 3 năm ở rủi ro 2%, khoảng 11 lệnh mỗi tuần. Nhưng nó lỗ ở rủi ro 1%, nên không được chọn và chưa được kiểm tra trên dữ liệu mới.

## 2. Học từ video

- Tôi lấy được toàn bộ phụ đề của video dài 7,5 giờ qua máy của bạn, vì máy chủ cloud bị chặn YouTube. Bản chép nằm ở `/mnt/project-files/research-inputs/youtube-qt55sMTiH68-transcript.txt`.
- Video dạy trade hợp đồng tương lai chỉ số Mỹ (NQ/ES) vào buổi sáng New York:
  - vẽ vùng hỗ trợ/kháng cự trên nến 4h hoặc 1h, rồi vào lệnh trên nến 1 phút khi giá phá đỉnh/đáy gần nhất;
  - scalp Heikin-Ashi theo EMA100;
  - phá vùng giá phiên London;
  - mẫu tam giác.
- Video không dạy ICT/SMC.
- Các tỷ lệ thắng trong video (75%, 44%) là do người làm video tự kiểm tra bằng tay, bên cạnh quảng cáo khoá học và quỹ của họ. Tôi không coi đó là bằng chứng.
- Có 4 phần tôi không lập trình được từ dữ liệu giá: cảm nhận vùng giá "rõ ràng", hướng đi trong ngày, tránh tin tức, và vẽ tam giác.

## 3. Cách của các trader nổi tiếng

Tôi chỉ lấy luật họ công bố trong sách, không dùng số lãi họ tự công bố:
- **Linda Raschke, "Holy Grail"** (sách *Street Smarts*, 1995): ADX trên 30, giá hồi về EMA20 rồi bật lên.
- **Larry Williams, phá biên độ** (*Long-Term Secrets to Short-Term Trading*, 1999): giá vượt giá mở cửa ngày cộng 0,6 lần biên độ hôm trước.
- **Toby Crabel, NR7** (*Day Trading with Short Term Price Patterns*, 1990): phá nến hẹp nhất trong 7 nến.

## 4. Kết quả chạy thử (BTC/ETH/SOL, 2021–2023)

| Cách | Rủi ro | Lãi/lỗ | Sụt sâu nhất | Lệnh/tuần (3 đồng) | Tỷ lệ thắng |
|---|---|---|---|---|---|
| Video: phá vùng London 5m | 1% | −68% | 69% | 11 | 31% |
| Video: phá vùng London + EMA100 | 1% | −54% | 55% | 7,5 | 30% |
| Video: scalp Heikin-Ashi 5m | 1% | −76% | 77% | 20 | 41% |
| Video: chạm vùng + phá đỉnh gần nhất | 1% | −50% | 53% | 18 | 36% |
| **Swing EMA nến 1h (được chọn)** | 1% | **−0,7%** | 28% | 21 | 21% |
| Raschke Holy Grail 1h | 1% | −36% | 37% | 8 | 49% |
| **Larry Williams phá biên độ** | 1% / **2%** | −2,8% / **+24%** | 19,5% / 19% | 11–12 | 41% |
| Crabel NR7 4h | 1% | −32% | 36% | 9 | 36% |

Luật chọn (đã ghi trước khi chạy) yêu cầu ít nhất 5 lệnh mỗi tuần và chọn ở rủi ro 1%, mức video khuyên. Không cách nào vừa đủ lệnh vừa không có năm lỗ, nên tôi chọn cách đỡ tệ nhất là swing EMA 1h.

## 5. Kiểm tra cuối (chạy một lần sau khi đã khoá)

Theo yêu cầu của bạn, tôi chỉ dùng nhóm 10 đồng lớn nhất và không tải thêm altcoin.

| Bài kiểm tra | Rủi ro | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Số lệnh | Tỷ lệ thắng |
|---|---|---|---|---|---|---|
| TRX 2021-01 → 2026-09 (chưa từng dùng) | 1% | 2.824$ | −71,8% | 77,7% | 2.165 | 18,6% |
| TRX | 2% | 1.122$ | −88,8% | 92,7% | 2.032 | 19,5% |
| TRX, phí ×2 | 1% | 560$ | −94,4% | 95,3% | 2.167 | 15,3% |
| BTC/ETH/SOL/TRX 2021–2026 (đã dùng trước) | 1% | 6.357$ | −36,4% | 51,2% | 8.574 | 19,6% |
| BTC/ETH/SOL 2024-01 → 2026-09 (đã dùng trước) | 1% | 7.371$ | −26,3% | 32,9% | 3.132 | 19,2% |
| BTC/ETH/SOL 2024–2026, x20 BTC/ETH, x5 SOL | 2% | 5.187$ | −48,1% | 56,2% | 3.098 | 19,0% |

- Trên TRX ở rủi ro 1%, 23 tháng lãi và 45 tháng lỗ.
- Bài BTC/ETH/SOL ở rủi ro 1% có 12 tháng lãi và 21 tháng lỗ. Tháng tốt nhất +7,4% (2026-08), tháng tệ nhất −5,7% (2025-12).
- Chỉ năm 2021 có lãi, vì cả thị trường tăng mạnh. Các năm sau đều lỗ.
- Ở x20/x5 với rủi ro 10%, tài khoản gần như về 0.

## 6. Sổ học hỏi (bot tự ghi lại)

- Từ vòng này, mỗi lần chạy được tự động ghi vào `crypto-paper-agent/docs/research/ledger/ledger.jsonl`. Mỗi bản ghi có cách nào, dữ liệu nào, rủi ro bao nhiêu, kết quả ra sao và commit đã khoá.
- Kết quả các vòng 1–6 đã được nhập vào sổ.
- Bản dễ đọc nằm ở `crypto-paper-agent/docs/research/ledger/LEARNING_LOG.md`, có bài học của từng vòng.
- **Chống tự lừa mình:** bot không được kiểm tra cuối lại trên dữ liệu đã dùng để kiểm tra cuối, vì như vậy là chỉnh tham số trên chính bài thi. Sổ sẽ từ chối việc đó. Bot chỉ được chạy lại khi lần trước hỏng vì lỗi cài đặt, và lần đó phải được đánh dấu rõ.
- Lỗi cài đặt đã gặp ở vòng này: TRX thiếu bảng đòn bẩy nên lần đầu không vào được lệnh nào. Tôi đã sửa, đánh dấu lần chạy đó là hỏng, và chạy lại đúng cách đã khoá.
- Bot ghi lại bài học bằng chữ, chứ không tự đổi tham số trên dữ liệu đã dùng.

## 7. Giới hạn kiểm chứng và bước tiếp theo

- Trong 10 đồng lớn nhất, giờ không còn đồng nào chưa dùng cho kiểm tra cuối từ 2021 đến 9/2026. Backtest thêm trên dữ liệu này sẽ không còn cho bằng chứng mới.
- Đề xuất của tôi:
  - Chạy giấy với dữ liệu thời gian thực cho 3 cách đáng theo dõi nhất: swing EMA 4h (vòng 5), nến tiếp diễn 4h (vòng 6) và phá biên độ Larry Williams. Dùng rủi ro 1–2%, ghi kết quả vào sổ học hỏi mỗi tuần.
  - Chỉ tăng số lệnh khi một cách đã chứng minh có lãi sau phí. Vòng này cho thấy tăng số lệnh trước sẽ làm lỗ nhanh hơn.
