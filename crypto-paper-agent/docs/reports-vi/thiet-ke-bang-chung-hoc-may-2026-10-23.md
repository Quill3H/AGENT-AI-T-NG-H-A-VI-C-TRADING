# Thiết kế bằng chứng cho học máy kiểu FreqAI (2026-10-23)

Đây là bản **thiết kế đăng ký trước**, chưa có mô hình nào được huấn luyện hay chọn. Mọi con số dưới đây là **đếm dữ liệu** trên phần dữ liệu đã thấy, không phải kết quả lãi lỗ. Giao dịch giấy, Binance USDⓈ-M perpetual. AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED.

## Tóm tắt

1. **Dữ liệu lịch sử đã thấy chỉ đủ để học máy chứng minh một lợi thế khá lớn.** Với nhãn 1 ngày trên nến 4h, 20 coin trong 5,75 năm cho khoảng **28.500 mẫu độc lập nếu coi các coin độc lập, nhưng chỉ khoảng 2.300 mẫu** khi tính đến việc các coin chạy cùng nhau (tương quan ngày trung bình 0,60–0,63, nên 20 coin chỉ bằng khoảng 1,6 coin độc lập).
2. **Phí làm ngưỡng hoà vốn cao hơn nhiều người nghĩ.** Nhãn 1 ngày cần đoán đúng khoảng **52,6%** chỉ để hoà vốn sau phí và trượt giá (0,16% một vòng). Chứng minh vượt ngưỡng đó 2 điểm cần khoảng 3.900 mẫu độc lập, nhiều hơn con số 2.300 thận trọng ở trên.
3. **Nên học dự đoán lợi nhuận tương đối giữa các coin (trung lập thị trường), không học hướng giá của từng coin.** Khi trừ đi phần chung của thị trường, tương quan giữa các coin gần như bằng 0, nên số mẫu hữu dụng gần với con số lớn (khoảng 28.500).
4. **Toàn bộ dữ liệu 20 coin đã bị tiêu hoặc đã thấy**, nên chỉ dùng để phát triển. Còn hai nguồn bằng chứng mới: **ALGO, VET, SAND** (2021-01..2026-09, đã tải, chưa từng mở, chưa có trong ledger) và **dữ liệu forward từ 2026-10-18 trở đi**.
5. **Khi nào đủ bằng chứng:** nếu chủ dự án đồng ý dùng ALGO/VET/SAND làm tập final một lần, khoảng 2.100 ngày ở đó đủ phát hiện mô hình có Sharpe năm từ khoảng **0,7** trở lên. Sau đó vẫn cần forward paper: ít nhất **8–9 tháng** nếu Sharpe khoảng 2, khoảng **15 tháng** nếu 1,5, khoảng **2,7 năm** nếu 1. Nếu không dùng ba coin này thì chỉ còn forward.

## Quyết định của chủ dự án (2026-10-23 10:29 UTC, trước bước 1)

Chủ dự án chọn **không dùng ALGO/VET/SAND, chỉ chạy forward**. Vì vậy:
- Ba coin này vẫn không được mở. `guard_seen` tiếp tục chặn chúng, và chúng không vào bất kỳ bước nào của nghiên cứu học máy.
- **Cổng F (mục 8) bị bỏ.** Bước 3 (mục 9) cũng bị bỏ. Ứng viên qua cổng D đi thẳng sang cổng P (forward paper trên top-10).
- Cổng P trở thành bằng chứng duy nhất. Sau 1 năm forward, cổng P chỉ phát hiện được Sharpe năm từ 1,65 trở lên. Sau 2 năm là từ 1,16 trở lên. Muốn phát hiện Sharpe 1 thì cần khoảng 990 ngày (khoảng 2,7 năm).
- Mục 5.5, mục 8 (cổng F) và mục 10.1 bên dưới giữ nguyên để ghi lại phương án đã cân nhắc, không còn hiệu lực.

## 1. Phạm vi và những gì giữ nguyên

- **Không cài hay nhúng Freqtrade/FreqAI.** Lý do: giấy phép GPLv3, và trong Freqtrade chỉ cần đổi `dry_run=false` là thành lệnh thật, trái AGENTS.md. Khung học máy sẽ tự viết trong `crypto-paper-agent`, chỉ lấy **ý tưởng** của FreqAI:
  - nhiều khung thời gian (1h/4h/1d),
  - đặc trưng của coin dẫn dắt (BTC, ETH) làm bối cảnh,
  - nến trễ 1–3 thanh,
  - huấn luyện trên cửa sổ trượt và huấn luyện lại mỗi 30 ngày,
  - bỏ qua tín hiệu khi mẫu mới quá khác dữ liệu huấn luyện ("dissimilarity index").
