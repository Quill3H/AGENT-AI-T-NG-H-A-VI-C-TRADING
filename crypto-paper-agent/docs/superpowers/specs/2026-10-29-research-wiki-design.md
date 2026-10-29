# Trading Research Wiki — thiết kế dự thảo

Ngày: 2026-10-29, Asia/Bangkok. Trạng thái: OWNER APPROVED trong chat ngày 2026-10-29, gồm bổ sung Understand Anything tại mục 12. Chủ dự án đã cho phép triển khai.

## 1. Mục tiêu và yêu cầu đã xác nhận

Chủ dự án muốn áp dụng LLM Wiki của Karpathy cho cả nghiên cứu/đánh giá chiến lược và tiếp nối công việc giữa các chat, sử dụng quy trình tốt phù hợp với dự án. Nguồn ý tưởng: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f .

Sản phẩm phải trả lời được: đã nghiên cứu gì, kết luận dựa trên bằng chứng nào, cấu hình/dữ liệu nào tạo kết quả, hạn chế nào còn mở, ai đã kiểm chứng và việc tiếp theo là gì. Wiki là lớp tổng hợp có thể kiểm tra, không thay thế nguồn gốc hoặc tự cấp quyền giao dịch.

## 2. Các cách xây

1. **Markdown có schema, mục lục, nguồn và công cụ kiểm tra** — đề xuất của người xây. Đọc trực tiếp trong Codex/Obsidian, lưu phiên bản, dễ sửa, không cần dịch vụ hoặc embedding. Hạn chế: chất lượng tổng hợp phụ thuộc việc AI đọc và cập nhật đúng quy trình.
2. **RAG trên tài liệu gốc** — tìm đoạn liên quan tốt khi tài liệu nhiều; cần bộ lập chỉ mục và truy hồi, vẫn phải tổng hợp lại quyết định và mâu thuẫn. Không giải quyết riêng được hồ sơ nghiên cứu tích lũy.
3. **Wiki kết hợp RAG** — linh hoạt nhưng thêm phụ thuộc và hai lớp phải duy trì. Để giai đoạn sau khi tìm kiếm văn bản/mục lục không đủ.

Chủ dự án đã duyệt phương án 1 trong chat ngày 2026-10-29. Các chi tiết kỹ thuật dưới đây là lựa chọn đề xuất của người xây.

## 3. Nguồn và hiện trạng đã quan sát

Repo: `eth-btc-research`, package: `crypto-paper-agent`. HEAD khi khảo sát: `47fdd6dbd6817ba251c6507186052fae48e51eb2`, branch `codex/eth-btc-cointegration-v1`. Đây là danh tính tại thời điểm khảo sát, phải đọc lại trước triển khai.

- `PROJECT_STATE.md`: checkpoint ETH/BTC 2026-10-22; phân biệt kết quả hồi cứu với chấp thuận kinh tế.
- `../PLANNER_HANDOVER.md`: checkpoint đầu tháng 9/2026; có độ trễ so với trạng thái và checkout.
- `../Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md`, `docs/decisions/`, `docs/reviews/`, `docs/research/`, `docs/reports-vi/`, `docs/operations/`: các nhóm nguồn cần đọc có chọn lọc.
- Có sửa đổi chưa commit trong Backtest Lab và PaperBroker, cùng các file ORB mới. Không kết luận chúng đã được kiểm thử/chấp thuận từ sự hiện diện của file.
- Chưa thấy `graphify-out/graph.json` tại root dự án hoặc repo. Không dựng graph tự động trong bước thiết kế.

Nguồn được đọc nguyên trạng. Không sửa `sources/` của ChatGPT project, không nhập các checkout review/tmp như thể đó là checkout chính. Các kết quả cũ chỉ là lời ghi trong báo cáo cho đến khi xác minh lại tương ứng.

## 4. Cấu trúc đề xuất

