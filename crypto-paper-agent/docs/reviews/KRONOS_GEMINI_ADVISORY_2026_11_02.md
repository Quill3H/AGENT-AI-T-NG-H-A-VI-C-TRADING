# Kronos Gemini advisory — engineering handoff

Owner approved assistance to the existing three deployed Gemini wallets,
then approved the written design in this chat on 2026-11-02.
Target: https://paper-studio-connectivity.onrender.com/ .
Repository: https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING .
Public repository status and current account admin/push access were checked
through the GitHub connector; Render settings independently point at this repo.

## Frozen code and scope

- Base main: df07280de7dc5fb19c334d17a4d356ed102902e4.
- Feature code: 1fd9c8f4260e40124b1ec565ca4a395712e23f39.
- Local branch: codex/kronos-gemini-advisory.
- Separate checkout: output/paper-bot-cloud; primary research modifications preserved.
- Nineteen source/config/test/docs files in the feature commit. No ledger,
  secrets, downloaded model weights or sources/ reference files included.

## Verified evidence

AUTHOR_VERIFIED and independently TESTER_VERIFIED:

```
node --test scripts/cloud-transport.test.mjs scripts/render-transport.integration.test.mjs scripts/gemini-paper*.test.mjs scripts/kronos-advisory.test.mjs scripts/prepare-kronos.test.mjs paper-bot-studio/*.test.mjs
```

95 passed, zero failed/skipped. Python scripts/test_kronos_forecast.py:
3 passed. Six JS files passed node --check; two Python files compiled.
Tester independently probed each failed frame while the other two proceeded,
all four pinned model hashes, and actual SL settlement/review of an existing
trade while missing/mismatched forecasts prevented new entry analysis.

Independent REVIEWER_VERIFIED: one P2 freshness defect found, reproduced in
two failing tests and fixed. Forecast validity now uses the post-capture
clock and is rechecked after Gemini, before management, and before entry.
Reviewer re-reviewed 31 focused passing tests and found no remaining P1/P2
engineering blocker. Tester and Reviewer were separate agents with read-only
scope, not the implementation author.

AUTHOR_VERIFIED real pinned-model CPU inference: all three frames produced
four six-column forecasts from 40 synthetic source candles and three
averaged paths. Cross-language input-hash/model-artifact/geometry contract
checks passed under an explicitly simulated within-cycle clock; this was
not a live market cycle or proof of real-time freshness. Local runtime was
Python3.12/PyTorch2.15.0+cpu. Linux Actions pins PyTorch2.5.1+cpu and remains
NOT_VERIFIED until a cloud run. Model/source revisions and hashes are in the
committed worker, manifest and operational documentation.

Graphify query was attempted; its existing graph contains no render-service
or gemini-paper module. Narrow current-source inspection was used for those
new modules rather than treating the older graph as current.

## Publication/deployment blocked

No source was pushed and no Render setting, ledger, schedule or public
runtime was changed. Local git push first hit a sandbox MSYS credential-helper
failure. A sandbox escalation was then rejected by automatic approval review.
After verifying repository identity/access, Render source mapping and a
19-file publication scan excluding credentials/ledgers/references, the second
review still rejected publication because the destination is public and
the user had not explicitly approved exposing this payload there.

Do not work around this rejection via connector commits, browser uploads or
other publication paths. Obtain explicit user approval for publishing these
source/config/docs changes to the named public repository and deploying the
matching existing Render service before retrying remote mutations.

## Remaining execution after approval

1. Push the feature branch, create/review the PR and integrate with main.
2. Deploy the matching Render source (currently sourced from codex/paper-cloud-probe);
   align it deliberately with the integration source and verify /health
   reports kronosProtocol:1. No billing/service upgrade.
3. Run the matching Actions workflow in a valid due window. Verify Linux
   dependencies, pinned model download/cache and actual forecast execution.
4. Verify signed inference evidence reaches Gemini and is durably committed
   with the untouched existing ledger. A rejected paper entry still needs
   auditable context/evidence; do not claim a fill from inference success.
5. Verify dashboard attribution for all three frames when they become due,
   then verify primary local main and GitHub main have matching SHAs while
   preserving the primary checkout's unrelated modifications.

This is scoped engineering evidence, not forecast accuracy, profitability,
historical OOS validity or economic/owner acceptance.
