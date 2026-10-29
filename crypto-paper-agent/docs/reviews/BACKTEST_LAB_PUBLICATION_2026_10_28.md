# Backtest Lab publication — 2026-10-28

The owner explicitly requested publishing the implemented tool to GitHub.
Publication branch: codex/backtest-lab. Target/base research branch:
claude/project-thread-uiqlsn at ab1ad81ea8f8275e34803298ea1c7ad5c222a45a.
GitHub main was observed at fe1c1330d913e78239db575ff8433cf069fe1b01;
it does not contain the existing research runners this tool requires.
No main integration, unrelated experiment publication, or gate acceptance is implied.

The seven-file Backtest Lab change was copied as a single commit from the
local research checkout. No cointegration experiment commits were included.
Implementation and independent review evidence from the previous base are
historical in BACKTEST_LAB_2026_10_27.md; the current publication validation is below.

Fresh author verification on publication code commit
16f18ebf43bc90394a6f9197dd5a2514535d2739:

```powershell
# From publication checkout's crypto-paper-agent, using the existing environment:
../../../eth-btc-research/.venv/Scripts/python.exe -m pytest tests -m 'not network' -q --tb=short --basetemp=../../lab-publish-qa-20261028
git diff --check origin/claude/project-thread-uiqlsn HEAD
```

Result: **685 passed, 4 skipped, 5 network deselected**, 95.12 seconds,
exit 0. Final diff whitespace check exit 0. The different test total reflects
the publication research base, which lacks the separate local cointegration
experiment. Existing runner interfaces used by Backtest Lab are unchanged.
The implementation's 19 tests are included in the passing suite.

Runner Git blob uses LF. Windows checkout SHA256 (CRLF):
168cbf87fc63eaa62f19e23c6962bbc184ffbcb5a56764b2665160aabddc7fda.
Exact output remains local at tmp/backtest-lab-publish-qa.log relative to the
parent ChatGPT workspace. Raw market data, cache, local paths containing
artifacts, runtime and virtual environment are not added to Git.

This document is a documentation-only follow-up. Software tests and the
owner's publication request do not establish profitability or accept project gates.
