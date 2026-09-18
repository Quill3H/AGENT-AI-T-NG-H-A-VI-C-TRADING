# PLANNER_HANDOVER — Hồ sơ tiếp nối cho GPT và Antigravity

> Đọc file này đầu mỗi phiên mới, rồi đối chiếu GitHub hiện tại. File này thay cho việc phụ thuộc trí nhớ hội thoại; không bảo đảm AI tự nhớ hoặc tự theo dõi GitHub.
> Chỉ cập nhật thông tin đã xác minh hoặc đánh dấu rõ “tác giả báo cáo”, “chưa kiểm tra”, “chờ người dùng”.

## 1. Dự án và cách phối hợp

- Repo: `Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING`, nhánh `main`.
- Gốc chương trình trong repo: `crypto-paper-agent/`.
- Mục tiêu: crypto paper trading agent; làm tuần tự từng giai đoạn, risk-first, chống lookahead.
- Người dùng không rành code. GPT làm planner/reviewer, Antigravity triển khai. Giải thích ngắn bằng tiếng Việt, tránh bắt người dùng truyền đi nhiều tài liệu kỹ thuật.
- GitHub là nơi bàn giao. GPT có thể tạo/cập nhật tài liệu review và task theo workflow đã thống nhất; không tự thay code triển khai trong một yêu cầu chỉ review.
- Người dùng quyết định nghiệm thu và cho phép chuyển giai đoạn. GPT không coi câu “Anti làm xong” là quyền tự bắt đầu giai đoạn tiếp.
- Không có kênh điều khiển trực tiếp Antigravity được thiết lập; GitHub không tự cập nhật nếu Anti chưa commit/push. Chỉ kiểm tra khi có phiên làm việc/yêu cầu; không hứa giám sát nền.

## 2. Trạng thái mới nhất đã xác minh

- **Giai đoạn 0–2:** PROJECT_STATE ghi đã được Claude duyệt trước khi GPT tiếp quản; không tuyên bố GPT đã review lại toàn bộ.
- **Giai đoạn 3:** Anti sửa qua ba vòng. Code cuối đã kiểm tra: `44014393a2ed6dba7188096a6d1de600daa972d0`.
- **GPT Review 04:** đạt kiểm tra kỹ thuật G1–G3 và hồi quy offline đã thực thi; khuyến nghị nghiệm thu, người dùng đã yêu cầu tiếp tục Giai đoạn 4. Chi tiết: `crypto-paper-agent/docs/reviews/GPT_STAGE_03_REVIEW_04.md`.
- **Phê duyệt người dùng:** sau kết luận Review 04, người dùng đã yêu cầu tạo prompt để tiếp tục giai đoạn tiếp theo. Giai đoạn 3 được chấp thuận theo phạm vi Review 04; cho phép Antigravity triển khai riêng Giai đoạn 4 theo task dưới đây.
- **Giai đoạn 4 — Paper Execution Engine:** đã giao task, chưa có bằng chứng code hoàn thành. Task hiện hành: `crypto-paper-agent/docs/planning/ANTIGRAVITY_STAGE_04_TASK.md`. Bước tiếp theo: Anti đọc task, triển khai/kiểm thử/commit/push rồi GPT review. Không cho phép Giai đoạn 5.
- Test reviewer: **151 passed, 2 skipped, 5 network deselected**; thêm **9/9 kiểm thử độc lập đạt**, mô phỏng vốn đạt. Không cộng 9 bài ngoài repo vào số collected chính thức.
- Anti báo **158/158 passed** tại môi trường riêng; reviewer chưa chạy lại network và thiếu pandas-ta cho 2 test.
- Không có blocker còn mở trong tập G1–G3 đã tái hiện. Ghi chú phạm vi/contract component và sửa con số tài liệu nằm trong Review 04.
- Nếu main đã tiến thêm commit: không tự gắn kết luận này cho code mới. Xem diff và review phần thay đổi trước.

## 3. Tài liệu nguồn cần đọc

Các đường dẫn dưới đây tính từ gốc repository:

