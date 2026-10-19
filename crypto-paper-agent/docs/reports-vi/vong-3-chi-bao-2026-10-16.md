# Vòng 3: chiến lược futures mới, không dùng funding (2026-10-16)

Đây là **giao dịch giấy**: tài khoản 10.000$, mỗi lệnh chịu rủi ro 10% vốn theo lựa chọn của bạn, các giới hạn an toàn khác giữ nguyên. Bot không nhìn trước nến. Mọi con số do tôi tự chạy, **chưa có người kiểm tra độc lập**.
Code: [PR nháp #7](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/7). Nhật ký đầy đủ: `crypto-paper-agent/docs/research/2026-10-16-indicator-search.md`.

## 1. Kết luận ngắn

- Tôi đã thử 6 chiến lược mới, dùng các chỉ báo khác nhau. Không chiến lược nào vượt qua bài kiểm tra trên dữ liệu bot chưa thấy.
- Chiến lược thắng ở vòng chọn lãi +875% trên 2021–2023, nhưng ra ngoài thì kết quả rất khác:
  - BTC/ETH/SOL từ 2024 đến 9/2026: **lỗ −1,3%**, có lúc tài khoản sụt 38%.
  - 4 đồng bot chưa từng thấy (BNB, XRP, DOGE, ADA), 2021 đến 9/2026: lãi +126%, nhưng gần hết tiền lãi đến từ năm 2021, có lúc tài khoản sụt 47,5%, và 41/69 tháng bị lỗ.
- Mục tiêu 20–50% mỗi tháng vẫn **không đạt**: chỉ 3/69 tháng có lãi trên 20%.

## 2. Cách kiểm tra công bằng

Toàn bộ dữ liệu BTC/ETH/SOL đến 9/2026 đã được dùng ở các vòng trước. Vì vậy tôi tải thêm 4 đồng mới làm "bài thi" mà bot chưa từng thấy. Tôi ghi luật chọn lên GitHub trước khi chạy, và khoá chiến lược được chọn trước khi mở bài thi.

## 3. 6 chiến lược đã thử (BTC/ETH/SOL, 2021–2023)

| Chiến lược | Ý tưởng | Lãi/lỗ | Sụt sâu nhất | Năm lỗ |
|---|---|---|---|---|
| Động lượng | Đi theo hướng giá 30 ngày qua | +72% | 28% | không |
| RSI(2) | Mua khi giá giảm mạnh ngắn hạn trong xu hướng tăng | +4% | 24% | 2022 |
| Squeeze | Vào lệnh khi giá bung ra sau giai đoạn đi ngang hẹp | +14% | 43% | 2023 |
| Đa khung | Xu hướng ngày + phá đỉnh/đáy 4 giờ | +127% | 41% | 2021 |
| **ADX + Donchian** (được chọn) | Phá đỉnh/đáy 20 ngày, chỉ khi xu hướng mạnh (ADX > 25) | **+875%** | 32% | không |
| Supertrend | Đổi chiều theo đường Supertrend | +27% | 39% | 2022 |

Chiến lược được chọn kiếm gần hết tiền lãi từ SOL năm 2021–2023 (riêng phần SOL lãi +2.396%). Phần BTC thì lỗ.

## 4. Kết quả bài thi

| Bài thi | Tiền cuối | Lãi/lỗ | Sụt sâu nhất | Tháng ≥20% | Tháng lỗ |
|---|---|---|---|---|---|
| BTC/ETH/SOL, 1/2024–9/2026 | 9.872$ | −1,3% | 38% | 0/33 | 20 |
| BNB/XRP/DOGE/ADA, 1/2021–9/2026 | 22.597$ | +126% | 47,5% | 3/69 | 41 |
| Như trên, phí ×2 | 21.832$ | +118% | 48,5% | 3/69 | 41 |

Lãi theo năm trên 4 đồng mới: 2021 +120%, 2022 −13%, 2023 +5%, 2024 +17%, 2025 +4%, 2026 −7%.

## 5. Bài học sau 3 vòng

- Các chiến lược theo xu hướng kiếm rất nhiều tiền trong năm thị trường tăng mạnh (2021, SOL năm 2023). Ở những năm đi ngang, chúng trả lại tiền dần dần.
- Kết quả ở vòng chọn càng đẹp thì càng dễ là may mắn. +875% đã biến thành gần hoà vốn khi ra dữ liệu mới.
- Với dữ liệu 2021–2026, 20–50% mỗi tháng đều đặn là không thực tế, kể cả ở rủi ro 10% mỗi lệnh.

## 6. Bước tiếp theo nên làm

- Dữ liệu lịch sử của cả 7 đồng đã dùng hết. Cách kiểm tra trung thực duy nhất còn lại là **chạy giấy với giá thật từ bây giờ** trong vài tháng.
- Nếu bạn đồng ý, tôi sẽ cho chiến lược ADX + Donchian (hoặc chiến lược động lượng, cái ổn định hơn) chạy giấy với giá thật, rồi so với backtest.