Tất cả đường dẫn sau tính từ package `crypto-paper-agent`:

```text
knowledge/
  AGENTS.md                 # hợp đồng đọc/ghi riêng cho wiki
  README.md                 # hướng dẫn tiếng Việt và ví dụ thao tác
  index.md                  # mục lục đủ trang, mô tả ngắn
  log.md                    # nhật ký thao tác, chỉ nối thêm
  project/                  # bản đồ dự án, quyết định, việc mở
  strategies/               # hồ sơ chiến lược và luận điểm
  concepts/                 # khái niệm đã tổng hợp, có nguồn
  experiments/              # hồ sơ từng thí nghiệm
  sources/                  # bản tóm tắt nguồn, không phải nguồn gốc
  templates/                # mẫu nguồn/chiến lược/thí nghiệm/bàn giao
  manifests/sources.json    # định danh nguồn và SHA-256
  handoff/latest.md          # điểm vào cho chat tiếp theo
scripts/research_wiki.py    # CLI offline bằng Python stdlib
tests/test_research_wiki.py
```

Không nhân bản toàn bộ dữ liệu thị trường hoặc mã nguồn vào wiki. `knowledge/sources/` chỉ chứa tóm tắt và liên kết đến tài liệu gốc; tên này không thay đổi quyền của thư mục `sources/` được đồng bộ ở root ChatGPT project.

## 5. Schema và bằng chứng

Mỗi trang nội dung có metadata định dạng JSON trong một khối được đánh dấu ở đầu Markdown, để parser stdlib đọc ổn định. Trường bắt buộc: `id`, `type`, `title`, `updated_at`, `source_ids`, `verification`. ID ổn định khi đổi tiêu đề. Ngày kiểm tra gần nhất không đồng nghĩa ngày nguồn ra đời.

Manifest nguồn có: ID, loại local/web, đường dẫn repo-relative hoặc URL, ngày truy cập, SHA-256 cho nguồn local và bản snapshot web nếu có, commit nếu tracked, cờ dirty/untracked, locator đoạn/trang/heading. Nguồn ngoài repo chỉ được nhận qua thư mục gốc nguồn được khai báo; không nhúng đường dẫn riêng tư tuyệt đối vào tài liệu có thể chia sẻ. CLI không chạy chỉ dẫn đọc từ nguồn.

Mỗi kết luận quan trọng phải trỏ tới source ID và vị trí cụ thể. Phân biệt dữ kiện, nhận định của tác giả nguồn và suy luận của AI. Trạng thái kiểm chứng gồm `NOT_VERIFIED`, `AUTHOR_REPORTED`, `INDEPENDENTLY_VERIFIED`, `CONFLICTED`, `STALE`; riêng quyết định nghiên cứu dùng trường khác: proposed, rejected, pending, accepted-by-owner. Không suy diễn sự chấp thuận từ nhãn kiểm thử.

Trang chiến lược: giả thuyết, luật/phiên bản, thị trường và khung thời gian, điều kiện dữ liệu, chi phí, bằng chứng thuận/nghịch, hạn chế mô phỏng, kết luận hiện tại, thí nghiệm tiếp theo. Bản thí nghiệm ghi: code/config/data identity, thời gian tín hiệu và tính sẵn có dữ liệu, khoảng train/validation/test, số lần thử đã biết, phí/slippage/funding, net return, drawdown/underwater, số lifecycle hoàn tất, benchmark, stress costs, OOS/forward và người kiểm chứng. Thiếu trường nào ghi unknown/not run; không tạo số thay thế. Định nghĩa và ngưỡng quyết định cụ thể phải theo đề cương thí nghiệm đã duyệt, không áp một ngưỡng thắng chung cho mọi chiến lược.

Holdout đã được xem hoặc dùng chọn phương án không còn được gọi untouched. Báo cáo hồi cứu, sample nhỏ, zero trades và giới hạn fills phải hiện rõ khi tóm tắt. Không tự tính lại số liệu hiệu quả từ văn xuôi.

