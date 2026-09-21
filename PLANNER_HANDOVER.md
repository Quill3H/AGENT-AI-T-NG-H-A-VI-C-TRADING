# PLANNER_HANDOVER — Hồ sơ tiếp nối cho GPT Reviewer và Codex Implementation Engineer

## Current G0 checkpoint — 2026-09-22

**PENDING INDEPENDENT REVIEW — NO SELF-ACCEPTANCE.** PM coordinates separate Tester and Independent Reviewer tasks; the former reviewer task is now PM and does not issue the independent verdict.

- Branch `codex/g0-market-validation`; code A `2c9a4d0985fc9eafd29386482793425c26d47835`; docs B is its documentation/evidence-only child supplied by full SHA in final handoff.
- Exact-source funding at settlement is mandatory in broker and basket. Reused08→16 raises `FUNDING_SOURCE_EVENT_MISMATCH` before mutation. Public preparation and fetcher share readiness rules.
- Primary count/win/expectancy/SQN use completed position lifecycles; raw realization slices remain auditable. Incomplete lifecycles are excluded from primary metrics while their realized cash remains in ledger totals. Direct Position/full/partial-final/force/breaker close paths have regressions.
- Plan/resource checkpoint was delivered to PM before implementation: `crypto-paper-agent/docs/superpowers/plans/2026-09-22-market-validation.md`. No market download/network experiment at G0/G1. Historical/current/holdout G2–G4 remain planned, not verified.
- Exact commands/results/runtime/raw synthetic hashes: `crypto-paper-agent/docs/reviews/G0_SETTLEMENT_LIFECYCLE_HANDOFF.md` and its evidence directory. Author execution does not substitute for QA/reviewer reruns. Old public/PPO numbers below are historical and have not been revalidated by G0.
- Exact-A author results:382 offline passed,2 skipped,5 network deselected; historical probes26/11/3 passed; LONG/SHORT replay each1 completed position/3 raw slices with reconciliation. Further scope waits for product contract and G0/G1 acceptance; public realtime data means paper simulation only.
- Main stays `e970337d504563e5987a4db6b5c06c635bf7244b`; preserve `.serena/` and unrelated user files. No main merge or force push.

## Previous Stage 6–11 repair checkpoint — 2026-09-21 (historical)

**IMPLEMENTED AND AUTHOR_TESTED — PENDING INDEPENDENT REVIEW.** No acceptance is claimed.

- Active branch: `codex/stage-06-to-11-completion`; final code/test/script A: `23f94376215a7fca69c8a7606e34139bc21d090c`.
- Baseline: `2236e839529cbcfb31cfd399107617f0b541e907`; main preserved at `e970337d504563e5987a4db6b5c06c635bf7244b`.
- User has authorized continuous implementation through Stage 11 including actual PPO, isolated dependencies and branch push. Earlier stop-before-7 and optional-RL task instructions are **SUPERSEDED**. No main merge, force-push, live/testnet, credentials, money or paid resources.
- Stage6: parsed calendar semantic snapshot, portable config/report identity and exact byte checksums. Stage7: causal LONG/SHORT Breakout E2E. Stage8: funded atomic basket + existing risk/breaker + cash ledger. Stage9: real 5m/1m FVG limits and 40/30/30 partial/BE/trailing exits. Stage10: executable four-account OOS workflow. Stage11: actual Gymnasium/SB3 PPO train/evaluate/save/load through PaperBroker.
- Final A gates: offline **356 passed, 2 skipped, 5 deselected**; network **5 passed, 358 deselected**; Review05 **26**, Review06 **11**, Review07 **3** passed; clean detached A offline **356 passed, 2 skipped, 5 deselected**. Two existing skips require optional pandas-ta.
- Four external-CWD custom-config synthetic CLI runs have actual fills and closed realizations. Public three-day dataset, four-strategy OOS, real PPO256/save-load/holdout and evaluate-only CLI all ran. Artifact audit checked JSON/SQLite/hash/CSV/PNG consistency and found no absolute machine paths in report artifacts.
- Public directional OOS:0 trades; funding1 basket/-25.18825656 USDT. PPO holdout:-477.11246108 USDT. Short sample proves engineering paths, not economic quality. All performance is **AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED**. Full historical window/2021–2023 replay is **PARTIAL / NOT_VERIFIED**.
- SMC report rows are realization slices, not independent full-position samples. Funding uses sampled spot/perp quotes, not hidden intrabar paths. Four comparison accounts have independent capital. No shared portfolio or profitable learned policy is claimed.
- Documentation commit B is the documentation-only child of A. Obtain its actual full SHA from the final branch handoff; do not confuse B with the code commit tested above.

