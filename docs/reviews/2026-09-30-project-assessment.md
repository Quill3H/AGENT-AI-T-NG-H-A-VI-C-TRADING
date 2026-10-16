# Đánh giá toàn dự án — 2026-09-30

## A. Kết luận điều hành

**AUTHOR_SELF_REVIEWED; chưa phải nghiệm thu độc lập.** Dự án có implementation và test chạy thật cho data/features/risk/broker, bốn rulebook nghiên cứu, reporting, walk-forward, Gymnasium/PPO và web local. Không cần viết lại engine hoặc tối ưu tham số để tạo giao dịch. Ưu tiên tiếp theo là tính toàn vẹn đầu vào, ownership journal, hợp đồng availability funding realtime và bộ kiểm định bị lệch đường dẫn.

**Chưa đủ bằng chứng để gọi toàn dự án engineering complete hoặc Windows paper bot vận hành liên tục.** Full suite hiện hành pass nhưng probe lịch sử nguyên trạng fail; audit bổ sung tái hiện các khoảng trống chưa được test suite bắt. Historical/OOS/economic validation không được suy ra từ test xanh, UI chạy hay PPO smoke.

Phạm vi: đánh giá toàn bộ nhóm chức năng ở mức kiến trúc, spec/ADR, gate và tests; đọc trực tiếp các convergence point rủi ro cao. Đây không phải audit từng dòng mọi file, penetration test hoặc chứng nhận không còn lỗi. Lượt này không sửa production, test hiện hành, UI, chiến lược, risk config; không cài task Windows, không khởi động tài khoản của chủ dự án, không tải market data, không commit/push/merge.

## B. Checkpoint và thẩm quyền

Đã chạy Git fetch origin --prune thành công. Working tree sạch trước audit.

| Mốc | Full SHA xác minh hiện tại |
| --- | --- |
| Checkout và origin/codex/web-chart-timeframes-and-signals | `1876b134684be6e925d954c4bd3635b61d33fcdc` |
| Nhánh nền local/origin codex/local-paper-futures-app | `d1cd95a726e12245ede22326e05b09990975ccd6` |
| Mốc tích hợp cũ origin/codex/paper-futures-integration | `2118e2cae327b005b314fc801db1a9fcafcc6149` |
| main local/origin | `fe1c1330d913e78239db575ff8433cf069fe1b01` |

Checkout hơn nhánh nền một commit (chart/timeframe/API/tests), khớp origin của chính nó: ahead/behind 0/0. Không tự đổi về nhánh nền hoặc main để viết báo cáo. File báo cáo/workflow mới là thay đổi local chưa commit, không phải tài liệu đã có ở SHA code trên.

Nguồn hiện hành: AGENTS.md; PROJECT_STATE; INDEX; SYSTEM_ARCHITECTURE; master spec; charter; ADR 0001–0012 (các hợp đồng liên quan); LOCAL_PAPER_WEB; API/schema/recovery v2; cây kiến trúc; handover. Báo cáo lịch sử chỉ dùng truy vết claim. Áp dụng hướng dẫn hiện hành không merge main; addendum main-2026-09-23 trong charter/routing/handover không phải quyền merge trong lượt này. Accepted ADR ghi đè phần spec cũ tại điểm cụ thể; ADR 0008 và 0009–0012 còn nhãn pending khác nhau, không tự nâng thành accepted.

Runtime kiểm chứng: Windows 10 build 19045, Python 3.12.14 trong `.venv-paper`; pandas 3.0.6, numpy 2.5.3, pytest 9.1.1, Gymnasium 1.3.0, SB3 2.9.0, torch 2.14.0, websocket-client 1.9.2, jsonschema 4.26.0; Node v24.21.0, npm 11.19.0. Không có pandas-ta; dùng fallback pure pandas.

## C. Kiến trúc và mức độ hiện thực

