# Agent AI tự động hóa việc trading

Dự án nghiên cứu **crypto futures, chỉ paper trading**. Mục tiêu là xây dựng một quy trình có thể tái lập để kiểm tra ý tưởng, giải thích quyết định và đánh giá kết quả sau đầy đủ chi phí. Hiện chưa có kết luận nghiệm thu lợi thế kinh tế hoặc quyền giao dịch tiền thật.

Cập nhật tài liệu: **29/10/2026**. Snapshot nguồn chính: `65960bff7341637557d8158c2440dcc087ce1a41`. Các kết quả và giới hạn được ghi trong [trạng thái hiện tại](<Project spec/CURRENT_STATUS.md>).

Bổ sung tích hợp **30/10/2026**: Backtest Lab, ETH–BTC, ORB và wiki đã được hợp nhất sau kiểm thử/review; xem [báo cáo tích hợp và giới hạn](crypto-paper-agent/docs/reviews/MAIN_INTEGRATION_2026_10_29.md). Các snapshot nghiên cứu bên dưới không tự được nâng mức nghiệm thu bởi việc merge.

## Đọc theo nhu cầu

| Bạn muốn biết | Đọc ở đâu |
| --- | --- |
| Dự án đang hướng tới điều gì? | [Định hướng hiện tại](<Initial idea/CURRENT_VISION.md>) |
| Đã làm gì, kết quả ra sao, điều gì chưa được xác minh? | [Trạng thái và bằng chứng](<Project spec/CURRENT_STATUS.md>) |
| Các thành phần nối với nhau như thế nào? | [Master Spec](<Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md>) |
| Nên làm gì tiếp theo và khi nào dừng? | [Lộ trình](<Project spec/ROADMAP.md>) |
| Chạy chương trình và tìm mã nguồn? | [Ứng dụng nghiên cứu](crypto-paper-agent/README.md) |
| Xem quyết định rủi ro, review và lịch sử thí nghiệm? | [Bản đồ tài liệu](<Project spec/README.md>) |
| Bắt đầu một phiên làm việc với AI? | [AGENTS.md](AGENTS.md), rồi xác minh Git và checkpoint nguồn |

## Bản đồ dự án

```text
Initial idea/          Vì sao làm: ý tưởng gốc và định hướng hiện tại
Project spec/          Làm gì: đặc tả, trạng thái, lộ trình và bằng chứng
crypto-paper-agent/   Thực hiện: mã, cấu hình, tests, hướng dẫn, ADR và báo cáo
PLANNER_HANDOVER.md    Bàn giao và lịch sử phối hợp; kiểm lại Git trước khi dùng
```

Luồng nghiên cứu: **ý tưởng → giả thuyết định lượng → dữ liệu có nguồn → khóa phiên bản → backtest và đối chứng → holdout chưa xem → paper forward → quyết định**.

Giữ ba câu hỏi riêng: phần mềm đã chạy đúng chưa; thí nghiệm có hợp lệ không; chiến lược có lợi thế sau chi phí không. Một câu trả lời “có” không tự trả lời hai câu còn lại.

## Quy tắc đọc kết quả

- Đếm vị thế hoàn tất riêng với các lần chốt từng phần; nhiều giao dịch cùng thị trường có tương quan.
- Báo cáo PnL ròng, drawdown, thời gian underwater, phí, trượt giá và funding; win rate hoặc số lượng lệnh không đủ để kết luận.
- Dữ liệu giả lập dùng kiểm tra phần mềm; dữ liệu đã xem dùng chẩn đoán hồi cứu. Cả hai không thay thế holdout chưa xem hoặc paper forward.
- Không có lệnh thật/testnet, khóa giao dịch hoặc ví trong phạm vi hiện tại.