Current evidence: [repair report](crypto-paper-agent/docs/reviews/STAGE_06_11_REPAIR_REPORT.md), [requirement matrix](crypto-paper-agent/docs/planning/STAGE_06_11_REPAIR_MATRIX.md), ADR0010–0012. Đọc các tài liệu này trước phần lịch sử bên dưới.


> Đọc file này đầu mỗi phiên mới, rồi đối chiếu GitHub hiện tại. File này thay cho việc phụ thuộc trí nhớ hội thoại; không bảo đảm AI tự nhớ hoặc tự theo dõi GitHub.
> Chỉ cập nhật thông tin đã xác minh hoặc đánh dấu rõ “tác giả báo cáo”, “chưa kiểm tra”, “chờ người dùng”.

## 1. Dự án và cách phối hợp

- Repo: `Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING`; branch triển khai hiện tại ở checkpoint đầu file, không phải main.
- Gốc chương trình trong repo: `crypto-paper-agent/`.
- Mục tiêu: crypto paper trading agent; làm tuần tự từng giai đoạn, risk-first, chống lookahead.
- Người dùng là người quyết định cuối cùng. Codex là Implementation Engineer chính từ 2026-09-21; GPT Planner/Reviewer ở phiên độc lập thực hiện review và nghiệm thu. Antigravity không còn là implementer đang hoạt động; attribution của các commit lịch sử được giữ nguyên.
- GitHub là nơi bàn giao. GPT có thể tạo/cập nhật tài liệu review và task theo workflow đã thống nhất; không tự thay code triển khai trong một yêu cầu chỉ review.
- Người dùng quyết định nghiệm thu và cho phép chuyển giai đoạn. GPT không coi câu “Anti làm xong” là quyền tự bắt đầu giai đoạn tiếp.
- Không có kênh điều khiển trực tiếp Antigravity được thiết lập; GitHub không tự cập nhật nếu Anti chưa commit/push. Chỉ kiểm tra khi có phiên làm việc/yêu cầu; không hứa giám sát nền.

## 2. Lịch sử các checkpoint trước repair pass (không phải kết quả trên A hiện tại)

