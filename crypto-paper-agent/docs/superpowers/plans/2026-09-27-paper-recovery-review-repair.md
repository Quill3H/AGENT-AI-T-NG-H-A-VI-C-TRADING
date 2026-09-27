# Paper recovery review repair plan

Owner authorizes direct implementation and self-review in this conversation.
Gate: backend recovery/reconnect repair, then UI-only integration; no acceptance
of G5 or main merge. Base backend 6bdaa0dd1d91d329a3983311088aeb33ac0c2fa7.
UI source now bab1f92371a520151a5dbfe04349dc9e3265ae01 (review fix).

1. Reproduce orphan/corrupt/partial journal, missing manifest and uncertain
   account display in tests/test_paper_recovery_review.py. Create a durable
   journal/checkpoint guard under src/paper; bind checkpoint bytes to journal
   digest. All existing storage restarts read-only. Unknown money is null;
   preserved last-known state is explicitly not reconciled. Never load pickle,
   resume partial broker state, reset an existing directory or import the web
   branch's persistence.py.
2. Test BTC/ETH/SOL closed-time mismatch through actual transport callbacks.
   Have the transport close/reconnect on rejected session input. Clear partial
   sets per connection; reject bool/nonfinite values and stream/REST conflicts.
   Preserve funding policy and broker risk/accounting implementation.
3. Exercise HTTP routes on a real loopback server: idempotency, malformed Origin,
   denied requests, source failure, recovery and second bind. Update state schema
   and generate full synthetic examples from tested session states. Windows
   launcher must use exclusive bind and preserve persistent account location.
4. After backend focused tests pass, commit backend and create integration branch
   in this clean worktree. Import only web-preview/src from reviewed UI SHA;
   preserve backend live_session.py and run_local_paper_web.py. Resolve field
   compatibility in backend. Test Python/web/build and Windows subprocess HTTP
   lifecycle on same code commit; perform bounded public stream attempt.
5. Self-review and publish exact test evidence, public-feed outcome, remaining
   recovery/independent-review limits; push only backend/integration branches.

Regression commands: python -m pytest -p no:cacheprovider tests/test_local_paper*
tests/test_paper_recovery_review.py -q (explicit filenames in actual invocation).
Final Python: python -m pytest -p no:cacheprovider -q. Web: npm test; npm run build.
No parameter tuning, real/testnet orders, credentials, subagents or UI redesign.
