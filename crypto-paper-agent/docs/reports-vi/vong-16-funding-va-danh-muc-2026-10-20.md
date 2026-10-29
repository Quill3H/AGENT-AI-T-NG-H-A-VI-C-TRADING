# Vòng 16: ăn funding ở ngưỡng lãi ngân hàng và danh mục ba cách (2026-10-20)

Chỉ giao dịch giấy. Kết quả do mình tự chạy, chưa có người kiểm tra độc lập (AUTHOR_REPORTED).

## Thử gì
- **K1:** mua spot, bán khống perp cùng lượng trên BTC/ETH/SOL. Chỉ mở khi funding cho lãi từ 6%/năm (bằng lãi ngân hàng).
- **K2:** như K1 nhưng ngưỡng 10%/năm.
- **M2:** một phần ba K1, một phần ba theo xu hướng C1 (10 đồng lớn), một phần ba giao dịch cặp P1.

## Kết quả giai đoạn thử (2021–2023)
| Cách | Lãi 3 năm | Sụt vốn sâu nhất | Lãi trung bình/tháng | 2022 |
|---|---|---|---|---|
| K1 | +14,5% | 3,4% | +0,38% | −2,7% |
| K2 | +15,6% | 3,2% | +0,40% | −2,2% |
| M2 rủi ro 5% (được chọn) | +67,9% | 11,1% | +1,45% | −3,8% |

## Kiểm tra lại trên 2024 – 09/2026 (dữ liệu đã từng xem)
| | Lãi | Sụt vốn sâu nhất | Tỉ lệ thắng | Lãi trung bình/tháng | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| M2 | **+12,2%** (khoảng 4,2%/năm) | 8,3% | 22,9% | +0,35% | +12,9% | −0,2% | −0,5% |
| M2, phí gấp đôi | +5,2% | 10,9% | 20,8% | +0,15% | +11,1% | −2,9% | −2,5% |

Lãi trên đã trừ phí 0,05% + trượt giá 0,03% mỗi chiều và funding.

## Kết luận thật
- **M2 thua gửi ngân hàng** (4,2% so với 5,9% mỗi năm). Toàn bộ lãi đến từ năm 2024; năm 2025 và 2026 đều lỗ nhẹ.
- Ăn funding một mình chỉ khoảng 5%/năm, gần bằng ngân hàng nhưng có rủi ro sàn.
- Kết hợp ba cách giúp sụt vốn giảm mạnh (C1 một mình sụt 19,6%, M2 chỉ 8,3%) nhưng lãi cũng giảm theo.
- Không đưa M2 vào chạy giấy tuần tới: phần xu hướng (C1) và cặp (P1) đã có sẵn, còn phần funding cần dữ liệu spot mà kho dữ liệu chạy tiếp chưa có.
