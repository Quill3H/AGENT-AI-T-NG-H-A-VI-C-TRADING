# Verification of remaining branches and artifact suites — 2026-10-30

Owner requested verification followed by integration of ready work. Base main:
`d4cc137e819d579e2446d01a0972d3ceb5997f6e`. Paper-only scope is unchanged.
Original sources, artifacts, accounts and branch histories were preserved.

## Integrated selective repair

Commit `0654b277a5e1815ca94068c1793f5e42b061baaf` extracts only the verified
data/CLI fixes from the older high-priority branch. Missing taker volume stays
unknown instead of becoming fabricated 50% volume; CVD remains unknown after an
unobserved delta. OI retains source time and bounded availability. CLI modes that
ignore explicit date ranges now reject them before loading/publishing results.

Exactly three production files and five regression cases changed. Broker, RL,
strategy risk, funding accounting and old results are untouched. This is a selective
commit, not acceptance or merger of the entire older branch.

Five regressions failed before the repair and passed afterward. Author focused
suite: 90 passed, 2 existing pandas-ta skips, 5 network deselected. Separate reviewer
ran the selected core suite: 1014 passed, 3 SQLite path failures, 7 skipped,
5 network deselected; the exact three tests then passed unchanged with shorter
Windows fixture paths. Thus 1017 distinct core tests were independently verified
passing. No P1/P2 remained in this four-file patch. Existing optional RL/native
symlink skips remain explicit; no existing assertion was weakened.

See [independent selective review](evidence/unmerged-2026-10-30/selective-review.md)
and [branch audit](evidence/unmerged-2026-10-30/remaining-branches.md).

## Windows/API branches retained pending integration

- PR #5: 53 focused tests passed; one websocket-dependent test was excluded.
- PR #6: 142 focused backend/Windows tests passed; one launcher check still needs
  websocket-client. Separate JSON-schema checks need jsonschema. Frontend:
  all 30 tests passed and Vite production build passed with the exact lockfile.
- These counts concern each branch's implementation, not a merged-main candidate.
  PR #5 is not an ancestor of PR #6 and the API/recovery contracts differ.
- Running current-main protection regressions against PR #6 produced 30 failures
  and 6 passes: missing kill-switch/gap protections, lost portfolio exposure/capacity
  behavior, and liquidation-bound failures. Keeping only main's broker also does
  not satisfy PR #6's recovery and batch contracts. A deliberate broker/recovery
  integration with passing current regressions is required before either main merge.
- Actual machine reboot, installed Scheduled Task, power loss, live public-stream
  soak and prospective/economic studies were not performed.

Automatic approval review rejected the worker's dependency-install command because
downloads conflicted with its verification restrictions. No installation occurred;
missing-dependency checks remain NOT_VERIFIED rather than counted as code failures
or passes. No bypass, task installation or owner-account initialization occurred.

See [Windows verification](evidence/unmerged-2026-10-30/windows-review.md).

## Other branch decisions and pre-existing defects

The alternate OI branch c0ca8dd predates main's reviewed F5. A fresh probe showed
it changes the effective project loss limit from 1% to 5% and delays a breaker
exit to the next day's time stop. Retained as superseded history; not merged.

The full high-priority branch ffbc14b also remains pending: its old broker loses
current gross-exposure limits and ORB peak tracking. Its original probes still
reproduce main's peer-funding/forced-close/stop-priority and overlapping-candle
defects. The selective data patch does not repair or accept those broker issues.
RL changes were not accepted without their optional dependency/runtime checks.

## Synthesized artifacts: engineering checks versus acceptance

Current source was exported at d4cc137 and all seven prior artifacts were copied
and SHA256-checked in isolation. All original bytes were preserved. Current
SynthesizedStrategy plus the two artifact audit suites: **44 passed**, no exclusions.
Independent acceptance probes: **6 failed, 2 passed**, with assertions retained.

Ledger reconciliation is approximately -1.69e-10 USDT, but the old artifact loses
91.28% of initial equity with 92.60% drawdown. Every one of its 10,892 entry slices
matches known-synthetic cache opens with the stated adverse slippage. The enabled
funding filter accepts missing funding and the runner supplies 0.0001 defaults.
Changing a peer's future close still changes an earlier opening fill. The economic
and risk acceptance assertions permit this losing path; their pass is not acceptance.

Full-year E2E: **20 passed, exit 0, 1534.66 seconds (25m34s)**. It ran the complete
2025-01-01 through 2026-01-01 synthetic engineering fixture, all ten pairs,
PYTEST_FAST_E2E unset and allow_network=False; no exclusions. The initial worker
session was interrupted by usage limits without a result; the root session reran
the unchanged command with a new fixture directory and collected the complete
result. All seven original artifact hashes were rechecked unchanged afterward.
The selective data/CLI changes are outside that execution path, as independently
checked. No real-market provenance, economic validity or project-gate acceptance
is implied by an E2E pass.

See [artifact review](evidence/unmerged-2026-10-30/artifact-review.md) and the saved
XML results in that evidence directory. Totals from overlapping suites are not
added together. Only the independently reviewed data/CLI patch was integrated;
PR #5/#6 and unsafe older broker/OI implementations remain unmerged.
