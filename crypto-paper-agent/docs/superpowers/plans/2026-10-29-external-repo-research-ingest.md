# Nhập nghiên cứu repo ngoài vào dự án

Ngày: 29/10/2026. Chủ dự án yêu cầu đưa các nghiên cứu QuantDinger và TradingAgents vào dự án chính.

Phạm vi: tài liệu và wiki local tại `crypto-paper-agent`; không phải triển khai các repo ngoài, thay engine, sửa risk hoặc chấp nhận hiệu quả kinh tế. Bản làm việc đang ở `codex/eth-btc-cointegration-v1`, HEAD `47fdd6dbd6817ba251c6507186052fae48e51eb2`, có thay đổi sẵn của nhiệm vụ khác; không chuyển nhánh, commit/push/merge trong nhiệm vụ này.

1. Kiểm tra wiki/nguồn/bàn giao trước nhập; giữ nguyên bản nghiên cứu đã lập và ngày khảo sát.
2. Sao chép ba báo cáo vào `docs/research/external-repos/`, kiểm tra SHA-256 khớp bản gốc; đăng ký nguồn và provenance trong manifest wiki.
3. Thêm hồ sơ QuantDinger, TradingAgents và bảng đối chiếu/ứng dụng; cập nhật mục lục, danh mục nguồn, nhật ký và bàn giao.
4. Chạy lint, kiểm nguồn, kiểm bàn giao, tìm kiếm và dựng lại graph wiki; kiểm graph mã còn mới. Đối chiếu hash các file đã dirty trước đó để bảo đảm không sửa việc khác.

Trạng thái bằng chứng của các báo cáo được giữ: đọc nguồn/tài liệu, chưa tự chạy repo ngoài, chưa xác minh lợi nhuận. QuantDinger neo khảo sát 23/10/2026; TradingAgents neo khảo sát 29/10/2026. Chưa refresh nội dung upstream trong lượt nhập.
