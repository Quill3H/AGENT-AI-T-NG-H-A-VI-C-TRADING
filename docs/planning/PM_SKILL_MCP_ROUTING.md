# PM skill and MCP routing — Quill3H paper bot

This is a routing guide, not a new project gate or permission to trade. `AGENTS.md`, the current checkout/HEAD, charter, ADRs, and latest review remain authoritative. The PM chooses a route when a task arrives; the owner need not name a skill. Check that a skill/tool is actually exposed in the current session, and use the same workflow manually if it is unavailable.

Owner workflow update (2026-09-23): `main` is the active integration branch and
must match GitHub after each push. This does not accept pending technical gates;
see `2026-09-23-main-sync-decision.md` and the latest `PROJECT_STATE.md`.

## Invocation syntax

- In Codex, `$skill-name` explicitly selects a skill. Examples:
  `$writing-plans`, `$crypto-bot-engineering`, `$systematic-debugging`,
  `$test-driven-development`, `$verification-before-completion`, and
  `$tradingview-paper-research`.
- `/name` is a harness command or compatibility shim, not a universal skill
  syntax. Execute it only when the command is registered and its backing
  command-skill has been read. Do not invent `/deploy`, `/review`, or `/plan`
  merely because the words sound plausible.
- Plain language is sufficient. The PM must classify the task and activate the
  matching skill automatically rather than asking the owner to resend it with
  `/` or `$`.
- For a feature use: planning -> TDD/domain implementation -> verification ->
  review. For a defect use: systematic debugging -> regression test -> minimal
  fix -> verification. Each arrow is a gate; do not load all skill bodies at
  once.

## Fast route

| Request | Primary skill | Add only when needed | MCP/CLI choice | Stop/evidence rule |
|---|---|---|---|---|
| Status, scope, next gate, handoff | None; read current project checkpoint and relevant ADR/review | `writing-plans` for an actual multi-step implementation plan; `ecc:architecture-decision-records` for a newly approved architecture choice | Git status/log and exact files first; `dev_memory` named-node lookup only for historical orientation | Do not run tests, fetch data, or advance a gate just to answer status. Verify current HEAD; memory is not authority. |
| Locate code, trace impact | None | `crypto-bot-engineering` once trading behavior is in scope | `rg` for a known file/string; choose **one** of `codebase_memory` or GitNexus for graph questions; Serena for symbol-level navigation/refactor | Check index freshness against the working tree; use direct source for final evidence. |
| Feature or multi-file change | `crypto-bot-engineering` | `writing-plans`, then `test-driven-development`; `ecc:python-testing` for pytest; `ecc:python-patterns` only for Python idioms/typing | Context7 or official docs only for an API whose behavior matters | One approved gate and owned file set; red/green evidence and fresh verification. |
| Bug, failed test, artifact mismatch | `systematic-debugging` | `crypto-bot-engineering` for trading semantics; `ecc:python-testing` for a regression test | Reproduce with the smallest command; use graph tools only if causal path is unclear | Preserve failing input and exact runtime; no speculative fix or pass claim. |
| Market data, funding, exchange adapter | `crypto-bot-engineering` | `tradingview-paper-research` only for TradingView comparison; `aicoin-market`/`aicoin-hyperliquid` only for their matching data questions | Approved public venue adapter and raw archive are primary; `crypto_market` is read-only cross-check | Preserve venue/instrument, event/receipt/availability time, UTC, raw hash, gaps and funding provenance. No generic spot quote as perp fill. |
| TradingView Strategy Tester | `tradingview-paper-research` | `crypto-bot-engineering` only if changing bot code | `crypto_market` for a separate comparison; native test requires Pine `strategy()` and TradingView report/export | An MCP backtest is not the native Strategy Tester. Without native evidence mark `NOT_VERIFIED`. |
| PPO/training/evaluation | `crypto-bot-engineering` | `ecc:mle-workflow` for data/model lifecycle; `ecc:pytorch-patterns` for PyTorch-specific code | Local pinned data/model artifacts; Context7 for uncertain APIs | Freeze train/validation/OOS and risk policy; no online learning in scored runs; no profitability claim. |
| API, secrets, webhook, external input | `ecc:security-review` | `crypto-bot-engineering` when trading data/risk affected; `ecc:error-handling` for retry/fail-closed design | Official docs/Context7; no credentials in MCP prompts, logs, fixtures or memory | Paper-only; no live/testnet orders, signing or credentialed deployment without explicit owner decision and plan. |
| Code review or acceptance | `requesting-code-review` for a completed implementation; `receiving-code-review` when responding to feedback | `verification-before-completion`; `ecc:ai-regression-testing` for AI-authored regression blind spots; specialist tester/reviewer only at the declared gate | Fresh tests/diff, exact SHA, runtime, artifact hashes; GitHub MCP only if exposed/authenticated for requested remote PR work | Author test is not independent verification; PM cannot self-accept. Owner-directed `main` integration is not gate acceptance. |
| Agent workflow or token-cost issue | `ecc:context-budget` for context bloat; `ecc:agent-architecture-audit` only when agent behavior is failing | `ecc:cost-aware-llm-pipeline` only for measured LLM API spend in the product | `headroom` stats/compression for large outputs; inspect enabled MCP namespaces rather than adding servers blindly | Record the measured bottleneck and proposed saving; do not disable shared/global tools without owner approval. |
| Preview web demo and deploy | Web/frontend skill exposed by the current harness; otherwise inspect stack and implement the smallest viable UI | `writing-plans`, security review for inputs/secrets, deployment/verification skill when exposed | Prefer a preview deployment. Use an existing authenticated provider/CLI; never put tokens in prompts or files | Browser smoke, build/test evidence, deployment URL and exact commit. Do not promote to production or expose trading credentials. |

