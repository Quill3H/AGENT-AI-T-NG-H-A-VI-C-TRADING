# Nhập nghiên cứu QuantDinger và TradingAgents

Ngày: 29/10/2026. Theo yêu cầu đưa các nghiên cứu vào dự án chính. Phạm vi tài liệu/wiki local, chưa triển khai repo ngoài.

## Identity và sở hữu

Repo eth-btc-research, branch codex/eth-btc-cointegration-v1, HEAD 47fdd6dbd6817ba251c6507186052fae48e51eb2. Có thay đổi sẵn từ nhiệm vụ khác. Không stage, commit, push, merge hoặc chuyển main. Không sửa nguồn synced, engine, risk, chiến lược, dataset, ledger hoặc kết luận nghiên cứu.

## Nhập nguồn

Ba báo cáo giữ nguyên bytes ở docs/research/external-repos: QuantDinger, TradingAgents và bằng chứng paper TradingAgents. Manifest đăng ký 3 nguồn cùng SHA-256, locator, ngày khảo sát/ngày nhập, origin_path và upstream_commit. Giữ trạng thái AUTHOR_REPORTED; chưa tự chạy repo ngoài hoặc xác minh lợi nhuận. QuantDinger khảo sát 23/10/2026; TradingAgents khảo sát 29/10/2026. Lượt nhập không refresh upstream.

Ba hồ sơ ở knowledge/external: quantdinger.md, tradingagents.md, comparison.md. Cập nhật index/source-catalog/log/handoff. Wiki hiện có 20 trang/14 nguồn; số 17/11 trong các checkpoint trước giữ làm lịch sử.

## Kiểm chứng

Dùng Python có sẵn ../.venv/Scripts/python.exe từ package:

- scripts/research_wiki.py --root knowledge --repo .. status
- scripts/research_wiki.py --root knowledge --repo .. lint
- scripts/research_wiki.py --root knowledge --repo .. check-sources
- scripts/research_wiki.py --root knowledge --repo .. handoff-check
- scripts/research_wiki.py --root knowledge --repo .. search TradingAgents
- scripts/build_wiki_graph.py và scripts/build_wiki_graph.py --check
- .ua/tools/build_code_graph.py và .ua/tools/build_code_graph.py --check
- git diff --check

CLI trước cập nhật log/handoff cuối: 20 trang/14 nguồn/0 findings. Ba bản sao khớp SHA-256 gốc. Năm file tracked dirty trước lượt nhập giữ nguyên hash. Graph wiki có đủ ba hồ sơ và 0 cạnh treo, 43 nodes/127 edges. Kiểm freshness chạy lại sau cập nhật log/handoff; đọc kết quả thực tế trong bàn giao phiên này.

Graph code ban đầu stale vì scripts/build_wiki_graph.py đã đổi trước lượt nhập; đã dựng lại derived graph từ bytes hiện tại, không sửa script. Coverage vẫn PARTIAL_STATIC. Parser wiki trung gian báo unresolved wikilinks dạng ID; adapter cuối/CLI xử lý được, graph cuối không có cạnh treo.

Một kiểm tra tự viết ban đầu dùng sai key metadata của graph nên AssertionError; đã kiểm schema thực tế, sửa truy vấn sang node IDs và xác minh đủ ba trang. Không sửa code sản phẩm để né kiểm tra.

Không thêm/chạy test chương trình vì thay đổi chỉ tài liệu/manifest và graph dẫn đường. Không chạy backtest, tải dữ liệu, gọi LLM hoặc mở dashboard. Kiểm cấu trúc/hash không xác nhận mọi nhận định, hiệu quả kinh tế hoặc trạng thái upstream hiện tại.

## Kết quả cuối sau cập nhật nhật ký/bàn giao

Đã dựng lại wiki graph rồi chạy riêng từng lệnh: status, lint, check-sources và handoff-check đều exit 0, 20 trang/14 nguồn/0 findings. Wiki graph và code graph đều fresh: true; git diff --check exit 0 (chỉ cảnh báo LF/CRLF ở hai file đã dirty từ trước). Không thay đổi thêm input wiki sau các lượt kiểm này. Đây là xác minh của tác giả trong phạm vi nhập tài liệu, không phải independent review hay economic acceptance.