- **Không lấy từ FreqAI:** học tăng cường (RL), mạng nơ-ron PyTorch, hyperopt, huấn luyện lại trong luồng chạy thật.
- **Giữ nguyên:** tham số v1 của vòng 18, kết luận NO_TRADES, cấm live/testnet/API key. Không chạy lại ma trận cũ. Không mở dữ liệu final chưa dùng.
- Trong giai đoạn thiết kế, mình chỉ chạy script **đếm** trên dữ liệu đã thấy. Script không huấn luyện mô hình nào và không ghi dòng nào vào ledger.

## 2. Dữ liệu đang có và phần đã tiêu

Theo `docs/research/ledger/LEARNING_LOG.md` và `src/research/ledger.py::spent_final_data`:

| Nhóm | Coin | Khoảng | Trạng thái |
|---|---|---|---|
| Top-10 | BTC ETH XRP BNB SOL DOGE TRX ADA LINK AVAX | 2021-01..2026-10-17 | Final đã tiêu (BTC/ETH/SOL 2021-23 là dev, cũng đã thấy) |
| 10 coin khác | ETC ATOM NEAR FIL XLM BCH UNI AAVE DOT LTC | 2021-01..2026-09 | Final đã tiêu |
| Dự trữ | ALGO VET SAND | 2021-01..2026-09 (SAND từ 2021-01-25) | **Chưa dùng**, không có trong ledger, script đếm không mở |
| Forward | mọi coin | từ 2026-10-18 | Chưa tải, chưa dùng |

- Dự án đã chạy **334 cấu hình** (số dòng chạy trong ledger) trên dữ liệu đã thấy. Mô hình học máy nào cũng là lần thử tiếp theo trên cùng dữ liệu đó, nên kết quả trên dữ liệu đã thấy **không bao giờ là bằng chứng**, chỉ dùng để loại bỏ.
- Script đếm có hàm `guard_seen`. Hàm này từ chối ALGO/VET/SAND, từ chối mọi ngày sau 2026-10-17, và từ chối mọi coin chưa có cửa sổ final đã tiêu. Có test riêng cho hàm này.

## 3. Đếm số mẫu thật

Script: `scripts/ml_evidence_census.py`. Dữ liệu ra: `docs/research/runs/ml-evidence-census-2026-10-23/census.json`.

**Cách đếm** (lưới đo cố định trước khi đọc số, không phải lựa chọn mô hình):

- **Chọn thời điểm có sự kiện:** dùng bộ lọc CUSUM hai phía trên log-return. Ngưỡng là độ lệch chuẩn EWM 100 nến, lấy từ nến trước nên không nhìn tương lai.
- **Vào và thoát lệnh:** vào ở giá mở cửa nến kế tiếp. Chặn trên và chặn dưới cách giá vào ±k·ATR14, chặn đứng sau H nến. Nếu một nến chạm cả hai chặn thì tính là chạm chặn lỗ trước.
- **Chi phí:** 0,05% phí taker + 0,03% trượt giá mỗi chiều, tức 0,16% một vòng. Cộng thêm mọi lần thanh toán funding trong khoảng (lúc vào, lúc ra], kể cả các lần lệch lịch như lỗi đã sửa ở vòng 17.
- **Độ trùng lặp:** "độ độc nhất" trung bình theo López de Prado, nghĩa là các nhãn chồng thời gian chỉ được tính một phần.
- **Mẫu độc lập:** n_eff = tổng độ độc nhất × (1−ρ₁)/(1+ρ₁), với ρ₁ là tự tương quan bậc 1 của dấu nhãn.
- **Hiệu chỉnh tương quan giữa các coin:** m_eff = m / (1 + (m−1)·ρ̄), với ρ̄ là tương quan ngày trung bình giữa các coin.

**Tương quan giữa các coin (log-return theo ngày):**

| Nhóm, giai đoạn | ρ̄ | m_eff | ρ̄ sau khi trừ trung bình thị trường |
|---|---|---|---|
| Top-10, 2021–23 | 0,572 | 1,63 | −0,09 |
| Top-10, 2024–26/09 | 0,626 | 1,51 | −0,11 |
| 20 coin, 2021–23 | 0,601 | 1,61 | −0,05 |
| 20 coin, 2024–26/09 | 0,623 | 1,56 | −0,05 |

