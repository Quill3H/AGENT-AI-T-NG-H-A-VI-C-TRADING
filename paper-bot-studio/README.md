# Paper Bot Studio — margin allocation and leverage

Ba ví paper độc lập100 USD cho15m/1h/4h; một lệnh mới mỗi chu kỳ hợp lệ. Theo giải thích mới ngày1/11/2026, mỗi lệnh dùng3–5% số dư đã ghi sổ làm vốn vào (initial margin danh nghĩa), nhân BTC15x / HYPE5x / SOL7x / ETH10x. Đây thay thế cách cũ lấy3–5% làm lỗ tại SL.

Ví100 USD, allocation4%: vốn4 USD; notional BTC60/HYPE20/SOL28/ETH40 USD trước làm tròn. Qty=notional/entry, làm tròn xuống theo sàn. MinQty/minNotional vẫn áp dụng, không ép lệnh khi dưới bước tối thiểu; BTC hiện có thể không đủ lot trong giới hạn5%. Phí0,05%/chiều và trượt giá0,02%/chiều trên toàn vị thế; funding từ Binance. Phí vào tính riêng. Lỗ dự kiến tại SL hiển thị riêng và phụ thuộc khoảng cách SL; không còn cố định3–5%. Không nhân PnL thêm một lần đòn bẩy.

Cho phép cộng dồn vị thế, không dự trữ margin danh mục hoặc mô phỏng thanh lý; initialMargin chỉ là cơ sở sizing. Giữ nguyên entry/qty; AI được dời TP/SL hoặc chốt sớm qua CLI manage và lưu audit. Chỉ paper, không real/testnet hoặc trading keys. Dashboard http://127.0.0.1:8792; bản gốc8791, sources và sổ báo cáo cũ không thay đổi.

Node server.mjs hoặc Start-Studio.ps1 khởi động worker. Node cli.mjs next kiểm tra lịch/sức khỏe, tạo analysisPath gọn giữ40 nến mỗi mã cùng quote/rules/funding; snapshot nguồn giữ nguyên và có SHA256. CLI submit dùng allocationPct; xem AI_RUNBOOK.md. Node --test chạy các kiểm tra. Không sửa data/state.json bằng tay, không in auth-token.

Dashboard/worker/CLI không gọi LLM. Phân tích thị trường dùng GPT-6.1 Sol Medium ở chat; tác vụ AI đơn giản riêng ưu tiên GPT-6 Luna khi chọn được. Automation chỉ thông báo lượt lỗi; không gửi báo cáo số lệnh/giữ lệnh/PnL thường lệ. Máy, Codex, mạng và hạn mức model phải sẵn sàng; heartbeat vẫn tiêu tốn usage dù im lặng.

Cách viết lệnh mới:3–5 lý do ngắn có số thứ tự, giọng chuyên nghiệp, không đoạn disclaimer lặp lại. Ba bot15m/1h/4h được xem là cuộc đua paper kiếm tiền ròng theo thời gian; so equity trừ100 USD cùng thời điểm, phân biệt lãi thả nổi và đã chốt. Giữ vốn/đòn bẩy/lịch và toàn bộ lịch sử.

Quản lý chủ động: AI xem vị thế lúc phân tích theo khung bot; được trailing/dời SL, đổi TP hoặc chốt toàn bộ sớm. Worker vẫn theo dõi TP/SL giữa các lượt AI. CLI manage kiểm chứng replay/funding trước thay đổi, bảo toàn first-touch mức cũ và lưu mức cũ/mới+lý do/thời điểm. Chốt sớm dùng giá bid/ask thực thi giả định và trạng thái EARLY_EXIT; không hỗ trợ chốt một phần.
