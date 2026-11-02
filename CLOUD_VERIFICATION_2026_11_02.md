# Cloud verification — 2026-11-02

Status: DRAFT, NOT ACCEPTED FOR CUTOVER. Local heartbeat, worker, wallets and ledger remain unchanged.

- Gemini secret exists on GitHub; model variable is gemini-3-flash-preview.
- Manual API-only probe passed on main commit 30ff761d0580de8cb0bf40acd174654b45ababa8, run 41389284512.
- Extended probe on branch codex/paper-cloud-probe commit 0675750878e8ede245c124f2f0722f884365446c: Gemini JSON inference passed, Binance public Futures clock returned HTTP451. Hosted runner reports Azure eastus. Run https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/actions/runs/41409812185 . No venue substitution, proxy or access workaround attempted.
- Offline command `node --test scripts/gemini-paper*.test.mjs paper-bot-studio/*.test.mjs`: final 55 pass, 0 fail, 0 skip.
- Separate Tester added orchestration, deadline and bounded incomplete-replay fixtures; genuine quote/funding errors fail immediately. Independent final review pending; no cutover acceptance.
- No migrated state, scheduled cloud run, dashboard publication or economic acceptance. Free-tier/billing status cannot be established by a successful API call.
- Auto-review rejected direct-main push of extended probe; safe alternative was publication on a separate branch. No default-branch integration performed for that change.

Owner reports no existing VPS. Next decision: hosting supported by the data provider, with explicit cost/card/capacity constraints. Do not move state until host connectivity, final code review, manual cycle and persistence are verified.

Owner declines card verification. Oracle signup not initiated. Render Free is a possible test host (Singapore offered), but it sleeps after15 idle minutes, lacks persistent disk, can suspend excessive outbound API traffic, and connectivity has NOT been tested. Any such adaptation needs remote durable storage and end-to-end verification; it is not an approved deployment.
