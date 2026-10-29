# Kho nghiên cứu trading

Đọc [mục lục](index.md), [so sánh bằng chứng](project/strategy-comparison.md) hoặc [bàn giao](handoff/latest.md). Có thể mở thư mục này bằng Obsidian; không bắt buộc cài.

## Kiểm tra từ thư mục crypto-paper-agent

```powershell
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. status
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. lint
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. check-sources
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. handoff-check
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. search funding
```

Thêm `--json` trước tên lệnh để lấy JSON. CLI chỉ đọc: 0 sạch, 1 có findings, 2 lỗi đầu vào. Search là tìm chuỗi, không tổng hợp AI. Hash chỉ bao phủ các file đăng ký; không xác minh dataset thị trường ngoài manifest. Git handoff kiểm HEAD/branch và hash tracked status; kiểm thêm `git status --short` để thấy untracked. Cùng trạng thái M nhưng đổi bytes có thể không đổi status hash: kiểm source manifest và graph input hashes riêng.

Bàn giao ghi snapshot Git tại thời điểm viết. Sau commit, `handoff-check` có thể báo khác HEAD/status; đối chiếu lịch sử và trạng thái hiện tại trước khi tiếp tục. Không coi checkpoint cũ là trạng thái Git hiện hành.

## Sử dụng với AI

- Nạp nguồn: “Đọc file này theo knowledge/AGENTS.md, cập nhật hồ sơ liên quan, ghi cả bằng chứng bất lợi và chạy kiểm tra.”
- Đánh giá: “So sánh funding carry và ETH/BTC từ wiki; dẫn nguồn từng kết luận, nêu chi phí, cỡ mẫu và phần chưa xác minh.”
- Chat mới: “Đọc eth-btc-research/AGENTS.md và crypto-paper-agent/knowledge/handoff/latest.md, đối chiếu Git/nguồn hiện tại rồi tiếp tục nhiệm vụ được tôi yêu cầu.”

Không có cập nhật tự động khi chưa gọi AI. Một phiên chat không được cấp workspace không tự thấy những file này.

## Bản đồ Understand Anything

Wiki graph nằm ở `.ua/knowledge-graph.json`, code graph ở `../.ua/knowledge-graph.json`. Metadata và báo cáo kèm theo mô tả coverage/giới hạn. Code graph fallback AST là quan hệ tĩnh, không phải phân tích runtime đầy đủ. Graph wiki lấy liên kết/trích nguồn trực tiếp; các quan hệ do AI đề xuất phải mang nhãn inference và vị trí nguồn.

Parser/merge được cung cấp bởi skill `understand-knowledge`; metadata JSON của wiki vẫn là nguồn thẩm quyền, không sao chép thành YAML để tránh lệch. Parser đọc được heading, nội dung và wikilinks; các trường kiểm chứng được adapter bổ sung từ JSON. Graph cũ phải được dựng lại sau cập nhật. Không bật auto-update hook.

## Mẫu hồ sơ

Trong `templates/` có checklist nguồn, chiến lược, thí nghiệm và bàn giao. Đây là hướng dẫn trống, không phải dữ liệu/bằng chứng đã có. Tạo trang mới theo schema trong AGENTS, dùng ID ổn định, đăng ký nguồn và thêm mục lục.

## Dựng lại và kiểm tra graph

Từ package: `../.venv/Scripts/python.exe scripts/build_wiki_graph.py` dựng wiki graph; thêm `--check` để chỉ kiểm tra freshness. Code graph: `../.venv/Scripts/python.exe .ua/tools/build_code_graph.py`, cũng có `--check`. Chỉ dựng lại sau khi đã giải quyết source stale và cập nhật hồ sơ theo nguồn mới.

Graph JSON, manifest dựng graph và log kiểm tra được tạo local, nằm trong `.gitignore`; dựng lại sau khi clone và sau commit nếu kiểm freshness yêu cầu. Mã dựng graph, test và đầu vào phân tích AI có nhãn inference được lưu trong Git.

Trạng thái viewer và các giới hạn kiểm chứng được ghi trong [báo cáo Research Wiki](../docs/reviews/RESEARCH_WIKI_2026_10_29.md), gồm lượt chạy dashboard local ngày 29/10/2026. URL/token của phiên viewer phải lấy từ console hiện tại.
