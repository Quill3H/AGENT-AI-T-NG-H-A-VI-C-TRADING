# PROJECT_STATE — Trạng thái Hiện tại của Dự án

> **Tài liệu trạng thái sống (Living Project State)**  
> Cập nhật lần cuối: 2026-10-17 (UTC+7)
> Quy tắc: Tài liệu này **chỉ mô tả trạng thái hiện tại**. Toàn bộ nhật ký kiểm định, walkthrough và lịch sử phát triển chi tiết được lưu trữ tại [docs/history/](history/) và [docs/handover/](handover/).

---

## 1. Tóm tắt Trạng thái Hiện tại (Current Snapshot)

### Windows paper replay S1-S5 - implementation candidate

**AUTHOR_SELF_REVIEWED; GitHub checkpoint 2026-10-17.** Fresh verification,
code-under-test SHA, publication scope and remaining work are recorded in the
[current handoff](handover/2026-10-17-github-checkpoint.md). This is not
independent acceptance, economic validation or demonstrated 24/7 operation.
Repaired code A: `d9670f41408c7abfe7bb682453e4edb7f198d3fb`.
Fresh Windows Python 3.12.14 offline result: **715 passed, 2 skipped
(pandas-ta comparison unavailable), 5 deselected**. Web: **30 passed** using
one threads worker after the default worker-start timeout; Vite build passed.
The owner approved the [Windows replay design](superpowers/specs/2026-10-01-windows-paper-replay-design.md)
and expressly authorized a **new separate account with 10,000 imaginary USDT**,
not continuation/reset of legacy capital. Scoped authority is recorded in
[ADR 0013](adr/0013-windows-paper-replay-and-trials.md).

- Implementation branch: `codex/windows-paper-replay`. Earlier code checkpoint:
  `c89333516f9032155923375a876d0350deb6c267`. Subsequent repairs and their fresh
  test results are pinned in the current handoff. The PR targets
  `codex/local-paper-futures-app`, verified at
  `d1cd95a726e12245ede22326e05b09990975ccd6`. Documentation/publication SHA is
  obtained from Git history and the PR; no self-referential SHA is guessed.
- New account profile: `crypto-paper-agent/data/paper_accounts/windows-paper-v3`.
  Legacy `data/paper_sessions` remains untouched; account startup and optional
  Scheduled Task installation will be reported separately after verification.
- One shared BTC/ETH/SOL account, mandatory stops, <=5x leverage and unchanged
  risk/fee/slippage/liquidation/Circuit Breaker controls. Initial recipe is Trend
  Following, closed 4h signals/next eligible 15m open; chart controls do not
  select the strategy. Breakout & Retest requires eligible causal research
  promotion; SMC/PPO and Funding Arbitrage are not active in this account.
- Fixed **SIMULATED** funding 0.01% at 07/15/23 UTC+7 (00/08/16 UTC) is scoped
  to this experiment; public-source funding in other modes remains fail-closed.
- Exact typed recovery, immutable account identity, checksummed transactional
  inputs/events/commit metadata and complete causal paginated replay are
  implemented candidates. Missing/corrupt/ambiguous evidence still requires
  RECOVERY_REQUIRED, never guessed exposure, erased funding or fresh capital.
- API v3 publishes backend-owned account/price/recovery/risk/trial values,
  stale-current-price nulls, REPLAY provenance, history pages and asynchronous
  controls. Immutable OPERATOR_REQUEST receipts precede the long writer wait;
  OPERATOR_INTENT application is committed with the exact effective timeline.
- Later express owner authorization allowed helper agents for bounded audits
  and documentation. This assistance is AUTHOR_SELF_REVIEWED work, not an
  independent tester/reviewer verdict. Earlier inline-only plans remain
  historical execution records.
- No main merge, force-push, live/testnet, trading credentials or paid resource
  is authorized. Last known main checkpoint is
  `fe1c1330d913e78239db575ff8433cf069fe1b01`; root final handoff rechecks refs.

