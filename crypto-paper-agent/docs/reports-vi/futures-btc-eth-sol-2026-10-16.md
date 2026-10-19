# Trade futures BTC, ETH, SOL: kết quả (2026-10-16)

Tất cả là **giao dịch giấy** với tài khoản 10.000$, chia đều 3 phần cho BTC, ETH, SOL. Bot chỉ dùng nến đã đóng, nên không nhìn trước được nến. Mọi con số dưới đây do tôi tự chạy và **chưa có người kiểm tra độc lập**.
Code nằm ở [PR nháp #7](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/7). Nhật ký đầy đủ ở `crypto-paper-agent/docs/research/2026-10-16-futures-search.md`.

## 1. Kết luận ngắn

- **Mục tiêu 20–50% mỗi tháng không đạt được.** Trong 60 tháng từ 2021 đến 2025, ở mức rủi ro an toàn hiện tại, chưa có tháng nào lãi tới 20%. Tháng tốt nhất chỉ được +11%.
- Chiến lược tốt nhất tôi tìm được lãi **+53%** sau 5 năm, tức trung bình khoảng 0,7% mỗi tháng. Mức sụt sâu nhất là 10%.
- Tuy vậy, chiến lược này lãi tốt ở giai đoạn 2021–2023 rồi **lỗ nhẹ ở 2024–2025** (−1,7%). Vì không chứng minh được là hiệu quả kéo dài, nên theo luật bạn đặt ra thì nó **thất bại**.

## 2. Cách tôi làm

1. Tôi ghi luật chọn chiến lược lên GitHub trước khi chạy, để không thể sửa luật sau khi đã xem kết quả.
2. Tôi thử 6 chiến lược trên dữ liệu 2021–2023:

   | Chiến lược | Lãi/lỗ 2021–2023 | Sụt sâu nhất |
   |---|---|---|
   | Theo xu hướng (code cũ) | +4,6% | 11,4% |
   | Breakout (code cũ) | −16,9% | 17,5% |
   | **Donchian ngày 20/10** (được chọn) | **+60,4%** | **8,9%** |
   | Donchian ngày 55/20 | +48,8% | 10,2% |
   | Donchian 4 giờ 20/10 | +20,3% | 13,8% |
   | Donchian 4 giờ 55/20 | +37,5% | 10,8% |

   "Donchian" nghĩa là: khi giá vượt đỉnh 20 ngày gần nhất thì mua (long), khi thủng đáy 20 ngày thì bán khống (short). Bot thoát lệnh khi giá đi ngược lại qua mốc 10 ngày. Mỗi lệnh luôn có stop-loss.

3. Tôi khoá lựa chọn, rồi mới mở dữ liệu 2024–2025 để kiểm tra:

   | Giai đoạn | Tiền cuối | Lãi/lỗ | Sụt sâu nhất | Tháng lãi ≥20% | Tháng lỗ |
   |---|---|---|---|---|---|
   | 2024–2025 (bot chưa từng thấy) | 9.834$ | −1,7% | 8,3% | 0/24 | 15 |
   | Cả 2021–2025 | 15.332$ | +53,3% | 10,0% | 0/60 | 30 |
   | Cả 2021–2025, phí ×2 | 14.882$ | +48,8% | 10,6% | 0/60 | 31 |

   Phần lớn tiền lãi đến từ SOL (riêng phần SOL lãi +114%). Từ năm 2024 trở đi, chiến lược này gần như hết hiệu quả.

## 3. Nếu tăng rủi ro thì sao? (chỉ để xem, chưa áp dụng)

Hiện tại mỗi lệnh chỉ chịu rủi ro 2% vốn. Tôi thử tăng mức này lên, giữ nguyên các giới hạn an toàn còn lại:

| Rủi ro mỗi lệnh | Tiền cuối 2021–2025 | Lãi TB/tháng | Tháng ≥20% | Sụt sâu nhất | 2024 / 2025 |
|---|---|---|---|---|---|
| 2% (hiện tại) | 15.332$ | +0,7% | 0/60 | 10% | −1% / −3% |
| 5% | 26.665$ | +1,7% | 2/60 | 25% | −5% / −9% |
| 10% | 53.271$ | +2,8% | 7/60 | 44% | −16% / −19% |

Kết luận từ bảng: tăng rủi ro thì lãi tăng ở những năm thuận lợi, nhưng lỗ cũng tăng tương ứng ở những năm xấu. Ngay cả ở mức 10%, chỉ có 7/60 tháng đạt 20%, và tài khoản có lúc mất gần một nửa giá trị so với đỉnh. Muốn có 20–50% **mỗi tháng đều đặn** thì phải dùng mức rủi ro gần như chắc chắn cháy tài khoản.

Tôi cũng thử dùng đòn bẩy 5x, nhưng hệ thống an toàn của bot đã từ chối mọi lệnh, vì khi đó giá thanh lý nằm quá gần stop-loss. Đây là hành vi đúng.

## 4. Mục tiêu tôi đề xuất

- **Thực tế:** 2–3% mỗi tháng (khoảng 25–40% mỗi năm), chấp nhận có lúc tài khoản sụt khoảng 20–25%.
- 20–50% mỗi tháng chỉ có thể xảy ra trong vài tháng thị trường cực mạnh (ví dụ SOL năm 2021). Không thể duy trì mức đó liên tục.

## 5. Lỗi đã sửa thêm trong lần này

- Bot bị dừng giữa chừng khi giữ một lệnh long đang lãi lâu (SOL năm 2021): phí funding làm hụt ký quỹ, và phần tính giá thanh lý báo lỗi sai. Đã sửa và có test kiểm tra.
- Bot giờ chạy được trên cả 3 đồng, và báo cáo kết quả theo từng tháng (số tháng ≥20%, số tháng lỗ, tháng tệ nhất, tài khoản có từng mất một nửa hay không).
- Dữ liệu ETH và SOL đã được kiểm tra checksum. 5 ngày SOL bị thiếu trong file tháng đã được vá bằng file ngày, cũng có checksum.
- Test: 444 qua, 4 bỏ qua, 5 cần mạng nên chưa chạy.

## 6. Bước tiếp theo

Dữ liệu 2024–2025 giờ đã được dùng để kiểm tra, nên không thể dùng lại làm bài kiểm tra "chưa thấy". Nếu thử phương pháp mới, tôi sẽ dùng 9 tháng đầu năm 2026 làm bài kiểm tra cuối mới.

Các hướng đáng thử là những cách vẫn chạy được khi thị trường đi ngang như 2024–2025:
- kết hợp lệnh theo xu hướng với lệnh ăn phí funding (cách cũ, năm nào cũng lãi);
- lọc thị trường: chỉ vào lệnh khi xu hướng đủ mạnh.

## 7. Vòng 2: rủi ro 10% (bạn chọn) và kết hợp với lệnh ăn phí funding

Bạn chọn rủi ro 10% mỗi lệnh. Mức này chỉ áp dụng cho giao dịch giấy, và mọi giới hạn an toàn khác vẫn giữ nguyên.
Tôi ghi luật chọn trước khi chạy, dùng 2021–2025 để chọn, và để dành 9 tháng đầu năm 2026 làm bài kiểm tra bot chưa thấy.

| Cách | 10.000$ thành (2021–2025) | Sụt sâu nhất | Năm lỗ |
|---|---|---|---|
| Chỉ ăn phí funding, 3 đồng | 12.865$ (+29%) | 2,9% | không có |
| Nửa trade xu hướng 10% + nửa ăn phí | 33.068$ (+231%) | 38,5% | 2024 −13%, 2025 −15% |
| Chỉ trade xu hướng 10% | 53.271$ (+433%) | 44,4% | 2024 −16%, 2025 −19% |

Theo luật đã ghi trước, cách được chọn là **chỉ ăn phí funding**, vì đó là cách duy nhất không có năm nào lỗ.

Kiểm tra trên năm 2026 (bot chưa thấy):
- **Chỉ ăn phí funding:** 0 lệnh. Phí funding năm 2026 chưa lần nào lên tới mức 15%/năm để vào lệnh, nên tiền giữ nguyên 10.000$. Bài kiểm tra này chưa đủ để kết luận.
- **Trade xu hướng 10% (chỉ để tham khảo):** 10.000$ thành 11.536$ (+15%) sau 9 tháng. Có lúc tài khoản sụt 26,6%. Lãi lỗ từng tháng dao động từ −15% đến +14%, và không tháng nào đạt +20%.

Ý nghĩa: trade futures rủi ro 10% có thể lãi nhanh ở năm thuận lợi. Nhưng nó lỗ hai năm liền (2024 và 2025), dao động rất mạnh, và 9 tháng dữ liệu năm 2026 là quá ngắn để chứng minh hiệu quả.
