# GitHub branch consolidation — 2026-09-28

Base for ongoing development: `codex/local-paper-futures-app` at `b2e62b931125036c678712a3c48c8d07d90abbf1` before this status update. PR #4 merged at `9fd81e718676a06e6a2c3bcdfce266042ebce181`. `main` remains at `fe1c1330d913e78239db575ff8433cf069fe1b01` and is behind this base.

## Inventory and decision

There are six remote branches after cleanup: `main`, the development base, and the four divergent branches below. Twelve non-base branch tips were confirmed to be ancestors of the development base and retired on 2026-09-28. Their names and SHAs are recorded below. The `main` tip is also an ancestor but stays as the default branch.

Four branches diverge and must be examined by diff before any merge: `codex/paper-futures-integration`, `codex/paper-stream-backend` (`37bf757`), `codex/paper-windows-recovery`, `codex/review-high-priority-data-fixes`. Relevant recovery runtime/Windows files were ported via PR #4, but the original branch's historical commits are not ancestors. Do not confuse copied changes with a Git merge.

## Order of work

1. PR #4 is merged into `codex/local-paper-futures-app` and offline tests passed. Verify a real Windows restart and market stream observation before operational acceptance. Keep `main` untouched.
2. Compare the remaining divergent branches file by file against the updated base; record unique changes, tests, and whether they are superseded. Port only verified work through separate PRs when needed.
3. Branch cleanup is complete. Any further deletion requires a fresh tip and open-PR check. Keep `main`, the development base, open PR heads and all divergent branches. Do not force push, rewrite history or merge into `main`.

## Archive record

Deleted after refreshed tip ancestry and open-PR checks on 2026-09-28: `codex/local-paper-safety-recovery-integration` (`6083a59`), `codex/architecture-task-tree-alignment` (`3133fa9`), `codex/final-project-completion` (`4b26525`), `codex/g0-market-validation` (`b174f54`), `codex/g2-binance-funding-coverage` (`5c19185`), `codex/local-paper-scanner` (`46ce69a`), `codex/pm-product-roadmap` (`1903dc2`), `codex/repository-information-architecture-cleanup` (`3a9a6df`), `codex/stage-06-completion` (`b04613a`), `codex/stage-06-review-12-fixes` (`2236e83`), `codex/stage-06-to-11-completion` (`c81dc4e`), `codex/web-preview-binance-dark-ui` (`866448c`). These commits remain reachable from the development branch and the recorded SHAs allow exact branch restoration. A fresh GitHub branch search confirmed the six retained branches and no open PRs.

For a nontechnical owner: work from the one base branch above. Treat the four divergent branches as candidates awaiting review; an older branch name does not indicate a newer version of the app.
