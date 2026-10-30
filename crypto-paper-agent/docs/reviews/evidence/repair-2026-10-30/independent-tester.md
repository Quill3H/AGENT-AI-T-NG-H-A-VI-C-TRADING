# Independent Tester — 2026-10-30

Separate Tester execution for the causal broker/recovery/evidence repair. The Tester did not author these implementation changes and made no production changes or Git mutations.

## Snapshot identity

- Base HEAD: `56382df63f0a58ba249d39b005ad97e90cd30150`; these tests concern the uncommitted working bytes, not that unchanged base commit alone.
- Method: exact filesystem copy of 401 selected source/config/test/operation-schema files into `tmp/repair-20261030/tester-snapshot`, including untracked implementation files. This is a disposable filesystem snapshot, not a Git worktree or full repository checkout.
- Excluded: market caches, reports, node_modules and pycache. Included the existing news-calendar fixture and root CLI file.
- SHA256 of every copied input is in `independent-tester-manifest.json`. Source and snapshot matched before testing and remained byte-identical afterward: source=True, snapshot=True.
- Python: project `.venv/Scripts/python.exe`, 3.12.14; pytest 9.1.1.

## Fresh result

```text
python -m pytest tests/test_broker_phase_repairs.py tests/test_funding_drained_collateral.py tests/test_kill_switch.py tests/test_crypto_orb_portfolio.py tests/test_synthesized_input_contract.py tests/test_economic_evaluation.py tests/test_paper_recovery_review.py tests/test_paper_main_compatibility.py tests/test_paper_research_cycle.py -q --tb=short --basetemp ../tester-fixtures --junitxml=../independent-tester.xml
166 passed in 10.49s
exit 0
```

No skip, deselection or network test was included. XML and complete output are saved as `independent-tester.xml` and `independent-tester.log`. Regression scope: 25 phased-broker cases, drained collateral, kill switch, shared-account ORB, strict data/funding/provenance and source-identity contracts, economic rejection, recovery storage/corruption, current-main static risk/duration compatibility, and research/promotion fail-closed behavior. Fixtures generated explicitly labelled synthetic data only in the disposable snapshot or test temporary directories.

## Limits

This does not verify a full-year E2E, the entire core suite, frontend/browser/Windows process lifecycle, original seven artifact bytes, actual historical market provenance, real-feed continuity, power-loss or Scheduled Task behavior. Root owns those other checks. Passing these regressions does not grant owner gate acceptance or establish profitable trading. No market download, exchange order, credential, owner account or OS task action was performed.