Sau khi trừ trung bình thị trường, tương quan còn lại xấp xỉ mức −1/(m−1), tức là mức phải có khi phần dư gần như độc lập. Vì vậy: với nhãn hướng giá của từng coin, nên dùng **cận dưới**. Với nhãn tương đối giữa các coin, số mẫu thật gần **cận trên**.

**Kết quả đếm, 20 coin, 2021-01..2026-09 (cộng hai giai đoạn):**

| Cấu hình | Sự kiện | Độ độc nhất TB | n_eff cận trên | n_eff cận dưới (×m_eff/m) | Biên độ trung vị | Phí / biên độ | Ngưỡng hoà vốn |
|---|---|---|---|---|---|---|---|
| A: 1h, k=2, H=24 (1 ngày) | 346.200 | 0,31 | 34.800 | 2.760 | 2,4% | 0,07 | 53,4% |
| B: 4h, k=2, H=6 (1 ngày) | 84.957 | 0,56 | 28.500 | 2.270 | 3,0% | 0,05 | 52,6% |
| C: 4h, k=3, H=30 (5 ngày) | 84.957 | 0,18 | 3.450 | 270 | 6,6% | 0,02 | 51,2% |
| D: 1d, k=2, H=5 (5 ngày) | 14.199 | 0,62 | 6.380 | 510 | 7,3% | 0,02 | 51,1% |

"Ngưỡng hoà vốn" là tỷ lệ đoán đúng tối thiểu với lời lỗ đối xứng ±biên độ trung vị, tính bằng p\* = 0,5 + phí / (2 × biên độ). Đây là ước lượng thô; cách tính đúng là theo lợi nhuận ròng của từng sự kiện.

**Các điểm khác đếm được (trung vị theo coin):**

- Nhãn "mua" có lãi ròng ở 48–51% sự kiện. Lợi nhuận ròng trung bình của lệnh mua là +0,03% (2021–23) và −0,17% (2024–26) với cấu hình B. Thị trường gần như không cho lợi thế miễn phí.
- Funding trung bình mà lệnh mua phải trả mỗi sự kiện: 0,03% (B) đến 0,14% (D) năm 2021–23. Funding không thể bỏ qua với nhãn dài ngày.
- 2026-10-01..17 (đã tiêu): chỉ khoảng 160 mẫu n_eff với B. Một nửa tháng quá ít để kết luận bất cứ điều gì.

## 4. Cần bao nhiêu mẫu

Tất cả là kiểm định một phía với α = 5% và độ mạnh 80%. Các con số do script tính, nằm trong `census.json → power`.

**Phát hiện tương quan giữa dự đoán và kết quả (IC):** n = ((z₀,₉₅ + z₀,₈) / atanh(IC))² + 3

| IC | 0,02 | 0,03 | 0,05 | 0,08 | 0,10 |
|---|---|---|---|---|---|
| Mẫu độc lập cần | 15.456 | 6.869 | 2.472 | 965 | 618 |

**Phát hiện tỷ lệ đúng p₁ so với p₀:** n = ((z₀,₉₅·√(p₀q₀) + z₀,₈·√(p₁q₁)) / (p₁−p₀))²

- Vượt p₀ thêm 1 điểm cần khoảng 15.400 mẫu. Thêm 2 điểm cần khoảng 3.860 mẫu. Thêm 3 điểm cần khoảng 1.720. Thêm 5 điểm cần khoảng 620.
- Phải so với **ngưỡng hoà vốn**, không so với 50%.

**Thời gian theo dõi tối thiểu (MinTRL, Bailey & López de Prado 2012):** MinTRL = 1 + (1 − γ₃·SR + (γ₄−1)/4·SR²) · (z₀,₉₅ / SR)²

| Sharpe năm | 0,5 | 1,0 | 1,5 | 2,0 | 3,0 |
|---|---|---|---|---|---|
| Số ngày cần (phân phối chuẩn) | 3.953 | 990 | 442 | 250 | 113 |
| Số ngày cần (lệch −0,5, nhọn 8) | 4.008 | 1.020 | 462 | 266 | 125 |

- Tính theo lệnh (lệch +1, nhọn 6): Sharpe mỗi lệnh 0,1 cần 248 lệnh, 0,2 cần 59 lệnh.

**Ngưỡng Sharpe bị nâng lên khi thử nhiều cấu hình (kỳ vọng Sharpe lớn nhất của K chiến lược vô dụng, quy ra năm):**

| K \ số ngày | 365 | 730 | 1.095 | 2.100 |
|---|---|---|---|---|
| 10 | 1,57 | 1,11 | 0,91 | 0,66 |
| 50 | 2,28 | 1,61 | 1,31 | 0,95 |
| 300 | 2,90 | 2,05 | 1,67 | 1,21 |