## Resource discipline

1. Read `AGENTS.md` and the current checkpoint, then retrieve only the relevant spec/ADR/review passages. Do not paste whole histories or entire tool catalogs into a task prompt.
2. Pick one primary skill first. Add process skills only when they change the current implementation or verification step; do not invoke overlapping skills merely because they are installed. Check current availability; names in this file are routing hints, not proof of availability.
3. Start with direct `rg`/Git for narrow facts. Use one code graph for structural questions, not `codebase_memory`, GitNexus and Serena in parallel by default. Re-index only when stale.
4. Use `headroom` compression only for large outputs that must be retained; retrieve by hash when exact lines are needed. `dev_memory` is a hint for stable decisions, never a substitute for repo files, current SHA, or evidence. Do not store secrets, market snapshots, mutable status, or unreviewed claims there.
5. Do not run `crypto_market`, AIcoin, browser automation, downloads, broad tests, or external research for a status/planning request unless its answer needs them. Do not enable every MCP server just to make it available.
6. Before delivery, state selected route, source/commit, commands actually run, pass/skip/deselected/network status, unresolved evidence, and next owner. Use `verification-before-completion` for implementation; a read-only PM handoff needs source checks, not a synthetic test pass.
7. For delegated work, call the event watcher once with the returned cursor and
   wait for a state transition. Do not re-read an unchanged thread. A timeout is
   not a failure and does not justify another immediate poll; remain quiet until
   completion, failure, required input, or a meaningful progress change.

## Current handoff priority (verify before reuse)

At the 2026-09-23 owner checkpoint, `main` contains the functional-completion candidate and the bounded G2 Binance diagnostic. Separate Tester and Independent Reviewer work and owner acceptance remain pending. The PM must recheck branch/HEAD and `PROJECT_STATE.md` before acting. The 2026-09-25 owner instruction separately authorizes a two-hour preview-web-demo task; it does not authorize further G2/G3/G4/G5 work, a TradingView account integration, market downloads, or live/testnet trading merely because a tool is available.
