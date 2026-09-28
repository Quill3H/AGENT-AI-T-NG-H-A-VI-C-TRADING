# GitHub branch consolidation — 2026-09-28

Base for ongoing development: `codex/local-paper-futures-app` at `4dcb2717d06a6a9271f735e035e750c73db8863a`. `main` remains at `fe1c1330d913e78239db575ff8433cf069fe1b01` and is behind this base. The integration candidate is `codex/local-paper-safety-recovery-integration`, with a PR targeting the base branch after verification.

## Inventory and decision

At the refreshed remote snapshot there are 17 branches including `main` (18 after pushing the candidate). These branches are already ancestors of the base and need no new merge: `main`, `codex/architecture-task-tree-alignment`, `codex/final-project-completion`, `codex/g0-market-validation`, `codex/g2-binance-funding-coverage`, `codex/local-paper-scanner`, `codex/pm-product-roadmap`, `codex/repository-information-architecture-cleanup`, `codex/stage-06-completion`, `codex/stage-06-review-12-fixes`, `codex/stage-06-to-11-completion`, `codex/web-preview-binance-dark-ui`.

Four branches diverge and must be examined by diff before any merge: `codex/paper-futures-integration`, `codex/paper-stream-backend` (remote moved to `37bf757` during this review), `codex/paper-windows-recovery`, `codex/review-high-priority-data-fixes`. The recovery candidate's relevant runtime and Windows files are being integrated into the new branch, but that alone does not make its historical commits ancestors. Do not confuse copied changes with a Git merge.

## Order of work

1. Review and verify the safety/recovery integration PR into `codex/local-paper-futures-app`, including a real Windows restart and market stream observation. Keep `main` untouched.
2. Compare the remaining divergent branches file by file against the updated base; record unique changes, tests, and whether they are superseded. Port only verified work through separate PRs when needed.
3. Mark ancestor branches as historical in the handover. After a separately authorized archival decision, use GitHub's branch management to reduce the visible branch count. This pass makes **no branch deletion, force push, history rewrite, or main merge** (per `AGENTS.md`).

For a nontechnical owner: work from the one base branch above. Treat the four divergent branches as candidates awaiting review; an older branch name does not indicate a newer version of the app.