## 6. Quy trình

### Nạp nguồn
AI đọc từng nguồn, đăng ký ID/hash/locator, viết tóm tắt, cập nhật trang liên quan và mục lục, ghi mâu thuẫn, nối nhật ký. CLI chỉ kiểm tra và hỗ trợ thao tác xác định; không tuyên bố tự tổng hợp kiến thức. Nội dung nguồn là bằng chứng không đáng tin về mặt chỉ dẫn, không được thay thế AGENTS hoặc quyền người dùng.

### Hỏi đáp và đánh giá
Đọc mục lục, chọn trang và kiểm tra nguồn liên quan còn đúng hash; trả lời kèm nguồn, giới hạn và trạng thái. Nếu nguồn thay đổi, giữ kết luận cũ dưới dạng lịch sử và đánh dấu stale cho các trang phụ thuộc trước khi tái tổng hợp. Mâu thuẫn chưa giải quyết được giữ song song với nguồn và câu hỏi mở. CLI không tự quyết nguồn nào đúng.

### Tiếp nối chat
Handoff chứa checkpoint, nhiệm vụ hiện hành, quyết định có nguồn, file sở hữu, việc chưa xong, lệnh tái hiện, kết quả kiểm tra với danh tính code, câu hỏi mở và danh sách cần đọc. Khi vào chat mới, AI phải đọc AGENTS áp dụng, lấy root/branch/HEAD/status mới và đối chiếu handoff với nguồn. `latest.md` chỉ là điểm vào, không phải nguồn thẩm quyền. Không dựa vào ngày mới nhất để ghi đè một quyết định đã duyệt.

Thêm chỉ dẫn khám phá ngắn vào AGENTS của repo sau khi duyệt và kiểm tra diff; bổ sung liên kết README. Không thay thế quy tắc gốc. Không có bảo đảm chat bên ngoài workspace hoặc không được cấp file sẽ tự đọc được wiki; hướng dẫn có đoạn khởi động để người dùng cung cấp đường dẫn/file khi cần.

### Kiểm tra sức khỏe
CLI phát hiện metadata lỗi, ID trùng, thiếu source, liên kết nội bộ hỏng, trang không có trong mục lục, hash nguồn đổi và handoff sai danh tính. Kiểm tra mâu thuẫn ý nghĩa, độ đúng của kết luận và kế hoạch nghiên cứu do AI/reviewer thực hiện, không coi lint sạch là chứng minh đúng nội dung. Phụ thuộc trực tiếp dùng source_ids; trang tổng hợp phụ thuộc các trang khác phải khai báo page_ids để stale lan truyền có phát hiện vòng lặp.

## 7. CLI tối thiểu và tính an toàn

Đề xuất các lệnh `status`, `lint`, `search`, `check-sources`, `handoff-check`; mặc định chỉ đọc, kết quả text hoặc JSON, offline. Search dùng chuỗi/keyword, không thực thi biểu thức hoặc mã trong nội dung. Không có daemon, lịch chạy, embedding hoặc API có phí. Việc ghi trang do AI thực hiện bằng công cụ sửa file với diff có thể review.

Mọi đường dẫn nguồn/link local được chuẩn hóa, kiểm tra nằm trong root khai báo sau resolve, bao gồm Windows junction/symlink và extended paths. Từ chối traversal và escape. Bỏ qua `.git`, secrets, venv, cache, raw market datasets, review/tmp checkouts trừ khi được chỉ định rõ như nguồn riêng. Không thực thi lệnh tái hiện chỉ vì chúng xuất hiện trong tài liệu. Không ghi đè nguồn, không xóa lịch sử, không chỉnh sửa dữ liệu/backtest/risk.

## 8. Nội dung seed và phạm vi phiên bản đầu

