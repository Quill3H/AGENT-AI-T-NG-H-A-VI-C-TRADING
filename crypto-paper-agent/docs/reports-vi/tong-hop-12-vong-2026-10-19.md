# Tổng hợp 12 vòng nghiên cứu futures (2026-10-19)

Đây là **giao dịch giấy**: tài khoản 10.000$, đòn bẩy 2x, lệnh nào cũng có stop-loss. Mọi kết quả đều đã trừ phí 0,05% mỗi chiều, trượt giá 0,03% và funding. Các con số do tôi tự chạy (AUTHOR_REPORTED). Riêng C1 và A2 đã được hai bên độc lập dựng lại và cho cùng kết quả (xem [vong-12-kiem-tra-cheo-2026-10-19.md](/mnt/project-files/repo-analysis/vong-12-kiem-tra-cheo-2026-10-19.md)). Sổ ghi đầy đủ từng lần chạy nằm ở `crypto-paper-agent/docs/research/ledger/LEARNING_LOG.md`.

## 1. Kết luận ngắn

- **Sau 12 vòng, chưa có cách nào đạt bậc 10% mỗi tháng** trên dữ liệu chưa dùng để chọn cách.
- Cách tốt nhất là **C1** (mua khi giá điều chỉnh về EMA trong xu hướng tăng, khung 4h) và bản cải tiến **A2** (thoát sớm hơn khi xu hướng yếu).
  - Giai đoạn 2021–2023, dùng để chọn cách: +4–5% mỗi tháng.
  - Giai đoạn 2024–2026, dữ liệu chọn cách chưa thấy: chỉ khoảng **+0,5% mỗi tháng**, tức +18% trong 33 tháng.
  - Tháng 10/2026: −1,4%.
- Phần lớn lãi đến từ **vài lệnh rất lớn**. Riêng một lệnh SOL cuối năm 2023 mang lại 57% toàn bộ lãi của A2.
- Bằng chứng mới thật sự chỉ có thể đến từ **chạy giấy trên dữ liệu từ 18/10 trở đi**. Lần kiểm tra tuần đầu là ngày 25/10.

## 2. Từng vòng: thử gì, lãi hay lỗ

| Vòng | Đã thử | Kết quả trên dữ liệu chưa dùng để chọn |
|---|---|---|
| 1 | Theo xu hướng Donchian khung ngày | Lỗ ở 2024–2025 |
| 2 | Ăn funding (carry) | Chỉ có lãi khi funding cao. Năm 2026 không vào lệnh nào |
| 3 | Các bộ chỉ báo RSI, MACD, Bollinger… | Lãi lớn lúc chọn (chủ yếu nhờ SOL 2021), sau đó thất bại |
| 4 | Các hướng mới trên nhiều đồng | Lãi +183%, nhưng gần hết nhờ một đồng AVAX, tức là may |
| 5 | Phong cách trade: scalp 1m–1h, swing | Mọi kiểu scalp đều lỗ sau phí, dù thắng 55% số lệnh. Swing EMA 4h lãi nhẹ |
| 6 | Mô hình nến, chốt lời nhanh, x20 | Chốt nhanh thì thắng nhiều lệnh hơn nhưng lỗ tiền. Mô hình nến 4h với mục tiêu 2R lãi nhỏ |
| 7 | Chiến thuật từ video, Raschke, Williams, Crabel, 5–10 lệnh mỗi tuần | Trade càng nhiều càng lỗ vì phí. TRX −72% |
| 8 | C1 swing EMA chỉ mua, mục tiêu 10%/tháng; Wynn, GCR, Hayes | 2024–2026 +0,5%/tháng, tháng 10 −1,4%. Kiểu bắt đỉnh, bắt đáy đều lỗ |
| 9 | Ichimoku | Chỉ tín hiệu cắt Tenkan/Kijun 4h ổn (+0,8%/tháng). Tháng 10 −2,3% |
| 10 | Wyckoff kết hợp Ichimoku | Wyckoff lỗ ở mọi bản. Bản trộn 3 cách: 2024–2026 +21,7%, sụt 15% |
| 11 | IncomeSharks, Nebraskangooner, Cheds | Tỷ lệ thắng tăng từ 27% lên 38%, nhưng lãi mỗi tháng giảm. Bộ lọc S1 lỗ 3,3% ở 2024–2026 |
| 12 | Tự thích nghi với thị trường: KAMA, ADX, Chandelier, lực mua, biến động | A2 tốt hơn C1 một chút: 2024–2026 +18,6% so với +17,8% của C1. Phí ×2 thì chỉ còn +1,5% |

