# Project Graphify snapshot

Built against integrated main `ee3a9537cf3382ba35468b5c15772f0e70e6c1d7`.
Open `graph.html` for the community overview; `graph.json` contains full node
details. `GRAPH_REPORT.md` records community cohesion, hubs and questions.

All 18 semantic batches were fully read and checked against line inventories
and SHA256. Local AST extraction used Graphify 0.9.97. Host-agent token usage
was unavailable; it is not reported as zero. No source was uploaded to an
external LLM provider. Machine caches/interpreter paths are ignored by Git.

Important limits: 2,493 unresolved-endpoint relationships are quarantined in
`unresolved-edges.json`; they were not invented or silently treated as valid.
The navigation graph is an undirected projection. `extraction.json` retains
typed directional relationships and `health.json` reports collapsed parallel
edges/self-loops. The DOCX converter omits 37 OMML equations; converted text
coverage does not assert mathematical or visual fidelity. Read originals for
those formulas. Historical author acceptance and synthetic performance claims
remain source claims, not present economic acceptance.

From the repository root:

```powershell
graphify query "PaperBroker funding recovery" --budget 1500
graphify explain "PaperBroker"
graphify update .
```

After source changes, use the installed Graphify skill to refresh semantic
documents as well as code; a code-only update does not establish fresh document
coverage. `source-manifest.json` records exact input hashes. `cost.json` discloses
unknown semantic token usage. Benchmark estimates are structural query-size
comparisons, not measured billing savings.

`integration-evidence/` contains fresh full-core and independent cache/RL
checks: 1,435 passed/6 skipped/5 network deselected; reviewer31 passed/2 skipped.
Real PPO training and full PPO quickstart were not run. Older alternative UI,
task-installation helpers and superseded branches remain explicitly classified
in the branch audit; this is not a claim that every old branch was merged by
ancestry. No OS task, market download, account reset or economic acceptance was
performed.
