# Main integration review — started 2026-10-29, completed 2026-10-30

Owner authorized review and merge of ready work into main. This records software
integration, not economic acceptance, project-gate acceptance or permission for
live/testnet orders. Paper-only scope is unchanged.

## Pinned inputs and scope

- Main before integration: `65960bff7341637557d8158c2440dcc087ce1a41`.
- Research candidate: `05a396f1f1568639e7fb86524c27c861e829386e`, including fixed
  ETH/BTC retrospective research, offline Backtest Lab, causal ORB portfolio and wiki.
- Backtest Lab publication branch: `95af0a28d25b9dbcb7bdef83d33d01af025073b9`, PR #8.
  Its batch runner/tests match the research candidate except additive portfolio
  dispatch; the separate publication receipt is useful historical evidence.
- External-repo research and research QA hardening are already ancestors of main.
  No duplicate cherry-picks or changes to those conclusions are needed.

Four conflicts in CHANGELOG, PROJECT_STATE, LEARNING_LOG and ledger.jsonl were
resolved by retaining both histories. JSONL parses as 427 records. Main broker
clock/cashflow guards and equal-timestamp snapshot replacement survive alongside
the portfolio phase barriers. Legacy sequential callers are not automatically
converted to process_batch.

## Integration repairs

1. Main's ledger now requires preregistration for new string round identifiers.
   The old cointegration --append-ledger path failed after replaying and publishing
   a scenario. It now rejects the legacy flag before any dataset/output work;
   ordinary artifact export is retained. No ledger governance bypass or retroactive
   preregistration was introduced. Existing retrospective rows remain historical.
   The regression failed with DATASET_UNAVAILABLE before the repair and passed after.
2. Existing main requirements.txt had reverted ccxt to >=4.4.27 while its lockfile
   and public-only regression require ==4.5.82. Restored that exact existing pin and
   installed it in the project venv. The failed pin check was observed first.
   Installed main's already-declared scikit-learn dependency for test collection.
3. Re-read changed state/planner/broker/pair-ops sources and dependent wiki pages.
   Updated four hashes, retained all former hashes in previous_versions, and kept
   verification labels unchanged. Reviewed the ETH/BTC semantic page update before
   refreshing its inference-input hash. Source hashes are not acceptance evidence.

## Fresh verification

From crypto-paper-agent, using the existing project Python 3.12.14 venv:

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
../.venv/Scripts/python.exe -X utf8 -m pytest tests .ua/tools/test_code_graph.py -m 'not network' --ignore tests/test_adversarial_m2_audit.py --ignore tests/test_adversarial_m2_empirical.py --ignore tests/test_e2e_synthesized_backtest.py -q -rs --tb=short --basetemp ../../tmp/main-merge-core-green-20261030
```

Author result: **1012 passed, 7 skipped, 5 network deselected**, exit 0, 129.07s.
Skips: PPO/quickstart optional extras, two pandas-ta comparisons, and three native
symlink/junction privilege checks. This is the core suite, not all repository tests.

Separate fresh-context reviewer verified the broker/PairAccount/Backtest Lab
integration with **69 passing tests**. Final independent repair checks: CLI
**4 passed**, fetcher/public-only pin **2 passed**; wiki lint and check-sources each
**20 pages / 14 sources / 0 findings**. No outstanding P1/P2 in reviewed scope.

Author also verified wiki lint/check-sources and rebuilt both local navigation
graphs; freshness checks returned true. Git whitespace check uses
`-c core.whitespace=cr-at-eol,-blank-at-eof` to preserve byte-hashed CRLF evidence
and original imported-report EOF blank lines. Handoff Git metadata remains an
explicit historical checkpoint; handoff-check is not claimed clean after commits.

## Limits and work not integrated

The first unrestricted offline run hit missing out-of-Git synthesized report
artifacts and was interrupted during its long synthetic yearly E2E fixture.
An untouched archive of the exact pre-merge main independently reproduced the
missing summary.json failure. An existing artifact-rich checkout of that same
main passed all 16 artifact-audit tests. The three unchanged empirical/acceptance
files listed in the command were excluded from the final core run; no full-year
backtest, economic study or network suite was rerun for this integration.

Pre-existing synthesized result/acceptance claims are retained as historical
source claims, not reaccepted by this merge. The separate local audit at
output/synthesized-retest-2026-10-29/BAO-CAO-KIEM-THU-LAI.md in the parent workspace
records unresolved synthetic provenance, funding assumptions and sequential
multi-symbol lookahead concerns. Those require a separate scoped repair; adding
process_batch does not itself migrate that runner or validate its old artifacts.

PR #5 and draft PR #6 target the legacy local-paper-futures-app branch, with
operational/recovery/independent acceptance work still pending. They and their
legacy branch stack are not approved by this integration review. The alternative
older OI branch does not replace main's later reviewed F1–F5 implementation.
No branch deletion, force push, account initialization or deployment is authorized
or performed as part of this integration.

Final merge and push identities are recorded in Git history and the user handoff,
rather than embedding a self-referential final commit SHA here.

## Backtest Lab publication integration — 2026-10-30

Research merge commit: `488df0a`. Merging publication head `95af0a2` then produced
two add/add conflicts in the batch runner and its operator guide. Kept the reviewed
main versions, which contain the original batch behavior plus portfolio dispatch.
An exact diff confirmed no runtime source, script, config or test changes relative
to `488df0a`; the publication adds only its historical receipt and this note.
Fresh Backtest Lab regression: **19 passed**, exit 0, 13.96s. The complete core
suite above already covers these same runtime bytes, so it was not repeated again.
PR #8 was retargeted from the old research base to main and marked ready after
verification. Both branch histories are retained by merge commits.
