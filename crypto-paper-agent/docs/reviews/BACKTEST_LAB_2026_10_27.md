# Backtest Lab — delivery and verification, 2026-10-27

## Scope and identity

Owner-approved additive offline batch tool, automatic identical-result reuse and
comparison reports. Existing directional and funding-carry execution is reused;
no broker, risk, funding policy or strategy rules were changed. Sources mirror
untouched. Specialized shared-account cointegration/OI workflows remain separate.

Repository: eth-btc-research; branch codex/eth-btc-cointegration-v1; base/HEAD
b6ccff26a538f65eec1b2206bdf424aca62b8968. Delivery consists of local changes,
not a new commit or GitHub integration. Final scripts/backtest_lab.py SHA256:
28cc9dcf5bc1ec053eb131b21f22b6d4b43ab15391286a8745f920b9da1a97fc.

Files: scripts/backtest_lab.py, tests/test_backtest_lab.py,
config/research/backtest_lab.example.yaml, docs/operations/BACKTEST_LAB.md,
docs/superpowers/plans/2026-10-27-backtest-lab.md, this report and README.md.

## Author verification on final code

Commands from crypto-paper-agent, existing Python 3.12.14 runtime:

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_backtest_lab.py -q --tb=short --basetemp=../../tmp/lab-final-focused
../.venv/Scripts/python.exe -m pytest tests -m 'not network' -q --tb=short --basetemp=../../tmp/lab-all-final
git diff --check
```

- Focused: **19 passed**, 22.42 seconds, exit 0.
- Full offline: **705 passed, 4 skipped, 5 deselected**, 113.14 seconds, exit 0.
- Whitespace check: exit 0. Logs: artifacts/backtest-lab-focused-final.log and
  artifacts/backtest-lab-full-final.log.
- The initial full run with a deeper fixture root had 3 pre-existing
  SQLite/report-path failures. All 3 passed on an unchanged isolated rerun
  with a shorter fixture root; the final full run above passes. Original
  evidence: artifacts/backtest-lab-full-tests.log and
  artifacts/backtest-lab-original-check.log. No unrelated code was patched.

## Separate Tester and Independent Reviewer

VERIFIED by separate Tester on the preceding 18-test revision: 18 focused
tests and 10 supplemental tests passed. Supplemental checks cover external-CWD
CLI runs, nonempty ETH carry fixture parity, date/equity-config invalidation,
cache reuse, missing funding, gaps, duplicates, timezone and coverage rejection.
Tester independently found the Windows long-cache-path and missing prior
carry funding defects; both were fixed and rechecked. Detailed historical and
final evidence is retained in artifacts/lab-tester-extra/TESTER_REPORT.md and
its JUnit files. Tester hash identifies that revision, not the final path fix.

Independent Reviewer found one further mixed Windows-prefix protection defect.
After reproduction and correction, final reviewer verification of prefixed
path protection, long paths and overwrite/data-directory protection: **3 passed**,
4.77 seconds, --basetemp=artifacts/rv3. Final verdict: no remaining actionable
P1/P2 in reviewed scope. No self-acceptance or economic gate acceptance.

## Real local data smoke and cache timing

Input: market-data/eth-btc-v1, already present BTCUSDT/ETHUSDT normalized public
data; exact data/code/runtime/config identities are in each comparison.json.
Batch: artifacts/backtest-lab-real-example.yaml. Fixed retrospective January
2024 swing_ema_pullback, BTC base, BTC costs2x and ETH base (4, 4 and 6 trades).
These are mechanical checks, not candidate optimization or an untouched OOS test.

```powershell
../.venv/Scripts/python.exe scripts/backtest_lab.py --data-dir market-data/eth-btc-v1 --batch artifacts/backtest-lab-real-example.yaml --output artifacts/backtest-lab-final-01
../.venv/Scripts/python.exe scripts/backtest_lab.py --data-dir market-data/eth-btc-v1 --batch artifacts/backtest-lab-real-example.yaml --output artifacts/backtest-lab-final-02
```

Subprocess wall time including startup and input hashing: **8.402 s first run,
3.705 s repeated run**. All three repeated jobs have cached=true, identical
run_id and identical full summaries. Exact measurements:
artifacts/backtest-lab-timing.json. Second report:
artifacts/backtest-lab-final-02/comparison.md (plus CSV and JSON).
No guaranteed speedup is inferred for other datasets/machines.

## Limits and next use

No GUI, optimizer, downloads, new dependencies or live orders. Each requested
parameter set must be an explicit YAML job. Cache hits still hash all input
Parquet/JSON and code; changing unrelated peer data or installed packages can
conservatively invalidate cache. Do not mutate input files concurrently.
No historical profitability validation or economic acceptance follows from
passing software tests. Next user action: copy the example YAML, choose existing
strategies/configs/windows, and run with a new report output directory.
