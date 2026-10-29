# Research Wiki Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or subagent-driven-development task by task. Design approved by owner in this chat 2026-10-29; proceed through implementation and independent review.

**Goal:** Evidence-linked strategy research and reliable cross-chat continuation.
**Architecture:** Offline Markdown wiki, stdlib validation CLI, two derived Understand Anything graphs.
**Tech Stack:** Python stdlib/pytest; installed Understand Anything tooling.
**Spec:** ../specs/2026-10-29-research-wiki-design.md

## Global Constraints
- Preserve sources/ and all pre-existing dirty trading files.
- Use local existing Python; no credentials, live/testnet, paid services or background hooks.
- Graph is derived, not evidence; stale graphs never override source.
- No commit/push until branch integration policy is resolved; deliver local reviewable files.

## Review Focus
- Windows path escape, junctions, source changes, malformed metadata, dirty handoff identity.
- Historical reported results must not become current verified evidence.
- Graph adapter must work against real installed parser, preserve explicit versus inferred relations.
- Tests must use separate fixture roots, not modify real sources.
- Preserve unrelated uncommitted files exactly.

## Task 1: Offline CLI
Files: scripts/research_wiki.py, tests/test_research_wiki.py.
Interface: --root <knowledge> --repo <repo> [--json] {status,lint,search,check-sources,handoff-check}; search takes query. Read-only stdout, exit 0 clean, 1 findings, 2 invalid input.
Metadata: <!-- wiki-meta {JSON} --> at beginning of each content page; fields id/type/title/updated_at/source_ids/verification/page_ids. Manifest {sources:[{id,path,sha256,locator}]} paths relative repo. Handoff metadata includes git_head, git_status_sha256 (SHA256 of git status --porcelain=v1 --untracked-files=no bytes), git_branch; untracked names recorded separately and reviewed by humans.
- [x] Write failing meaningful fixture tests for schema, source staleness/transitive dependencies, links/index coverage, cycle/unknown references, literal search, traversal/symlink, UTF8, Git mismatch, malformed CLI input.
- [x] Run RED using ../.venv/Scripts/python.exe -m pytest tests/test_research_wiki.py -q.
- [x] Implement minimal stdlib CLI and run GREEN; no writes from CLI.

## Task 2: Seed and operator contract
Files: knowledge/**, repo AGENTS.md append, package README.md append.
Consumes Task 1 schema. Produces 12–20 sourced content pages, templates, index/log, source manifest and latest handoff.
- [x] Read each selected source and capture SHA, HEAD/dirty evidence and section locators.
- [x] Write Vietnamese strategy/concept/experiment/project pages; distinguish retrospective/author-reported/dirty states and unknown fields.
- [x] Add ingestion/query/lint/handoff contract and actual examples; no automatic updates promised.
- [x] Run CLI on real wiki; reconcile all IDs, sources and links.

## Task 3: Understand Anything integration
Files: knowledge/.ua/**, package .ua/** and graph adapter only if required.
- [x] Test installed parse-knowledge-base.py on fixture; adjust metadata adapter without duplicate authorities.
- [x] Run parser, article analysis and merge per skill; validate endpoints and provenance.
- [x] Build code graph via installed understand pipeline where available; preserve partial evidence and report any dependency restriction. Do not write plugin installation outside workspace.
- [x] Validate freshness via input hashes; dashboard per installed skill after graph validation.

## Task 4: Verification and independent review
- [x] Run targeted tests, CLI real walkthrough, parser/graph checks and full offline suite (logs outside source).
- [x] Independent tester/content reviewer reviews new owned files only, reports exact commands and findings; fix important issues and rerun affected checks.
- [x] Update handoff/report with evidence, limitations, next-step instructions and no gate acceptance.
- [x] Check pre-existing dirty files retained; deliver local result and entrypoint.

## Execution ledger
Ruling: Continue authorized implementation without another approval round; owner approved full design and requested building.
Ruling: Additive owned files in current feature checkout avoid copying unrelated dirty strategy work; no stage/commit/push. Native execution with independent task support and final review as required by skill.

Task 1: complete — CLI44pass2skip; Tasks2/3: local wiki and graphs built. Task4: focused58pass2skip, regression775pass6skip5deselected; independent final defect recheck recorded in review report.
Ruling: Full Understand code pipeline unavailable (unbuilt installed core); use labelled partial AST graph. External dashboard viewer blocked by automatic approval review; local graphs delivered and no remote-code bypass. No commit/push due preserved dirty checkout and integration policy.
