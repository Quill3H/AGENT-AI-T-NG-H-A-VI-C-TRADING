# Crypto Futures Paper Agent: Product Charter and Gate Specification

Status: Product direction frozen for planning, 2026-09-22. Entries explicitly
marked `PENDING` or `PROPOSED` still require an owner decision. This document is
not an acceptance report or an amendment to approved risk ADRs.
The owner decides product choices and acceptance. The Technical Lead implements;
Tester produces independent test evidence; Independent Reviewer gives the gate
verdict; PM coordinates and preserves the decision trail.

## 1. Source of truth and original intent

Read in this order at the start of any new project task:

1. This charter for product intent and unresolved decisions.
2. `PROJECT_STATE.md` and repository-root `PLANNER_HANDOVER.md` for the latest
   factual checkpoint. Pin their Git commit, not a moving branch name.
3. Approved ADRs in `docs/decisions/` for binding implementation/risk policy.
4. `Project spec/CRYPTO_PAPER_TRADING_AGENT_MASTER_SPEC.md` for the technical
   baseline, then `Initial idea/AGENT_SPEC.docx` for the founding vision.
5. The exact gate plan, code/tests, manifests and independent review report for
   the work being considered. Conversation memory and author summaries do not
   replace these artifacts.

If these disagree: the owner's latest explicit decision governs scope; an
approved ADR governs technical/risk behavior until changed by a separately
reviewed decision. The master spec fills remaining detail. The initial idea is
the intent to preserve, not automatic authorization to loosen risk or to claim
profitability. Record a conflict rather than silently choosing a convenient
reading.

The original `Initial idea/AGENT_SPEC.docx` (SHA-256
`7CCC263EEEEE1118E967F3508F6659BE9E7E47A42FEDAA6A4367D5FB544BD1CA`)
describes a perception-decision-action paper agent for crypto perpetuals. Its
four explicit rulebooks are Trend Following, Breakout & Retest, SMC Liquidity
Sweep and spot/perpetual Funding Arbitrage. It calls for multi-timeframe OHLCV,
OI, funding and CVD where actually available; mandatory stops, sizing,
liquidation distance, low leverage and breakers; a journal; and optional
reinforcement learning that rewards net results while penalizing drawdown and
rule violations. The document states an aspiration of positive expectancy
with maximum drawdown under 10%. Its illustrative win rates, APR and trader
anecdotes are hypotheses, not verified strategy performance or approved risk
budgets. Some inputs such as DOM/footprint/heatmaps may not be available in
public historical data; absence must be disclosed rather than invented.

The currently agreed benchmark window remains 2021-01-01 through 2026-09-01
UTC. Do not silently extend or rewrite it when adding a near-current holdout.
Software correctness and reproducibility do not require profitable outcomes.

Trace the founding ideas without promoting them to evidence:

| Original idea | Current interpretation | Authority / evidence status |
| --- | --- | --- |
| Four rulebooks, market state and journal | Keep each rulebook explainable and compare separately; choose a primary candidate only by owner decision | Original idea, master spec and ADR 0008-0012; implementation pending independent review |
| Mark price, last price, OI/CVD/funding | Preserve source and availability time; use an executable price/cost model for fills | Master spec data/execution sections and ADR 0007/0011; historical fidelity depends on source coverage |
| Exchange-hosted protective stop | Simulated protective stop in paper broker, never an exchange order in current scope | Original mechanism superseded by paper-only decision |
| Always-on macro-news blackout | Disabled by default; if explicitly enabled, missing/bad calendar fails closed | Later PROJECT_STATE/ADR policy supersedes original default |
| PPO reward and learning | PPO implementation allowed, but economic learning/generalization unverified | ADR 0010 and independent evidence gates |
| Illustrative win rates, gross funding APR, trader examples, 10% ultra-high conviction | Research hypotheses/anecdotes, not target performance or sizing permission | Not verified; binding risk policy stays in approved ADRs |

## 2. Product boundary and learning contract

The current product is local research, historical backtesting and prospective
paper trading on public market data. "Live" means data received as the market
runs with simulated orders and simulated account state. There is no real or
testnet order submission, trading credential, private key, wallet signing,
paid feed/cloud, or real-money deployment in the current authorization.

The four rulebooks are explicit prior trading knowledge, not models trained
from outcomes. PPO may learn a policy within the paper broker's immutable risk
and execution envelope; it may not learn to bypass stops, breakers, margin,
funding provenance or logging. Do not describe a short training smoke as
learning a profitable method. A selected strategy or policy must carry a
versioned rulebook/config/model/scaler identity and an explanation of what was
fixed by humans versus fitted on training data.

