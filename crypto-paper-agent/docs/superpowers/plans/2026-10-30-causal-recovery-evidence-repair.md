# Causal broker, recovery and evidence repair plan

> **For agentic workers:** Use superpowers:subagent-driven-development with TDD and independent review. Execute continuously within the owner's authorized paper-only repair scope.

**Goal:** Repair reproduced broker/risk/recovery regressions and invalid synthesized-data/acceptance behavior; preserve old failed evidence.

**Architecture:** Retain current main's synchronized phase scheduler and risk limits. Make historical input validation fail closed, synthetic execution explicit, funding provenance truthful, and engineering/economic verdicts distinct. Adapt legacy recovery/API callers to that broker only after core invariants pass.

**Tech Stack:** Existing Python/pandas/pytest and Windows/web test tooling; no new trading endpoint or credential.

**Spec:** AGENTS.md, master spec U1–U7, approved ADRs, docs/reviews/UNMERGED_AND_ARTIFACT_VERIFICATION_2026_10_30.md and its saved independent evidence. Owner explicitly requested these defects repaired and graph-reviewer.md plus Superpowers used. Base: 56382df63f0a58ba249d39b005ad97e90cd30150.

## Constraints and rulings

- Paper-only; no live/testnet order, owner-account reset, OS reboot/task installation or new economic claim.
- Retain capacity, pending slots, gross limits, kill switch, gap guards, STOP_WIDENED and isolated-margin liquidation protections.
- Do not silently fallback to synthetic or fabricate funding. Explicit synthetic runs must label all outputs and cannot receive historical/economic acceptance.
- Preserve original artifacts and old forensic probes. Static claims about immutable bad artifacts cannot become true through a code repair; new tests must verify they are rejected/reclassified, not rewrite originals.
- No parameter tuning to make historical PnL, sample counts or tests look good. Economic evaluation must reject negative net expectancy/PF<1 and fail closed without a declared risk contract; a rejected strategy is a valid software outcome.
- The supplied graph reviewer validates navigation quality, not runtime correctness. Use exact source and tests for behavior; never invent graph edges.
- Package dependencies required by declared test/runtime contracts may be installed in the project venv; no market-data downloads in this repair without a separately scoped need. This clarifies the previous worker's overly broad no-download restriction.

## Tasks and ownership

### 1. Validate and use the code graph
- [x] Run exact deterministic checks/decision from the owner-provided graph-reviewer.md against package .ua/knowledge-graph.json; save script/results/report in workspace tmp/repair-20261030.
- [x] Identify source paths for broker phases, breaker callbacks, recovery serialization, synthesized loader/runner/filter and report acceptance. Record graph coverage limits.

### 2. Broker correctness (exclusive owner: broker implementer)
Files: src/execution/paper_broker.py; new targeted broker regression tests. Dependencies: no changes to loader/runner or acceptance module.
- [x] Reproduce peer funding omitted by early breaker close, stale-price forced exits, bypassed peer stop, direct overlapping/same-open late mutation and drained-collateral liquidation bounds.
- [x] Repair phase-level lock handling and preflight atomically without dropping existing risk/portfolio behavior.
- [x] Test original failing assertions plus current broker/ORB/funding/risk regressions, single-symbol parity, simultaneous gaps/settlements/locks and invalid-batch no-mutation.

### 3. Synthesized data and scheduling (exclusive owner: data implementer)
Files: src/data_layer/universe_loader.py; scripts/run_synthesized_backtest.py; src/strategies/synthesized.py; dedicated tests. Parent coordinates acceptance interface.
- [x] Reproduce fallback/provenance/funding defects and cross-symbol earlier-fill mutation.
- [x] Historical mode rejects missing/unproven cache/funding and misaligned clocks; explicit synthetic mode uses isolated cache identities and truthful metadata.
- [x] Synchronize runner using process_batch; preserve source/event/availability times and actual funding idempotency; unknown filter inputs reject.
- [x] Keep default risk protections through configuration composition and record exact config/code/data identity.
- [x] Run causal future-mutation, source identity, funding gaps/nonfinite/duplicate, cache-conflict and CLI-mode tests.

### 4. Acceptance and historical errata (exclusive owner: parent)
Files: focused acceptance module if needed; tests/test_e2e_synthesized_backtest.py and artifact/acceptance tests; new corrective review document. Do not alter original artifacts.
- [x] Reproduce permissive win-rate OR and 95% DD acceptance; define engineering checks separately from economic rejection.
- [x] Use a declared economic/risk contract, reject malformed/nonfinite metrics and synthetic/unverified provenance. Do not invent an owner-approved drawdown threshold.
- [x] Correct current-facing claims about original synthetic evidence, parameters and fee math while preserving dated source reports.

### 5. Recovery/API integration after broker stabilization
- [x] Review PR5/PR6 recovery state and metadata requirements using graph/source, adapt in an isolated candidate while preserving current broker, and retain both valid API contracts where required.
- [x] Verify recovery commit/exposure identity, pending closes/orders/funding, replay idempotency, request-time controls, launcher/schema and frontend. Install declared small missing dependencies only in venv as needed.
- [x] Merge only a reviewed composition, not a wholesale old broker replacement. Record genuine unverified operational checks separately.

### 6. Review and delivery
- [x] Fresh-context independent review and separate tester evidence, scoped RED/GREEN proof, then full core and end-to-end engineering flow. Use short Windows fixture paths.
- [x] Run an explicit full-year synthetic E2E only after smaller regressions stabilize; do not represent it as real market validation.
- [x] Reassess changed wiki sources, retain prior hashes/labels, update current checkpoint and handoff, refresh navigation graph and owner-requested review.
- [x] Commit/push authorized fixes, verify main local/remote SHA, report remaining limitations and no profitability acceptance.

Completion evidence: docs/reviews/CAUSAL_RECOVERY_EVIDENCE_REPAIR_2026_10_30.md. Main publication identity is verified after commit; no economic or real operational acceptance follows.