| Slice | Implementation present | Remaining acceptance evidence |
| --- | --- | --- |
| S1 Funding/identity | Frozen FIXED_SIMULATED model and versioned recipe/formula/config/source identity | Current offline results in handoff; independent identity/funding review pending |
| S2 Storage/recovery | SQLite WAL/FULL, immutable identity, atomic checkpoints/event roots, exact typed broker/risk/exposure restore and limited checked migration | Current recovery/ledger/integrity regressions in handoff; clean-checkout and power-loss verification pending |
| S3 Causal runner | Shared chronological broker runner, retained feature prefix, full gap pagination, synchronization and honest REPLAY/REALTIME labels | Current causal/restart regressions in handoff; public reconnect/long-gap/soak pending |
| S4 Trials/research | <5,000 failure, >=15,000 target/continue, durable allocations, frozen 180/90/90-day study and cost/sample gates | Technical regressions in handoff; independent review/full empirical 360-day study NOT_VERIFIED |
| S5 API/Windows/web | Durable controls, responsive read snapshots, v3 schema/six SYNTHETIC examples, one-writer launch/task tools and existing UI integration | API/schema/Windows test results and 30 web tests/build in handoff; browser/logon/reboot/24x7 NOT_VERIFIED |

Operational entry points: [Windows runbook](operations/LOCAL_PAPER_WEB.md),
[API v3](../crypto-paper-agent/docs/operations/PAPER_REPLAY_API_V3.md),
[schema](../crypto-paper-agent/docs/operations/paper_replay_state_v3.schema.json)
and [synthetic examples](../crypto-paper-agent/docs/operations/paper_replay_api_examples_v3.json).
The checkpoint includes repairs/regressions for recovery/ledger, paused setup,
request-time controls, research-control races and commit integrity. The current
handoff separates automated verification from unperformed operational gates.

### Historical S0 checkpoint - 2026-10-01

Chủ dự án đã duyệt [thiết kế Windows replay và strategy trials](superpowers/specs/2026-10-01-windows-paper-replay-design.md)
ngày 2026-10-01, gồm funding **mô phỏng** cố định 0.01% tại 07/15/23 UTC+7
(00/08/16 UTC), replay toàn bộ nhân quả và không reset vốn khi restart.
At this historical S0 checkpoint, these were approved changes, not yet the
complete implementation described in the current candidate section above.

- Nhánh triển khai riêng: `codex/windows-paper-replay`; nguồn code
  `1876b134684be6e925d954c4bd3635b61d33fcdc`.
- Code-under-test S0: `d021857731752f8d8fe34d6bde032358f5d946d7`.
- Trên chính commit này: offline **556 passed, 2 skipped, 5 deselected** trong
  136.51 giây; historical probes Review05/06/07: **26/11/3 passed**.
- S0 sửa volume không hợp lệ, completeness/cache miss, quyền ghi tài khoản
  độc lập cổng HTTP và race Start/shutdown; historical probes được sửa đường dẫn
  sau di chuyển, không đổi assertion tài chính.
- Đây là **AUTHOR_SELF_REVIEWED**, chưa nghiệm thu độc lập. Chi tiết lệnh/kết quả
  và phạm vi còn mở ở [báo cáo S0](reviews/2026-10-01-paper-s0-repair.md).
- **Historical S0: S1-S5 were not yet implemented:** fixed funding/versioned recipe, SQLite compact/migration,
  full outage replay, trial/research promotion và controls/Windows/API mới.
  Không chạy tài khoản của chủ dự án hoặc tự cài Scheduled Task trong lượt này.
- `main`/`origin/main` vẫn ở `fe1c1330d913e78239db575ff8433cf069fe1b01`.
  Không merge, force-push, rebase hay squash.

The older subsystem/test snapshots below are preserved for context; they are
not final verification of the repaired Windows v3 candidate. That candidate
can resume only a provable exact state, otherwise RECOVERY_REQUIRED remains.