Với 334 lần thử sẵn có, một cấu hình mới phải có Sharpe trên khoảng **1,2** trên toàn bộ 5,75 năm đã thấy thì mới vượt mức may mắn.

**Đủ mẫu cho loại mô hình nào** (quy tắc kinh nghiệm; kiểm tra quyết định vẫn là các cổng ngoài mẫu ở mục 8):

| Mô hình | Quy tắc | Với cấu hình B, cửa sổ 2 năm, 20 coin | Kết luận |
|---|---|---|---|
| Hồi quy logistic L2, p đặc trưng | ≥ 20 mẫu thuộc lớp ít hơn cho mỗi đặc trưng | Cận dưới khoảng 790 mẫu, tức p ≤ khoảng 20. Cận trên khoảng 9.900, tức p ≤ khoảng 250 | Dùng được, giữ ≤ 20 đặc trưng với nhãn hướng giá |
| Cây tăng cường, độ sâu ≤ 3 | ≥ khoảng 5.000 mẫu huấn luyện, đường học phải phẳng | Chỉ đạt theo cận trên | Chỉ dùng với nhãn tương đối giữa các coin |
| Rừng ngẫu nhiên | như trên | như trên | như trên |
| Mạng nơ-ron, LSTM, RL | ≥ 10⁵ mẫu độc lập | Không đạt | Không dùng |
| Meta-label lọc tín hiệu C1 | Khoảng 2.430 lệnh C1 top-10 2021–26/09 (1.269 + 1.162), tương quan cao | Cận dưới khoảng 400 | Không dùng làm nghiên cứu chính (vòng 11/12 cho thấy bộ lọc cắt mất lệnh thắng lớn) |

## 5. Chia dữ liệu

1. **Tập phát triển (đã thấy):** 20 coin, 2021-01-01..2026-09-30 (top-10 đến 2026-10-17). Chỉ dùng để phát triển và loại bỏ, không bao giờ là bằng chứng.
2. **Walk-forward có purge và embargo** (giống chu kỳ của FreqAI):
   - Huấn luyện trên 730 ngày trượt (365 ngày là một lần thử riêng). Huấn luyện lại mỗi 30 ngày, kiểm tra trên 30 ngày tiếp theo.
   - Tháng kiểm tra đầu tiên là 2023-01, nên có 45 tháng ngoài mẫu đến 2026-09.
   - **Purge:** bỏ mọi mẫu huấn luyện có khoảng nhãn [t, t₁] chạm vào khối kiểm tra.
   - **Embargo:** bỏ thêm max(H nến, 1 ngày) sau mỗi khối kiểm tra.
   - Purge tính theo **thời gian chung cho mọi coin**: nhãn BTC lúc t mang thông tin thị trường đến t₁, nên cũng làm rò rỉ sang coin khác.
3. **Combinatorial purged CV (CPCV)** để tính PBO và phân phối Sharpe: chia 2021-01..2026-09 thành 12 nhóm (mỗi nhóm khoảng 5,75 tháng), chọn 2 nhóm kiểm tra, được 66 cách chia và 11 đường kiểm tra. Purge và embargo như trên.
4. **Chọn siêu tham số** chỉ trong từng cửa sổ huấn luyện: 20% cuối của cửa sổ, có purge. Chuẩn hoá z-score, ngưỡng loại outlier và ngưỡng dissimilarity cũng chỉ học trên cửa sổ huấn luyện.
5. **Final một lần** (cần chủ dự án duyệt): ALGO/VET/SAND, 2021-01..2026-09.
   - Code và lịch huấn luyện lại khoá bằng commit. Mô hình chỉ học từ 20 coin phát triển với dữ liệu trước mỗi tháng kiểm tra.
   - Gọi `ledger.check_untouched` trước khi chạy, ghi stage `final`.
   - Chạy qua engine và trạng thái rủi ro của dự án (bài học vòng 18). Sau lần chạy này, dữ liệu đó coi như đã tiêu.
6. **Forward paper:** top-10, cộng ba coin trên nếu được duyệt, tính từ ngày khoá. Dữ liệu lấy qua `scripts/extend_vision_daily.py` và funding công khai. Huấn luyện lại theo đúng lịch đã khoá, không sửa code giữa chừng.

## 6. Nhãn và đặc trưng không rò rỉ

**Nhãn (cấu hình chính B, cấu hình phụ C tính là lần thử riêng):**

