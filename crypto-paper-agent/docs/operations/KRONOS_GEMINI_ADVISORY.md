# Kronos advisory for the deployed OKX paper studio

Owner approved design on 2026-11-02: assist the existing 15m/1h/4h Gemini
wallets; no fourth wallet. The separate Python PaperBroker system is not
the deployment target. The authoritative ledger remains paper-state-okx.

## Flow

The scheduled Actions job installs pinned CPU dependencies, checks out
Kronos source 67b630e67f6a18c9e9be918d9b4337c960db1e9a and restores a model cache.
It asks Render's authenticated POST /kronos/input for due confirmed OKX
inputs. The endpoint cannot trade or write account state. Its response is
signed with the existing transport mechanism. No Gemini secret is passed
to the inference subprocess.

Python uses 40 confirmed candles, four forecast candles, three sampled
paths averaged by upstream KronosPredictor, seed123, T1 and top_p0.9.
Actual OKX quote volume supplies amount where available. Models and
tokenizer are pinned by revision and checked against the four SHA-256
values in scripts/kronos-model-manifest.json. No remote model code is run.
The cache is not an integrity authority.

Actions includes forecasts in the existing signed /run request. Render
compares every forecast's input hash, symbol set, frame, venue, cycle,
target times, model/artifact identity and finite OHLC geometry with the
actual context sent to Gemini. Forecasts have a 240-second freshness
limit and cannot extend the existing entry window or context expiry.
Freshness is rechecked after context capture, after Gemini, before each
management mutation and immediately before entry admission.

Gemini sees the scenario and may disagree. The original order/fee/funding,
allocation, leverage and admission rules remain enforced. Existing-position
replay and settlement happen before forecast checking. Missing/invalid
advisories block new entries for that frame; other valid frames can proceed.
There is no Gemini-only entry fallback.

## Evidence and operation

- Successful decision records include Kronos model/revision, input hashes
  and a contexts/kronos-<context-id>.json evidence pointer.
- Full forecasts include model file hashes, runtime versions, generation
  time and target candle timestamps. Context/decision artifacts travel in
  the existing authenticated batch and are committed with the ledger.
- state-view.json records advisory availability/errors by frame. The
  dashboard displays the current advisory status and decision attribution.
- Actions recovery artifacts additionally include .kronos/input.json and
  .kronos/forecast.json; these contain public market data and paper evidence,
  not provider credentials.
- New runtime and workflow must both be deployed. /health reports
  kronosProtocol:1. Existing wallet balances/history must never be reset
  to make the new code start.

No billing upgrade is authorized. Actions execution/download/cache use
the account's available quota and may fail; no alternative paid service
is provisioned. Cold installs can miss a cycle; a late cycle is skipped.
Always inspect the committed state and Actions outcome after failures.
Do not automatically retry an ambiguous transport or partial install.

## Verification and limits

Node cloud/engine regression tests and Python input-contract tests are
listed in the workflow. Independent Tester/Reviewer results and deployment
verification are recorded in the matching review handoff.
Local real-model inference exercised all three timeframes on synthetic
fixtures using installed PyTorch2.15.0+cpu; the deployment pins Linux
PyTorch2.5.1+cpu and must be verified on its runner separately.

The predictive scenarios are neither probabilities nor calibrated
confidence. No forecast accuracy or economic acceptance follows from
installation/tests. Pretraining data coverage is not independently proven.
Existing paper-ledger margin/liquidity/liquidation limitations still apply.