- **Giai đoạn 0–2:** PROJECT_STATE ghi đã được Claude duyệt trước khi GPT tiếp quản; không tuyên bố GPT đã review lại toàn bộ.
- **Giai đoạn 3:** Anti sửa qua ba vòng. Code cuối đã kiểm tra: `44014393a2ed6dba7188096a6d1de600daa972d0`.
- **GPT Review 04:** đạt kiểm tra kỹ thuật G1–G3 và hồi quy offline đã thực thi; khuyến nghị nghiệm thu, người dùng đã yêu cầu tiếp tục Giai đoạn 4. Chi tiết: `crypto-paper-agent/docs/reviews/GPT_STAGE_03_REVIEW_04.md`.
- **Phê duyệt người dùng:** sau kết luận Review 04, người dùng đã yêu cầu tạo prompt để tiếp tục giai đoạn tiếp theo. Giai đoạn 3 được chấp thuận theo phạm vi Review 04; cho phép Antigravity triển khai riêng Giai đoạn 4 theo task dưới đây.
- **Giai đoạn 4 — Paper Execution Engine:** bản đầu được review tại `e4cb87b975d3404fbe73b31281d1d9697522cce0` (Review 05: E1–E8, probes 24 failed/2 passed). Anti sửa tại `60f693016160f6c44bd7e9ff3569540324708bfc`; 26/26 probes Review 05 đã pass trong môi trường reviewer.
- **GPT Review 06:** chưa đạt nghiệm thu tại commit `60f6930` (10 failed/1 passed probes Review 06; H1–H6).
- **GPT Review 07:** chưa đạt nghiệm thu tại commit `b0af6b199973f17a7bd1b9690a450f015403ef68` (probes Review 07: 3 failed/0 passed; phát hiện J1–J3).
- **GPT Review 08:** chưa đạt nghiệm thu tại commit `e92d48476c38c3196bfffe89120c9c8bfbc55baf` do phát hiện lỗi kiến trúc **K1 — Production code nhận diện và né probe test** (sử dụng `inspect.currentframe()` và `_is_legacy_probe_caller` để nới lỏng funding provenance cho probe cũ).
- **Sửa đổi hoàn tất theo Review 08 (Chuẩn bị nghiệm thu Review 09):** Anti đã khắc phục triệt để K1:
  - Xóa bỏ 100% `import inspect`, `_is_legacy_probe_caller()` và mọi logic nhận diện test/caller/stack trong `src/execution/paper_broker.py`.
  - Hợp đồng Funding Provenance & Readiness tại settlement (00, 08, 16 UTC) là fail-closed vô điều kiện: `funding_readiness` bắt buộc là boolean `True`, timestamp nguồn hợp lệ không future/stale, `funding_rate` hữu hạn (`0.0` được phép). Không cho phép bất kỳ cờ cấu hình nào (như `strict_provenance`) nới lỏng.
  - Bổ sung metadata hợp lệ vào helper `candle()` của test cũ Review 05 & Review 06, giữ nguyên 100% tất cả các assertions.
  - Bổ sung 3 regression tests K1 kiểm tra AST (chặn inspect/caller frame inspection) và kiểm tra tính bất biến trước tên caller stack.
  - 40/40 probes Review 05–07 pass (26/26 R05, 11/11 R06, 3/3 R07).
  - 16/16 tests trong `tests/test_stage_04_review_07_coverage.py` pass.
  - 237/237 unit tests offline pass (5 deselected network tests).
  - Script mô phỏng Phần A và Phần B đạt đối soát 100%.
  - Báo cáo sửa đổi chi tiết tại `crypto-paper-agent/BÁO CÁO TÓM TẮT/GIAI ĐOẠN 4/BAO_CAO_SUA_DOI_THEO_GPT_REVIEW_08.md`.
- **Giai đoạn 5 — Trend Following & Backtest Engine:** tài liệu lịch sử ghi ĐÃ ĐƯỢC NGHIỆM THU CHÍNH THỨC theo GPT Review 10 tại Code-under-test commit `060f8a8d72e0eb2acbb6bd327ae67fbcb0805aac` và Documentation commit `dc0ab9bec51ec34351e9f21ec8ef31970ff8392e`. Người dùng đã cho phép chuyển sang Giai đoạn 6.
- **Giai đoạn 6 — Trade Logger & Performance Report:**
  - Bản đầu tại commit code `1d486f76da1430e1c02fa1ac24be177262d53c67` và docs `8e7a3cd735e5a55f78ba05a7e4dc5d67f1af3c77` bị GPT Review 11 phát hiện các điểm nghẽn (schema Section 4.6, composite keys, full idempotency, hermetic CWD paths, benchmark reconciliation).
  - Tác giả (Antigravity) đã hoàn thiện khắc phục triệt để toàn bộ 9 yêu cầu của GPT Review 11 tại Code Commit A: `0b63f2702024993575735157528d4738be181e75`:
    1. `trades.json` chuẩn xác 100% nguyên văn Master Spec Section 4.6 (17 key gốc, 4 key null unmeasured trong `market_context`, 7 key trong `outcome`, `rule_compliance: true`, RFC 8259).
    2. SQLite composite keys `(run_id, order_id)`, `(run_id, trade_id)`, `(run_id, event_id)`, `(run_id, timestamp)`, lưu `rejection_reasons_json`, lan truyền metadata từ OrderRequest, ánh xạ trực tiếp AccountSnapshot.
    3. Idempotency toàn diện qua SHA-256 canonical payload hash; fail-closed khi xung đột.
    4. Xử lý trong suốt nested production config qua `parse_config_metadata`.
    5. Run ID tất định (loại bỏ wall-clock), phân giải đường dẫn tương đối hermetic từ `PROJECT_ROOT`, bảo toàn đường dẫn tuyệt đối.
    6. Bổ sung trọn vẹn provenance, candle counts, candle gaps, đối soát kế toán, và fail-closed type validation (chặn `bool`, `NaN`, `Inf`).
    7. Phân tách rành mạch chỉ số Circuit Breaker khỏi từ chối do thiếu ký quỹ riêng lẻ.
    8. Đối soát Benchmark Chuẩn Tắc 3 năm BTCUSDT: 22 orders, 16 trades, fees -162.82 USDT, funding -225.89 USDT, net PnL +2,100.96 USDT (+21.01%), Max Drawdown -16.15%. Chính thức bác bỏ và tuyên bố vô hiệu số liệu dự thảo không đồng bộ (48 orders, 24 trades, fees 82.49, funding -22.56).
    9. Bộ test mở rộng lên 29 tests cho Stage 6; toàn bộ 309/309 tests trong repo đều PASS 100%.
