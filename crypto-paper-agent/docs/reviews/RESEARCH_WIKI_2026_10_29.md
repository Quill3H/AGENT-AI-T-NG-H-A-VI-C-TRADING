# Research Wiki — local delivery and verification

Date: 2026-10-29, Asia/Bangkok. Owner approved design including Understand Anything integration in this chat. Local feature, not project/economic gate acceptance. No commit/push/merge.

## Scope

17 Vietnamese content pages, 11 original local sources, source manifest with byte hashes and locators; four templates; operator contract and handoff. Offline read-only CLI supports status, lint, check-sources, handoff-check and literal search. Source staleness propagates through declared page dependencies, retaining verification labels. Short entrypoint additions in repo AGENTS/package README.

Derived knowledge graph uses installed understand-knowledge parser/merge with authoritative JSON-metadata adapter, explicit source/dependency edges and labelled AI inferences. Code graph is PARTIAL_STATIC Python AST fallback under package `.ua/`; full installed Understand scanner failed because core/dist was not built. No plugin installation/build outside workspace.

Pre-existing Backtest Lab, PaperBroker and ORB working changes belong to other work; not modified by wiki task. Original synced `sources/`, datasets, strategy/risk logic and personal Codex memories untouched. Original source hashes are verified against manifest, not against an external truth authority.

## Identity and reproducibility

Repository HEAD surveyed: `47fdd6dbd6817ba251c6507186052fae48e51eb2`, branch `codex/eth-btc-cointegration-v1`. Dirty/untracked bytes are included by manifests; HEAD alone is not the feature identity. Handoff checks live tracked status and separately exposes untracked paths. Same M status can retain its Git-status hash after another byte edit; use source/graph hashes to detect content changes in declared scope.

Run from package with existing Python 3.12 runtime:

```powershell
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. status
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. lint
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. check-sources
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. handoff-check
../.venv/Scripts/python.exe scripts/research_wiki.py --root knowledge --repo .. search funding
../.venv/Scripts/python.exe scripts/build_wiki_graph.py --check
../.venv/Scripts/python.exe .ua/tools/build_code_graph.py --check
```

## Verification record

- CLI TDD author final: 44 passed, 2 skipped; host denies native symlink/junction creation. Real wiki lint/status/source/handoff checks: zero findings, 17 pages/11 current sources. Literal search `funding`: 19 matches at time tested.
- Static code graph fixture checks: 4 passed, 1 skipped (native symlink denied). Full external Node scanner/Zod semantic pipeline not executed; see `.ua/README.md` and validation artifacts for actual coverage.
- Independent review initially ran CLI + code-graph tests: 48 passed, 3 skipped. All 11 locators occur in source bytes. Reviewer compared strategy summaries to original reports and performed fresh-context onboarding walkthrough.
- Reviewer found Windows source-alias containment and graph input-change-during-build defects in initial adapter; these require regression tests and final recheck below before completion.
- Initial broad test invocation raced TDD file creation and stopped at collection because `build_wiki_graph.py` did not exist yet. This is not counted as a passing verification run. Final test results recorded below supersede it.

## Review and limitations

Knowledge has not independently re-run historical backtests, validated profitability or accepted a trading gate. Reports remain AUTHOR_REPORTED/NOT_VERIFIED as appropriate. CLI checks structure and byte freshness, not semantic truth. Wikilink-only relationships are navigation; page_ids declare staleness dependencies. No web auto-ingestion/daemon/background update.

Dashboard is **not launched or verified**. Pinned external viewer v2.9.8 download inside sandbox failed DNS. Automatic approval review rejected elevated download/execution of the unverified remote npm package against local project data. No bypass attempted. JSON graph files remain available locally. External viewer execution requires separate explicit owner authorization and inspection.

## Final integration results