Đọc có chọn lọc và tạo khoảng 12–20 trang hữu ích: bản đồ dự án, quyết định/việc mở, tiêu chuẩn bằng chứng, Backtest Lab, hạn chế thực thi, funding carry, ETH/BTC cointegration, ORB/FVG, mục lục thí nghiệm và handoff. Số trang không phải tiêu chí hoàn thành; mỗi trang phải có nguồn thực tế. ORB đang dirty phải mang nhãn chưa commit/chưa kiểm chứng, không lấy kết quả từ tên file.

Seed mặc định chỉ từ checkout `eth-btc-research` hiện tại; không quét tất cả project, lịch sử chat hoặc tải nguồn web hàng loạt. Có thể bổ sung nguồn local `reports/`, `output/` qua root khai báo sau khi xác minh nguồn gốc. Không lưu vào bộ nhớ cá nhân Codex; wiki này thuộc dự án.

## 9. Kế hoạch kiểm chứng và nghiệm thu

Sau duyệt: viết kế hoạch Superpowers, chọn phạm vi sở hữu file, triển khai CLI bằng TDD với fixtures nhỏ độc lập, rồi seed nội dung và review riêng. Dùng runtime Python đang có; không cài gói nếu stdlib đủ.

Kiểm thử cần bao phủ: source thay đổi khiến kết luận stale; stale lan tới trang tổng hợp; nguồn thiếu/hash sai; liên kết hỏng; metadata/ID trùng; traversal/junction escape; UTF-8 tiếng Việt; handoff HEAD/dirty mismatch; báo cáo cũ không được nâng trạng thái. Test các hợp đồng quan trọng, không tạo test chỉ lặp implementation.

Chạy walkthrough thực tế: nạp một nguồn; trả lời một câu hỏi so sánh chiến lược có dẫn chứng; thay bản sao fixture nguồn và phát hiện stale; mở phiên reviewer với handoff để tìm bước tiếp theo. Reviewer đọc riêng nội dung tài chính/nghiên cứu như kiểm tra nguồn và logic, không coi đó là chấp thuận lợi nhuận. Không gọi backtest đầy đủ chỉ để thử wiki. Chạy targeted suite và git diff --check; chạy full offline suite nếu quy định repo áp dụng cho mốc hoàn tất hoặc có thay đổi tích hợp ảnh hưởng bot, ghi rõ kết quả thực chạy.

Điều kiện đạt: không sửa nguồn/bot; mọi claim seed trọng yếu truy được nguồn; không có lỗi lint blocking; thay đổi nguồn được phát hiện; chat reviewer xác định được checkpoint và bước tiếp theo; không có P1/P2 chưa xử lý. Chủ dự án quyết định nghiệm thu. Báo cáo phân biệt kiểm tra của tác giả và reviewer.

## 10. Triển khai và quản lý phiên bản

Sau duyệt, đọc lại git status. Không stage/commit thay đổi có sẵn. Trước commit/push phải đối chiếu quy định main với checkout branch hiện tại và xác định nơi tích hợp an toàn; bản thiết kế này không cấp quyền ghi đè/merge hoặc tuyên bố đồng bộ remote. Có thể hoàn thiện bản local để review mà không cần chạm nhánh chính. Lưu bản thiết kế riêng, không commit kèm thay đổi người khác. Không sửa checkpoint dự án để tuyên bố wiki hoàn thành trước khi kiểm tra thực tế.

## 11. Giới hạn và các lựa chọn giao cho người xây

Không có dashboard, tự tìm chiến lược thắng, tự tối ưu, live/testnet hay tự tiếp tục chạy sau khi chat kết thúc. Wiki được cập nhật khi AI được gọi và làm theo hợp đồng; automation cần yêu cầu riêng. Obsidian chỉ là cách xem tùy chọn, không bắt buộc cài.