Each research iteration has a one-way lifecycle:

`raw public data -> integrity gate -> rulebook/train -> chronological validation
-> freeze candidate -> untouched historical OOS -> near-current closed-bar
replay -> prospective live-data paper session -> locked report -> new iteration`.

No online learning or parameter/risk changes during a scored holdout or paper
session. An emergency risk stop may end the session, but a changed strategy,
model, cost assumption or data repair creates a new version and a new
evaluation. Record all attempted candidates, including failures; never select
only the best-looking result after opening the final holdout.

## 3. Causal chronology

An old year is a valid out-of-sample test only when the model and all selected
parameters were fixed using information available *before* that year. Training
on 2024-2026 and then scoring 2021 as if it were a contemporaneous decision is
a retrospective diagnostic, not causal OOS. A separate rerun of the historical
2021-2023 benchmark can establish software reproducibility even if that period
was used for development; label it accordingly, not as untouched validation.

Planner must pre-register half-open UTC train/validation/test boundaries and
the warm-up/position-at-boundary policy. Walk-forward folds may test old and
new regimes with train-only fitting per fold; each fitted model has its own
hash. If pre-2021 data is unavailable, do not claim a 2021 OOS year for a model
trained from 2021 onward. The final holdout after 2026-09-01 ends at the last
fully closed, actually available candle for each timeframe. Its cutoff and
source manifest must be frozen before results are inspected. Closed-bar replay
collected today is not a prospective paper session.

Every dataset manifest records venue, spot/perpetual instrument, symbol,
timeframe, UTC coverage, event/availability/collection times, last closed
bar, raw URL and SHA-256, normalized SHA-256, source version, gaps, duplicates,
revisions and transformation policy. Spot must not be substituted with perp.
Funding settlements require an exact unique source event; mark/index prices
must not masquerade as executable quotes. Preserve input snapshots and bounded
download/retry/resource budgets from the gate-specific plan.

G2 must publish *per-strategy, per-year and per-regime* usable coverage before
G3 freezes a candidate. Trend needs causal 4h/15m closed bars and a disclosed
OI-missing bypass rate under ADR 0005. Breakout needs complete volume history
for its baseline and delayed retest. SMC needs 5m/1m bars, confirmed swing
timing and honest taker/CVD availability; public bars alone cannot reconstruct
DOM, queue position or actual intrabar limit fills. Funding baskets need
synchronized spot/perp legs and a distinct source event at every settlement;
an 8h rate sample is not an independent completed basket. PPO needs the same
causal features and missingness masks in train and holdout, without refitting
the scaler. If any required source is unavailable, mark that fidelity level
or interval `NOT_VERIFIED`/`DATASET_UNAVAILABLE` rather than fabricate it.

## 4. Roadmap and gates

| Gate | Deliverable | Independent exit evidence | Failure route |
| --- | --- | --- | --- |
| G0 Correctness repair | Funding event identity and completed-position metrics, raw slice audit retained | Tester reproduces old failure and new invariant; Reviewer inspects fixed SHA and account/ledger/breaker atomicity | Fix cause on a new code SHA; no market performance claim |
| G1 Engineering replay | Full offline and historical regressions, causal LONG/SHORT/funding/partial synthetic runs, PPO save/load smoke | Commands, runtime lock, artifact hashes, exact code A/docs B, independent rerun | Distinguish implementation failure from environment block; no G2 advancement |
| G2 Functional completion and data contract | Wire reusable cached/fixture data through all strategies, PPO, broker, reports and operator workflows; add only the minimum bounded data needed for a core path to run | Clean-environment quick start, capability matrix, provenance/coverage/gap report and negative-path tests | Degrade or fail closed honestly; missing ideal coverage is not a functional blocker when an existing deterministic dataset exercises the contract |
| G3 End-to-end research workflow | Explainable rulebook baselines and bounded PPO train/evaluate/save/load, deterministic replay, CLI/operator start-stop-recovery and artifact documentation | Versioned run registry, inputs/outputs/hashes, examples for every strategy/PPO, independent usability and correctness test | Report `NO_TRADES`, missing data or negative performance as diagnostic output; do not hide it or call it an implementation pass/fail by itself |
| G4 Learning improvement and historical evaluation | Expand data only after functional acceptance; causal regime analysis, chronological comparison and untouched holdout per version | Frozen candidate registry, training cutoffs, dataset/model/config identities and reviewed per-period reports | Do not tune on a scored holdout; create a new version and unused evaluation period |
| G5 Prospective paper experiment | Fixed-version public live-data feed driving simulated orders; this may be a forward learning/evaluation experiment and is not a profitability claim | Raw feed/events, decision/receipt/fill clocks, daily ledger reconciliation, faults/kill-switch logs and independent report | Quarantine stale/disconnected data and stop admission; restart a new labeled session if version changes |
| G6 Future product choice | Owner may consider manual signal assistance or separately authorized real-money automation | New scope, security/operational/legal/risk plan and explicit owner approval | No real order endpoint or credential added under this charter |

