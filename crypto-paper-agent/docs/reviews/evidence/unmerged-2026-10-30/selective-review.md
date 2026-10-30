# Independent selective integration review — 2026-10-30

Candidate: `0654b277a5e1815ca94068c1793f5e42b061baaf`, parent `d4cc137`. Reviewed at `tmp/remaining-branches-20261030/candidate` read-only. No source, tests, index, or refs changed by this reviewer.

## Scope and review

Exactly four files differ: `crypto-paper-agent/run_backtest.py`, `src/data_layer/fetcher.py`, `src/features/cvd.py`, and new `tests/test_input_fidelity.py`. Production change is 29 additions / 13 deletions. All prior tests are unchanged; no added skip, xfail, or altered assertion masks the deferred broker/RL issues.

- Missing six-field OHLCV taker volume stays NaN instead of invented 50% buy volume (`fetcher.py:211`). CVD rejects nonfinite, negative, and greater-than-volume observations, and propagates unknown cumulative values after the first unknown delta (`cvd.py:47–65`). Existing fully observed behavior is preserved.
- OI backward joins now have a finite mapped sampling-age limit, preserve source timestamp, mark unavailable observations, and reject stale/nonfinite values (`fetcher.py:623–649`). No future OI value is admitted. This does not claim to solve deferred intrabar strategy availability issues outside this patch.
- `run_backtest.py:159–165` refuses explicit date flags for the two modes which did not apply those flags, before loading files or producing reports. Other strategy modes retain their existing date behavior.
- Broker, RL environment, OI-reclaim simulator, risk settings, execution/funding accounting and existing tests have no diff. Current OI-reclaim F5 minimum-of-project/v1 loss-limit logic remains at `src/strategies/oi_reclaim.py:163–166`.

No P1/P2 defect found in this selective source change. This recommendation applies only to this commit, not the parent legacy branch, PR5 or PR6.

## Independent verification

Runtime: primary repository `.venv/Scripts/python.exe`, Python 3.12.14 / pytest 9.1.1, Windows. `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `PYTHONDONTWRITEBYTECODE=1`.

From candidate package:

```
python -X utf8 -m pytest tests .ua/tools/test_code_graph.py -m 'not network' --ignore tests/test_adversarial_m2_audit.py --ignore tests/test_adversarial_m2_empirical.py --ignore tests/test_e2e_synthesized_backtest.py -q -rs --tb=short --basetemp <primary-repo>/tmp/windows-verify-20261030/selective-core-fixtures
```

First full-core result: **1014 passed, 3 failed, 7 skipped, 5 network deselected**, 124.93 seconds (`selective-core.log`). All three failures are `sqlite3.OperationalError: unable to open database file` in unchanged report generation using excessively long Windows fixture paths. They are not changed-data assertions.

Focused rerun uses shorter external basetemp `<primary-repo>/tmp/sv065`:

```
python -X utf8 -m pytest tests/test_comparison.py::test_four_strategy_workflow_real_execution_and_artifacts tests/test_stage_06_integration.py::test_deterministic_run_id_across_invocations tests/test_stage_06_integration.py::test_config_identity_is_cross_root_and_sensitive_to_fees -q --tb=short --basetemp <primary-repo>/tmp/sv065
```

Rerun: **3 passed in 20.28 seconds**, log `selective-path-rerun.log`. Across the full selected core scope, **1017 distinct cases independently verified pass, 7 existing skips, 5 network deselected**. The initial three failures were resolved solely by shortening the fixture path, with no source or test changes. `git diff d4cc137 --check` passed and the candidate remained clean.

Existing skips: RL/PPO extras, pandas-ta cross-checks, and host symlink/junction privileges. RL runtime is not independently executed; its source is unchanged. Current broker, kill-switch, liquidation, ORB portfolio, funding, OI-reclaim/F5 and the five new regressions are included in the passing core scope. No network tests or package installation occurred.

## Full-year synthetic E2E impact

The separate yearly artifact tests were intentionally excluded because the parent independently owns those longer checks on original main. Source tracing establishes no dependency on these three changed production files for the `allow_network=False` synthetic E2E route:

- `scripts/run_synthesized_backtest.py:183–189` calls `UniverseDataLoader.load_universe`.
- `src/data_layer/universe_loader.py:607–633` reads its own cache or uses `generate_synthetic_universe`, which constructs OHLCV directly at lines 333–430. It does not call changed fetcher/CVD code.
- The synthesized runner computes EMA/ATR/RSI/ADX directly at lines 205–232 and uses its unchanged broker/strategy.
- Changed `run_backtest.py` is a separate entrypoint.

Thus the selective patch does not change the full-year synthetic test execution path by inspected call graph; this is not a rerun of that full-year suite, market evidence, or economic acceptance.

Verdict: **Ship selective commit 0654b277a5e1815ca94068c1793f5e42b061baaf. No P1/P2 findings.** Preserve the separately documented deferrals for the full legacy PRs and broker/RL behavior.
