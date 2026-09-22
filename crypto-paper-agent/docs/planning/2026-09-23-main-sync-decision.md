# Owner decision: one visible integration branch and local/remote sync

Date: 2026-09-23. Source: owner's instruction in the current project task to keep GitHub edits synchronized with the local machine and simplify work to one `main` branch.

## Change record

- Previous workflow: implementation/evidence lived on separate `codex/*` branches and worktrees; `main` remained at the older Stage 6 checkpoint pending independent review and owner acceptance.
- New workflow: `main` is the single **active integration branch** for this local paper-research project. The owner authorized fast-forwarding the latest G2 documentation checkpoint into `main`. Future in-scope edits should use the primary local checkout, commit/push `main`, then verify local `HEAD` equals `origin/main` and the GitHub remote SHA. Do not create extra worktrees unless isolation is genuinely needed for an independent test or unsafe concurrent change.
- Rationale: the owner does not want to track multiple active trees or different local/GitHub code states.
- Approval owner: repository owner, via the 2026-09-23 conversation. This is authorization to integrate a snapshot, **not** acceptance of G0/G1/G2 correctness, economic validity, or production readiness.
- Affected gates: G0/G1/Stage 6–11 and G2 retain their existing `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED` or pending-review labels. Separate Tester and Independent Reviewer evidence remains required. G3/G4 holdout and prospective paper gates remain unopened.
- Affected technical policy/tests: none. ADR 0011 exact funding provenance, no-lookahead, accounting and paper-only safeguards remain unchanged. The existing code A regression suites were run before integration; the latest focused G2 tests also passed from a clean checkout.
- Scope boundary: do not force-push, rewrite history, delete historical branches/worktrees, or stage unrelated local edits. In particular, locally modified `AGENTS.md` and untracked `.serena/` and `docs/planning/PM_SKILL_MCP_ROUTING.md` remain owner-local until explicitly reviewed for inclusion. Public market datasets stored outside Git are not automatically synchronized by Git.

## Verification and handoff

The fast-forwarded G2 documentation checkpoint was `5c191856b4a5877923dabbae5426fffa7f01a9b9`, with code-under-test A `d4afed6d365b3e435e79a772f7de912ee4a39b11`. Before this documentation update, `main`, `origin/main` and GitHub `refs/heads/main` were checked at that same B SHA. The final documentation SHA must be read from Git history after this file and the checkpoint updates are committed; no self-referential SHA placeholder is asserted.