G0/G1 author handoff currently concerns code A
`2c9a4d0985fc9eafd29386482793425c26d47835` and docs B
`b174f544462d45bacec3e6b27a1409ca4fc32325`; these SHAs are a review
target, not a passed gate. G2-G5 are plans, not completed work. The existing
G0-G4 market plan remains a technical input, but this charter changes its
product priority: complete and document the usable end-to-end bot first;
large data expansion and economic optimization are a later backlog.
Before each later subsystem starts, the Technical Lead writes a separate
task-sized implementation plan with exact file ownership, interfaces, tests,
resource budget and stopping rule. PM does not turn this roadmap into one
unreviewable code change.

## 5. Evaluation and promotion policy

`TECHNICALLY COMPLETE / RESEARCH-READY` means the system can ingest and check
causal market data, run explicit strategies or a learned policy, apply all
hard risk admission, simulate execution/funding/accounting, train and
save/load a versioned policy, replay it end-to-end and produce reproducible
reports with documented operation and fail-closed behavior. It does not mean
profitable. `ECONOMICALLY VALIDATED` is a later finding that a frozen candidate
met an owner-approved effectiveness protocol across historical and prospective
paper evidence. Passing one milestone never implies the next.

Numeric performance thresholds, a statistically ideal dataset and selection
of an optimal primary strategy are not prerequisites for building and
accepting the complete functional research pipeline. Existing caches,
fixtures and recorded artifacts should be reused for integration, training
smokes, deterministic replay and operator examples when they exercise the
contract. `NO_TRADES`, sparse samples, missing features and negative outcomes
are valid diagnostic results; provenance, gaps and fidelity limits must remain
visible. Add public data only when a core capability cannot otherwise be run
or verified, within the approved resource budget.

Before opening final OOS, the owner must approve a versioned economic protocol:
minimum covered years/regimes and completed-position sample, net expectancy
and return after fees/spread/slippage/funding, drawdown and exposure limits,
cost sensitivity, uncertainty/CI and baseline comparisons. Report incomplete
lifecycles and SMC partial slices separately from completed trades. Funding
baskets are not directional single-position trades. Four strategies have
independent equal-capital accounts; do not sum folds into a fictional shared
portfolio. If the sparse Trend rulebook yields too few trades, the result is
inconclusive, not an invitation to lower the threshold after seeing OOS.

The initial idea's under-10% drawdown is an aspiration requiring an explicit
decision on measurement and horizon. A preliminary PO suggestion of a 20%
economic threshold is **not approved** and does not alter any binding risk,
daily breaker or leverage ADR. Likewise proposed trade counts, confidence
levels, stress factors and an eight-week paper interval remain options for
owner review. Positive backtest performance cannot guarantee future profit.

The PO offers two **unapproved** sample protocols for an owner decision made
before OOS labels are opened. A standard protocol asks for at least 60
independent completed lifecycles across two full OOS years and predefined
regimes. A sparse-aware protocol, only if pre-approved, asks for at least 24
across two full years, at least 8 in each full year, plus conservative
block-bootstrap uncertainty, leave-one-year-out and doubled-cost stress.
Neither protocol overrides data coverage, causal separation or the owner's
drawdown choice; neither may be adopted retrospectively to pass a sparse
result. The historical 16 Trend trades in 2021-2023 are author-reported and
not an untouched OOS sample. Missing sample means `INSUFFICIENT_EVIDENCE`,
not an approved economic pass. These proposals belong to the later learning
improvement/validation backlog and may not block functional completion.

## 6. Prospective paper operating contract

Observe-only public-feed collection can begin after the data contract is safe;
it produces operational/data evidence but no trade-performance score. A G5
paper session can be run as a forward learning/evaluation experiment after
the bot is research-ready and its version/session contract is frozen. Its
result contributes to later economic validation; it need not be called
economically validated before it starts and never authorizes real-money use.