- Final focused CLI + wiki graph: **58 passed, 2 skipped**, 11.33s; `../.venv/Scripts/python.exe -X utf8 -m pytest tests/test_research_wiki.py tests/test_wiki_graph.py -q -rs --basetemp ../../tmp/wiki-final-focused --tb=short`.
- Full existing offline regression including CLI tests, excluding graph fixture file tested separately: **775 passed, 6 skipped, 5 network deselected**, 134.25s. Command: `../.venv/Scripts/python.exe -X utf8 -m pytest tests -m 'not network' --ignore tests/test_wiki_graph.py -q --tb=short --basetemp ../../tmp/wiki-regression`. Log at project `tmp/wiki-build/regression-offline.log`. Graph fixture tests separately **14 passed**; counts overlap focused result, do not add both.
- Regression emitted one subprocess UTF-8 decoding thread warning in existing `test_external_cwd_replay_cli_emits_nonempty_both_sides_and_checksums`. Re-ran exact test with PYTHONUTF8=1, PYTHONIOENCODING=utf-8 and `-W error`: **1 passed**, 4.87s. No trading/test implementation changed to suppress it.
- Final code graph rebuilt: **216 scoped files, 1,004 nodes, 1,283 explicit static edges**, 12 layers/5 tour steps; freshness check returned true. Coverage remains partial static, not full semantic Understand analysis.
- Wiki graph built by installed parser/merge plus adapter: **17 content articles, 11 sources, 6 topics, 2 labelled inferred entities; 36 nodes, 111 edges**, 8 layers/6 tour steps. Graph freshness will be checked again after the final wiki log update.
- All 11 original source hashes current. Source content and unchanged verification labels inspected independently. Two P2 graph findings received RED/GREEN regression fixes: Windows aliases/private-path containment and immutable pre/post input snapshot guarding publication. Native reparse-point testing limitations remain documented.
- `git diff --check` passed (Git emitted only line-ending notices for pre-existing dirty files). Final independent finding recheck is recorded below.

### Final separate reviewer verdict

Separate fresh-context reviewer reran all three owned suites: **62 passed, 3 skipped**, 11.74s (`tests/test_research_wiki.py`, `tests/test_wiki_graph.py`, `.ua/tools/test_code_graph.py`, basetemp `artifacts/wiki-independent-final`). Native symlink/junction skips reflect host privileges, not successful native tests. Original independent alias probes are now rejected; deterministic parser/merge mutation aborts and preserves prior graph bytes. All four real CLI validation commands exit0; both graph freshness checks return true; wiki graph has zero dangling edges. **No outstanding P1/P2 in reviewed scope.** This is feature review only, not economic/project gate acceptance.

Parent final integration also ran status/lint/check-sources/handoff-check: all exit0/0 findings; both graph checks fresh:true; git diff --check exit0. Wiki log updated before final graph rebuild. Local delivery is ready for use; remote viewer remains blocked as above.

### Dashboard follow-up — owner authorization 2026-10-29

Owner explicitly authorized downloading/running the viewer. Pinned v2.9.8 release tarball returned HTTP 404. Fallback copied installed plugin source into project tmp/wiki-build/viewer-source; installed pnpm10.6.2 frozen-lockfile dependencies with --ignore-scripts (workspace store/cache), compiled core via TypeScript (exit0), and ran local Vite6.4.2 dashboard on 127.0.0.1:5174. Original installed plugin untouched. Server session 21374; local Chrome tab successfully displayed Trading Research Wiki and graph nodes/links and was marked deliverable. Sandbox-only5173 instance was inaccessible to browsers;5174 runs with explicitly approved host access. No public host binding or deployment.

Latest graph loaded by viewer includes separately added external-repo knowledge pages (20 content articles,14 sources); this follow-up did not edit those pages. Dashboard shows a generic 29 working-tree-file/commit-metadata warning. The separate byte-manifest build_wiki_graph.py --check still returns fresh:true. No warning was hidden or acceptance implied. Restart token changes per process; capture Dashboard URL from console rather than using a stale URL.
