# Repository map and safety boundaries

**Snapshot reviewed:** `main` at `ea375c35cd4093efc2093bae05d1786602c494e1` (tree `cf1c3dd673ff97489061c5ec1f712abc26b79c62`). This is a map of the tracked repository at that commit, not a claim that every source file, runtime deployment, or trading invariant has received a full independent audit.

## Purpose and evidence boundary

This repository contains multiple paper/research applications and their evidence. Public exchange market data is used in simulations and paper workflows. A passing test, successful API call, or paper result does not establish a valid market backtest, prospective operating reliability, or profitability. The 2026-10-30 repair report explicitly corrected earlier synthesized results as synthetic and loss-making; do not repeat older claims as market validation.

The governing project boundary is paper/research only. No real-money or testnet order submission, exchange trading credentials, private-key operations, wallet signing, or withdrawals are authorized by the committed project instructions. Any future change to that boundary requires a separate explicit owner authorization and plan.

## Repository map

```text
/
├── .github/workflows/                 # two distinct operational workflows; see below
├── .agents/teamwork/                  # retained agent/task artifacts, not application code
├── Initial idea/                       # founding specification and current vision
├── Project spec/                       # master spec, current status, roadmap, evidence register
├── crypto-paper-agent/                 # Python research and local paper application
│   ├── src/                            # data, features, strategies, risk, execution,
│   │                                   # research, paper runtime, logging and reports
│   ├── tests/                          # pytest suite; some tests skip or require network/data
│   ├── config/                         # default, strategy, and experiment configurations
│   ├── scripts/                        # Python research, reproduction, and operator commands
│   ├── data/                           # tracked fixtures such as news calendar; local datasets
│   ├── docs/                            # ADRs, planning, operations, research, reviews/evidence
│   ├─��� knowledge/                       # source-manifested research wiki and handoffs
│   ├── web-preview/                     # separate Vite frontend for Python local-paper runtime
│   ├── BÁO CÁO TÓM TẮT/                 # historical implementation reports
│   ├── run_backtest.py                  # Python backtest entry point
│   ├── requirements*.txt                # current dependency files; not yet consolidated
│   └── PROJECT_STATE.md                 # living project checkpoint, read with handoff/spec
├── paper-bot-studio/                   # separate Node.js simulated-account service/dashboard
├── scripts/                            # cloud/Gemini/Kronos/OKX integration used with Studio
├── docs/superpowers/                   # root-level implementation plans
├── graphify-out/                       # derived graph and committed graph/evidence outputs
├── README.md                           # repository landing page
├── AGENTS.md                           # agent workflow and safety instructions
├── PLANNER_HANDOVER.md                 # handoff/history; reconcile with live Git state
├── CLOUD_SETUP.md                      # cloud setup notes; parts are historical/stale
├── CLOUD_VERIFICATION_2026_11_02.md    # dated cloud verification record, not current runtime proof
└── OKX_DATA_CHECK_2026_11_02.md        # dated OKX data diagnostic
```

### Applications and entry points

| Area | Role | Key entry points / references |
| --- | --- | --- |
| Python research/backtest | Offline research, public-data ingestion, strategies, risk checks, simulated broker, reports, research tools | `crypto-paper-agent/README.md`, `crypto-paper-agent/run_backtest.py`, `crypto-paper-agent/scripts/` |
| Python local paper runtime | Explicitly started, loopback-only paper session; public Binance USD-M feed and simulated broker/account | `crypto-paper-agent/scripts/run_local_paper_web.py`, `crypto-paper-agent/src/paper/local_server.py`, `crypto-paper-agent/src/paper/live_session.py`, `crypto-paper-agent/docs/operations/LOCAL_PAPER_RUNTIME.md` |
| Python web preview | Vite UI for the local paper runtime; separate from cloud/Studio UI | `crypto-paper-agent/web-preview/`; build instructions are in the local runtime guide |
| Paper Bot Studio | Separate Node service with three simulated paper accounts, public-market adapters, dashboard and local ledger | `paper-bot-studio/README.md`, `paper-bot-studio/server.mjs`, `paper-bot-studio/engine.mjs` |
| Cloud/AI integration | Gemini paper-analysis cycle, signed transport, Render service and OKX/Kronos helpers | `scripts/gemini-paper.mjs`, `scripts/render-service.mjs`, `scripts/cloud-transport.mjs`, `scripts/kronos-advisory.mjs`, `.github/workflows/paper-bot-studio.yml` |

Do not treat these as one deployable application or combine their dependencies without a separately tested packaging plan. In particular, root `scripts/` is not the Python research script directory; the latter is `crypto-paper-agent/scripts/`.

## Safety boundaries verified in the reviewed paths

### Python local paper runtime