1. `crypto-paper-agent/PROJECT_STATE.md`: quyết định, checklist, giới hạn đã ghi nhận.
2. `Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md`: đặc tả; đọc phần tương ứng giai đoạn đang làm.
3. `crypto-paper-agent/docs/decisions/`: ADR 0001–0006 và phụ lục.
4. `crypto-paper-agent/docs/reviews/GPT_STAGE_03_REVIEW_04.md`: kết luận review mới nhất.
   Task tiếp theo: `crypto-paper-agent/docs/planning/ANTIGRAVITY_STAGE_04_TASK.md`.
5. `crypto-paper-agent/CHANGELOG.md` và code/tests tại commit thực tế.
6. `crypto-paper-agent/BÁO CÁO TÓM TẮT/GIAI ĐOẠN 3/`: báo cáo triển khai của Anti.
7. `Initial idea/AGENT_SPEC.docx`: ý tưởng ban đầu; không ghi đè quyết định mới bằng ý tưởng cũ.

Khi mâu thuẫn: yêu cầu hiện tại được người dùng xác nhận và quyết định/ADR mới có ưu tiên hơn mặc định cũ trong spec. Code/test là bằng chứng hành vi thực tế, không tự chứng minh hành vi đó đúng yêu cầu. Báo cáo tác giả không thay thế review độc lập. Nếu thiếu nguồn hoặc quyền đọc repo, nêu rõ và xin nguồn/quyền; không phỏng đoán.

## 4. Quy tắc đã chốt phải giữ

- Paper-only; không triển khai đặt lệnh tiền thật/testnet, không cần API key giao dịch ở phạm vi hiện tại.
- News filter mặc định disabled. Nếu bật thì lịch thiếu/hỏng phải chặn; lịch rỗng đúng schema được phép theo chính sách đã công bố.
- Phục hồi risk sau **3 lệnh thắng liên tiếp** (`after_3_wins`), không quay về mặc định cũ phục hồi sau 1 thắng.
- Mốc dữ liệu backtest đã chọn: `2021-01-01` → `2026-09-01`; không tự đổi.
- RL chỉ optional Giai đoạn 11; không chen vào 0–10.
- Đồng hồ UTC mô phỏng; không fallback datetime.now để duyệt lệnh. Admission dùng `account_state.current_time`, không dùng thời điểm signal cũ.
- Không lookahead; swing CVD xác nhận tại i+k, không gán ngược tín hiệu về i.
- OI hybrid Data Vision + REST; confluence optional, NaN fallback có chủ đích theo ADR 0005.
- pandas-ta có fallback pure pandas theo ADR 0004; thiếu thư viện phải phân biệt skip với pass.
- Risk gate đối soát actual stop risk với ngân sách khai báo sau multiplier; available margin gồm phí vào ước tính; không double reduction.
- Breaker: sliding window (T-24h,T], thời gian monotonic, lock 24h, không kéo dài khóa vì giao dịch từ chối; sau hết hạn vẫn xử lý loss mới và khóa lại nếu cần; vốn cạn halted.
- Liquidation: tier tại notional thanh lý, bracket liên tục, không ngoại suy ngoài snapshot, không fallback tier cuối.
- Không nới risk hoặc nuốt dữ liệu lỗi để làm test pass.
- Máy Anti có PROJECT_ROOT chính thức trong PROJECT_STATE. Không suy đoán/quét ổ đĩa/tạo bản project khác trên máy người dùng; mọi nghi ngờ phải hỏi. Môi trường review độc lập có thể dùng checkout tạm riêng.

## 5. Lịch sử review tối thiểu để không làm lại vòng cũ

