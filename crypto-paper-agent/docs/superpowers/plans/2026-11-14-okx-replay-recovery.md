# OKX dense native replay recovery

Base: 9f7473cc9e5fc16933ac2f52671f16eca0e504e1. Scope: paper-bot-studio/okx-market.mjs and its replay tests; incident report. No strategy, risk, ledger reset, exchange orders, provider substitution or paid services.

Observed Actions run 43592442015 fails before Gemini: the open BTC 15m trade at replayTime 1794174899999 exceeds 128 history-trades pages. Public API probes confirm correct backward pagination but hundreds of trades within milliseconds near the end of the requested minute.

1. Reproduce dense-minute page exhaustion with deterministic native trade fixtures.
2. Adaptively shorten the requested prefix while retaining the total 128-page bound and shared deadline. Discard unproven suffixes on restart; return only a fully covered chronological prefix. A one-millisecond overload still fails closed.
3. Verify exact TP/SL ordering, equal-timestamp boundaries, subsequent replay and no-progress failure. Run workflow offline checks and Kronos validation.
4. Replay the actual historical position read-only against a copied ledger; independent review before proposed publication. Keep remote ledger authoritative.

Affected callers: server.mjs tick/manage, gemini-paper.mjs catch-up loop, render-service.mjs. Their partial-progress contract remains unchanged.

## Authorized deployment and bounded optimization

Owner approved GitHub/Render deployment and useful optimizations on 2026-11-14. PR #20 merged as f82f560; that SHA is live on Render. Optimize only unnecessary Kronos bootstrap when the same existing due-frame predicate is empty: move ledger read/preflight ahead of pip/source/model cache, preserve Python validation, always run recovery and persist signed partial outcomes. Use one shared selector and recheck during preparation. If a frame becomes due after a skipped bootstrap, it waits for a later scheduled run rather than receiving an unvalidated forecast. Do not infer inevitable failure from a stale blocked/healthy flag. Separate review/test evidence required.
