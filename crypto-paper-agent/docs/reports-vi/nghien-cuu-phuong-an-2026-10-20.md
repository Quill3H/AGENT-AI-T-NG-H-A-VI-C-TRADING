# Tìm thêm phương án trên mạng: so với gửi tiết kiệm ngân hàng (2026-10-20)

Mốc so sánh là **gửi tiết kiệm 12 tháng**: Vietcombank, BIDV và VietinBank trả **5,9% mỗi năm** (khoảng 0,48% mỗi tháng). Đầu tháng 10/2026, mức lãi của 35 ngân hàng nằm trong khoảng 3,7–7,8% mỗi năm ([nguồn](https://thitruongtaichinhtiente.vn/lai-suat-dau-thang-10-2026-tiet-kiem-giu-nhip-on-dinh-chung-chi-tien-gui-hut-khach-85944.html)).

## 1. Bảng so sánh các phương án

| Phương án | Lãi công khai có bằng chứng | Rủi ro chính | Vốn và điều kiện | Mô phỏng được bằng dữ liệu hiện có? |
|---|---|---|---|---|
| **Gửi tiết kiệm** | 5,9%/năm, chắc chắn | Gần như không có | Bao nhiêu cũng được | Không cần |
| **Ăn funding trung lập**: mua spot, bán khống perp cùng lượng | **5–10%/năm sau phí** với BTC/ETH trong 2020–2024 ([He và cộng sự](https://arxiv.org/pdf/2212.06888)). Ethena sUSDe đạt khoảng 18% năm 2024, 4–15% năm 2025, khoảng 3,7% đầu năm 2026 ([nguồn](https://stablecoininsider.org/ethena-usde-q1-2026-report/)) | Funding âm kéo dài, sàn sập, thanh lý chân perp khi giá tăng vọt | Cần cả tài khoản spot lẫn futures | **Có**, cho BTC/ETH/SOL → **vòng 16** |
| **Theo xu hướng** (C1, A2 của mình) | Bản thử của mình giai đoạn 2024–2026: khoảng +7–8%/năm | Sụt vốn khoảng 20%, lãi dồn vào vài lệnh lớn | 10.000$ là đủ | Có, đã thử ở các vòng 8 và 12 |
| **Giao dịch cặp** (P1 của mình) | Bản thử của mình giai đoạn 2024–2026: +3%/năm ở rủi ro 5%, +6%/năm ở rủi ro 10% | Mới có 34 lệnh, còn ít | 10.000$ là đủ | Có, đã thử ở vòng 14 |
| **Danh mục kết hợp nhiều cách** (funding + xu hướng + cặp) | Các quỹ đa chiến lược dùng cách này để tăng lãi trên mỗi đơn vị rủi ro | Phụ thuộc vào từng phần | 10.000$ là đủ | **Có** → **vòng 16** |
| Tạo lập thị trường (market making) | Lãi đến từ chênh lệch giá mua bán và việc sàn trả phí cho lệnh chờ | Bị khớp lệnh ngược chiều khi giá chạy mạnh. Cần tốc độ cao và cấp phí VIP | Người nhỏ lẻ trả phí maker khoảng 0,02% thay vì được sàn trả | **Không**: cần dữ liệu sổ lệnh từng mili-giây |
| Bán quyền chọn ăn biến động | Lãi đều đặn nhưng có thể mất lớn khi thị trường sập | Mất lớn đột ngột khi thị trường sập | Cần tài khoản quyền chọn (Deribit), không phải futures | **Không**: không có dữ liệu quyền chọn |
| Bot lưới (grid) | Chỉ có số liệu quảng cáo của sàn | Lãi khi giá đi ngang, lỗ nặng khi có xu hướng | 10.000$ là đủ | Chỉ mô phỏng được một phần |
| Copy trade, nhóm tín hiệu, bot "X% mỗi tháng" | Một khảo sát hơn 100.000 kết quả copy trade trên Binance, Bybit và MEXC: chỉ khoảng **48%** người copy có lãi. Khoảng 97% trader dẫn đầu tự báo có lãi, nhưng chỉ **44%** làm người copy có lãi ([nguồn](https://www.kucoin.com/blog/is-crypto-copytrading-profitable-in-2026)) | Thiên lệch người sống sót, số liệu không được kiểm toán | | **Không**: không có sổ sách kiểm chứng |

## 2. Phần nào là quảng cáo, không kiểm chứng được

- Các lời hứa "10–50% mỗi tháng" từ bot, nhóm tín hiệu hay bảng xếp hạng copy trade đều **không có sao kê kiểm toán**.
  - Bảng xếp hạng chỉ hiện những người đang thắng. Người đã thua thì biến mất khỏi bảng.
  - Chính bài viết của KuCoin cũng ghi rằng con số của họ có lẫn quảng cáo cho sàn.
- Mức lãi cao của Ethena năm 2024 là có thật, nhưng nó **giảm còn khoảng 3,7%** khi thị trường hết hưng phấn. Không nên lấy năm tốt nhất làm kỳ vọng.
- Không có nghiên cứu công khai nào mà mình tìm được cho thấy có cách lãi ổn định 10% mỗi tháng sau phí trên futures crypto.

## 3. Kết luận và cách chọn cho vòng 16

**Kết luận thật:**
- Các cách có bằng chứng công khai thường lãi **5–20% mỗi năm**, tức là ngang hoặc hơi hơn gửi ngân hàng, nhưng có rủi ro thật.
- Muốn lãi cao hơn nhiều thì gần như chỉ có cách tăng đòn bẩy. Khi đó sụt vốn cũng tăng theo.

**Hai hướng được chọn để thử ở vòng 16:**
1. **Ăn funding ở ngưỡng lãi ngân hàng:** chỉ mở rổ spot/perp khi funding cho lãi từ 6%/năm (K1) hoặc 10%/năm (K2) trở lên.
2. **Danh mục ba cách kết hợp (M2):** một phần ba ăn funding, một phần ba theo xu hướng C1, một phần ba giao dịch cặp P1. Ba cách này kiếm lời từ ba nguồn khác nhau.

**Nếu danh mục cho lãi ổn định với sụt vốn thấp,** bước sau có thể là tăng quy mô một cách có kiểm soát. Việc này cần bạn đồng ý, và sẽ chỉ chạy như bản thử "nếu như" có nhãn riêng.

## 4. Repo bạn gửi: Synpath-ai/prediction-market-arbitrage-trading-bot

Mình chỉ đọc trang GitHub, không chạy code, không dùng khoá hay ví nào ([link](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot)).

**Cách kiếm lãi:**
- Repo này chơi **chênh lệch giá giữa hai thị trường dự đoán, Kalshi và Polymarket**.
- Khi giá "CÓ" trên sàn này cộng giá "KHÔNG" trên sàn kia, sau phí, rẻ hơn 1$ ít nhất 2 xu, nó mua cả hai phía.
- Đến khi sự kiện có kết quả, một trong hai phía chắc chắn được trả 1$, nên phần chênh lệch là lãi đã khoá trước.

**Bằng chứng hiệu suất: yếu.**
- Con số duy nhất là một lần chạy thử trên dữ liệu cũ: 3 thị trường, 60 ngày, 20 lệnh, lãi +29,4%.
- Tác giả tự ghi rằng đây là kết quả mô phỏng và giả định luôn khớp lệnh đúng giá niêm yết.
- Repo không có kết quả chạy tiền thật, cũng không có kiểm toán.
- Repo có 0 sao và 0 fork. Toàn bộ dữ liệu ghép cặp, giá và phí đều lấy từ dịch vụ trả phí của chính công ty viết repo (Synpath). Đây là dạng quảng cáo sản phẩm.
- Phần mô tả còn tự mâu thuẫn: có chỗ ghi "tự động đặt lệnh hai phía", có chỗ lại ghi "không bao giờ đặt lệnh thật".

**Rủi ro thật mà repo cũng thừa nhận:** hai sàn có thể phân xử cùng một sự kiện khác nhau. Khi đó cả hai chân cùng thua. Ngoài ra, 20 lệnh quá ít để kết luận.

**Phần áp dụng được cho futures crypto:**
- Ý tưởng **giữ hai chân ngược nhau để khoá chênh lệch** chính là ăn funding/basis giữa spot và perp. Mình đang thử đúng ý tưởng này ở vòng 16 (K1, K2, M2).
- Phiên bản giữa hai sàn futures (ví dụ funding Binance khác funding Bybit) cũng cùng nguyên lý. Nhưng hiện mình chỉ có dữ liệu Binance, nên **chưa mô phỏng được**.

**Phần không áp dụng được:**
- Thị trường dự đoán không phải futures.
- Cần tài khoản Kalshi/Polymarket và ví, tức là vượt ngoài phạm vi chỉ giao dịch giấy của dự án.
- Chênh lệch kiểu này thường chỉ còn vài xu và biến mất rất nhanh.
