# Áp dụng sơ đồ "AI Trading System – Full Working Pipeline" vào dự án (2026-10-23)

AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Paper-only. Không tiêu dữ liệu final, không đổi v1, kết luận vòng 18 vẫn NO_TRADES.
Đây là phụ lục cho thiết kế học máy `thiet-ke-bang-chung-hoc-may-2026-10-23.md` (nhánh `claude/project-thread-secv2t`). Mọi ràng buộc ở đó giữ nguyên: tối đa 24 cấu hình, Deflated Sharpe, PBO, mốc C1 và 5,9%/năm, forward paper là bằng chứng duy nhất (chủ dự án đã bỏ ALGO/VET/SAND).

## Ánh xạ từng khối

| Khối trong sơ đồ | Trong dự án | Quyết định |
|---|---|---|
| 1. Dữ liệu Binance | Có: Binance Vision (lịch sử) + ccxt công khai không key (gần hiện tại), funding, OI BTC | Giữ |
| 1. Yahoo Finance, NSE, Zerodha | Không có | **Loại.** Ngoài phạm vi (cổ phiếu Ấn Độ). Zerodha là API đặt lệnh thật, trái AGENTS.md. Yahoo không có perp/funding Binance |
| 2. Chỉ báo, mẫu hình, xu hướng, biến động | Có: `indicator_suite.py`, `src/features/` | Giữ. Đã thêm test recursive (`389d3d8`); 2 chỉ báo chưa hội tụ được ghi lại |
| 3. Ensemble 6 mô hình dự báo thống kê | Chưa có | **Chỉ thêm dạng đặc trưng**, không thành mô hình riêng. Naive, EMA drift, mean reversion, AR(1) có thể nằm trong bộ "30 đặc trưng" (một cấu hình, không tăng K). Holt và hồi quy tuyến tính trên giá gần như trùng EMA/momentum nên bỏ. Dự báo giá đúng không có nghĩa là lệnh có lãi (sơ đồ cũng tự nói vậy) |
| 4. 5 mạng nơ-ron | Không | **Loại.** Theo đếm mẫu, mạng nơ-ron cần khoảng 10⁵ mẫu độc lập, dự án có khoảng 2.300 (hướng giá) đến 28.500 (tương đối giữa các coin) |
| 4. Hồi quy logistic + cây tăng cường | Đã có trong thiết kế học máy | Giữ. Trung bình xác suất của hai mô hình ("ensemble voting") được phép, nhưng tính là **một cấu hình** trong 24 |
| 4. Calibration xác suất | Chưa có | **Đã thêm** `fit_isotonic`, Brier, ECE, bảng độ tin cậy. Chỉ fit trên 20% cuối của cửa sổ huấn luyện (có purge), không fit trên dữ liệu kiểm tra |
| 5. Ngưỡng xác suất | Chưa có | **Đã thêm** `break_even_probability`: chỉ vào lệnh khi xác suất đã calibrate vượt ngưỡng hoà vốn sau phí (khoảng 52,6% với nhãn B). Biên thêm là tham số đăng ký trước, không dò |
| 5. Kiểm tra bất đồng giữa các mô hình | Chưa có | Thêm vào thiết kế: bỏ tín hiệu khi \|p_logistic − p_cây\| > 0,15. Giá trị cố định trước, không tính là lần thử riêng nếu không đổi |
| 5. R:R, phí, giới hạn rủi ro, chế độ chiến lược | Có: `risk/`, circuit breaker, kill switch, trần 2 lần vốn | Giữ |
| 6. Paper engine | Có: `paper_broker.py` (phí, trượt giá, funding, thanh lý theo bracket) | Giữ. Thêm hook ghi sổ lệnh (`d970fdf`) để đo trượt giá thật khi forward |
| 7. Kết quả lệnh, bộ nhớ học | Có: ledger (bài học, dữ liệu đã tiêu, giờ thêm `variants_tried`/`fold_scores`) | Giữ |
| 7. Scorecard | Chưa có | **Đã thêm** `scorecard()`: số ngày, số lệnh, lợi nhuận năm, Sharpe, PSR, DD, Brier, ECE, tỷ lệ đúng so với ngưỡng hoà vốn, loại dữ liệu |
| 7. Champion/challenger, promote/rollback | Chưa có | **Đã thêm** với ngưỡng bằng số (bên dưới) |
| 7. Dashboard, báo cáo | Có: `web-preview/`, báo cáo `src/report/` | Giữ. Scorecard có thể hiển thị sau, chưa làm |
| "AI học" bước 4: cập nhật learner từ kết quả paper | — | **Có điều kiện.** Huấn luyện lại chỉ theo lịch 30 ngày đã khoá, không theo kết quả. Dữ liệu forward đã dùng để chấm thì được đưa vào huấn luyện lần sau, nhưng không bao giờ chấm lại chính mô hình đó |

## Champion/challenger: ngưỡng đăng ký trước (`PromotionRules`)

- Champion ban đầu là **"không mô hình" (giữ tiền, NO_TRADES)**.
- Challenger chỉ được xét trên **dữ liệu forward paper sau ngày khoá**. Dữ liệu dev/walk-forward không bao giờ dùng để promote.
- **Promote** khi đạt tất cả:
  - ít nhất 180 ngày và 100 lệnh;
  - PSR(SR\* = 0) ≥ 0,95;
  - lợi nhuận năm ≥ 5,9% và cao hơn champion (nếu champion là một mô hình);
  - DD ≤ 30% và ≤ 1,25 × DD của champion (nếu champion là một mô hình);
  - ECE ≤ 0,05;
  - tỷ lệ đúng ≥ ngưỡng hoà vốn sau phí;
  - cách lần promote trước ít nhất 90 ngày.
- **Rollback** (về champion trước hoặc về giữ tiền) khi có một trong các điều:
  - DD > 1,5 × DD ngoài mẫu ở dev;
  - sau 180 ngày mà PSR < 0,05;
  - ECE > 0,10 (calibration trôi);
  - dữ liệu lỗi.
- Mỗi challenger tính thêm một lần thử vào ngân sách K và vào `ledger.variants_tried`.
- Các ngưỡng này khớp cổng P trong thiết kế. Đổi ngưỡng là một nghiên cứu mới, phải đăng ký trước khi có challenger.

## Đã thêm vào mã

- `src/research/model_governance.py`: hàm thuần, không huấn luyện mô hình, không đọc dữ liệu thị trường, không đặt lệnh.
- `tests/test_model_governance.py`: 7 test offline trên dữ liệu tổng hợp.
- Chưa thêm scikit-learn (bước 1 của thiết kế học máy mới cần).

## Không làm

Không huấn luyện mô hình nào, không chạy dev, không mở dữ liệu final, không đổi v1, không dùng mạng nơ-ron, không dùng Yahoo/NSE/Zerodha.
