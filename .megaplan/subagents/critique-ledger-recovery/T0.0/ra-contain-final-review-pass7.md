# RA-CONTAIN adversarial review pass 7

Use GPT-5.6 Luna high reasoning. Perform a fresh READ-ONLY adversarial review of exact
commit:

`25dc026546b9586db63ec0a39e5987321bf4bd0f`

in:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Do not edit, commit, push, deploy, or mutate cloud/external state. Run local tests and
ephemeral fault/concurrency probes. Read the prior FAIL report and verify every finding
independently:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass6-result.md`

## Required review

1. Re-run caller-chosen fake `production_capable`/trust/domain/backend self-authorization.
   Inspect the new `ReleaseAuthorityBackend` boundary. Production must either use a real
   pinned external owner integration or fail typed/closed; subclassing, constructing,
   deserializing, monkeypatching ordinary inputs, or passing a self-signed head must not
   create production authority. Clearly distinguish a sound unavailable integration seam
   from formal T0.0 completion.
2. Re-run both pending-CAS and final-CAS ambiguity paths through signed reconciliation.
   Successful reconcile must return only after authenticated `status()` and all `check`
   effects agree with an `operation="reconcile"` head and canonical record.
3. Re-run same/divergent decision ID, idempotency key, nonce, and operation identity after
   active issue, terminate, restart, ambiguity, and reconciliation. Exact replay is stable;
   divergent content always conflicts.
4. Re-run CLI `check --effect` for observe plus every denied effect, missing/malformed
   descriptors/files/JSON/fields, unknown actions, and help. No traceback or hard-coded
   observe path.
5. Re-run rollback/truncate/replace/fork scenarios. Do not grant production security credit
   to `LocalTestOwnerAnchorBackend`; prove it cannot be mistaken for accepted authority.
6. Verify strict schemas and semantic relationships: bool/int, NaN/Infinity, TTL, clocks,
   unknown/missing fields, genesis/cursor/revision/record/receipt/candidate relationships.
7. Verify thread and separate-process races with one valid history; include storage lock,
   SQLite/WAL and external-anchor ordering.
8. Verify TTL/explicit revoke across restart/injected clock boundaries, including expired
   signed request envelopes and expired containment receipts.
9. Check crash points before/after every journal/anchor/nonce/idempotency durable transition.
   No false success, duplicate effect, unrecoverable valid state, or ambiguity downgrade.
10. Verify the generic contract/reducer dependency boundary was restored without hiding
    persistence policy in a generic module. Check installed dependencies/lock consistency.
11. Inspect public APIs, representation, logging, CLI argv/env, files, and exceptions for
    bearer/private key leakage or alternate bypasses.
12. Ensure the expanded tests did not merely encode implementation assumptions or delete
    required prior coverage. Run dependency-closure and installed-wheel tests if applicable.

Write:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass7-result.md`

Start exactly `PASS` or `FAIL`. For every defect give severity, exact file/function/line,
reproduction/reasoning, and minimum root fix. A PASS may state that the local primitive and
integration seam are sound while formal T0.0 remains blocked on accepted GEN-DEPLOY backend,
cloud installation, and an actual owner decision. Include exact commands/test counts.