Người xây quyết tên file/ID cụ thể, JSON schema chi tiết, câu chữ mẫu, thứ tự seed và cách trình bày kết quả CLI trong phạm vi trên. Mọi mở rộng sang remote services, đọc nguồn riêng tư mới, chạy thí nghiệm dài, thay luật chiến lược hoặc tự động hóa phải có yêu cầu riêng.

## 12. Bổ sung skill Understand Anything và phân công công cụ

Đã đối chiếu SKILL.md của `understand` và `understand-knowledge` sau câu hỏi của chủ dự án về skill mới cài. Trước bổ sung này, thiết kế chưa tích hợp nhóm đó. Chưa chạy tạo graph hoặc dashboard; đây là cập nhật thiết kế.

- `superpowers:brainstorming`: thiết kế; đã dùng builder check riêng. Sau duyệt dùng writing-plans, TDD cho hành vi CLI, review và verification theo phạm vi tương ứng; không tuyên bố đã chạy các bước triển khai.
- `understand-anything:understand`: đề xuất tạo bản đồ codebase riêng tại `crypto-paper-agent/.ua/`, phục vụ tìm module và mối quan hệ trước khi AI sửa mã. Đọc phần còn lại của skill, kiểm tra runtime và phạm vi nguồn trước khi chạy; không âm thầm cài/build vào thư mục plugin ngoài workspace.
- `understand-anything:understand-knowledge`: đề xuất tạo graph wiki tại `knowledge/.ua/` sau khi có seed. Skill này nhận diện chính mẫu wiki Karpathy. Giữ graph kiến thức và graph code riêng để tránh trộn suy luận nghiên cứu với quan hệ mã nguồn.
- `understand-chat`, `understand-diff`, `understand-explain`, `understand-onboard`, `understand-dashboard`: các tuyến dự kiến cho hỏi đáp code, phân tích thay đổi, giải thích module, hướng dẫn tiếp nối và xem graph. Chưa đọc chi tiết hoặc thực thi các skill này; đọc SKILL.md tương ứng khi công việc thực tế gọi tới, rồi kiểm tra khả năng tích hợp.
- Graphify: đã đọc skill và kiểm tra chưa có graph sẵn. Không dựng thêm graph trùng lặp mặc định; chỉ cân nhắc khi có nhu cầu mà pipeline trên chưa đáp ứng.

Điều chỉnh định dạng: các liên kết giữa trang wiki dùng `[[target]]` với target ổn định và không trùng tên; nguồn gốc dùng Markdown links kèm source ID. CLI lint phải hiểu wikilink, anchor và phát hiện target mơ hồ. Metadata JSON đầu trang chỉ được giữ sau khi thử fixture với parser `parse-knowledge-base.py`; nếu parser không nhận trường cần thiết, dùng adapter hoặc frontmatter tương thích được kiểm chứng, tránh duy trì hai nguồn metadata mâu thuẫn. Thử parser trên fixture trước khi seed hàng loạt.

Graph là chỉ mục có thể tái tạo. Mọi cạnh suy luận phải phân biệt với liên kết trích dẫn trực tiếp và không nâng trạng thái bằng chứng. Ghi hash các file được phân tích cùng HEAD/dirty tại thời điểm dựng; thay đổi đầu vào đánh dấu graph stale. Chat đọc trực tiếp nguồn nếu graph thiếu/cũ hoặc pipeline không khả dụng. Không bật hook auto-update hoặc background service mặc định. Nếu dashboard yêu cầu dependency/build ngoài workspace hoặc quyền bổ sung, giữ wiki dùng được trước và báo riêng giới hạn.

Bổ sung nghiệm thu: parser thực sự nhận được fixture wiki tiếng Việt và wikilinks; graph không có cạnh dangling; node truy ngược được trang gốc; graph cũ được phát hiện sau khi sửa nguồn/trang; một phiên reviewer dùng handoff và graph để xác định đúng module và bằng chứng liên quan. Việc graph tồn tại không chứng minh nội dung hoặc hiệu quả chiến lược.