- **Quyền lịch sử — SUPERSEDED bởi nhiệm vụ Stage6–11:** Giai đoạn 6 ĐANG CHỜ GPT REVIEW TIẾP THEO NGHIỆM THU. **TUYỆT ĐỐI KHÔNG BẮT ĐẦU GIAI ĐOẠN 7** hoặc bất kỳ giai đoạn nào tiếp theo cho đến khi có xác nhận nghiệm thu chính thức từ người dùng và GPT Reviewer.
- **GPT Review 12 repair pass theo nhiệm vụ người dùng phê duyệt ngày 2026-09-21:**
  - Baseline: `e970337d504563e5987a4db6b5c06c635bf7244b`; Documentation Commit B hiện tại: `b04613a338c9678108f6349ad669bd1d9881abcb`.
  - Branch triển khai: `codex/stage-06-review-12-fixes`; Code-under-test Commit A2: `99d4b4063c798cf3a89d610e4bd64a19f3395659`.
  - Canonical config identity hiện chuẩn hóa machine-specific absolute cache roots; cùng config logic ở nhiều cache root có cùng `config_hash`/run ID, còn `fees.taker_pct` khác sẽ đổi cả hai. Reproduction metadata dùng config repo-relative hoặc `<CONFIG_PATH>`.
  - CLI benchmark annotation dùng metric thực tế và xử lý zero-trade; summary Markdown hiển thị loss rate, average realized RRR và Circuit Breaker lock count riêng với hai loại rejection.
  - Xác minh trên A2: offline `276 passed, 2 skipped, 5 deselected`; historical probes `40 passed`; network `5 passed, 278 deselected`; focused integration/report regressions `13 passed`.
  - CLI smoke từ CWD ngoài project và custom-cache tests tạo/đọc đủ 6 artifacts, kiểm tra JSON/SQLite/CSV/PNG, config hash xuyên root, phí taker và không chứa absolute machine path. Dataset smoke chỉ có `0 trades`; đây là kiểm tra pipeline/artifact, không phải benchmark hiệu năng.
  - Benchmark 2021–2023 không được chạy lại vì checkout không có dataset/cache chuẩn tắc: `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`.
  - Trạng thái: **DỪNG CHỜ GPT REVIEW GIAI ĐOẠN 6; không bắt đầu Giai đoạn 7.**

## 3. Tài liệu nguồn cần đọc

Các đường dẫn dưới đây tính từ gốc repository:

1. `crypto-paper-agent/PROJECT_STATE.md`: quyết định, checklist, giới hạn đã ghi nhận.
2. `Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md`: đặc tả; đọc phần tương ứng giai đoạn đang làm.
3. `crypto-paper-agent/docs/decisions/`: ADR 0001–0007 và các phụ lục đã chốt.
4. `crypto-paper-agent/docs/reviews/GPT_STAGE_04_REVIEW_09.md`: file review độc lập mới nhất thực sự có trong repository. Review 10/11 được tài liệu sống thuật lại nhưng file nguồn không có trong cây Git hiện tại; phải coi là `NOT_VERIFIED` nếu cần nội dung nguyên văn.
   Nhiệm vụ Stage 6 có thẩm quyền được người dùng cung cấp trực tiếp ngày 2026-09-21; đã hoàn thành tại Commit A nêu trên.
5. `crypto-paper-agent/CHANGELOG.md` và code/tests tại commit thực tế.
6. `crypto-paper-agent/BÁO CÁO TÓM TẮT/GIAI ĐOẠN 3/`: báo cáo triển khai của Anti.
7. `Initial idea/AGENT_SPEC.docx`: ý tưởng ban đầu; không ghi đè quyết định mới bằng ý tưởng cũ.

Khi mâu thuẫn: yêu cầu hiện tại được người dùng xác nhận và quyết định/ADR mới có ưu tiên hơn mặc định cũ trong spec. Code/test là bằng chứng hành vi thực tế, không tự chứng minh hành vi đó đúng yêu cầu. Báo cáo tác giả không thay thế review độc lập. Nếu thiếu nguồn hoặc quyền đọc repo, nêu rõ và xin nguồn/quyền; không phỏng đoán.

## 4. Quy tắc đã chốt phải giữ

- Paper-only; không triển khai đặt lệnh tiền thật/testnet, không cần API key giao dịch ở phạm vi hiện tại.
- News filter mặc định disabled. Nếu bật thì lịch thiếu/hỏng phải chặn; lịch rỗng đúng schema được phép theo chính sách đã công bố.
- Phục hồi risk sau **3 lệnh thắng liên tiếp** (`after_3_wins`), không quay về mặc định cũ phục hồi sau 1 thắng.
- Mốc dữ liệu backtest đã chọn: `2021-01-01` → `2026-09-01`; không tự đổi.
- RL thuộc Giai đoạn 11 và đã được người dùng yêu cầu triển khai; nhãn optional cũ đã được thay thế cho nhiệm vụ hiện tại.
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
| `e4cb87b975d3404fbe73b31281d1d9697522cce0` | Review 05 | Chưa đạt: E1–E8, probes 24 failed/2 passed; cần sửa Giai đoạn 4, không sang 5 |
| `60f693016160f6c44bd7e9ff3569540324708bfc` | Review 06 | Chưa đạt: 26/26 probes cũ pass nhưng probes mới 10 failed/1 passed; còn H1–H6, không sang 5 |
| `b0af6b199973f17a7bd1b9690a450f015403ef68` | Review 07 | Chưa đạt: 3 probes Review 07 failed; còn J1–J3 (funding provenance fail-closed, transactional solver settlement, finalize force_close KeyError). Anti đã sửa |
| `e92d48476c38c3196bfffe89120c9c8bfbc55baf` | Review 08 | Chưa đạt: phát hiện K1 (test-aware inspection qua `inspect`/`_is_legacy_probe_caller`). Anti đã khắc phục triệt để và vô điều kiện cho Review 09 |
| `b16fa1e0b7f064f764cea12fc97ae5c0677a40d2` | Review 09 | **Đạt — nghiệm thu Giai đoạn 4**; cho phép phát hành task riêng Giai đoạn 5 |
| `060f8a8d72e0eb2acbb6bd327ae67fbcb0805aac` | Review 10 | **Đạt — nghiệm thu Giai đoạn 5**; cho phép bắt đầu triển khai Giai đoạn 6 |
| `1d486f76da1430e1c02fa1ac24be177262d53c67` | Review 11 | Chưa đạt: 9 điểm nghẽn (schema Mục 4.6, composite keys, full idempotency, CWD paths, benchmark reconciliation). Anti sửa tại Commit A: `0b63f2702024993575735157528d4738be181e75` |
| `99d4b4063c798cf3a89d610e4bd64a19f3395659` | GPT Review 12 | ĐÃ KHẮC PHỤC — ĐANG CHỜ GPT REVIEW 12 LẦN TIẾP THEO; test bắt buộc và regression đã chạy, chưa nghiệm thu |