| Mốc code | Vòng đánh giá tiếp theo | Phát hiện và trạng thái hiện tại |
|---|---|---|
| `6bdf5038a6d5bb5fc3d422d319662fd7e105519d` | Review 01 | R1–R6: dữ liệu lỗi, sizing/margin, clock/bảo vệ, breaker, liquidation tier, mô phỏng thiếu minh bạch. Anti sửa tại d121cf6 |
| `d121cf6449599c71867dfbe3db5b7808094587f4` | Review 02 | F1–F5: ngân sách khai báo, malformed input/margin, admission/news, đồng hồ breaker, solver ngoài bracket. Anti sửa tại 2f3bc30 |
| `2f3bc30709fa3e24ccb0a0ebbc7823f0ef779522` | Review 03 | G1–G3: config/multiplier NaN, gate lùi thời gian crash, enabled news thiếu lịch vẫn pass. Anti sửa tại 4401439 |
| `44014393a2ed6dba7188096a6d1de600daa972d0` | Review 04 | Các tái hiện G1–G3 và hồi quy độc lập đạt; người dùng đã yêu cầu tiếp tục Giai đoạn 4 |

Review 02/03 lưu ở `crypto-paper-agent/docs/reviews/`; ADR 0006 ghi quyết định risk qua các vòng. Không tiếp tục yêu cầu sửa lỗi đã đạt nếu không có bằng chứng hồi quy mới.

## 6. Quy trình bắt đầu mỗi phiên GPT

1. Đọc hồ sơ này và PROJECT_STATE trên GitHub, không chỉ bản chat cũ.
2. Xác định SHA main hiện tại và commit cần review. Phân biệt commit code với commit tài liệu của reviewer.
3. Đọc latest review, ADR và phần spec liên quan; nếu mới hơn hồ sơ thì cập nhật trạng thái từ nguồn xác minh.
4. Chỉ review khi được yêu cầu review; chỉ giao triển khai khi người dùng cho phép. Không push thay đổi code trong vai trò reviewer.
5. Khi kiểm thử, báo riêng pass/skip/deselected/network chưa chạy, môi trường và SHA; không sao chép số tác giả thành kết quả của mình.
6. Sau mỗi mốc quan trọng, cập nhật file này với latest review, blocker, quyền cho phép hiện tại và next action; lưu task triển khai riêng có tiêu chí nghiệm thu.
7. Handoff cho Anti: đọc hồ sơ + task mới trên main sau pull; code đúng phạm vi, tests, cập nhật PROJECT_STATE/CHANGELOG/ADR/báo cáo, commit/push rồi dừng chờ review.
8. Nếu tài liệu sống quá dài: giữ hồ sơ này ngắn, chuyển lịch sử chi tiết sang review/ADR; không xóa bằng chứng cũ.

## 7. Task hiện hành được phép triển khai

Task đầy đủ đã giao: `crypto-paper-agent/docs/planning/ANTIGRAVITY_STAGE_04_TASK.md`. Được phép Giai đoạn 4; các gợi ý dưới đây chỉ là tóm tắt, task đầy đủ là tiêu chí thi công/nghiệm thu:
- Đọc spec Paper Execution Engine trước khi chốt thiết kế; dự kiến `paper_broker.py`, `order_models.py`.
- Lập rõ model lệnh/vị thế, cash/equity/margin, thời điểm signal/admission/fill, thứ tự xử lý OHLCV và SL/TP cùng nến, phí/funding/slippage, trạng thái từ chối và đóng lệnh.
- Risk gate kiểm tra ngay trước mở lệnh bằng snapshot tài khoản thực tế và đồng hồ dùng chung; chống bypass/double reduction.
- Tiêu chí tích hợp phải có no-lookahead, bookkeeping đối soát vốn, margin release, lock/recovery và dữ liệu lỗi.
- Không mở rộng sang chiến lược Giai đoạn 5 hoặc live trading khi chưa được phép.

## 8. Câu mở cuộc trò chuyện mới cho người dùng

“Tôi tiếp tục dự án Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING. Hãy đọc PLANNER_HANDOVER.md ở gốc repo, PROJECT_STATE.md và review mới nhất trên GitHub rồi làm planner tiếp; kiểm tra trạng thái hiện tại, không dựa vào trí nhớ chat cũ.”

Nếu không còn kết nối GitHub, người dùng có thể gửi bản hồ sơ và PROJECT_STATE hiện tại. Không cần gửi lại toàn bộ lịch sử chat.