- Tín hiệu ở giá đóng cửa nến t, khớp ở giá mở cửa nến t+1.
- Chặn ±k·ATR14 tính đến hết nến t, chặn đứng sau H nến.
- Lợi nhuận ròng = gộp − 0,16% − funding theo chiều lệnh. Kịch bản phí gấp đôi trừ 0,32%.
- Nếu giá nhảy qua chặn lỗ thì thoát ở min(giá mở, giá chặn). Script đếm dùng giá chặn, bản triển khai phải dùng mức xấu hơn.
- **Nhãn chính khuyến nghị (trung lập thị trường):** lợi nhuận ròng của coin trừ lợi nhuận ròng trung bình của rổ, trong cùng [t, t₁]. Giao dịch bằng cách mua nhóm cao nhất, bán nhóm thấp nhất, có phí. Lưu ý vòng 13 đã thấy momentum chéo đơn giản không sống nổi qua phí, nên đây là giả thuyết chứ không phải điều chắc chắn.
- **Trọng số mẫu** = độ độc nhất. Tuỳ chọn nhân thêm |lợi nhuận ròng| (tính là một lần thử).

**Đặc trưng:**

- Chỉ dùng nến **đã đóng** trước hoặc đúng t.
- Nến khung lớn ghép theo **giờ đóng** (giờ mở + độ dài ≤ t), không theo giờ mở. Ghép theo giờ mở thì nến 4h có nhãn lúc 08:00 sẽ chứa dữ liệu đến 12:00, đây là lỗi rò rỉ hay gặp.
- Funding lấy lần thanh toán **trước** t, theo đúng cách `basket_frame` dùng `allow_exact_matches=False`.
- Không dùng OI ở v1, vì dữ liệu OI chỉ có cho BTC và có lỗi chất lượng ở vòng 18.

**Kiểm tra bắt buộc trước khi chạy dev (test tự động):**

1. **Cắt cụt:** với 500 thời điểm t ngẫu nhiên, đặc trưng tính trên dữ liệu[:t] phải bằng đặc trưng tính trên toàn bộ dữ liệu, sai lệch tương đối dưới 1e-9.
2. **Xáo tương lai:** hoán vị dữ liệu sau t, đặc trưng tại các thời điểm ≤ t không được đổi.
3. **Đệ quy / khởi động** (ý tưởng recursive-analysis của Freqtrade): tính với điểm bắt đầu lệch 0, 500 và 1.000 nến. Sau số nến khởi động W khai báo cho từng đặc trưng, kết quả phải bằng nhau. Kiểm tra này bắt lỗi `ewm(adjust=False)` phụ thuộc điểm đầu.
4. **Soát nhãn:** mọi dấu thời gian của đặc trưng phải nhỏ hơn giờ khớp lệnh. Mọi t₁ của mẫu huấn luyện phải nhỏ hơn mốc bắt đầu khối kiểm tra trừ embargo.
5. **Kiểm tra cả bộ máy cổng trên dữ liệu tổng hợp:** chuỗi không có lợi thế phải **trượt** các cổng ở mục 8. Chuỗi được gài một lợi thế biết trước (IC 0,08) phải **qua**.

## 7. Chống quá khớp khi thử nhiều biến thể

- **Ngân sách thử đăng ký trước: K_max = 24 cấu hình ngoài**, gồm:
  - nhãn {B, C},
  - mô hình {logistic, cây tăng cường},
  - bộ đặc trưng {15 cơ bản, 30 có bối cảnh BTC/ETH},
  - cửa sổ {365, 730},
  - cộng tối đa 8 cấu hình dự phòng.
  - Mọi lần chạy, kể cả lần lỗi, đều ghi vào ledger với stage `dev-ml`. Không mở rộng K sau khi đã xem kết quả.
- **Deflated Sharpe (DSR):** tính với K bằng số cấu hình thật sự đã chạy, phương sai Sharpe đo giữa các cấu hình. Báo cáo thêm DSR với K = 24 + 334 để tham khảo.
- **PBO bằng CSCV:** chia đường lợi nhuận ngày thành S = 16 khối, xét mọi tổ hợp 8/8. PBO là tỷ lệ tổ hợp mà cấu hình tốt nhất trong mẫu lại đứng dưới trung vị ngoài mẫu.
- **Block bootstrap dừng (Politis–Romano):** khối trung bình 20 ngày, 5.000 lần. Dùng cho khoảng tin cậy của lợi nhuận năm, Sharpe, và chênh lệch Sharpe so với mốc so sánh.
- **Hoán vị nhãn:** xáo nhãn theo khối 30 ngày trong từng coin rồi chạy lại toàn bộ walk-forward 200 lần, được phân phối "không có lợi thế".
- **Mốc so sánh** (cùng coin, cùng cửa sổ, cùng phí):
  - (b0) gửi ngân hàng 5,9%/năm;
  - (b1) C1 khoá ở 5% rủi ro, đo trên top-10 bằng cùng code báo cáo. Số đã ghi: 2021–23 +174%, DD 21%; 2024–26/09 +25%, DD 19,6%;
  - (b2) giữ đều top-10 ở đòn bẩy 1x;
  - (b3) mô hình đơn giản: logistic 3 đặc trưng (momentum 20 nến, biến động, funding);
  - (b4) vào lệnh ngẫu nhiên với cùng mức phơi nhiễm.

