# Functional paper-bot completion candidate — author handoff

Status: **AUTHOR_SELF_REVIEWED / PENDING SEPARATE TESTER AND INDEPENDENT REVIEWER**. Do not self-accept or merge. Engineering implementation is present; empirical validation is **PARTIAL**. This is a research paper-trading system, not production-ready software or an investment recommendation.

Code-under-test commit: `51b039b5e1b4ec0b649e9d2604a93a83f01b0a73`.
Documentation commit: see Git history and final handoff.
Branch: `codex/final-project-completion`; base `1903dc286878719c94786480481e50e99dddf26f`; `main` observed at `e970337d504563e5987a4db6b5c06c635bf7244b`.

## Scope and self-review

Stage 6 logging/identity/artifacts, Stage 7 Breakout, Stage 8 funded basket, Stage 9 causal SMC/partial lifecycle, Stage 10 four independent accounts and Stage 11 real Gymnasium/SB3 PPO were retained and exercised. New work closes operator command contracts, offline quick-start, synthetic Trend LONG/SHORT evidence, bounded public download and output collision/path checks. `AGENTS.md` and generated `.serena/`/`.gitnexus/` were excluded from A. No exchange order submission, testnet order, trading API key, private key, wallet signing or real-money path was added.

Self-review found and fixed two High regressions during work: (1) a helper accidentally nested inside the `run_backtest.py` parser made the CLI exit 0 without execution; Stage 6 integration tests caught it and the helper was moved outside `main()`. (2) the public downloader's Vietnamese console output raised `UnicodeEncodeError` under Windows cp1252; ASCII operator output and a cp1252 regression test fixed it. The existing G0 offline preparation test was updated to explicitly opt into its mocked network and use a fresh output target after the public downloader contract became fail-closed. This author review is **not** an independent verdict.

## Exact verification on frozen A

Runtime: Python 3.12.14, pytest 9.1.1, pandas 3.0.6, NumPy 2.5.3, Gymnasium 1.3.0, Stable-Baselines3 2.9.0, PyTorch 2.14.0+cpu, PyArrow 25.0.1. Execute from `crypto-paper-agent/`:

| Command | Outcome |
| --- | --- |
| `python -m pytest -p no:cacheprovider -m "not network" -q` | Detached clean A: **409 passed, 2 skipped, 5 deselected**, 2 Gymnasium warnings, 134.42 s |
| `python -m pytest -p no:cacheprovider -m network -q` | Detached clean A: **5 passed, 411 deselected**, 20.66 s |
| `python -m pytest -p no:cacheprovider docs/reviews/test_stage_04_review_05.py -q` | Working A pre-commit: **26 passed**, 3.19 s |
| `python -m pytest -p no:cacheprovider docs/reviews/test_stage_04_review_06.py -q` | Working A pre-commit: **11 passed**, 1.32 s |
| `python -m pytest -p no:cacheprovider docs/reviews/test_stage_04_review_07.py -q` | Working A pre-commit: **3 passed**, 1.08 s |
| The three historical probe files together, same command | Detached clean A: **40 passed**, 2.65 s |
| `python -m pytest -p no:cacheprovider tests/test_functional_cli_contract.py tests/test_functional_strategy_workflows.py tests/test_functional_artifact_contract.py tests/test_quickstart.py -q` | Clean A focused: **26 passed**, 42.73 s |

The two skips are optional `pandas-ta` comparisons. No test failure remains in the completed clean-A suite. An earlier full-suite attempt stopped abruptly on Windows before its summary; it was rerun in the detached clean checkout and produced the complete result above. A new standalone environment from the lockfile could not build `coincurve` because cffi exposed zero LICENSE files (`RuntimeError: Expected exactly one LICENSE file in cffi distribution, got 0`). The pinned QA Python environment was therefore used; clean dependency installation remains **BLOCKED** in that interpreter/setup and must not be called verified.

Clean A test paths use pytest temporary data, not untracked `data/raw`. Stage 6 integration exercised custom external-CWD config/cache and read JSON, Markdown, SQLite, CSV and PNG. A separate synthetic quick-start audit parsed 121 files, SQLite `integrity_check` was `ok`, and no root absolute-path leakage was found. One quick-start completed under a socket guard; a second consecutive run in the same Windows session terminated before writing `quickstart_report.json`, so cross-run byte reproducibility is **NOT_VERIFIED** and should be rerun by Tester in fresh processes.

## Datasets and observed outcomes

Synthetic fixture: Trend, Breakout and SMC each produced a LONG and SHORT completed lifecycle through real broker paths. Trend LONG/SHORT: one fill each, -2.2 USDT each. Breakout LONG/SHORT: one fill each, +388.5477/+387.4512 USDT. SMC LONG/SHORT: one fill each, +449.2124/+448.7951 USDT. These constructed prices are **functional fixtures**, not performance estimates. Synthetic PPO used train/validation/holdout 1,440 rows each, seed 42, 256 actual timesteps, save/load equal; validation -6.0922607447 USDT and holdout +99.6138437875 USDT are meaningless as alpha evidence.

Public Binance Vision sample (author-local, outside Git): 2024-01-01 00:00 through 2024-01-03 23:59 UTC; 4,320 1m perp and 4,320 1m spot rows, zero detected gaps. The full raw archive URL/ZIP/CSV hash manifest is in the local sample output. Main dataset SHA-256 identities: perp 1m `b99069942ceff4a1666a4e168beff3f51c7d3419693823afdf351622e616eef1`, basket `8677f3da2fcfc9a295cab3fcaa2da0e89dc35e57347eaa2e86f51ee9504db58f`. No parameter tuning was performed to force trades or profit. Trend/Breakout/SMC public OOS had **0 trades**; funded basket completed one at **-25.1882565593 USDT**. Public PPO used 256 actual timesteps and seed 42; holdout -477.1124610771 USDT / 60 completed trades / 1,318 invalid-or-rejected action penalties; no-trade baseline 0 and fixed MA5/20 baseline -478.7600420183 USDT. These are **AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED**, not economic validation.

Separate near-current Binance Futures public REST snapshot: 500 BTCUSDT 15m candle opens from 2026-09-17 10:30 to 2026-09-22 15:15 UTC, plus 100 funding rows from 2026-08-20 08:00 to 2026-09-22 08:00:00.004 UTC. It is a download/readability check, not a scored prospective paper session; last candle close and funding source quality must be checked before replay. No near-current simulated performance is claimed.

The canonical 2021-01-01 through 2026-09-01 historical window was **NOT RUN** here; the older 2021–2023 benchmark remains `AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`. Therefore **EMPIRICAL VALIDATION COMPLETE is false**. Longer year-by-year historical, untouched OOS, near-current closed-bar replay and then prospective paper observation remain separate future gates after owner/reviewer acceptance.

## Remaining debt and next owner

- Medium: one fresh quick-start success but second consecutive run aborted without a summary; independent fresh-process replay needed.
- Medium: standalone dependency installation fails at `coincurve`/cffi on this host; provide a clean-environment recipe or compatible wheel without relaxing pinned behavior.
- Medium: three-day public window has no directional trades and cannot establish strategy effectiveness or regime coverage; canonical historical replay is pending.
- Low: `run_backtest.py --help` still describes the old timestamp-style default run ID despite deterministic implementation.
- Low: Gymnasium checker emits two non-failing warnings (`warn` argument ignored; unregistered render modes).

Next owners: separate Tester reruns frozen code A and verifies artifacts/data hashes; separate Independent Reviewer audits causality, funding/accounting, broker risk and evidence. PM records their verdict; only the owner can accept/merge or authorize the next empirical gate.
