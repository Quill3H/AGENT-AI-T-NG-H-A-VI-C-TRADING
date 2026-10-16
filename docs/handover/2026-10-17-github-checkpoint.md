# Bàn giao GitHub và tiến trình hiện tại — 2026-10-17

Ngày báo cáo: **2026-10-17, UTC+7**. Phạm vi: đóng gói công việc đang có trong
checkout chính, bổ sung thông tin tiếp nối và xuất bản nhánh/PR để review.
Trạng thái: **AUTHOR_SELF_REVIEWED / INDEPENDENT_REVIEW_PENDING**.
Đây là checkpoint triển khai và kiểm thử tác giả; chưa nghiệm thu vận hành hoặc
hiệu quả kinh tế. Các kết quả cũ không được dùng làm kết quả của mã đã sửa.

## A. Git, phạm vi xuất bản và định danh bằng chứng

| Mục | Giá trị |
| --- | --- |
| Repository | `Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING` |
| Nhánh công việc | `codex/windows-paper-replay` |
| Base PR đã fetch/đối chiếu | `codex/local-paper-futures-app` — `d1cd95a726e12245ede22326e05b09990975ccd6` |
| Checkpoint trước sửa | `c89333516f9032155923375a876d0350deb6c267` |
| Commit code/test đã sửa (A) | `d9670f41408c7abfe7bb682453e4edb7f198d3fb` |
| Commit tài liệu bàn giao ban đầu (B) | `ceb8bcd819b534d63aa60920a632d7d8a18f113c`; commit receipt tiếp theo chỉ bổ sung liên kết/kết quả xuất bản |
| Main quan sát trong lượt này | `fe1c1330d913e78239db575ff8433cf069fe1b01` |
| Pull request | [#6 — Windows causal replay candidate and current handoff](https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/pull/6), OPEN / DRAFT, chưa merge |

Base là tổ tiên của nhánh hiện tại; giữ nguyên lịch sử sáu commit công việc có
sẵn sau base, bổ sung commit sửa code/test, tài liệu và receipt xuất bản. PR #5 đang mở cho
API/chart ở nhánh khác; không sửa/merge PR đó trong lượt này. URL và SHA xuất bản
cuối cùng được đối chiếu với GitHub trong bàn giao cuối của lượt làm việc.

Kiểm thử chạy trên cây source/test đã stage, trước khi tạo A; A đóng băng đúng
nội dung đó. B chỉ bổ sung hồ sơ/tài liệu và script probe audit cũ, không sửa
runtime hoặc test suite. Chưa chạy lại trên một checkout sạch độc lập của A/B.

## B. Công việc đã đưa vào checkpoint

- Giữ toàn bộ phần chart 1m/15m/4h, S0 input/cache/ownership, thiết kế Windows
  replay và triển khai S1-S5 đã có trên nhánh.
- Bổ sung đối soát exposure từ broker request/entry terms/financial ledger;
  typed restore từ chối trường bị constructor tự chuẩn hóa; giữ đầy đủ partial
  targets, chi phí, funding và pending lifecycle khi phục hồi.
- Củng cố SQLite input/event/commit integrity, checkpoint/corruption gates và
  trạng thái dừng legacy; không đoán vị thế hoặc tạo vốn mới khi thiếu bằng chứng.
- Ghi nhận durable OPERATOR_REQUEST trước khi chờ writer; áp dụng intent theo
  effective timeline, kể cả lúc replay, research/promotion hoặc writer đang bận.
- Bổ sung regression cho request-time controls, research-control races,
  scheduled partial restore và commit integrity; sửa đường dẫn launcher tuyệt
  đối và nhận diện process khi quản lý Windows service.
- Xuất bản API v3, ADR 0013, runbook, kiến trúc, charter, audit/probe 2026-09-30,
  workflow và năm kế hoạch S1-S5 còn nằm cục bộ. Audit cũ giữ ngày/phạm vi gốc,
  không được xem là review độc lập cho A.
- Ignore rõ `/crypto-paper-agent/data/paper_accounts/` để lock/account runtime
  không đi vào Git. Không đưa SQLite, account identity, log, môi trường ảo,
  node_modules hoặc dist vào commit.

## C. Tiến trình S1-S5 và điều kiện còn lại

| Slice | Triển khai hiện có | Bằng chứng hiện tại | Công việc còn lại |
| --- | --- | --- | --- |
| S1 Funding/identity | FIXED_SIMULATED, recipe/formula/config/source identity, cô lập public funding | Broker/funding/recipe/formula regressions trong bộ offline mục D | Review độc lập về identity/funding; không suy ra edge kinh tế từ funding cố định |
| S2 Storage/recovery | SQLite WAL/FULL, immutable identity, commit roots, exact broker/risk/exposure/ledger restore | Compact-store, exposure, recovery, commit-integrity và partial-restore regressions | Clean-checkout reproduction, power-loss/filesystem durability; nghiệm thu recovery độc lập |
| S3 Causal runner | Replay gap phân trang đầy đủ, closed-history prefix, shared BTC/ETH/SOL broker, nhãn REALTIME/REPLAY | Causal/recovery/no-lookahead và request-time control regressions | Public-feed reconnect/long-gap/soak trong môi trường vận hành thực |
| S4 Trials/research | <5,000 FAILED; >=15,000 TARGET_REACHED/continue; allocation có ledger/gates; frozen 180/90/90 study | Trials/research/race regressions với dữ liệu tổng hợp | Nghiên cứu đủ 360 ngày, dữ liệu/holdout/cost/sample gates và review kinh tế độc lập |
| S5 API/Windows/web | API v3 bất đồng bộ, responsive snapshots, schema/sáu ví dụ SYNTHETIC, launcher/manager, UI hiển thị backend state | API/schema/server và sáu Windows lifecycle tests trong offline; 30 web tests/build | Browser smoke hiện hành, install/logon/reboot/sleep/network và vận hành kéo dài |

Implementation present không đồng nghĩa gate accepted. Không có tỉ lệ hoàn thành
kinh tế hoặc cam kết uptime được suy ra từ bảng này.

## D. Kiểm thử mới và cách tái lập

Môi trường: Windows, `.venv-paper/Scripts/python.exe`, **Python 3.12.14**,
**pytest 9.1.1**; **Node v24.21.0**, **npm 11.19.0**.

| Kiểm tra | Kết quả trong lượt 2026-10-17 |
| --- | --- |
| Full Python offline, `-m "not network" -ra` | **715 passed, 2 skipped, 5 deselected, 2 warnings**, exit 0; 437.70 giây |
| Frontend mặc định, `npm test` | Không test nào chạy; ba lỗi worker startup timeout, exit 1 |
| Frontend thử lại, một threads worker | **30 passed / 3 files passed**, exit 0 |
| `npm run build` | **PASS**, Vite 8.3.1, 23 modules; JS 426.45 kB/CSS 14.75 kB trước gzip |
| Working-tree `git diff --check`, staged diff check | **PASS** |
| Tích lũy toàn PR, `git diff --check base..HEAD` | Hai cảnh báo blank line at EOF: `tests/test_local_paper_server.py:159` và `web-preview/src/App.test.jsx:1154` (đường dẫn dưới crypto-paper-agent); chưa sửa trong checkpoint |
| Liên kết file tương đối trong tài liệu đang xuất bản | **138 links checked**, không thiếu target |
| Rà credential patterns trên candidate files | Không khớp private-key/token/API-secret literal patterns đã kiểm tra; không phải chứng nhận security audit |
| API JSON schema + ví dụ backend tổng hợp | Thuộc test `test_paper_replay_contract.py` trong full offline |

Hai skip nằm ở `tests/test_indicators.py:75` và `:106`: chưa cài `pandas-ta`
để chạy so sánh chéo. Hai warning thuộc Gymnasium env checker (tham số `warn`
bị bỏ qua và không có spec để thử render modes khác); không có test failure.
Sáu test trong `test_paper_windows_lifecycle.py` đã pass trên Windows, gồm
launcher/process/port/restart với tài khoản tạm, không phải task logon/reboot.

Từ repository root, chạy Python:

```powershell
cd crypto-paper-agent
.\.venv-paper\Scripts\python.exe -m pytest -q -m "not network" -ra
```

Frontend, từ `crypto-paper-agent/web-preview`:

```powershell
npm test -- --maxWorkers=1 --pool=threads
npm run build
```

Lần retry frontend dùng cấu hình worker trên command line; không thay package,
test hoặc dependency để bỏ qua lỗi. Kết quả thành công không xóa bằng chứng lần
chạy mặc định bị timeout. Network tests bị deselect, không được báo là đã pass.
Chưa chạy lại các historical review harness ngoài testpaths, clean checkout,
browser UI hoặc public-stream soak trong lượt xuất bản này.

## E. Hợp đồng API và vận hành bàn giao

[API v3](../../crypto-paper-agent/docs/operations/PAPER_REPLAY_API_V3.md),
[JSON schema](../../crypto-paper-agent/docs/operations/paper_replay_state_v3.schema.json),
[sáu ví dụ SYNTHETIC](../../crypto-paper-agent/docs/operations/paper_replay_api_examples_v3.json)
và [Windows runbook](../operations/LOCAL_PAPER_WEB.md) là tài liệu tiếp nối.

- `GET /api/health`, `/api/state`, `/api/history` và `/api/chart` phục vụ trạng
  thái/history/chart. Chart chỉ hiển thị, không chọn strategy hoặc tạo tín hiệu.
- `POST /api/start|pause|resume|stop` trả 202 bất đồng bộ. Phải theo dõi
  operation, operator_intent, recovery và risk gate; 202 không có nghĩa hoàn tất.
- Pause vẫn giữ bảo vệ/funding; Stop tiến qua STOPPING đến STOPPED khi đủ dữ liệu
  và đối soát. Dừng process/service là hành động khác với StopBot.
- Dữ liệu giá stale là null; replay có provenance riêng. Capital/PnL/order/fill
  là mô phỏng, không phải thực thi trên sàn.
- Mặc định loopback `127.0.0.1:8765`; URL này là cấu hình, không phải bằng chứng
  service tài khoản của chủ dự án đang chạy trong lượt này.

## F. Trạng thái runtime quan sát được và phạm vi bảo toàn

Kiểm tra thư mục mặc định `data/paper_accounts/windows-paper-v3` trong lượt này
chỉ thấy `.paper-owner.lock` rỗng, **không thấy `paper.sqlite3` hoặc
`paper-account.identity.json`**. Không có bằng chứng tài khoản mặc định đã được
khởi tạo; không suy ra trạng thái của profile tùy chỉnh khác.

Tra cứu read-only Scheduled Task tên `CryptoPaperResearchBackend` trả về không
tìm thấy task mang tên đó. Không cài task hoặc khởi chạy tài khoản để hoàn thành
yêu cầu xuất bản GitHub. Test subprocess dùng tài khoản tạm; không đồng nghĩa
tài khoản vận hành của chủ dự án đã sẵn sàng.

Không xóa/chuyển/reset legacy `data/paper_sessions`, không thay Windows power
settings, không xóa cache/temp của người dùng. SQLite/runtime data được giữ ở
máy và bị ignore, không phải bản sao lưu trên GitHub.

## G. Ranh giới bắt buộc và giới hạn chưa xác minh

- PAPER/RESEARCH ONLY; không API key, live/testnet, ví, ký lệnh, nạp/rút hoặc
  paid infrastructure. Không merge main, force-push, rebase hay squash.
- Tài khoản v3 riêng 10,000 USDT ảo theo ADR 0013; public funding ở chế độ khác
  vẫn fail-closed. FIXED_SIMULATED 0.01% tại UTC 00/08/16 không có provenance sàn.
- Trend Following ban đầu: closed 4h signals, next eligible 15m-open fills.
  Mandatory stops, <=5x leverage, sizing và Circuit Breaker giữ nguyên.
- Breakout & Retest chỉ qua research promotion gates; SMC/PPO/Funding Arbitrage
  không được tự kích hoạt trong tài khoản thử nghiệm này.
- **NOT_VERIFIED:** clean checkout độc lập, browser smoke mới, general mobile
  usability, public reconnect/soak, Scheduled Task/logon/reboot/sleep/power loss,
  vận hành 24/7, nghiên cứu empirical 360 ngày và hiệu quả kinh tế.
- Independent Tester/Reviewer verdict và owner gate acceptance vẫn pending.

## H. Công việc tiếp theo và vai trò tiếp nhận

| Ưu tiên | Việc cần làm | Vai trò tiếp nhận | Điều kiện hoàn thành |
| --- | --- | --- | --- |
| P1 | Review diff của A và các commit trước nó so với base; tập trung exposure, ledger, request ordering và promotion | Independent Reviewer | Findings gắn code SHA/path và verdict riêng |
| P1 | Tái lập offline/web/build từ checkout sạch; kiểm tra lý do skip và runner timeout | Tester | Ghi exact SHA/runtime/commands/results; không dùng số liệu checkpoint cũ |
| P1 | Browser desktop/mobile + API pending/busy/stale/recovery flows | Tester/UI reviewer | Bằng chứng trình duyệt và giới hạn usability cụ thể |
| P1 | Chốt profile/identity rồi kiểm tra startup và public feed bằng tài khoản được chủ dự án cho phép | Operator + owner | Không reset vốn; ghi identity, source/replay/funding/risk state và log |
| P2 | Cài/task logon và kiểm tra reboot/sleep/reconnect/soak khi nằm trong scope vận hành được duyệt | Operator | Task/process/account continuity và log theo từng tình huống |
| P2 | Chạy frozen 360-day research với dữ liệu đủ provenance, holdout và cost gates | Research engineer + reviewer | Không reuse holdout hoặc promote khi thiếu dữ liệu/gate |

Chưa chỉ định cá nhân GitHub hoặc gửi yêu cầu review cho người khác. Không có
gate nào được tự động chuyển sang accepted nhờ việc tạo PR.

## I. Checklist bàn giao

- [x] Thu thập branch/base/main refs và phân loại source/test/docs/runtime.
- [x] Đóng gói source, regression, API/runbook/ADR và kế hoạch hiện có.
- [x] Ghi kết quả kiểm thử mới, lần frontend timeout và retry thành công.
- [x] Cập nhật PROJECT_STATE, PLANNER_HANDOVER, INDEX và tiến độ S1-S5.
- [x] Ghi cụ thể blockers, NOT_VERIFIED và vai trò tiếp nhận.
- [ ] Independent technical/economic acceptance và owner operational sign-off.

- [x] Đã push nhánh; local HEAD/origin/remote branch cùng SHA B khi mở PR.
- [x] GitHub xác nhận PR #6 OPEN / DRAFT, base đúng nhánh/SHA nêu ở mục A.

Receipt này được bổ sung sau khi tạo PR; đọc publication HEAD mới nhất từ PR
và Git history. Runtime/test/frontend/config giữ nguyên so với A. Kết quả bàn
giao cuối đối chiếu lại local/remote/PR HEAD sau khi push receipt.