## 8. Tiêu chí đạt và dừng, đăng ký trước bằng số

**Cổng D: dev, ngoài mẫu walk-forward 2023-01..2026-09.** Dữ liệu này đã thấy, nên cổng D chỉ được loại bỏ hoặc cho phép đi tiếp tới final.

| Mã | Tiêu chí |
|---|---|
| D1 | Lợi nhuận ròng năm ≥ 5,9% ở phí gốc, và > 0 khi phí gấp đôi |
| D2 | Lợi nhuận/DD và Sharpe ngày ≥ C1 (b1) trên cùng cửa sổ |
| D3 | DSR ≥ 0,95 với K = số cấu hình đã chạy |
| D4 | PBO ≤ 0,25, hoặc cấu hình được chọn giữ Sharpe ngoài mẫu dương ở ≥ 90% cách chia CSCV (sửa sau tự kiểm tra, mục 12) |
| D5 | p hoán vị nhãn ≤ 0,01, tức thắng ít nhất 198/200 lần |
| D6 | Thắng b3: cận dưới khoảng tin cậy 90% bootstrap của chênh lệch Sharpe > 0 |
| D7 | Dương ít nhất 3/4 năm (2023, 2024, 2025, 2026-01..09). Không coin nào > 30% lợi nhuận. 5 lệnh lớn nhất < 50% lợi nhuận (C1 từng có 1 lệnh SOL chiếm 57%) |
| D8 | IC Spearman trung bình theo tháng ≥ 0,02, thống kê t Newey–West ≥ 2 |

- **Quy tắc dừng:** nếu dùng hết K_max mà không cấu hình nào qua D1–D5 thì **dừng nhánh học máy**, ghi bài học vào ledger. Không thêm đặc trưng hay cấu hình. Muốn thử tiếp thì phải đăng ký một nghiên cứu mới và có dữ liệu final mới.

**Cổng F: final một lần, commit khoá, ALGO/VET/SAND 2021-01..2026-09.**

| Mã | Tiêu chí |
|---|---|
| F1 | Lợi nhuận ròng năm ≥ 5,9% |
| F2 | PSR(SR\* = 0) ≥ 0,95. Với khoảng 2.100 ngày, tương đương Sharpe năm ≥ khoảng 0,69 |
| F3 | Phí gấp đôi vẫn > 0 |
| F4 | Max DD trên nến 15m (bài học vòng 18) ≤ 1,5 × DD ngoài mẫu ở dev, và ≤ 30% |
| F5 | Không coin nào > 60% lợi nhuận |

Trượt bất kỳ tiêu chí nào là loại ứng viên, và dữ liệu final đó coi như đã tiêu.

**Cổng P: forward paper.**

- Chưa kết luận trước khi có ít nhất 180 ngày và 100 lệnh.
- **Đạt** khi PSR(SR\* = 0) ≥ 0,95 và lợi nhuận năm ≥ 5,9%.
- **Dừng sớm** khi DD > 1,5 × DD ngoài mẫu ở dev, hoặc sau 180 ngày mà PSR < 0,05.

## 9. Kế hoạch theo bước và khi nào đủ bằng chứng

| Bước | Việc | Dữ liệu dùng | Ước lượng |
|---|---|---|---|
| 0 | Thiết kế và đếm mẫu (bản này) | Đã thấy, chỉ đếm | Xong |
| 1 | Khung `src/research/ml/`: đặc trưng, nhãn, chia purge/CPCV, DSR/PBO/bootstrap/hoán vị, cùng các test ở mục 6. Thêm `scikit-learn` (giấy phép BSD) vào requirements | Chỉ dữ liệu tổng hợp | Xong (mục 12) |
| 2 | Nghiên cứu dev, ≤ 24 cấu hình, cổng D | Đã thấy | 1–2 ngày |
| 3 | ~~Final một lần, cổng F~~ (bỏ theo quyết định 2026-10-23) | — | — |
| 4 | Forward paper, cổng P | Từ ngày khoá | ≥ 6 tháng, thực tế 8 tháng đến 2,7 năm |