| Nhóm | Code/đầu ra thực tế | Bằng chứng lượt này và giới hạn |
| --- | --- | --- |
| Market Data | fetcher, Vision downloader, Parquet cache; merge backward OI/funding có provenance | Test offline data/public pipeline pass. Tái hiện cache seam F-02. Network/source thật không chạy lại. |
| Features | indicators/CVD/OI/SMC; swing confirmation và future perturbation | Test offline causal pass; hai test so sánh pandas-ta skip. Dữ liệu taker/OI không được tự tạo khi thiếu. |
| Risk | sizing, invariant_checks, liquidation solver, CircuitBreakerState | Test stop/leverage/margin/news/clock/streak/funding pass; after_3_wins theo ADR 0002. Không đổi policy. |
| Simulation | PaperBroker request queue → next-open sizing/invariants → fill; process_batch dùng shadow state atomic | Source `paper_broker.py:343`, `:811`, `:866`, `:883`; accounting, LONG/SHORT và multi-symbol tests pass. Không có bằng chứng exchange-executable fill. |
| Stage 6 Reporting | Broker ledger → metrics; generator gọi logger lưu SQLite, xuất JSON/CSV/PNG/MD | Source `engine.py:271`, `generator.py:282`, `lifecycles.py`; logger/artifact/idempotency/config/external-CWD tests pass. Metrics không cần đọc ngược SQLite để đúng ADR 0009. |
| Stage 7 Breakout | delayed breakout/retest, LONG/SHORT qua broker | Focused cases nằm trong full offline; quickstart tạo fills/realizations thật từ fixture. Không chứng minh public alpha. |
| Stage 8 Funding basket | spot long/perp short riêng, synchronized input, risk gate và atomic basket ledger | Hand oracle/fail-closed tests pass. Không phải shared portfolio hay scanner đang chạy arbitrage. |
| Stage 9 SMC | 5m/1m, FVG limit, OB confluence, partial 40/30/30 | Test partial, causal LONG/SHORT và whole-position metrics pass; queue/intrabar fidelity vẫn là mô hình OHLCV. |
| Stage 10 Research | fold train/validation/test; tài khoản độc lập/reset; force-close và manifests | comparison/workflow tests pass. Không được gọi tổng PnL thí nghiệm là shared-capital portfolio. Canonical dài hạn chưa chạy lại. |
| Stage 11 PPO | Gym env, train-only scaler, broker actions, CPU PPO/save/load/evaluate | Test train/save/load 128 timesteps; quickstart offline ít nhất 256 và save/load equal. Reward trừ realized/cost/DD/violation theo ADR 0010; không suy diễn hội tụ/sinh lời. |
| Realtime paper | BTC/ETH/SOL; chỉ Trend Following 4h/15m; shared paper account 10.000 USDT; public WS + REST confirmation | stream/API/recovery fixture tests pass. F-03/F-04 cản vận hành bền vững. Nến forming chỉ display; broker xử lý cả bar sau close, không phải khớp sàn tức thời. |
| Web | React/Vite, coin/timeframe 1m/15m/4h, local API, browser stream display-only | 28 Vitest pass, build đạt. Không browser-verify lại trong lượt này; static evidence/replay là artifact viewer, không online learning. |
| Windows | loopback server, exclusive port, optional logon Scheduled Task/retry/logs | Hai subprocess/launcher tests thật chạy trên Windows trong full suite. Không tương đương reboot/logon/sleep/power loss hoặc 24/7 soak. |

Luồng order chuẩn: Strategy/RL → OrderRequest → PENDING → giá open nến hợp lệ kế tiếp/slippage → sizing/liquidation → invariants/news/breaker/margin → fee/Position. Funding adapter có gate hai chân riêng. Exit/protective stop do broker quản lý, không yêu cầu sizing entry lần nữa. Reporting chỉ chạy sau mô phỏng; nghiên cứu không tự promote model vào scanner.

## D. Findings xác nhận và ưu tiên

### F-01 — High: validator OHLCV bỏ qua miền giá trị volume

`crypto-paper-agent/src/backtest/engine.py:127` yêu cầu cột volume nhưng `:133` chỉ kiểm tra số học OHLC. Probe `validate_dataset` chấp nhận volume NaN, Inf, -1 và True. Breakout/CVD/feature processing dùng volume; gate dữ liệu không được coi đây là input hợp lệ. Lỗi code input validation, không phải lỗi chiến lược. Chưa chứng minh một trade giả cụ thể từ mỗi input lỗi; đã chứng minh gate chấp nhận input không hợp lệ.

Hướng sửa đề xuất: volume numeric finite, không bool, >=0; negative-path tests trước constructor/feature mutation. Zero-volume không tự cấm nếu spec cho phép. Không lấp NaN bằng số giả.

### F-02 — High: hai định nghĩa cache complete không thống nhất, fetch_all crash

`cache_manager.py:174` chỉ xét min/max; `_is_cache_sufficient` (`:258`) đếm coverage 99%. Cache 200 slot còn 150 row, giữ nguyên hai đầu: `has_complete_cache=True`, `load_from_cache=None`. `fetcher.py:723` gọi len(None) trước fallback; probe trực tiếp `fetch_all` báo **TypeError: object of type 'NoneType' has no len()**. Hai seam OI/funding có pattern tương tự `:741/:757` (chưa probe riêng hai nhánh).

