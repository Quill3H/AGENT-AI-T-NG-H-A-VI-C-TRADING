# Vòng 5: thử các phong cách trade bạn gửi (2026-10-17)

Đây là **giao dịch giấy**: tài khoản 10.000$, đòn bẩy 2x, margin cô lập, luôn có stop-loss. Phí được tính 0,05% mỗi chiều, cộng trượt giá 0,03%. Mọi con số do tôi tự chạy và **chưa có người kiểm tra độc lập**. Code nằm ở [PR nháp #7](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/7), nhật ký ở `crypto-paper-agent/docs/research/2026-10-17-trading-styles.md`.

## 1. Kết luận ngắn

- **Scalping thua lỗ ở mọi khung thời gian** (1 phút, 5 phút, 15 phút, 1 giờ), sau khi đã tính phí. Có cách thắng tới 56% số lệnh mà vẫn mất 77–94% tiền, vì phí và mức cắt lỗ rộng hơn mức chốt lời đã ăn hết phần lãi.
- Cách tốt nhất là **swing 4 giờ, vào lệnh khi giá hồi về EMA20 theo xu hướng EMA50/EMA200**. Ở rủi ro 1–2% mỗi lệnh, cách này lãi nhẹ trên dữ liệu bot chưa thấy, nhưng vẫn có năm lỗ.
- Ở rủi ro 10%, cách này lỗ: tài khoản tăng mạnh năm 2021 rồi sụt 90% từ đỉnh.
- **Mục tiêu 20–50% mỗi tháng vẫn không đạt.** Ở rủi ro 1–2%, không tháng nào lãi tới 20%.

## 2. Các cách đã thử (chọn trên dữ liệu 2021–2023, BTC/ETH/SOL)

Cột lãi/lỗ và sụt sâu nhất là ở mức rủi ro 2% mỗi lệnh.

| Phong cách | Cách | Lãi/lỗ | Sụt sâu nhất | Tỷ lệ thắng | Năm lỗ |
|---|---|---|---|---|---|
| **Swing 4h** | **Giá hồi về EMA20 theo xu hướng (được chọn)** | **+80%** | **13,6%** | 26% | **không** |
| Swing ngày | Nến Nhật (engulfing, hammer) ở vùng hỗ trợ/kháng cự | −12% | 13,6% | 27% | 2021, 2023 |
| Swing 4h | Wyckoff spring/upthrust, có lọc khối lượng | +1% | 8,8% | 36% | 2023 |
| Day trade 1h | Phá vùng giá 4 giờ đầu ngày | −31% | 40% | 43% | 2022, 2023 |
| Day trade 15m | Giá lấy lại đường VWAP trong ngày | −51% | 71% | 38% | cả 3 năm |
| Scalp 5m | EMA9 cắt EMA21 | −46% | 46% | 40% | cả 3 năm |
| Scalp 5m | Bollinger đảo chiều | −39% | 40% | 37% | cả 3 năm |
| Scalp 15m | Bollinger đảo chiều | −49% | 50% | 33% | cả 3 năm |
| Scalp 15m | RSI(2) hồi, chốt lời nhanh | −94% | 94% | **55%** | cả 3 năm |
| Scalp 1h | Bollinger đảo chiều | −27% | 28% | 33% | cả 3 năm |
| Scalp 1h | RSI(2) hồi, chốt lời nhanh | −77% | 79% | **56%** | cả 3 năm |
| Scalp 1 phút (thử quý 1/2023) | EMA cắt / Bollinger, rủi ro 1% | −5% / −7% sau 3 tháng | | 49% / 34% | |

Vì scalp 1 phút đã lỗ ngay trong lần chạy thử, tôi không tải thêm dữ liệu 1 phút.

## 3. Kiểm tra cuối cho cách được chọn (chạy một lần sau khi đã khoá)

| Bài kiểm tra | Rủi ro/lệnh | 10.000$ thành | Lãi/lỗ | Sụt sâu nhất | Tháng ≥20% |
|---|---|---|---|---|---|
| A: 4 đồng chưa từng dùng (ETC, ATOM, NEAR, FIL), 2021-01 → 2026-09 | 1% | 10.872$ | +8,7% | 11,9% | 0/69 |
| A | 2% | 11.492$ | +14,9% | 24,3% | 0/69 |
| A | 10% | 7.739$ | −22,6% | 90,2% | 6/69 |
| A, phí ×2 | 2% | 9.950$ | −0,5% | 31,8% | 0/69 |
| B: BTC/ETH/SOL, 2024-01 → 2026-09 | 1% | 10.349$ | +3,5% | 5,7% | 0/33 |
| B | 2% | 10.649$ | +6,5% | 10,7% | 0/33 |
| B | 10% | 9.076$ | −9,2% | 40,0% | 3/33 |

Lãi/lỗ từng năm ở rủi ro 2%:
- **A:** 2021 +20,9%, 2022 +10,4%, 2023 +1,8%, 2024 −6,8%, 2025 −10,0%, 2026 +0,8%.
- **B:** 2024 +5,5%, 2025 −3,0%, 2026 +4,0%.

Lãi/lỗ hằng tháng trên BTC/ETH/SOL (bài B, rủi ro 2%, %):

| | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024 | −1,3 | +5,4 | +0,8 | −0,5 | −3,6 | −1,2 | +1,3 | +0,4 | +0,3 | +0,4 | +5,6 | −1,9 |
| 2025 | −2,9 | +1,9 | −0,9 | −1,3 | +2,6 | −2,8 | +5,3 | −0,2 | −2,9 | −2,8 | +5,6 | −4,0 |
| 2026 | +2,7 | +3,0 | −3,3 | −2,1 | +0,8 | +5,9 | −3,7 | +1,5 | −0,4 | | | |

## 4. Những điều cần biết

- **Tỷ lệ thắng cao không có nghĩa là có lãi.** Cách scalp RSI(2) thắng 55–56% số lệnh nhưng vẫn lỗ nặng. Mỗi lệnh chốt lời nhỏ, cắt lỗ lớn hơn, và mất khoảng 0,16% phí cho mỗi lệnh mua và bán.
- **Ở rủi ro 10%, scalp gần như không được vào lệnh.** Với stop-loss rất gần, muốn chịu rủi ro 10% thì lệnh phải lớn hơn 2 lần vốn, mà giới hạn an toàn không cho phép. Tôi giữ nguyên giới hạn này.
- **Đòn bẩy 5x** vẫn bị hệ thống an toàn chặn, vì giá thanh lý quá gần stop-loss, nên mọi lần thử dùng 2x.
- Cách được chọn là ứng viên đáng theo dõi nhất từ trước đến nay ở rủi ro thấp. Nhưng lãi nhỏ, dao động lớn, và khoảng tin cậy của lãi trung bình mỗi lệnh vẫn chứa 0. Vì vậy chưa thể nói nó có lợi thế thật.

## 5. Bước tiếp theo tôi đề xuất

Chạy cách swing EMA pullback 4h trên giấy với dữ liệu thời gian thực trong vài tháng, ở rủi ro 1–2%. Chỉ cách này mới cho bằng chứng mà backtest không làm giả được.
