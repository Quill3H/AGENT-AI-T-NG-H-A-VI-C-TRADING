# Windows Paper Replay — S0 Repair Evidence

Date: 2026-10-01. Reviewer: implementation author, **AUTHOR_SELF_REVIEWED**.
This is a bounded engineering checkpoint, not independent acceptance, economic
validation, continuous-operation evidence or completion of the replay product.

Code-under-test commit: `d021857731752f8d8fe34d6bde032358f5d946d7`
Documentation commit: see Git history and final handoff.
Branch: `codex/windows-paper-replay`.
Approved spec: `docs/superpowers/specs/2026-10-01-windows-paper-replay-design.md`.
Scoped plan: `docs/superpowers/plans/2026-10-01-paper-input-ownership-repair.md`.

## Baseline and repository safety

After fetch, source/origin `codex/web-chart-timeframes-and-signals` remained
`1876b134684be6e925d954c4bd3635b61d33fcdc`; development base/origin remained
`d1cd95a726e12245ede22326e05b09990975ccd6`. Local/origin main remained
`fe1c1330d913e78239db575ff8433cf069fe1b01`. Design-only parent was
`b6229fbec5d003a15992be1a9977a8f29a99cb08`.
Existing INDEX modifications and untracked prior assessment/probe/workflow files
were preserved and excluded from these commits. No extra checkout, branch merge,
main update, force-push, history rewrite, owner account start or task installation.

## Confirmed repairs and adversarial findings

| Finding | Severity | Repair and execution evidence |
| --- | --- | --- |
| Backtest requires volume but validates only OHLC | High | Validate real/non-bool finite volume >=0 before feature preparation; NaN/Inf/negative/bool/numpy-bool/text regression on both 4h/15m; broker balances, orders, exposure, snapshots and clock unchanged |
| Cache metadata claims complete from endpoints despite middle gaps | High | Shared exact cadence predicate for metadata/load; 1 and 50 missing bars rejected for OHLCV/OI/funding; duplicate/off-grid/missing boundary/out-of-order/NaT rejected |
| Cache-load miss after metadata hit crashes via len(None), including OI/funding | High | Fetch from actual load outcome, no check/use split; real Parquet and merge exercised for all three types; incomplete fetched OHLCV cannot reach strategy consumption |
| Different HTTP ports admit writers to the same account | High | Lifetime nonblocking OS lock, resolved aliases; server claims before auto-resume; direct session claims before start/resume; retired session cannot checkpoint or reopen through callbacks/poll |
| Start during teardown allocates a new account | High, self-review | Red test returned HTTP200 and created account during delayed shutdown; closing gate plus serialized lifecycle now returns503 and leaves no financial account marker |
| Historical probes point to docs/config after relocation | Medium | Only ROOT corrected to repository/crypto-paper-agent; 26/11/3 financial assertions unchanged |
| Legacy resume test actually builds resumable v2 | Medium | Test now explicitly removes machine and sets v1, asserts RECOVERY_REQUIRED with no broker |

The marker `.paper-owner.lock` is operational, zero-length, and is not deleted
on release. Windows locks a byte beyond EOF; POSIX uses flock. OS process death
releases ownership. Unknown files other than the explicitly reserved marker and
existing logs policy remain evidence and block a fresh account. Read-only
inspection can view history but cannot promote it while another writer owns it.
Shutdown joins the market worker before releasing the account; timeout retains
ownership and fails closed. The OS lock is not a protection against a human
deleting all financial evidence or noncooperating programs rewriting files.

Additional issues caught during testing were corrected, not hidden: the first
cache fixture used pandas-invalid `15m` instead of `15min`; metadata-only frames
were treated as empty because they have zero value columns; old Windows file-list
assertions omitted the new operational marker. No financial assertion was weakened.

## Executed commands

All commands run from `crypto-paper-agent` on Windows with the existing
`.venv-paper\Scripts\python.exe` (Python3.12.14), pytest9.1.1. No install required.
Counts below distinguish red development runs and final gates. Logs are available
in this conversation; no invented timing or pass evidence.