**Ước lượng khi nào đủ bằng chứng:**

- **Bằng chứng lịch sử sớm nhất:** khoảng đầu tháng 11/2026, nếu D và F đều qua. Đây là bằng chứng cho Sharpe ≥ khoảng 0,7 trên coin chưa thấy.
- **Bằng chứng forward:** Sharpe 2 cần khoảng 250 ngày, tức khoảng tháng 7/2027. Sharpe 1,5 cần khoảng 442 ngày, tức khoảng đầu năm 2028. Sharpe 1 cần khoảng 990 ngày, tức khoảng giữa năm 2029.
- **Nếu không dùng ALGO/VET/SAND:** chỉ còn forward. Sau 1 năm phát hiện được Sharpe từ 1,65 trở lên, sau 2 năm từ 1,16 trở lên.
- **Kết luận thẳng:** với dữ liệu hiện có, học máy chỉ có thể đạt mức "ứng viên đáng chạy forward". Không có cách nào có đủ bằng chứng cho một lợi thế vừa phải (Sharpe khoảng 1) trước năm 2028–2029 mà không cần dữ liệu forward dài.

## 10. Quyết định cần chủ dự án

1. **Dùng ALGO/VET/SAND làm tập final một lần cho học máy?** Khuyến nghị: có. Đây là lịch sử chưa thấy duy nhất còn lại. Coin chưa thấy cũng kiểm tra được mô hình có khái quát hay không. Nhóm coin giao dịch thật vẫn là top-10 như chủ dự án đã quyết.
2. **Nhãn chính trung lập thị trường thay cho hướng giá từng coin?** Khuyến nghị: có, vì số mẫu hữu dụng lớn hơn khoảng 12 lần.
3. **Ngân sách K_max = 24 và các ngưỡng ở mục 8:** chủ dự án có thể chỉnh, nhưng phải chỉnh **trước** bước 2.

## 11. Tái lập và giới hạn

- Nhánh `claude/project-thread-secv2t`, gốc `claude/project-thread-ryvuyt` @ `fd466ac`.
- Lệnh đếm:

```
python scripts/ml_evidence_census.py \
  --forward-dir /mnt/project-files/market-data/binance-vision-usdm-forward \
  --base-dir /mnt/project-files/market-data/binance-vision-usdm \
  --out docs/research/runs/ml-evidence-census-2026-10-23/census.json
```

  Chạy mất khoảng 45 giây. Test: `pytest tests/test_ml_evidence_census.py`, 3 test đạt.
- **Giới hạn:**
  - Cận dưới n_eff giả định nhãn tương quan giữa các coin bằng tương quan giá. Đây là cách tính thô và thận trọng.
  - Ngưỡng hoà vốn dùng biên độ trung vị.
  - Quy tắc số mẫu cho từng loại mô hình là kinh nghiệm, không phải định lý.
  - Nến 1h/4h/1d dựng lại từ 15m cho mọi coin.
  - Chưa có Tester hay Reviewer độc lập kiểm tra.
- **Nguồn phương pháp:** López de Prado, *Advances in Financial Machine Learning* (2018), các chương về triple-barrier, độ độc nhất, purge/embargo và CPCV. Bailey & López de Prado (2012) về MinTRL/PSR. Bailey & López de Prado (2014) về Deflated Sharpe. Bailey, Borwein, López de Prado & Zhu (2017) về PBO/CSCV. Politis & Romano (1994) về stationary bootstrap. Tài liệu FreqAI (freqtrade.io) cho các ý tưởng ở mục 1, không chép mã.

## 12. Bước 1 đã làm: khung học máy (2026-10-23)

Code trong `src/research/ml/`. Bước này chỉ chạy trên dữ liệu tổng hợp, không mở dữ liệu thị trường nào và không ghi dòng nào vào ledger.

