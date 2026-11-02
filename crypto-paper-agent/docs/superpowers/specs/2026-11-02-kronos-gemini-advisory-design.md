# Kronos forecasts for the three deployed Gemini paper bots

Status: Owner approved in chat on 2026-11-02. Implementation and deployment evidence are separate.
Observed source: main df07280de7dc5fb19c334d17a4d356ed102902e4.
Target: https://paper-studio-connectivity.onrender.com/ .

## Owner-selected behavior

Kronos supplies forecasts to the existing Gemini 15m, 1h and 4h bots.
There is no fourth bot or new wallet. Preserve the current OKX ledger,
balances, positions, fee/funding rules, leverage and admission checks.
Gemini retains responsibility for entry and position-management decisions.

## Approaches

The owner selected assistance to all three Gemini bots rather than a fourth
independent Kronos wallet. For hosting, run CPU inference on the scheduled
GitHub Actions runner, keeping the current Node.js Render runtime. This
avoids requiring Python/PyTorch and weight loading inside the existing
Render process. Local-machine inference would require the owner's PC to
remain running and is unsuitable for the deployed scheduled bots.

## Proposed implementation choices

1. Add an authenticated, read-only Render endpoint that captures confirmed
   OKX candles for due frames using the existing market adapter. It must
   not create ledger contexts, trade, manage positions or write account state.
   Reuse the existing request/response authentication and fixed symbol list.
2. Actions loads pinned Kronos-small and its matching tokenizer, using the
   already installed and tested revisions. Cache downloads; record exact
   model/source revisions and artifact SHA-256 hashes. Do not use a moving
   upstream branch or download code implicitly from a model repository.
3. For each due frame and symbol, predict the next four candles from the
   last 40 confirmed input candles, matching the data visible to Gemini.
   Use CPU, fixed seed, T=1, top_p=0.9 and sample_count=3. These are initial
   engineering defaults, not economically validated strategy parameters.
   Use actual quote volume for amount when supplied by OKX; otherwise
   disclose omission rather than manufacture turnover.
4. Bind every forecast to venue, symbol, timeframe, input-candle SHA-256,
   cutoff, target times, model identity and generated-at time. Render
   compares this identity with the actual Gemini context, rejects stale,
   missing, malformed, non-finite or mismatched forecasts, and makes no
   new entry for the affected frame. Existing-position replay and settlement
   must still run. Forecasts cannot renew the context's expiry window.
5. Include the validated forecast in Gemini's context, explicitly as a
   model scenario without calibrated confidence or guaranteed direction.
   Gemini may disagree with it. It does not bypass any runtime gate.
6. Persist forecast evidence with context/decision artifacts and show
   whether Kronos was available in the dashboard's decision detail.
   Keep the three wallet identities and account schema unchanged.

## Validation and rollout

First test in isolated synthetic ledgers, never reset or transplant the
authoritative paper-state-okx branch. Tests must cover all three frames,
future/provisional/gapped candles, tampered or stale forecasts, mismatched
input hashes, model failures, existing-position reconciliation during
forecast failure, duplicate cycle/restart handling and authenticated cloud
transport. Run real pinned-model CPU inference on saved sample input.

Separate Tester and Independent Reviewer verdicts are required by the
repository instructions before acceptance. Only then deploy the matching
Render code and Actions workflow, run one bounded cloud cycle and verify
the committed ledger/dashboard evidence before enabling recurring use.
No billing upgrade, new service subscription or live/testnet order is in scope.

## Limits

The current cloud product is a virtual signal ledger, not the separate
Python PaperBroker simulator. Its disclosed margin/liquidation limitations
remain. Kronos installation and a successful forecast do not establish
forecast skill, profitability or economic acceptance. Pretrained historical
training coverage is not independently established; retrospective results
must not be called clean out-of-sample evidence on that basis alone.