Hướng sửa đề xuất: một hợp đồng cache readiness; caller xử lý miss/None trước len và có fallback bounded đúng network policy. Không biến missing candles thành coverage pass. `save_to_cache` hiện ghi trực tiếp Parquet, chưa atomic và ghi đè revision theo keep-last; đây là debt bổ sung về crash/revision provenance, chưa fault-inject.

### F-03 — High: khóa cổng không đảm bảo một writer trên journal

`local_server.py:44/:190` khóa socket, không khóa thư mục account. `durable_journal.py:82` có exclusive init/checksum/temp-file detection nhưng không giữ OS lock ownership suốt đời process. Probe tạo hai server cổng khác nhau cùng journal thành công, cả hai IDLE; **không thử concurrent write và không tuyên bố đã làm hỏng journal**. Checksum/temp-file có thể phát hiện xung đột nhưng không thay thế single-writer guarantee; default 8765 tránh một lớp lỗi, custom port vẫn mở.

Hướng sửa đề xuất: OS-backed lifetime journal ownership, acquire trước inspect/restore/start, từ chối second writer kể cả khác cổng, release khi shutdown/process chết. Lock không được tạo file khiến inspector tự coi là tài khoản legacy mới. Test cần hai process thật, death/restart và symlink/case/path alias nếu được hỗ trợ.

### F-04 — High operational blocker: closed-bar receipt không thể thỏa funding availability hiện tại

`live_session.py:365/:376` dùng thời gian receipt hiện tại rồi từ chối khi receipt > settlement open. `poll:462` gọi helper khi bar settlement đã đóng. Với **cùng source event exact 08:00 và rate hữu hạn**, probe receipt 08:00 được nhận; receipt 08:15 bị từ chối: `exact funding event observed after settlement 2026-09-27T08:00:00+00:00`. Không phải chỉ lỗi delay 1–6 ms; mô hình closed-bar processing tự tạo delay cả bar. Phân biệt source event identity với observation availability.

Kết luận: giữ fail-closed là đúng; nhưng đường realtime có exposure qua settlement có thể quarantine dù public event đúng nguồn. **Không đề xuất backdate receipt, reuse rate hoặc bỏ readiness.** Cần owner/ADR chốt event-time/receipt-time/deferred settlement hoặc công bố phạm vi observer-only tại điểm không đáp ứng. Sau đó mới có regression E2E tương ứng. Lượt này không chạy market settlement thật.

### F-05 — Medium; chặn historical gate: review probes hỏng sau di chuyển tài liệu

`docs/history/reviews/test_stage_04_review_05.py:9`, Review06 `:9`, Review07 `:12` dùng `parents[2]` nay trỏ về docs, tìm `docs/config/default_config.yaml`. Chạy nguyên trạng: Review05 **26 failed**, Review06 **11 failed**, Review07 **3 failed**, tổng 40 fail trước logic broker. Đây là lỗi test harness/path migration, không được báo là 40 financial failures.

Diagnostic riêng chỉ thay ROOT module trong RAM thành CWD crypto-paper-agent: **40 passed**; không sửa assertion, funding metadata hay broker. Diagnostic không thay thế pass nguyên trạng và không phải nghiệm thu độc lập. Hướng sửa đề xuất: ROOT repository đúng + crypto-paper-agent, giữ assertions và chạy lại ba tập riêng. Không sửa production để nhận diện caller/test.

### F-06 — Medium: tài liệu sống và bản đồ hiện hành còn claim/đường dẫn lỗi thời

Charter/routing/handover vẫn gọi main là integration branch và dùng đường dẫn trước migration. Cây kiến trúc đóng băng ở fe1c133 và chỉ mô tả static preview, thiếu realtime journal/recovery/API/Windows. PROJECT_STATE vừa nói đã nghiệm thu kỹ thuật một số nhóm vừa nói independent acceptance pending; ADR 0008 vẫn pending. README badge 507 khác kết quả hiện tại 510; README hướng setup Python 3.11/3.12 khác badge 3.12+ và danh sách requirements. API docs nằm dưới crypto-paper-agent/docs trong khi docs/README ở đó nói mọi docs đã chuyển.

Không tự xóa lịch sử hoặc phê duyệt gate: thêm superseded/source dates, một đường dẫn hiện hành, link immutable code/test evidence, trạng thái capability/run/evidence tách biệt. Handover cần checkpoint mới trước mọi thay đổi triển khai.