| File | Nội dung |
|---|---|
| `labels.py` | Triple-barrier cho cả mua và bán: khớp ở nến kế tiếp, nhảy giá qua chặn lỗ thì thoát ở giá xấu hơn, phí 0,16%, funding trong (lúc vào, lúc ra]. Nhãn trung lập thị trường. Độ độc nhất |
| `features.py` | Đặc trưng 4h + 1d (ghép theo **giờ đóng**), nến trễ, funding đã biết, bối cảnh BTC. Ba hàm kiểm tra: cắt cụt, xáo tương lai, khởi động 365 ngày |
| `splits.py` | Purged walk-forward (purge theo thời gian chung cho mọi coin, embargo 1 ngày), tách 20% cuối để hiệu chỉnh, CPCV 12 nhóm / 66 cách chia / 11 đường |
| `stats.py` | DSR (dùng PSR có sẵn của `model_governance`), PBO/CSCV kèm xác suất lỗ ngoài mẫu, stationary bootstrap, hoán vị nhãn theo khối 30 ngày, IC theo tháng, t Newey–West |
| `models.py` | Logistic L2, cây tăng cường độ sâu 3, trung bình hai mô hình. Calibration isotonic chỉ fit trên 20% cuối cửa sổ. Bỏ tín hiệu khi \|p_logistic − p_cây\| > 0,15, hoặc khi DI vượt phân vị 99% |
| `walkforward.py` | Chạy walk-forward, sổ mua/bán trung lập (nửa vốn mua, nửa vốn bán, phí trên toàn bộ danh nghĩa), lợi nhuận theo ngày, phân phối hoán vị |
| `gates.py` | Cổng D1–D8 với ngưỡng cố định. Kiểm tra nào không tính được thì là NOT_EVALUATED và chặn kết luận như FAIL |
| `synthetic.py` | Bảng giá tổng hợp nhiều coin, có thể gài một lợi thế momentum riêng của từng coin |

Dùng lại `src/research/model_governance.py` từ nhánh `claude/project-thread-jrmpfx` (commit 7bebd39), lấy nguyên file, để chỉ có một bản PSR và một bản calibration.

**Tự kiểm tra trên dữ liệu tổng hợp** (6 coin, ngoài mẫu 2022-03..2023-06; test trong `tests/test_ml_framework.py`):

| Bảng giá | Lợi nhuận năm | Sharpe năm | IC | D1 | D3 | D4 | D7 | D8 |
|---|---|---|---|---|---|---|---|---|
| Không lợi thế | −18,9% | −0,45 | 0,011 | FAIL | FAIL | FAIL | FAIL | FAIL |
| Gài lợi thế (IC thật khoảng 0,1) | +167% | 3,15 | 0,094 | PASS | PASS | PASS | PASS | PASS |

- Cả hai bảng giá đều có kết luận FAIL, vì D2 (so với C1), D5 (cần 200 lần hoán vị) và D6 (so với mô hình đơn giản) chưa tính trong test. Đây là hành vi đúng: thiếu kiểm tra nào thì không được kết luận đạt.
- Một test riêng xác nhận: với lợi thế gài sẵn, Sharpe thật cao hơn mọi lần chạy hoán vị.

**Các test cũng bắt được ba kiểu rò rỉ cố ý:** ghép nến 1d theo giờ mở, đặc trưng nhìn trước một nến, và đặc trưng không bao giờ quên điểm bắt đầu.

**Hai điều chỉnh thiết kế rút ra từ tự kiểm tra** (làm trước bước 2, chưa có kết quả thật nào):

1. **D4:** khi các cấu hình tốt ngang nhau, PBO nằm quanh 0,3–0,5 ngay cả khi lợi thế là thật, vì chọn cái tốt nhất trong mẫu lúc đó chỉ như tung đồng xu. Vì vậy D4 qua khi PBO ≤ 0,25, **hoặc** khi cấu hình được chọn vẫn có Sharpe ngoài mẫu dương ở ít nhất 90% cách chia. PBO cũng không phải phép thử lợi thế: bảng giá không lợi thế bị loại ở D1, D3 và D8, không phải ở D4.
2. **Khởi động:** EMA50 trên nến 1d sau 365 ngày vẫn còn lệch khoảng 3e-6 ATR so với khi chạy từ đầu chuỗi, nên ngưỡng sai lệch khi kiểm tra khởi động là 1e-5. Bỏ 365 ngày đầu của mỗi coin khỏi tập dữ liệu.

**Chưa làm, để dành cho bước 2:**
- Nối các hàm trên thành script chạy dev trên 20 coin đã thấy.
- Tính mốc C1 bằng cùng code báo cáo.
- Mô hình đơn giản b3 cho D6.
- Chạy 200 lần hoán vị.
- Ghi mọi cấu hình vào ledger với stage `dev-ml`.
- Đường triple-barrier có hướng chưa nối vào sổ; nhãn chính là nhãn trung lập.

**Test:** offline 715 đạt, 2 bỏ qua, 5 network bỏ chọn. 16 test mới mất khoảng 30 giây.
