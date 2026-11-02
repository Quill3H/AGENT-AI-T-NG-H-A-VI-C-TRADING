# Gemini cloud paper runner

Owner selected GitHub Actions with Gemini API free tier on 2026-11-02.
Base: e9cb2ef4d66cb71b410174e521649a3e9d3dcf52.

## Design and implementation plan
- Preserve the original local runtime and ledger. Vendor only source/tests/assets into paper-bot-studio.
- Reuse createRuntime, aggregate-trade replay, funding, management and packContext. No approximate 1m liquidation model.
- Require an explicitly migrated state.json; never initialize replacement wallets silently.
- Use Gemini generateContent with explicit model/key. No provider fallback, billing upgrade or automatic model substitution. The key's project must be Free tier; code cannot establish billing status from a key.
- Run sequential 15m/1h/4h, review verified closed trades, manage positions, recapture context, submit one decision per due cycle. Never replay missed entry cycles.
- Store model identity with decisions; API/schema/replay errors fail the run.
- State lives on a dedicated paper-state branch, with one workflow writer. Only state.json is staged, never auth-token or worker.lock. Local heartbeat must be stopped at cutover to prevent two divergent writers.
- [ ] Write and run failing integration tests for missing state, missing key, structured output and provider errors.
- [ ] Implement runner and run copied runtime tests.
- [ ] Independent review before publishing/activation.
- [ ] Owner supplies GEMINI_API_KEY through GitHub Secrets and confirms Free tier; perform one manual cloud run before enabling schedule.

## Audit of prior script
The main script calls nonexistent CLI snapshot/apply; real CLI uses context/submit. It never invokes its catch-up or lesson helper, sends initial capital instead of actual wallet balance, and advances watermarks after failed CLI calls. It defaults to gpt-4o while claiming SOL 6.1. No workflow/runtime source exists in the checked remote tree. GitHub Models retired July 30, 2026.

## Limits
GitHub schedule can be late or dropped. Existing runtime rejects entries over 10 minutes after a candle boundary and replay beyond 47 hours. Do not loosen these guards to make cron appear successful. Lessons are prospective observations, not proof of improvement. No exchange orders or trading credentials.