### F-07 — Medium: test legacy resume đặt tên không đúng hành vi kiểm chứng

`tests/test_paper_resume.py::test_legacy_view_cannot_be_promoted_to_running_broker` không chuyển marker thành v1/loại machine; nó khôi phục v2 và assert WAITING_CONNECTION. Test này không chứng minh legacy không promote. Có negative legacy/orphan cases ở tập recovery khác; không kết luận mọi recovery test là vacuous. Cần fixture v1 hợp lệ nhưng thiếu machine, assert RECOVERY_REQUIRED, admission false và byte evidence không đổi.

### Debt Low / giới hạn thiết kế

- `web-preview/src/lib/paperEngine.js` còn random prices/funding/PnL giả, nhưng rg và import graph main→App hiện không dùng module này. **Không kết luận UI hiện tạo số giả.** Quarantine/xóa dead helper sau xác minh import để tránh tái nối nhầm; evidence.js/replay cũng không thuộc App hiện hành.
- UI STRATEGY_METADATA ghi SMC 15m và breakout 15m/1m khác rulebook/ADR đang dùng. Đây là label research dormant, không phải scanner chạy chiến lược đó.
- `_rebaseline_after_gap` và `reconcile_resume` khóa exposure gap là hành vi an toàn, không cần bypass để resume. Recovery với open/pending qua gap dài vẫn chưa hoàn thành về tính liên tục. `POST /api/stop` terminal, khác pause/resume; phải chốt product semantics trước khi đổi broker.finalize.
- Journal append hash toàn file, full state/checkpoint/history lặp lại có nguy cơ tăng chi phí lưu trữ và latency theo thời gian. Chưa benchmark growth; retention/compaction phải giữ auditability, không tự xóa evidence.
- Không có file .github workflow được track ở SHA này; QA automation còn dựa lệnh thủ công. Chưa clean-install/rebuild dependency trên máy trắng trong lượt này.

Không có Critical mới được xác nhận trong phạm vi audit; điều đó không chứng minh không còn Critical. Findings trên chưa sửa production vì nhiệm vụ hiện tại là workflow và đánh giá.

## E. Invariants và khoảng trống nghiệm thu

| Invariant | Quan sát | Trạng thái |
| --- | --- | --- |
| No-lookahead/UTC/closed-bar/next-open | Test future perturbation, CVD confirmation, SMC/engine chronology pass | Author tests VERIFIED; source availability thực tế còn gate |
| Stop/max leverage 5x/risk/margin/news/breaker | Gate ở broker trước fee/Position; mô phỏng clock, after_3_wins | Author tests VERIFIED; không nới risk |
| Fee/slippage/collateral/funding/PnL | Accounting oracle/partial/basket/multi-symbol tests pass | Author tests VERIFIED; realtime funding F-04 OPEN |
| Idempotency/không reset tài khoản | Journal detects torn/missing/conflict; typed v2 recovery và same-ID fixtures | Author tests VERIFIED; writer ownership F-03 OPEN |
| Input integrity/cache | Volume và sparse-cache probes tái hiện lỗi | OPEN F-01/F-02 |
| Historical probe pack | Files không tìm được config sau migration | FAIL harness F-05; official gate chưa pass |
| Tái lập artifact/external CWD/PPO save-load | test_quickstart chạy process riêng, chặn network, kiểm hash/path leaks; artifacts LONG/SHORT có fills | Author tests VERIFIED, không phải fresh clone/independent rerun |
| Public prospective/scored history/24-7 | Không mở public feed/scored dataset/Windows logon trong lượt này | NOT_VERIFIED, không gọi BLOCKED khi chưa thử |

## F. Lệnh và kết quả thực thi

Từ repo root: Git rev-parse/branch/remote/status; `git fetch origin --prune`; log, show-ref, diff/stat, ahead/behind; rg source/docs/imports; runtime version checks. Các lệnh đọc file đoán đường dẫn không tồn tại đã được kiểm lại bằng rg; không dùng nội dung đoán làm chứng cứ.

Từ crypto-paper-agent:

```powershell
.\.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider -q -m "not network"
.\.venv-paper\Scripts\python.exe -m pytest -p no:cacheprovider ..\docs\history\reviews\test_stage_04_review_05.py ..\docs\history\reviews\test_stage_04_review_06.py ..\docs\history\reviews\test_stage_04_review_07.py -q
```

