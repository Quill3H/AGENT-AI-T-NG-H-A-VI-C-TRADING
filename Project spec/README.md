# Đặc tả và bản đồ tài liệu

Cập nhật: 29/10/2026. Hai lớp cần đọc cùng nhau: **đặc tả nói hệ thống phải làm gì; bằng chứng nói một phiên bản đã làm được gì**.

| Tài liệu | Vai trò |
| --- | --- |
| [Master Spec](CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md) | Hợp đồng hiện tại và baseline kỹ thuật gốc được bảo tồn |
| [CURRENT_STATUS](CURRENT_STATUS.md) | Tiến độ, số liệu, nhánh và giới hạn xác minh |
| [ROADMAP](ROADMAP.md) | Việc tiếp theo, đầu ra và điều kiện chuyển bước |
| [EVIDENCE_REGISTER](EVIDENCE_REGISTER.md) | Commit/path của nguồn và các mâu thuẫn cần xử lý |
| [Định hướng](<../Initial idea/CURRENT_VISION.md>) | Mục đích, cách nghĩ và các hướng nghiên cứu |
| [Product charter](../crypto-paper-agent/docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md) | Quyền, vai trò, trình tự G0–G6 và quyết định còn mở |
| [ADR](../crypto-paper-agent/docs/decisions/) | Các quyết định kỹ thuật/risk, đọc đúng phạm vi và phiên bản |
| [PROJECT_STATE](../crypto-paper-agent/PROJECT_STATE.md), [handover](../PLANNER_HANDOVER.md) | Checkpoint và lịch sử; có phát biểu tác giả cần đối chiếu nguồn |
| [Operations](../crypto-paper-agent/docs/operations/) | Cách vận hành và tái hiện |
| [Review](../crypto-paper-agent/docs/reviews/) | Báo cáo kiểm tra, chưa tự đồng nghĩa người dùng nghiệm thu |
| [Research](../crypto-paper-agent/docs/research/), [ledger](../crypto-paper-agent/docs/research/ledger/LEARNING_LOG.md) | Thí nghiệm và lịch sử lựa chọn |
| [Config](../crypto-paper-agent/config/), [src](../crypto-paper-agent/src/), [tests](../crypto-paper-agent/tests/) | Cấu hình, triển khai và kiểm tra hành vi |

## Thẩm quyền và cách xử lý khác biệt

Yêu cầu mới nhất của chủ dự án quyết định phạm vi; ADR được duyệt quyết định hành vi kỹ thuật/risk trong phạm vi đó. Charter giữ hợp đồng sản phẩm. Master Spec lấp chi tiết còn lại. Ý tưởng gốc giữ lý do làm dự án.

Code là bằng chứng hành vi, không tự chứng minh hành vi đúng đặc tả. Báo cáo tác giả, kết quả tester, review độc lập và quyết định nghiệm thu phải ghi riêng. Khi khác nhau, lưu cả hai và chỉ rõ nguồn; không tự sửa số để các tài liệu trông nhất quán.

## Quy tắc tổ chức

- Giữ đường dẫn hiện tại để các task/review cũ còn tra được; không di chuyển mã hay xóa lịch sử trong lượt cập nhật này.
- Dùng mục lục để điều hướng thay vì nhân bản cùng một trạng thái trong nhiều tài liệu.
- Mỗi thí nghiệm có ID, giả thuyết, code/config/data hash, thời gian, universe, costs, đối chứng, kết quả và người kiểm chứng.
- Một thay đổi chỉ mục hoặc graph không nâng mức bằng chứng. Bản đồ cục bộ chưa có trên main không phải tài liệu GitHub đã bàn giao.
- Ngày cập nhật trang không phải ngày chạy lại thí nghiệm. Ghi rõ khi chỉ đọc nguồn.
