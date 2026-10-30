# Causal broker, recovery and evidence repair — 2026-10-30

Owner-directed repair on main, base `56382df63f0a58ba249d39b005ad97e90cd30150`.
Engineering integration only; economic acceptance remains rejected/unverified.
The original artifacts, dated handoff, six failed forensic probes and branch
histories remain unchanged. This report corrects their interpretation.

## Original synthesized evidence: correction

The preserved seven artifacts under the local
`output/synthesized-retest-2026-10-29/repo/crypto-paper-agent/reports/synthesized_backtest_1y`
are synthetic evidence. The earlier independent audit matched all 10,892 entry
slice prices against seed-42 synthetic cache opens with 3 bps adverse slippage;
4,816 funding events used the assumed constant 0.0001. The date range does not
make this a verified historical market backtest.

Original results: 6,455 completed lifecycles, 10,892 realization slices,
net -91,280.33 USDT from 100,000, maximum drawdown 92.6019%, profit factor
0.7504, lifecycle win rate 49.20%. A favorable win rate cannot accept that loss.
The configured ADX threshold is 20; exits are 1R/50% and 2R/25%, leverage 2.5.
The old handoff's ADX 25 and 1.5R/60%, 2.5R/25% description is unsupported.

At identical fills, changing taker fees 0.05% to maker fees 0.02% saves
26,950.18 USDT, not more than 35,000. Net would remain about -64,330.16 USDT;
even zero fees leaves about -46,363.37 USDT. This arithmetic is a sensitivity,
not a maker-fill replay or a profitable strategy. See the preceding
[independent verification](UNMERGED_AND_ARTIFACT_VERIFICATION_2026_10_30.md).

Static probes about immutable old artifacts cannot become true through a code
patch. New regressions require the old losing/unproven result to be rejected,
and newly generated evidence to disclose its actual mode and identity.

## Implemented behavior

- Broker batches retain synchronized opening, funding, admission, protective
  and closing phases. Breaker lock state blocks admissions immediately; peer
  flattening waits for the appropriate phase so peer funding, opening marks and
  touched stops are honored. Overlapping direct candles reject before mutation.
  Current notional/capacity, gap, kill-switch and liquidation guards remain.
- Historical mode is the default and fails closed on missing, unproven,
  conflicting or malformed local OHLCV/funding. There is no silent synthetic or
  OHLCV-only network fallback. Cache manifests bind declared source, market,
  symbol, timeframe and SHA; the parser reads the exact verified bytes.
- Synthetic mode is explicit, has a separate seed/window cache namespace and
  declares generated OHLCV and constant funding. The runner uses synchronized
  batches, preserves default risk configuration and replays the exact half-open
  date window. Unknown funding rejects an enabled funding filter.
- Settlement availability has its own event-time check (at most the approved
  one-second timestamp jitter); a rate arriving later within the candle cannot
  fund an earlier opening decision. Candle-close availability is checked
  separately. All replay/report Python sources are hashed; a mid-run source
  change prevents publication. Existing output evidence cannot be overwritten.
- Economic evaluation rejects synthetic/unverified evidence, losses,
  nonpositive expectancy, PF <= 1 and invalid metrics. Positive historical
  metrics without a declared risk contract are NOT_EVALUATED. Explicit contracts
  can yield only ELIGIBLE_FOR_REVIEW, never owner acceptance. JSON, Markdown and
  HTML retain the same mode/provenance/verdict.
- Recovery/API functionality is a selective composition from PR5/PR6 with the
  current broker. Typed durations, static guards, exposure, commit integrity,
  pending actions, exact funding identity and request-time controls are retained.
  Fixed simulated funding is explicit. Automatic replacement promotion fails
  closed even for positive diagnostics or forged client evidence.
- The existing archived-evidence UI remains. An opt-in local PAPER panel uses
  v3 state and closed-only chart/source time, separates provisional prices from
  account valuation, and permits durable stop/pause controls during writer work
  or a public chart outage. See [runtime instructions](../operations/LOCAL_PAPER_RUNTIME.md).

Old branches are not wholesale merged: their obsolete brokers would remove
current protections. Selective integration does not erase their history or
accept unrelated RL work.

## Verification and limitations