| Thông số | Trạng thái Hiện tại |
| :--- | :--- |
| **Giai đoạn dự án** | Stage 06–11 nghiên cứu/backtest; Local Paper Web đang kiểm định tích hợp |
| **Nhánh nền phát triển** | `codex/local-paper-futures-app` (PR #4 đã merge tại `9fd81e7`); `main` (`fe1c133`) chưa cập nhật theo nhánh này |
| **Trạng thái bản sửa** | PR #4 đã hợp nhất vào nhánh nền; tiếp tục kiểm định Windows và nguồn dữ liệu trước khi nghiệm thu vận hành |
| **Chế độ giao dịch** | **PAPER TRADING ONLY** (mô phỏng, không API key, không nạp/rút, không ví tiền) |
| **Nguồn dữ liệu thị trường** | Backend dùng public Binance USD-M Futures `/market` WebSocket và xác minh nến đóng qua REST; trình duyệt hiển thị stream riêng. Không có endpoint đặt lệnh sàn. |
| **Historical baseline test snapshot** | Python offline: **510 passed, 2 skipped, 5 deselected** (Windows .venv-paper); nhóm paper: **76+ passed**; web: **28 passed**, Vite build đạt (dist: 423 kB JS, 14.7 kB CSS). Not final repaired-v3 results. |

---

## 2. Tình trạng các Phân hệ (Subsystem Status)

### 2.1 Các phân hệ đã hoàn thành & đã nghiệm thu kỹ thuật (Completed Subsystems)
- [x] **Data Layer (Giai đoạn 1):** Kéo OHLCV, Open Interest, Funding Rate từ Binance public API; lưu trữ cache Parquet; Vision downloader cho dữ liệu lịch sử >28 ngày (ADR 0001, ADR 0004).
- [x] **Feature Engine (Giai đoạn 2):** Tính toán EMA, RSI, MACD, ATR, CVD phân kỳ nhân quả (ADR 0003), OI Delta có fallback (ADR 0005) và cấu trúc thị trường SMC.
- [x] **Risk Manager (Giai đoạn 3):** Tính kích thước lệnh theo % rủi ro cố định, Circuit Breaker 24h/streak (ADR 0002), đệm thanh lý an toàn (ADR 0006).
- [x] **Paper Execution Engine (Giai đoạn 4):** Động cơ khớp lệnh Isolated Margin 5 pha, hạch toán kế toán oracle, thanh toán funding 8h chính xác (ADR 0007).
- [x] **Trend Following Strategy (Giai đoạn 5):** Chiến lược xu hướng đa khung (tín hiệu 4h, khớp 15m) kèm stoploss dời theo swing causal (ADR 0008).

### 2.2 Các phân hệ đang hoạt động (Active & Candidate Subsystems)
- [x] **Trade Logger & Metrics Report (Giai đoạn 6):** Lưu sự kiện vào SQLite (`trades.sqlite`), xuất báo cáo đa định dạng (JSON, CSV, PNG) (ADR 0009).
- [x] **Breakout & Retest Strategy (Giai đoạn 7):** Chiến lược phá vỡ cản kèm kiểm định lại, hỗ trợ cả 2 chiều LONG và SHORT (ADR 0010).
- [x] **Funding Arbitrage Strategy (Giai đoạn 8):** Rổ kinh doanh chênh lệch funding Spot/Perpetual nguyên tử (ADR 0011).
- [x] **SMC Liquidity Sweep (Giai đoạn 9):** Quét thanh khoản, lệnh limit tại FVG, chốt lời đa tầng 40/30/30 (ADR 0012).
- [x] **Multi-Strategy Walk-Forward Engine (Giai đoạn 10):** So sánh đa chiến lược với tài khoản vốn phân lập cho từng fold.
- [x] **Reinforcement Learning Environment (Giai đoạn 11):** Môi trường Gymnasium + Stable-Baselines3 PPO hoàn chỉnh.
- [x] **Web Chart Timeframes & Coin Switcher (hoàn thiện):** Hỗ trợ chuyển đổi khung `1m`, `15m`, `4h` qua các button tương tác chuẩn trợ năng; tải lịch sử nến `/api/chart` theo cặp/khung; stream WebSocket công khai tương ứng; hủy và loại bỏ nến cũ ngay khi chuyển; loại bỏ response bất đồng bộ đến trễ (out-of-order drop); không tự chế nến giả khi mất mạng; giải thích rõ đổi khung biểu đồ không làm thay đổi luật vào lệnh Trend Following (4h/15m).
- [ ] **Local Paper Web v3 candidate:** Public closed-bar validation and full causal
  replay feed the same broker; SQLite/identity preserve exact state. The UI
  renders API v3 account/trial/funding/operation/provenance rather than inventing
  accounting. Candidate implementation is present; final frozen verification,
  actual task/logon/reboot and sustained public operation remain separate gates.
  Unknown evidence stays RECOVERY_REQUIRED; wide UI requires mobile scrolling.

---

## 3. Tài liệu Quy chuẩn Điều phối Dự án (Canonical Governance)

| Vai trò | Tài liệu Source of Truth |
| :--- | :--- |
| **Sổ tay AI Agent** | [AGENTS.md](../AGENTS.md) |
| **Đặc tả Kỹ thuật gốc** | [docs/specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md](specs/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md) |
| **Kiến trúc Hệ thống** | [docs/architecture/SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md) |
| **Quy chuẩn Quyết định** | [docs/adr/](adr/) (ADR 0001-0012 and scoped Windows experiment ADR 0013) |
| **Điều lệ Sản phẩm & Gates** | [docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md](planning/PRODUCT_CHARTER_AND_GATE_SPEC.md) |
| **Bản đồ Tài liệu tổng hợp** | [docs/INDEX.md](INDEX.md) |

---

## 4. Vấn đề Tồn đọng & Nợ Kỹ thuật (Known Blockers & Technical Debt)

S0 input/completeness/ownership repairs are preserved. S1-S5 compact storage,
causal replay, fixed funding and trial controls are now implemented candidates,
not pending absence. Automated verification and remaining operational gates are
tracked in the [current handoff](handover/2026-10-17-github-checkpoint.md).
Legacy journals are preserved, not converted to guessed balances. Public-source
funding remains fail-closed outside the explicit fixed-mode experiment.

- Repaired code SHA and current test evidence: see the current handoff.
  Owner-profile startup/task installation are not performed by this GitHub
  publication task; installed/running owner-account status is NOT_VERIFIED.
- Full empirical 360-day candidate research/promotion and canonical full-history
  economic validation: NOT_VERIFIED, not implied by fixture tests.
- Task installation/logon, machine reboot, power-loss durability and 24/7 uptime:
  NOT_VERIFIED unless separately recorded. No power setting was changed.
- Existing wide desktop UI has a mobile horizontal-scrolling limitation; no
  universal mobile usability or accessibility acceptance is claimed.
- C: exhausted space during earlier QA; a later read-only check reported 4.34 GB
  available. QA used process-local TEMP/TMP on G:, no deleted user temp files or
  permanent environment changes. Free space is mutable and must be rechecked.

1. **Millisecond-late Funding Source Timestamps (G2 Diagnostic):**
   - *Bối cảnh:* Một số sự kiện funding của sàn Binance đến trễ từ 1–6 ms so với mốc tròn giờ (00:00, 08:00, 16:00 UTC).
   - *Hành vi hiện tại:* Hệ thống tuân thủ nghiêm ngặt nguyên tắc **fail-closed** theo ADR 0011 (từ chối khớp lệnh nếu dữ liệu nguồn chưa đạt trạng thái sẵn sàng).
   - *Hướng xử lý:* Cần quyết định chính sách từ chủ dự án trước khi nới lỏng hoặc mô hình hóa độ trễ ms.
2. **Cài đặt môi trường độc lập với thư viện C và Windows:**
   - Cài đặt mới từ zero trên một số môi trường Windows có thể gặp lỗi build C extension. Lịch chạy ở Windows, tự khởi động sau đăng nhập và xử lý gián đoạn điện/mạng chưa được xác minh trên máy chủ dự án.
3. **Nghiệm thu Độc lập (Independent Acceptance):**
   - Phân hệ Stage 6–11 và Web Preview đã hoàn thiện code và vượt qua author tests, nhưng vẫn chờ Tester và Independent Reviewer đánh giá chính thức trước khi tuyên bố nghiệm thu kinh tế (economic validation).

---

## 5. Kế hoạch Được phê duyệt Tiếp theo (Next Approved Work)

Current priority: review the published S1-S5 candidate and complete the remaining
clean-checkout, browser, public-data and operational gates listed in the current
handoff. The publication task records progress; it does not start/reset an owner
account, install a task or change power settings. Do not expand PPO or promote
economic claims in this milestone.
The [S0 plan](superpowers/plans/2026-10-01-paper-input-ownership-repair.md) and
S1-S5 plans retain implementation history and current execution addenda.

1. PR #4 đã merge vào `codex/local-paper-futures-app`; xác minh trên Windows với journal cũ/mới, tự khởi động và tái kết nối trước khi nghiệm thu vận hành.
2. Theo dõi dữ liệu public dài hạn và kiểm định độc lập G2–G5; hiệu quả kinh tế chưa được chứng minh.
3. [Dọn nhánh](planning/2026-09-28-branch-consolidation.md) là checkpoint lịch sử; kiểm tra refs hiện hành trước khi hợp nhất/xóa nhánh. Lượt bàn giao này chỉ xuất bản nhánh Windows replay, không merge hoặc xóa nhánh.
4. Không nạp/rút tiền thật hoặc kết nối API key trading.