## 3. Cái gì có lãi, cái gì lỗ

**Có lãi (nhỏ):**
- Theo xu hướng trên khung 4h, giữ lệnh vài tuần, cắt lỗ sớm và để lệnh lãi chạy (C1, A2, I1, M1).
- Trộn nhiều cách giúp đường vốn mượt hơn (M1 sụt 15%), nhưng không làm lãi tăng lên.

**Lỗ:**
- Scalp và mọi khung từ 1 giờ trở xuống, vì phí và trượt giá ăn hết phần lợi thế.
- Bắt đỉnh, bắt đáy (đánh ngược xu hướng), Wyckoff, và phá vỡ từ vùng đi ngang.
- Chốt lời sớm để tăng tỷ lệ thắng.
- Thêm bộ lọc vào lệnh: giúp ở giai đoạn này nhưng lại hại ở giai đoạn sau.

## 4. Vì sao: 7 bài học chung

1. **Tỷ lệ thắng cao không đồng nghĩa có lãi.** Cách có lãi chỉ thắng khoảng 25–28% số lệnh, nhưng lệnh thắng lớn gấp nhiều lần lệnh thua. Chốt sớm để thắng nhiều lệnh thì mất chính những lệnh lớn đó.
2. **Phí là kẻ thù số một.** Cứ trade nhiều hơn là kết quả tệ hơn. Với phí và trượt khoảng 0,16% cho một lệnh vào ra, 20 lệnh mỗi tuần đã mất khoảng 3% vốn danh nghĩa mỗi tuần.
3. **Kết quả đẹp lúc chọn cách thường không lặp lại.** 2021 và 2023 là hai năm crypto tăng mạnh. Mọi cách theo xu hướng đều trông rất giỏi ở hai năm này, rồi yếu hẳn ở 2024–2026.
4. **Lãi dồn vào vài lệnh và vài đồng** (SOL, AVAX). Trung vị lãi mỗi tháng gần như bằng 0. Đó là dấu hiệu của may mắn hoặc của một lợi thế rất mỏng, không phải một cỗ máy kiếm tiền đều đặn.
5. **Không cách nào tốt ở mọi giai đoạn.** WY2 lỗ ở 2021–2023 nhưng lãi ở 2024–2026. S1 thì ngược lại.
6. **Mức rủi ro thật thấp hơn tên gọi.** Luật giảm rủi ro sau chuỗi thua làm bản "5%" thật ra chỉ rủi ro khoảng 2,5% mỗi lệnh. Nếu bỏ luật này thì sụt vốn sẽ vượt mức trần 35%.
7. **Dữ liệu đã cạn.** Mọi nến của 10 đồng top đến 17/10/2026 đều đã được dùng để kiểm tra. Từ nay, chỉ chạy giấy tiếp diễn mới cho bằng chứng thật.

## 5. "Không lẽ trên thế giới không ai có lời từ trade futures?"

**Có người có lãi, nhưng họ là số rất ít, và phần lớn không có lãi nhờ đoán hướng giá.**