- `public_stream.py` constructs a public Binance USD-M WebSocket URL and validates symbols, intervals, event timing and candle geometry. The stream class documents that the session owns decisions and gates.
- `live_session.py` uses a fixed public base URL and allowlists only `/fapi/v1/time`, `/fapi/v1/klines`, and `/fapi/v1/fundingRate`; market processing is passed to the simulated `PaperBroker`.
- The local HTTP server binds to `127.0.0.1`, restricts host/origin and exposes explicit paper control routes. The operations guide says the session starts only after an explicit request; the chart does not start an account.
- Recovery, journal ownership, risk admission, and data-freshness checks are part of the implementation. This source inspection is not an independent proof that every path preserves every invariant.

### Paper Bot Studio and cloud integration

- `paper-bot-studio/market.mjs` uses public Binance REST endpoints for quotes, rules, candles, aggregate trades and funding. `server.mjs` binds its runtime to loopback, uses a local bearer token for control routes, serializes state changes, and writes a local simulated ledger.
- Root `scripts/gemini-paper.mjs` requires a Gemini API key/model for AI inference and sends decisions through the Studio paper runtime; that Gemini credential is not an exchange trading credential. The cloud transport signs requests and does not transmit the raw key as the transport authenticator, according to `CLOUD_SETUP.md`.
- The scheduled workflow `.github/workflows/paper-bot-studio.yml` is materially different from CI: it has a five-minute schedule and manual dispatch, checks out the separate `paper-state-okx` branch, runs the paper cycle, and has `contents: write` so it can commit/push paper ledger and evidence files to that state branch. Treat it as a state-mutating operational workflow, not a test workflow. Its write permission is a real repository-level security boundary and should be reviewed before changing triggers, checkout targets, or permissions.
- `.github/workflows/gemini-api-check.yml` is manual-dispatch only and uses `GEMINI_API_KEY`; its validation path uses an isolated `cloud-validation` data directory. It is not a PR-safe, secret-free CI job.
- Neither workflow, by itself, proves current provider connectivity, successful scheduled operation, persistent hosting, or economic validity. A runtime/deployment claim needs dated operational evidence.

### Secret and artifact handling

- The root `.gitignore` excludes environment files and selected local runtime/data paths. `crypto-paper-agent/.gitignore` excludes common caches, datasets, reports and databases. Ignore rules reduce accidental inclusion risk but are not a secret scan and do not remove files already tracked.
- The Python local account/journal and Studio ledgers are runtime state, not source fixtures. Do not copy, reset, publish, or move them as part of a documentation or CI change.
- `graphify-out/` and `.ua/` are derived navigation/audit artifacts. Their own manifests and freshness evidence are needed before relying on them; a graph is not a runtime call graph or safety proof.

## Which document is authoritative?

Use the source order in `AGENTS.md` and `crypto-paper-agent/docs/planning/PRODUCT_CHARTER_AND_GATE_SPEC.md`: current owner authorization and approved ADRs govern behavior; `PROJECT_STATE.md`, `PLANNER_HANDOVER.md`, and the dated handoff/review explain checkpoints and evidence. Pin the commit when making a claim. Keep author reports, independent tester results, independent review, and owner acceptance distinct.

The root README is the general navigation page. `Project spec/README.md` maps product/spec/evidence documents. `crypto-paper-agent/README.md` maps the Python application. `paper-bot-studio/README.md` maps Studio. This file complements those maps; it does not replace them or override a more recent owner decision.

## Documentation discrepancies to resolve

1. `CLOUD_SETUP.md` labels the cloud candidate “NOT DEPLOYED” and describes adding a schedule only after acceptance, while the committed `paper-bot-studio.yml` currently contains a cron schedule. The workflow file proves the schedule is configured in Git; it does not prove a successful live deployment or accepted operation. Reconcile this wording against the latest merged operational evidence before changing the workflow.
2. `CLOUD_VERIFICATION_2026_11_02.md` is explicitly dated and says “DRAFT, NOT ACCEPTED FOR CUTOVER”; do not use that historical status as proof of the current deployment state.
3. `PLANNER_HANDOVER.md` includes extensive historical instructions and checkpoints. Some are marked superseded; always use its top checkpoint and compare with the current tree rather than applying stale stage restrictions literally.
4. Open PRs are not part of this pinned `main` snapshot. In particular, use merged files only when describing the current repo; do not silently treat draft PR content as current documentation or authorization.

## Scope and limitations of this review

The tracked-tree inventory was enumerated at the pinned commit. I reviewed the root navigation and agent rules, Python project state/charter/operations, dependency manifests, the two workflow definitions, cloud status notes, and selected safety-critical Python/Node entry points listed above. I did **not** read every line of every tracked file, run the test suites, inspect a deployed service or owner machine, perform a complete credential/secret scan, or independently audit every order-like code path. Therefore this map is a source-grounded orientation and scoped boundary check—not a full security audit, production certification, gate verdict, or economic validation.

Before adding CI or changing dependencies, separately verify a clean checkout install and test command per application. Keep ordinary PR CI offline, without Gemini secrets or ledger writes; keep scheduled paper-state mutation in its own explicitly reviewed workflow.
