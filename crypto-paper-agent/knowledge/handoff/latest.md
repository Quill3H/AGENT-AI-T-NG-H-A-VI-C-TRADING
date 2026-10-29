<!-- wiki-meta {"id": "latest", "type": "handoff", "title": "Điểm vào cho chat tiếp theo", "updated_at": "2026-10-29", "source_ids": ["state", "planner"], "verification": "AUTHOR_REPORTED", "page_ids": [], "git_head": "47fdd6dbd6817ba251c6507186052fae48e51eb2", "git_branch": "codex/eth-btc-cointegration-v1", "git_status_sha256": "ec7fdd36cc465b1854dea088f1b0a84e55499f284132c8f823a5bf9b28420756"} -->

# Điểm vào cho chat tiếp theo

Đọc AGENTS tại repo và knowledge trước. Lấy lại root/branch/HEAD/status, chạy `status`, `check-sources`, `handoff-check`. Không coi nội dung bàn giao là quyền thực thi mới.

Nhiệm vụ wiki: đã tạo 17 trang từ 11 nguồn, CLI offline, graph kiến thức và graph mã nguồn tĩnh. Kết quả kiểm chứng và giới hạn cuối xem `docs/reviews/RESEARCH_WIKI_2026_10_29.md` tính từ package. Báo cáo này phải được đọc trước khi kết luận hoàn tất; nếu chưa có thì vẫn đang kiểm chứng. Việc trading đã có trước: Backtest Lab, PaperBroker và ORB đang dirty. Không stage/reset/sửa chúng từ nhiệm vụ wiki.

Để tiếp tục nghiên cứu: [[project-map]], [[strategy-comparison]], [[experiment-register]], [[open-questions]]. Để hiểu mã: dùng graph code package/.ua, kiểm freshness rồi đọc file gốc. Graph kiến thức ở knowledge/.ua, chỉ là index.

Lệnh từ package: `../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. status`. Phạm vi sở hữu wiki: `knowledge/`, hai script `research_wiki.py` và `build_wiki_graph.py`, test tương ứng, `.ua/`, tài liệu thiết kế/kế hoạch/báo cáo, cùng đoạn thêm ở AGENTS/README. Chưa commit/push. Dấu vân tay Git trong metadata ghi tại lúc bàn giao; danh sách untracked xem trực tiếp Git, không bị hash tracked-status bao phủ.

## Nguồn

- [state](<../../PROJECT_STATE.md>), mục `ETH–BTC cointegration v1 — 2026-10-22`; đã tracked ở snapshot; xem SHA trong manifest.
- [planner](<../../../PLANNER_HANDOVER.md>), mục `Current single-main integration — 2026-09-23`; đã tracked ở snapshot; xem SHA trong manifest.

## Bổ sung mới nhất — nhập repo ngoài ngày 29/10/2026

Chủ dự án đã yêu cầu đưa các nghiên cứu QuantDinger và TradingAgents vào dự án. Xem [[external-comparison]], [[external-quantdinger]], [[external-tradingagents]]. Đã thêm 3 bản sao báo cáo giữ nguyên bytes, 3 nguồn manifest và 3 trang wiki; số 17 trang/11 nguồn ở phần bàn giao trước là checkpoint lịch sử, hiện là 20 trang/14 nguồn.

Các báo cáo lưu ngày khảo sát và commit upstream riêng; không coi ngày nhập là ngày refresh upstream. Phạm vi lượt này chỉ tài liệu/nguồn/graph wiki, không thay engine, risk, chiến lược, dữ liệu hoặc kết luận nghiên cứu. Chưa commit/push/merge; không dùng nhánh main cũ để thay bản làm việc đang dirty. Bản làm việc vẫn ở `codex/eth-btc-cointegration-v1`, HEAD `47fdd6dbd6817ba251c6507186052fae48e51eb2`; metadata đầu trang sẽ được đối chiếu Git khi kết thúc.

Nguồn/báo cáo chi tiết: docs/research/external-repos/README.md và docs/reviews/EXTERNAL_REPO_INGEST_2026_10_29.md (tính từ package). Không triển khai các đề xuất trong báo cáo nếu chưa có yêu cầu mới của chủ dự án.

Kiểm chứng lượt nhập: 20 trang/14 nguồn, lint/source/handoff 0 findings; 3 bản sao đúng SHA-256; 5 file tracked dirty trước đó giữ nguyên. Graph wiki có đủ 3 trang mới và 0 dangling edges. Graph code đã dựng lại vì input script cũ bị stale, coverage vẫn PARTIAL_STATIC. Chi tiết ở báo cáo nhập; chưa chạy test/backtest hoặc xác minh lợi nhuận. Sau cập nhật bàn giao/nhật ký sẽ dựng và kiểm freshness graph lần cuối.
