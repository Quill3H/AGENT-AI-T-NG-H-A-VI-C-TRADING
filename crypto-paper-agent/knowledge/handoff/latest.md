<!-- wiki-meta {"id": "latest", "type": "handoff", "title": "Điểm vào cho chat tiếp theo", "updated_at": "2026-10-30", "source_ids": ["state", "planner", "repair-review"], "verification": "AUTHOR_REPORTED", "page_ids": [], "git_head": "56382df63f0a58ba249d39b005ad97e90cd30150", "git_branch": "main", "git_status_sha256": "e4164e002dc335391eb67a001c29905a26a6dab74a83b1fc51d6e261a5eb20b6"} -->

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

## Hợp nhất với main ngày 29/10/2026

Checkpoint và metadata ở trên là lịch sử trước commit. Lượt hiện tại hợp nhất 05a396f với main 65960bf, giữ cả hai phía của bốn xung đột tài liệu/ledger. Chỉ metadata Git thực tế và báo cáo docs/reviews/MAIN_INTEGRATION_2026_10_29.md xác định trạng thái tích hợp mới. Nguồn state/planner/broker/pair-ops đã được đọc lại; cập nhật hash giữ lịch sử phiên bản trong manifest, không nâng nhãn kiểm chứng. CLI cointegration từ chối --append-ledger trước I/O theo quy tắc preregistration hiện hành; chạy không có cờ này vẫn xuất artifact. Không chạy lại thí nghiệm lịch sử để lựa chọn chiến lược.

## Checkpoint sửa lỗi ngày 30/10/2026

Main từ 56382df có bản sửa broker/risk/recovery và bằng chứng. Đọc [[synthesized-repair]] cùng docs/reviews/CAUSAL_RECOVERY_EVIDENCE_REPAIR_2026_10_30.md từ package trước khi tiếp nối. Báo cáo chứa commands, review độc lập, Tester snapshot, kết quả full core/E2E và giới hạn. Các checkpoint chưa commit/feature ở trên là lịch sử. Không tự chạy market download, reset account hoặc chấp nhận kinh tế; Git identity đầu trang là snapshot trước commit, sau commit phải đối chiếu lịch sử và HEAD hiện hành.

- [repair-review](../../docs/reviews/CAUSAL_RECOVERY_EVIDENCE_REPAIR_2026_10_30.md), các mục correction, implemented behavior và verification.
