# GPT-5.6 Luna implementation — T1.10 repair pass 4

Continue from exact clean commit `0c3d662024bc0497ed3979991a20b3b48ecf19cd`
in `/private/tmp/arnold-critique-recovery-notification-ux-20260802`. Start only
when a mutating slot is free. Read the full T1.10 plan contract, pass-3 repair
result, and pass-4 hard-fail review. Preserve all canonical data-plane fixes.

Close every local code blocker:

1. Make installed-wheel and materialized `arnold-notification-delivery` and
   diagnostic entrypoints bind one attested package/runtime generation and work
   from the deployment directory without `PYTHONPATH`/checkout assumptions.
   Verify exact import origins/content/help/schema and fail closed on mismatch.
2. Retire `discord_dm.py`, `agentbox_adapter` completion DM, exception fallthrough,
   environment-selected provider calls, and every alternate direct writer. They
   must call the canonical owner boundary with an accepted occurrence/intent or
   return a typed retired/unavailable result; no token/env/import/fallback may
   make a provider call. Add static and executable bypass tests.
3. Add a canonical signed trust-set/key-rotation transaction for owner and
   provider receipt keys: monotonic predecessor/revision, overlap window where
   explicitly authorized, revocation, restart/replay, wrong key/ID, downgrade,
   fork and rollback rejection. A document sequence change is not key rotation.
4. Implement reminder buckets as durable meaningful state transitions with
   deterministic due windows, one intent per occurrence/version/bucket, quiet
   suppression, acknowledgement/cancel behavior, and restart/concurrency proof.
5. Implement canonical chunk planning before provider effects. Derive stable
   child GLEKs from parent intent + chunk index/count/content digest/recipient;
   persist all child intents before calls; independently receipt each; represent
   acknowledgement loss as child `INDETERMINATE`; never resend ambiguous chunks;
   rebuild one incident card from child results without notification storms.
6. Normalize divergent recipient re-admission to the public typed conflict API.
   Expand crash/restart/fence/lease/receipt/corruption/two-process/200-observer
   coverage around all new transitions.

The production RA/Custody/WBC adapters, credentials and supervisor remain owner-
installed external prerequisites. Keep production unavailable without them; do
not fabricate local production adapters merely to turn tests green. Define the
exact frozen adapter/supervision interfaces needed for later T1.5/T1.6
integration and make absence typed/fail-closed.

Run the full focused set (including the previously red materialized-wrapper
test), dependency closure, installed wheel in a clean environment, materialized
parity, static/diff/compile and bypass scans. Large validation is single-flight;
remove only reproducible scratch after capture. Do not send messages, contact
providers/cloud, deploy, or provision authority. Commit only scoped changes,
leave clean, and write exact commit/tree/files/tests/limitations to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.10/notification-ux-repair-pass4-result.md`.
Do not claim formal T1.10 completion before T1.5/T1.6 integration and owner
deployment receipts.