Author full offline integration: **1,385 passed, five skipped, five network
deselected in 186.43s**, with the full-year E2E executed separately. The two
forensic artifact suites are included using SHA-verified copies of the originals.
The preceding run had 1,383 passes and two failures: a Windows subprocess timeout
and a CLI fixture placed inside the repository (therefore correctly represented
as a relative config path). Both tests passed unchanged with an external short
fixture path; then the entire offline suite passed using that fixture layout.
Skips: optional RL module, optional PPO quickstart, two pandas-ta comparisons and
Windows symlink creation. They are not passes.

The explicit one-year synthetic E2E finished **19 passed, one skipped in
774.16s**. The skip is the optional legacy report at the default output path;
the preserved originals were audited separately via PAPER_ARTIFACT_DIR. The new
run produced 7,171 completed lifecycles, 350,400 execution bars and 21,900 macro
bars across ten symbols and generated all seven artifacts. It lost
93,232.78 USDT from 100,000, drawdown 93.6748%, PF 0.7171, expectancy -13.0014
USDT, win rate 48.17%. Its explicit verdict is **REJECTED**, with synthetic
provenance and losses disclosed. This is the expected software classification
of an unsuccessful simulation; it is not a repaired profitable strategy or
historical validation. No parameter tuning followed the result.

Independent Tester: **166 passed in 10.49s**, no skips/deselections, in an
isolated filesystem snapshot of 401 source/config/test/schema inputs. SHA256
maps matched both source and snapshot before and after execution. This tested
broker phase, drained collateral, kill switch, ORB, input, economic, recovery,
main compatibility and research regressions without copying market caches.

Independent broker/data/report review found one P1 availability leak, reproduced
it, and verified its repair with **134 passing tests**. Independent recovery/API
review ran **85 passing tests**; the UI P2 findings were repaired, followed by
**13 passing frontend tests** and a successful production build. Initial
findings, incomplete follow-ups and final scoped verdicts remain in the evidence
directory. These counts overlap the author suite and must not be added to it.

Reproduction from the package (the original artifact directory must be available):

```powershell
$env:PYTHONUTF8='1'
$env:PAPER_ARTIFACT_DIR=(Resolve-Path tmp/original-artifact).Path
../.venv/Scripts/python.exe -m pytest tests -m 'not network' --ignore=tests/test_e2e_synthesized_backtest.py -q --tb=short --basetemp ../../tmp/c2 --junitxml=tmp/repair-core-final.xml
# Separate explicit synthetic one-year engineering replay:
Remove-Item Env:PYTEST_FAST_E2E -ErrorAction SilentlyContinue
../.venv/Scripts/python.exe -m pytest tests/test_e2e_synthesized_backtest.py -q --tb=short --basetemp tmp/repair-year --junitxml=tmp/repair-year.xml
```

The seven original binaries are local immutable evidence, not shipped in Git.
The tests' explicit PAPER_ARTIFACT_DIR selects them; their historical sample
counts are not expectations for a newly repaired strategy run. Current E2E
checks count completed lifecycles and cannot substitute realization slices.

Compact commands, logs, XML, independent reviews, Tester input hashes, original
artifact hashes and the new year-run manifest are under
[evidence/repair-2026-10-30](evidence/repair-2026-10-30/).

The owner-requested graph reviewer first rejected 46 filename-only summaries.
The generator now creates factual AST summaries. A regenerated graph passed
all critical checks: 1,486 nodes, 1,884 edges, 13 layers, five tour steps; two
short-summary warnings remain. It is PARTIAL_STATIC (contains/imports only),
not runtime call or financial proof. Generator contracts: five passed, one
Windows symlink skip. Original rejection is preserved.

No market-data download, live/testnet order, credential, owner-account reset,
Scheduled Task installation, reboot, power-loss trial or real-feed soak was
performed. Actual market-data provenance and prospective economics require a
separate reproducible run and independent review. Fixture-driven Windows
lifecycle success cannot establish those operational claims.

The wiki was reassessed against broker/state/planner and this report; prior
source hashes and conclusions remain recorded. Git metadata in the handoff is
a pre-commit snapshot, so a later HEAD/status mismatch is expected and must be
reconciled with commit history. Derived graphs are local rebuildable outputs.
Main integration is selective: PR5/PR6 branch ancestry remains separate, and
unreviewed old broker/RL changes are not accepted by this commit.