For G5, receive public market events with event time, source close time,
receipt time and decision time recorded. A strategy only sees complete bars
and data available when its decision occurs; an order cannot fill before the
next eligible simulated execution opportunity plus declared latency. Record
simulated bid/ask or declared proxy, fees, spread, slippage, partial/rejected
fills, funding and margin. Publish fidelity limits when only OHLCV is present.

Stale/missing/revised/out-of-order bars, clock drift, reconnect uncertainty,
or absent settlement funding must fail closed under predeclared thresholds.
The paper breaker/kill switch, stop and force-close policy, idempotent journal
and daily account reconciliation remain in force. The session preserves a
single frozen candidate and a fixed duration if the run is scored. Online
updates are disabled during a scored session; continued learning creates a new
version/session. No trade endpoint is required for public-feed paper simulation.

## 7. Decisions, roles and context continuity

Decision register (do not convert `PROPOSED` into `CONFIRMED` without an owner
statement and a dated decision/ADR):

| ID | State | Decision / question | Source |
| --- | --- | --- | --- |
| D-01 | CONFIRMED | First live phase uses real-time market data with paper orders and no money | Owner clarification, 2026-09-22 |
| D-02 | DEFERRED | After evidence of effectiveness, owner may choose real-money automation or manual execution from bot information; neither authorized now | Owner clarification, 2026-09-22 |
| D-03 | PENDING | Which of the four rulebooks is the primary expertise and how PPO challenges it? | Original idea and PO analysis |
| D-04 | PENDING | Pre-registered economic thresholds and treatment of the original under-10% drawdown aspiration | Original idea and PO analysis |
| D-05 | PENDING | Duration, instruments, venue and sampling/fidelity requirements for prospective paper observation | PO analysis |
| D-06 | CONFIRMED | Current priority is a usable, correct and reproducible end-to-end paper/research bot with clear operation; alpha optimization and economic proof follow later | Owner direction, 2026-09-22 |

D-03 through D-05 do not block NOW functional completion, training/replay
smokes or connector testing with fixtures/recorded inputs. After the G2 data
feasibility audit and before a final scored holdout or scored prospective
session, the owner freezes the relevant candidate and economic/session
protocol. The tentative sample thresholds, eight-week interval and quarterly
offline retraining cadence are suggestions, not approved defaults.

At each gate the Technical Lead hands PM immutable A/B SHAs, branch/base,
changed-file scope, config/data/model hashes, commands, raw results and known
limits. Tester reruns on a separate checkout and owns QA evidence. Reviewer
checks code-vs-docs, probes and claims independently; PM routes findings and
tracks status but does not issue their verdict. The owner alone accepts or
authorizes merge. Label every claim `VERIFIED` (by whom and on which SHA),
`AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED`, `NOT_VERIFIED` or `BLOCKED` with the
precise cause. A passing test is not proof of strategy edge.

For every new agent/chat turn: read the source order in section 1; record
`git status`, branch, code/docs/main SHAs and dirty files; state the one gate
and exact task ownership; compare the decision register with the latest user
message; do bounded work; write a handoff containing what changed, what ran,
what failed, data/model identities and the next owner. Do not edit another
agent's worktree, rely on chat memory alone, or overwrite a prior result.
Update `PROJECT_STATE.md` only with verified checkpoint facts and link to the
relevant decision/review. Preserve superseded decisions for traceability.
When a requirement changes, first create an explicit change record: source,
old rule, new rule, rationale, affected gates/tests, approval owner and date;
then revise the gate plan and tell Tester/Reviewer before implementation.

## 8. Immediate sequence

1. Tester and Independent Reviewer finish G0/G1 evaluation on the frozen A/B;
   PM records their distinct outcomes without self-acceptance.
2. PM and Technical Lead inventory every required capability and usage path:
   clean setup; cached/fixture inputs; four strategies; PPO train/evaluate;
   paper replay; artifacts; `NO_TRADES`/missing-data behavior; start, stop,
   recovery and logs. Tester and Reviewer validate functionality and usability.
3. After the owner accepts the complete bot and its usage, create a separate
   data/model improvement roadmap for regime analysis, tuning, comparison,
   statistical/economic gates and broader/longer observations.
4. Observe-only public data and recorded/synthetic connector tests may support
   functional completion. A frozen G5 paper experiment follows the applicable
   session contract; real-money and manual-signal products remain out of scope.
