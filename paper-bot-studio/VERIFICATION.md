# Verification — 31/10/2026

- Node24: node --test →24 tests passed,0 failed (entire standalone runtime suite).
- Independent review: three initial issues and one additional rollback issue fixed with failing-then-passing regressions; executable-side liquidity checked separately.
- Actual Binance public time, bookTicker, exchangeInfo, premiumIndex and closed-candle captures succeeded for four symbols and all three frames.
- Manually executed initial AI cycle sequentially15m→1h→4h. Three HOLD decisions recorded with evidence and source context IDs. Balances100/100/100; no paper position forced to demonstrate activity.
- Runtime restarted without resetting wallet data. Latest health verified true, error null.
- Dashboard/API/assets HTTP200; browser inspection confirms three wallets, source decisions, live quote timestamps; browser console errors0.
- Active chat heartbeat: ba-v-paper-ai-15m-1h-4h; every quarter-hour; checks1h/4h only when due. Automation create returned ACTIVE and view displayed its card. First scheduled run has not yet been observed; manual flow is verified.
- Monitoring continues without dependence on the browser tab. Computer, Codex app, network and available model usage are required. No Windows login startup task installed.
- Paper model has1x notional cap and assumed fees/slippage; no full market-impact/liquidation model. Public aggregate-trade history beyond available window blocks for review.

## Superseding verification —1 November2026
- Cumulative per-trade policy deployed with immutable older trade levels verified; mandatory entries retain per-trade booked-balance1x check, uncapped aggregate virtual exposure, no margin reservation/liquidation. Earlier31October one-position/HOLD and portfolio1x statements above describe the old policy only.
- Core28 tests passed including multi-position rollback, funding idempotence and slow-poll queue regression; independent review completed. Live second15m trade accepted with aggregate risk above5%; original trade fields preserved. Worker restarted once, session46805 retained, healthy.
- Added deterministic analysis-pack.mjs and cli.mjs next, source snapshots preserved with SHA256. Full32-test suite passed. Subsequent targeted4-test regression passed after correcting UNVERIFIED items to retain levels and exclude them from TP/SL-only reviews. Independent focused review completed.
- Actual source108213 bytes versus initial compact11008 bytes (89.83% smaller); not a tokenizer measurement and not a promised daily usage saving. Pack retains40 closed candles each for4 symbols plus exact quote/filter/premium.
- Live CLI next smoke: NO_DUE_CYCLES, worker healthy, no order mutation. Automation remains ACTIVE, notification_policy=failed_runs_only, quarter-hour cadence preserved; prompt uses compact tool. Current chat selector visually verified GPT-6.1 Sol Medium; no unsupported per-heartbeat/per-tool model override or global setting edit.

## Latest user clarification — initial margin allocation1 November2026
- Supersedes SL-loss3–5% interpretation: each new entry allocates3–5% booked balance as initial margin, then BTC15/HYPE5/SOL7/ETH10 leverage. PnL/fees/funding use actual qty once. Entry fee is separate; actual rounded allocation remains3–5%; qty/min-notional gates unchanged.
- New schema allocationPct required; legacy riskPct/riskBudgetPct proposals rejected. New trades record leverage,initialMargin,allocationRequested,allocationPct; plannedLoss and actual riskPct remain descriptive SL loss.
-34 full-suite tests passed, including per-symbol leverage arithmetic, stop-independent sizing, lot rounding bounds and impossible BTC lot at100 USD. Focused independent review found no important issues.
- Worker restarted in retained session92309. Live API healthy:true, error:null, exact leverage map and allocation policy verified. All preexisting trade entry/qty/SL/TP/notional/plannedLoss/riskPct fields matched pre-restart values. Ledger backup saved under data/backups/before-margin-leverage-*.json; no live/testnet orders.
- Dashboard labels split initial margin from SL risk, show per-symbol/per-trade leverage; old trades display old policy. Automation prompt updated to exact latest interpretation, ACTIVE with failed_runs_only notifications. This remains a virtual ledger without aggregate margin reservation/liquidation.

## Active TP/SL management — owner approval1 November2026
- Owner permits prospective TP/SL changes and full early exits, including legacy OPEN trades; entry/qty/original source reasons remain unchanged. New manageTrade and authenticated /api/manage + CLI manage support UPDATE_LEVELS/CLOSE with stable idempotent managementId.
- Fresh quote-time replay and funding reconciliation precede edits; earlier TP/SL triggers are committed as preempted. Incomplete/stale/history/funding/close-side-liquidity failures reject management. Level audit has effective event time, prior/new levels and reason; replay selects historically applicable levels instead of retroactive new stops. Trailing stops may cross entry.
- EARLY_EXIT settles executable bid/ask with assumed slippage and fees once; included in metrics, CLI review and late funding reconciliation. currentPlannedLoss reflects changed stop, original risk baseline preserved. No partial exits.
-41 full-suite tests passed including management idempotence, old-trigger priority, audit, temporal replay, long/short early exit, rollback, persistence, closed review and funding. Independent focused review found no important issues. Dashboard script syntax passed; live HTTP serves management audit, concise3–5 reason list and EARLY_EXIT filter.
- Worker retained session2450, live API healthy:true/error:null, positionManagement=AI_UPDATE_LEVELS_OR_EARLY_EXIT. Backup before-active-management-*.json saved; existing trade levels/qty unchanged merely by deployment. New behavior is discretionary on bot analysis cycles, not continuous10-second AI.
- Existing automation updated and ACTIVE; quiet failed_runs_only retained. Entry notes3–5 concise numbered reasons; paper race compares net equity at same observation time.