Review 02/03/04/05/06/07/09 có file trong `crypto-paper-agent/docs/reviews/`; walkthrough 08 có file riêng. Không tìm thấy file Review 10/11 trong cây Git hiện tại. ADR 0006/0007/0008/0009 ghi quyết định risk, execution, strategy và reporting qua các vòng.

## 6. Quy trình bắt đầu mỗi phiên GPT

1. Đọc hồ sơ này và PROJECT_STATE trên GitHub, không chỉ bản chat cũ.
2. Xác định SHA main hiện tại và commit cần review. Phân biệt commit code với commit tài liệu của reviewer.
3. Đọc latest review, ADR và phần spec liên quan; nếu mới hơn hồ sơ thì cập nhật trạng thái từ nguồn xác minh.
4. Chỉ review khi được yêu cầu review; chỉ giao triển khai khi người dùng cho phép. Không push thay đổi code trong vai trò reviewer.
5. Khi kiểm thử, báo riêng pass/skip/deselected/network chưa chạy, môi trường và SHA; không sao chép số tác giả thành kết quả của mình.
6. Sau mỗi mốc quan trọng, cập nhật file này với latest review, blocker, quyền cho phép hiện tại và next action; lưu task triển khai riêng có tiêu chí nghiệm thu.
7. Handoff cho Codex Implementation Engineer: đọc hồ sơ + task được người dùng phê duyệt; code đúng phạm vi, tests, cập nhật PROJECT_STATE/CHANGELOG/báo cáo, commit/push branch riêng rồi dừng chờ review.
8. Nếu tài liệu sống quá dài: giữ hồ sơ này ngắn, chuyển lịch sử chi tiết sang review/ADR; không xóa bằng chứng cũ.

## 7. (HISTORICAL — quyền dừng cũ đã được thay thế) Task hiện hành được phép triển khai

Nhiệm vụ sửa GPT Review 12 do người dùng phê duyệt ngày 2026-09-21 đã hoàn tất tại Code-under-test Commit A2 `99d4b4063c798cf3a89d610e4bd64a19f3395659`.

Task hiện hành: **ĐÃ KHẮC PHỤC — ĐANG CHỜ GPT REVIEW 12 LẦN TIẾP THEO**. Không merge vào `main` và không bắt đầu Giai đoạn 7 nếu chưa có xác nhận mới của người dùng.

## 8. Câu mở cuộc trò chuyện mới cho người dùng

“Tôi tiếp tục dự án Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING. Hãy đọc PLANNER_HANDOVER.md ở gốc repo, PROJECT_STATE.md và review mới nhất trên GitHub rồi làm planner tiếp; kiểm tra trạng thái hiện tại, không dựa vào trí nhớ chat cũ.”

Nếu không còn kết nối GitHub, người dùng có thể gửi bản hồ sơ và PROJECT_STATE hiện tại. Không cần gửi lại toàn bộ lịch sử chat.

## Historical implementation handoff before repair (2026-09-21)

**SUPERSEDED:** phần dưới ghi trạng thái trước findings, không mô tả implementation hiện tại. Xem checkpoint đầu file và báo cáo repair.

Working branch: `codex/stage-06-to-11-completion`.

Implemented modules are paper/research only. Stage 7 and Stage 9 are wired into the existing 4h signal/15m execution runner. Stage 8 is a standalone explicit-leg simulator with fail-closed input validation. Stage 10 provides split/comparison helpers. Stage 11 provides a risk-aware environment and explicitly refuses to claim PPO completion when dependencies are absent.

Evidence: source files under `crypto-paper-agent/src/strategies`, `src/features`, `src/research`; configs under `config/strategies`; focused tests under `tests`. Test execution used pytest after installing missing local dependencies; full suite remains NOT_VERIFIED.