| Command arguments after interpreter | Result | Seconds |
| --- | --- | --- |
| `-m pytest -p no:cacheprovider tests/test_backtest_engine.py tests/test_cache_integrity.py -q -k 'volume or cache or fetched_ohlcv'` | Red:31failed,4passed,15deselected; 2 failures were fixture frequency and were corrected before cache implementation | 13.36 |
| `-m pytest -p no:cacheprovider tests/test_cache_integrity.py -q --tb=line` | Corrected red:17failed,2passed | 2.53 |
| `-m pytest -p no:cacheprovider tests/test_cache_integrity.py -q` | Green:19passed | 7.46 |
| `-m pytest -p no:cacheprovider tests/test_backtest_engine.py tests/test_cache_integrity.py tests/test_breakout_retest.py tests/test_data_layer.py tests/test_public_data_pipeline.py tests/test_stage_06_integration.py -q -m 'not network'` | Intermediate:84passed,11failed,5deselected; metadata empty-frame bug fixed | 52.95 |
| `-m pytest -p no:cacheprovider tests/test_cache_integrity.py -q -k complete_cache_named --tb=short` | Metadata regression:3failed,16deselected before fix | 2.13 |
| `-m pytest -p no:cacheprovider tests/test_paper_account_lock.py -q --tb=short` | Red:8failed,2passed | 6.79 |
| `-m pytest -p no:cacheprovider tests/test_paper_account_lock.py tests/test_local_paper_server.py tests/test_paper_resume.py -q --tb=short` | Intermediate:15passed,10failed; Windows locked-file read and old simultaneous-owner fixtures corrected | 9.47 |
| `-m pytest -p no:cacheprovider tests/test_paper_account_lock.py tests/test_local_paper_server.py tests/test_paper_resume.py tests/test_paper_recovery_review.py tests/test_paper_safe_integration.py tests/test_local_paper_session.py tests/test_paper_api_examples.py -q --tb=short` | Intermediate:75passed,5failed (attempting to read locked operational marker, corrected to compare financial evidence) | 18.51 |
| `-m pytest -p no:cacheprovider tests/test_paper_account_lock.py tests/test_paper_recovery_review.py -q` | Green:41passed before teardown test addition | 7.91 |
| `-m pytest -p no:cacheprovider tests/test_paper_account_lock.py -q -k late_transport --tb=short` | Callback red:1failed,10deselected | 1.70 |
| `-m pytest -p no:cacheprovider tests/test_paper_account_lock.py -q -k late_transport --tb=short` | Poll red:1failed,10deselected after extending regression | 2.03 |
| `-m pytest -p no:cacheprovider tests/test_paper_account_lock.py -q -k teardown --tb=short` | Red:1failed,11deselected; HTTP200 instead of503 | 3.31 |
| `-m pytest -p no:cacheprovider tests/test_paper_account_lock.py tests/test_local_paper_server.py tests/test_paper_windows_lifecycle.py -q` | Final focused:23passed | 12.44 |
| `-m pytest -p no:cacheprovider tests/test_paper_windows_lifecycle.py -q` | Windows entrypoint/launcher:2passed | 5.62 |
| `-m pytest -p no:cacheprovider -q -m 'not network'` | Initial full:554passed,1failed,2skipped,5deselected,2warnings (marker expectation) | 169.49 |
| `-m pytest -p no:cacheprovider -q -m 'not network'` | Precommit full:556passed,2skipped,5deselected,2warnings | 140.40 |
| `-m pytest -p no:cacheprovider -q -m 'not network'` | On code commit:556passed,2skipped,5deselected,2warnings | 136.51 |
| `-m pytest -p no:cacheprovider ../docs/history/reviews/test_stage_04_review_05.py ../docs/history/reviews/test_stage_04_review_06.py ../docs/history/reviews/test_stage_04_review_07.py -q --tb=line` | Relocated-path red:40failed | 1.29 |
| `-m pytest -p no:cacheprovider ../docs/history/reviews/test_stage_04_review_05.py -q` | Precommit:26passed | 1.54 |
| `-m pytest -p no:cacheprovider ../docs/history/reviews/test_stage_04_review_06.py -q` | Precommit:11passed | 1.30 |
| `-m pytest -p no:cacheprovider ../docs/history/reviews/test_stage_04_review_07.py -q` | Precommit:3passed | 1.17 |
| `-m pytest -p no:cacheprovider ../docs/history/reviews/test_stage_04_review_05.py -q` | On code commit:26passed | 1.49 |
| `-m pytest -p no:cacheprovider ../docs/history/reviews/test_stage_04_review_06.py -q` | On code commit:11passed | 1.25 |
| `-m pytest -p no:cacheprovider ../docs/history/reviews/test_stage_04_review_07.py -q` | On code commit:3passed | 1.13 |

Postcommit full offline suite passed on the pinned code commit above. No
production or executable test file differs from that commit at documentation handoff.
The two offline skips are optional pandas-ta comparisons, not risk/funding
tests. Five network tests were deselected. Two pre-existing Gymnasium checker
warnings concern ignored warn argument and alternate rendering without env spec.

Full suite also exercises external-CWD CLI/report artifact tests. It does not
constitute a fresh isolated clean-checkout test. Focused ownership tests exercise
real Windows sockets, processes, killing an owner, path/case aliases, idempotent
shutdown, late callbacks and actual HTTP/API refusal. Controlled sources are
synthetic, not live market evidence. Trading protections are not disabled.

## Open requirements / debt

- S1 fixed simulated funding and versioned recipe identity: NOT_IMPLEMENTED in
  this checkpoint. Current public funding still uses its strict provenance gate.
- S2 compact SQLite, exact legacy migration and power-loss tests: NOT_IMPLEMENTED.
- S3 complete paginated outage replay and stable recursive seeds: NOT_IMPLEMENTED.
  Existing gap behavior remains fail-closed/read-only with exposure; no full replay claim.
- S4 <5000 failure / >=15000 milestone, research/promotion and exactly-once new
  allocation: NOT_IMPLEMENTED. No restart capital reset introduced.
- S5 new pause/resume/stop/service intent semantics and paginated UI contract:
  NOT_IMPLEMENTED. Existing APIv2/start/terminal-stop is preserved.
- Medium: Parquet writes are still direct, duplicate source revisions overwrite,
  and repeated cache acquisition/whole JSONL checkpoint costs remain; these are
  separate storage/input versioning work. No claim of atomic Parquet or full
  provenance repair. Account lock assumes cooperating application writers.
- Real public WebSocket, network gates, UI browser/build, scheduled task install,
  logon/reboot, sleep/power-loss behavior, long soak and independent review:
  NOT_VERIFIED this turn. No BLOCKED label without an actual failed attempt.
- No UI design/code edited; no keys, live/testnet orders, wallet, investment
  recommendation, profitability claim, deployment or paid resources.

Next authorized work is S1 then S2/S3/S4/S5, each with a concrete scoped plan and
regression evidence. The owner already approved the overall design; no additional
design approval is inferred to be needed to continue these named slices.
