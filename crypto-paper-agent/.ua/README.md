# Partial static code graph

This is a derived navigation map, not engineering or economic acceptance.
The installed Understand `scan-project.mjs` was attempted with Node v24.22.0
and failed with `ERR_MODULE_NOT_FOUND` for `packages/core/dist/index.js`.
The plugin has no `node_modules` or compiled core; no package was installed or
built outside the workspace. The full scanner/analyzer/architecture/reviewer
pipeline was therefore **not run**.

The stdlib fallback in `tools/build_code_graph.py` reads every regular file
under `src/`, `scripts/`, and `config/`, excluding cache/data/artifact/dependency
directories. Python AST supplies named class/function/method declarations,
lexical `contains` edges, and explicit internal `imports` edges. Module nodes,
layers, and tour steps are directory/navigation groupings. Conditional and
local imports are syntax observations; they do not establish execution.
No `calls`, inheritance, data-flow or inferred configuration relationships are
emitted. YAML is inventoried and hashed, not semantically analyzed. External
and unresolved imports remain in `import-evidence.json` without graph edges.
Line-count complexity thresholds are `<60` simple, `<250` moderate, otherwise
complex; they are navigation heuristics, not a maintainability assessment.

`knowledge-graph.json` uses the fields in the installed core's `schema.ts`,
including `kind: codebase`, node complexity, edge direction/weight, layers and
tour. `validation.json` records structural checks and limitations. Validation
here is stdlib structural validation; it does not claim execution of the
unavailable installed Zod validator. No official `meta.json` or
`fingerprints.json` is written: this is not an incremental-analysis baseline.
Automatic hooks are disabled.

From the `eth-btc-research` repository root, build and check with the existing
runtime (build replaces only derived files in package `.ua/`):

```powershell
.\.venv\Scripts\python.exe crypto-paper-agent/.ua/tools/build_code_graph.py
.\.venv\Scripts\python.exe crypto-paper-agent/.ua/tools/build_code_graph.py --check
.\.venv\Scripts\python.exe crypto-paper-agent/.ua/tools/test_code_graph.py
```

The read-only check compares exact scoped file membership and SHA-256, the
generator and saved graph hashes, and Git HEAD. Exit 0 means fresh, 1 means
stale, and 2 means invalid input/read/parse failure. `source-inventory.json`
stores every source hash, sizes, line counts, scope, exclusions and build-time
Git identity. Dirty and untracked files are included as current bytes: HEAD
alone does not identify this graph. Changes to unrelated wiki documents do not
invalidate the scoped code inventory. Read the manifest and current source
before using any graph relationship.

Outside scope: root `run_backtest.py`, tests, documentation, `web-preview`, raw
market data, backtest outputs, dependency environments, and Git history. Named
AST declarations are covered; lambdas, runtime-created declarations, dynamic
imports and symbol/value alias resolution are omitted. File docstrings are
source text, not reviewed claims. Root CLI entry points outside scope require
direct source inspection.