**Số liệu về nhà đầu tư nhỏ lẻ:**
- Cơ quan chứng khoán châu Âu ESMA cho biết **74–89% tài khoản nhỏ lẻ** giao dịch sản phẩm đòn bẩy (CFD) **bị lỗ** ([esma.europa.eu/node/84933](https://www.esma.europa.eu/node/84933)).
- Nghiên cứu toàn bộ người day-trade ở Đài Loan (Barber, Lee, Liu, Odean, 2014) thấy **chưa tới 1%** có lãi ổn định và dự đoán được sau phí ([ideas.repec.org](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html)).

**Những ai thường có lãi, và họ dựa vào gì** (phần này là hiểu biết chung về thị trường, tôi chưa kiểm chứng bằng số liệu riêng):

| Ai | Lợi thế | Bot của mình có không? |
|---|---|---|
| Nhà tạo lập thị trường (market maker) | Đặt lệnh hai chiều, ăn chênh lệch mua bán, được sàn **trả phí** thay vì phải trả | Không. Mình trả phí taker 0,05% cộng trượt giá |
| Quỹ chênh lệch funding / basis | Mua spot, bán perp để ăn funding, gần như không cược hướng giá | Đã thử ở vòng 2: chỉ có lãi khi funding cao |
| Đội có hạ tầng tốc độ cao | Chạy nhanh hơn người khác vài mili-giây, giao dịch khối lượng rất lớn | Không thể có với cách chạy theo nến 4h |
| Quỹ theo xu hướng hoặc theo yếu tố định lượng | Rất nhiều thị trường cùng lúc, quản trị rủi ro chặt, chấp nhận nhiều năm lãi ít | Đây là hướng gần nhất với C1, A2 và vòng 13 |
| Trader nổi tiếng | Vài lệnh lớn kiểu bất cân xứng, sống sót qua nhiều lần thua, cộng thêm thu nhập từ khoá học, kênh, sàn giới thiệu | Mình đã mô phỏng luật của họ ở vòng 7–11: không có lợi thế rõ sau phí |

**Thiên lệch người sống sót:** ta chỉ nghe về những người thắng. Hàng nghìn người dùng cùng cách và thua thì không ai kể. Lợi nhuận mà trader trên mạng công bố thường không có sao kê kiểm toán, nên **không kiểm chứng được**.

**Điểm mấu chốt:** 12 vòng vừa qua đều tìm lợi thế bằng cách **đoán hướng giá của từng đồng riêng lẻ**. Đây chính là nơi mà phần đông người chơi thua. Vì vậy vòng 13 đổi sang một loại lợi thế khác.

## 6. Vòng 13 khác gì

- **Không đoán một đồng sẽ lên hay xuống.** Mỗi tuần, so sức mạnh của 10 đồng top với nhau: mua 3 đồng mạnh nhất trong 3 tuần qua, bán 3 đồng yếu nhất, và giữ một tuần.
- Cơ sở: nghiên cứu của Liu, Tsyvinski và Wu (NBER w25882). Theo nghiên cứu này, chênh lệch giữa nhóm mạnh và nhóm yếu khoảng **4% mỗi tuần** ở giai đoạn 2014–2018.
  - Hạn chế: nghiên cứu dùng hàng trăm đồng và không tính phí.
  - Một số kiểm định khác trong cùng bài không cho kết quả có ý nghĩa thống kê.
  - Vì vậy kết quả này **chưa chắc chắn**.
- Có 4 bản:
  - X1: 3 tuần, mua lẫn bán.
  - X2: chỉ mua.
  - X3: chỉ mua đồng có lãi và chỉ bán đồng đang lỗ.
  - X4: 1 tuần.
- Tính đủ phí và funding. Sụt vốn tối đa 35%. Luật chọn được ghi và commit trước khi chạy.
- **Kết quả:** bản được chọn (X3) gần như hoà vốn ở 2024–2026: +0,3%, sụt sâu nhất 9,7%. Cùng giai đoạn đó, C1 lãi +25% trên cùng 10 đồng. Chi tiết ở [vong-13-so-suc-manh-10-dong-2026-10-19.md](/mnt/project-files/repo-analysis/vong-13-so-suc-manh-10-dong-2026-10-19.md).
