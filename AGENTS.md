# Project Agent Instructions

This repository is a crypto futures **paper-only** research project. Public
live market data may drive simulated orders. Do not add exchange order
submission, testnet orders, trading keys, private keys, wallet signing or
real-money behavior without a new, explicit owner authorization and plan.

Owner workflow update (2026-09-23): `main` is the single active integration
branch. After an in-scope commit/push, verify the primary local checkout and
GitHub `main` have the same SHA. This branch consolidation does not accept any
pending engineering gate or relax the paper-only/risk rules. See
`crypto-paper-agent/docs/planning/2026-09-23-main-sync-decision.md`.

## Codex skill and MCP routing contract

This project is configured for automatic skill selection. The Project Manager (PM) and coding chats must route each request before acting; do not wait for the owner to name a skill. Use only skills actually available in the current session, and fall back to the same workflow manually when one is unavailable.

1. **Session bootstrap:** Read this file, the current checkpoint at the top of `crypto-paper-agent/PROJECT_STATE.md`, the relevant part of `PLANNER_HANDOVER.md`, the applicable master-spec/ADR section, and the latest relevant review. Confirm repository root, branch, `HEAD`, and working-tree status. Read deeper only as the task needs; never infer state from an older chat.
2. **Code context:** Use `codebase_memory` or GitNexus for repository structure, symbol relationships, impact analysis, and targeted snippets when that is more efficient than direct search. Use Serena for symbol-aware navigation/refactors when available. Re-index only when stale; never treat an index as fresher than the working tree.
3. **Documentation lookup:** Use Context7 or official project documentation for library/API behavior. For exchange, market-data, or chain semantics, use the project's approved data sources and preserve source/event/availability timestamps.
4. **Plan before multi-file work:** For a new feature, gate, migration, or cross-module change, use `writing-plans` when available and save a scoped plan under `crypto-paper-agent/docs/superpowers/plans/` before implementation. Keep one declared gate and one file-ownership scope active at a time.
5. **Implementation workflow:** Use `crypto-bot-engineering` for trading/data/backtest/risk/execution work. Add `test-driven-development` and `ecc:python-testing` for Python behavior changes; use `systematic-debugging` for unexpected failures. Use `ecc:mle-workflow`/`ecc:pytorch-patterns` only for PPO/model work and `ecc:security-review` only for security-sensitive changes. Prefer the smallest change consistent with current ADRs.
6. **Review and delivery:** Use `verification-before-completion` with fresh, scoped commands before claiming a fix or completion. Use `requesting-code-review`/`receiving-code-review` when their review workflows apply. Separate Tester/Independent Reviewer work is still required at the project's declared review gate; do not self-accept. Report pass, skip, deselected, network, author-reported, reviewer-verified, and blocked results separately.
7. **Market/TradingView routing:** Use `tradingview-paper-research` plus the installed `crypto_market` MCP for read-only TradingView-style market comparison or a TradingView Strategy Tester reconciliation. `crypto_market` backtests are not native TradingView Strategy Tester runs. For native results, require a Pine strategy and TradingView Strategy Report/export; label it `NOT_VERIFIED` until observed. Use `aicoin-market` only for suitable market-data queries and `aicoin-hyperliquid` only for Hyperliquid/on-chain analytics. None substitutes for the repository's reproducible venue-specific data pipeline or proves executable fills/profitability.
8. **Safety boundary:** The default mode is paper-only and read-only credentials. No live/testnet order, wallet signing, withdrawal permission, secret creation, deployment with trading credentials, or external mutation is implied by a coding request. Stop and request explicit owner authorization plus a plan before any such action.

PM routing: use the task-to-skill/MCP matrix in `crypto-paper-agent/docs/planning/PM_SKILL_MCP_ROUTING.md` before assigning a new gate or specialist task. Select one primary skill and only the additional skill/MCP needed for the current step; do not load every installed skill or query every code graph by default. For status-only work, direct Git/file checks may be sufficient. State the selected route and evidence level in the handoff. Do not start market downloads, browser login, TradingView webhooks, or a new project gate just because a tool is available.

Before taking project action, read:

1. `crypto-paper-agent/docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md` for
   product intent, gate sequence and unresolved owner decisions.
2. `crypto-paper-agent/PROJECT_STATE.md` and `PLANNER_HANDOVER.md` for the
   current factual checkpoint. Verify branch, full code/docs/main SHA and
   working-tree status; do not assume the document's SHA is still HEAD.
3. Relevant approved ADRs and the master spec. Consult
   `Initial idea/AGENT_SPEC.docx` to preserve founding intent, but do not
   silently replace later owner decisions or binding risk policy with it.
4. The exact gate plan and review/evidence manifest for the task at hand.

Work on a single declared gate and file ownership at a time. Keep train,
validation, historical OOS, near-current replay and prospective paper
observations distinct. No future data in a decision or retrospective tuning
on holdout. Preserve source/event/availability times, raw hashes, spot/perp
identity, risk gates, broker accounting and funding event idempotency. No
profit claim follows from test pass or a short backtest.

Every handoff records scope, branch/base/full code and docs SHAs, changed
files, config/data/model identity, exact commands and outcomes, failures,
unverified claims, resource limits and next owner. Label `VERIFIED` with who
verified it; otherwise use `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`,
`NOT_VERIFIED` or `BLOCKED` and name the cause. Do not self-accept; Tester and
Independent Reviewer work separately, and the owner decides gate acceptance.
The owner-authorized `main` integration is not itself an acceptance verdict.

If a new user requirement conflicts with the charter, spec or ADR, record
the conflict and ask PM/owner to resolve it before widening scope. Update the
decision register and affected gate plan after approval; do not erase old
decisions. Preserve unrelated worktree changes and use separate worktrees for
independent verification.
