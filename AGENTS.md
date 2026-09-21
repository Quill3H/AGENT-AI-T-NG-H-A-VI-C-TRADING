# Project Agent Instructions

This repository is a crypto futures **paper-only** research project. Public
live market data may drive simulated orders. Do not add exchange order
submission, testnet orders, trading keys, private keys, wallet signing or
real-money behavior without a new, explicit owner authorization and plan.

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
`NOT_VERIFIED` or `BLOCKED` and name the cause. Do not self-accept or merge;
Tester and Independent Reviewer work separately, and the owner decides.

If a new user requirement conflicts with the charter, spec or ADR, record
the conflict and ask PM/owner to resolve it before widening scope. Update the
decision register and affected gate plan after approval; do not erase old
decisions. Preserve unrelated worktree changes and use separate worktrees for
independent verification.