| Run | Passed | Failed | Skipped | Deselected | Thời gian / exit |
| --- | ---: | ---: | ---: | ---: | --- |
| Full offline trên HEAD 1876b134 | 510 | 0 | 2 | 5 | 194.70 s; exit 0 |
| Historical pack nguyên trạng | 0 | 40 | 0 | 0 | 9.24 s; exit 1 |
| Diagnostic ROOT-only trong RAM (không đổi file) | 40 | 0 | 0 | 0 | 3.28 s; exit 0; không phải official gate |
| Vitest npm test (web-preview) | 28 | 0 | 0 | 0 | 47.32 s; 2 files; exit 0 |
| npm run build (web-preview) | — | — | — | — | Vite 2.38 s; exit 0; 423.11 kB JS / 14.75 kB CSS |

Hai skip là comparisons cần pandas-ta; không skip Windows tests. Hai Gym warnings: warn parameter ignored và không có spec để check alternate render modes. RL test đã dùng thư viện thật; không lấy smoke loss/profit làm nghiệm thu.

Probe offline tái lập được, từ repo root:

```powershell
.\crypto-paper-agent\.venv-paper\Scripts\python.exe docs/reviews/2026-09-30-project-audit-probes.py
```

Script xuất JSON quan sát F-01/F-02/F-03/F-04 trên storage/listener tạm; **exit 0 chỉ có nghĩa diagnostic chạy xong, không phải các invariant pass**. Probe thêm fetch_all sparse cache thực thi bằng Python stdin, gặp len(None) như F-02; script lưu chỉ kiểm cache seam để không vô tình fetch network khi một lần sửa tương lai thay hành vi.

Diagnostic historical ROOT-only đã chạy bằng Python stdin như sau:

```python
from pathlib import Path
import pytest
class AuditRootOnly:
    def pytest_collection_modifyitems(self, items):
        for item in items:
            if item.module.__name__.startswith('test_stage_04_review_'):
                item.module.ROOT = Path.cwd()
raise SystemExit(pytest.main([
    '-p', 'no:cacheprovider', '-q', '--tb=short',
    '../docs/history/reviews/test_stage_04_review_05.py',
    '../docs/history/reviews/test_stage_04_review_06.py',
    '../docs/history/reviews/test_stage_04_review_07.py',
], plugins=[AuditRootOnly()]))
```

## G. Những gì chưa kiểm chứng

Không chạy network tests (một test kéo 60 ngày OI), public WS/REST market session, canonical 2021-01-01→2026-09-01, native TradingView, browser manual/automation, fresh dependency install/clean clone, Scheduled Task install/logon/reboot/sleep/power-loss, concurrent journal write race hoặc 24/7 soak. Các claim dữ liệu/benchmark lịch sử giữ AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED. Không báo mất mạng là BLOCKED khi chưa thử mạng trong lượt này.

Không có API key/private key/testnet/live order/wallet; không thay power setting; không deploy/chi tiền. Test Windows dùng process/listener tạm, không user account. Build thay dist ignored; Windows launcher test có thể append startup diagnostic vào log ignored. Không đưa các runtime file này vào Git.

## H. Quyết định cần owner, không chặn việc độc lập

1. Chốt semantics source event time/receipt availability/funding settlement cho realtime bằng ADR; không nới fail-closed để chạy được.
2. Chốt stop terminal hay cần một API pause/resume riêng; nếu giữ terminal phải hiển thị rõ tài khoản không tự restart.
3. Chốt cách đối soát exposure gap/legacy: migration có bằng chứng riêng, không reset vốn. Có thể làm input/cache/ownership/harness trước khi quyết định này xong.
4. Chốt frozen candidate và protocol trước scored OOS/paper, không curve-fit hay online update trong scored run.

## I. Workflow và bàn giao

Workflow chi tiết, phụ thuộc/đầu ra/tiêu chí kiểm chứng và regression đề xuất ở [kế hoạch](../superpowers/plans/2026-09-30-project-workflow.md). Thứ tự: sửa harness/docs và input/cache → single writer → funding availability decision/implementation → Windows lifecycle → frozen engineering validation → data coverage/scored research → prospective paper → independent review/owner acceptance.

Skill đã dùng: using-superpowers, crypto-bot-engineering, writing-plans, verification-before-completion; thêm systematic-debugging khi probe failure xuất hiện. Chúng dẫn tới source-first audit, isolated probes và tách pass test khỏi acceptance. Không dispatch sub-agent. Không sửa các High trong lượt đánh giá; cần nhiệm vụ triển khai tiếp theo trên code SHA mới. main được giữ nguyên.
