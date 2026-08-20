# T0.0 RA-CONTAIN repair pass 5 — external monotonic owner authority

You are the GPT-5.6 Luna mutation-authorized implementer for non-VERY-HARD T0.0. Work only in:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Start at exact commit `a0334cfbc9e3bfde6aa3310c45975d539153b1f5`. Do not amend, push, deploy, mutate cloud, or touch the main checkout. Read the complete independent pass-5 FAIL report:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass5.md`

Fix every blocker at root. You may replace the HMAC/head implementation rather than preserving a flawed shape. Passing the existing suite is insufficient.

Required outcomes:

1. **No same-domain rollback illusion.** Production construction and the real CLI must require an explicitly provisioned monotonic owner-authority backend/anchor in a distinct protected domain. Remove the adjacent `journal.head` default. A file test adapter must be named test/local and cannot satisfy production construction. If a production filesystem adapter is supported, prove/enforce a distinct mounted device or accepted Release Authority domain identity and require its signed provisioning receipt. Paired rollback of journal plus local artifacts must still refuse against the external owner head.
2. **Atomic monotonic anchor/CAS.** Define a narrow `OwnerAnchorBackend` contract: authenticated read, compare-and-swap from exact revision to pending/committed/indeterminate head, monotonic sequence, and independently verifiable receipt. Use an in-memory/fault-injectable backend for tests and a durable transactional local adapter only if it cannot silently claim production authority. No overwrite-in-place protocol. Partial write/flush/fsync/close/replace must preserve the last committed head or leave externally visible indeterminate state.
3. **Crash-safe canonical journal.** Replace direct append semantics if necessary (SQLite WAL/FULL or equivalent transactional framing) so issue/terminate/reconcile records cannot leave an unrecoverable torn suffix. Recovery itself must be repeatable after a crash at every boundary. Projection/file export is audit output, never authority.
4. **Unknown outcomes stay unknown.** A failure after any possible commit must produce a durable external indeterminate occurrence that all reads/checks/mutations/retries reject until owner reconciliation. Simulate the primary commit succeeding while every local/backstop write fails; a fresh process must not convert that into ordinary idempotent success.
5. **Asymmetric owner boundary.** Remove `--owner-secret`, secret environment fallback, public raw `secret`, `token()`, capability equality shortcuts, and repository test secrets in process args. Use externally signed Ed25519 owner operation envelopes/trust bundle or an opaque signer/verifier handle so runtime verification needs public material only. Private keys are external to the store/CLI; tests generate ephemeral keys. Exact capability, issuer, target tuple, operation, CAS, TTL, nonce/idempotency, and expiry must be signed. No arbitrary Python caller may provision a canonical production store without an accepted signed provisioning decision.
6. **Strict anchor/head semantics.** Validate exact types and all relationships: schema version (bool rejected), operation-to-cursor/journal-record/current-receipt/request binding, genesis-only invariants, pending/committed/indeterminate transition legality, monotonic sequence, domain identity, and signer/trust revision. Recomputed/authenticated but semantically malformed heads must refuse in API and CLI.
7. **Provisioning and CLI.** Add an explicit one-time signed provisioning flow bound to exact journal/store path, external anchor backend/domain, owner trust revision, incident tuple/target, nonce, expiry, and production/test mode. Canonical-path permissions/identity must be checked. Real CLI requires the protected backend/domain and signed envelope paths or stdin/FD; no raw secret and no silent local bootstrap. Help and JSON errors are deterministic and traceback-free.
8. **Current-state-only policy.** Every check resolves the monotonic external head plus canonical journal state. No caller receipt, cache, marker, local head copy, or process state may authorize. Keep zero `verify_containment` references.
9. **Complete fault/regression matrix.** Turn every pass-5 reproduction into a deterministic test, plus crash at every journal DB transaction/WAL/fsync and anchor backend CAS/read boundary; paired rollback; primary commit success + client timeout; reconciliation crash/retry; two writers; replayed signed envelopes/nonces; expired/wrong target/capability/signature; malformed semantic heads; CLI process-list secret audit; production constructor refuses local/test backend; restart and installed-entrypoint tests. Repeat concurrency/fault tests.
10. **Scope/integration.** Keep this a minimal RA-CONTAIN authority. Do not implement cloud transport or deploy. Design the backend/provisioning receipt so the pending signed `GEN-DEPLOY` Release Authority can provision it later without a bypass.

Acceptance before commit:

- all original and new tests pass;
- broader Run Authority/cloud containment selections pass;
- every pass-5 counterexample independently returns a typed refusal or recoverable indeterminate state;
- race/fault repetitions pass;
- `git diff --check`, compile, exports, and zero-bypass search pass;
- no private key/bearer secret reaches argv, environment contract, JSON, repr, logs, fixture constants, or public token methods.

Commit a new follow-up commit and write exact results/trust model/residual deployment requirements to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-pass5-repair-result.md`

Do not claim T0.0 complete; accepted deployment, off-volume production backend provisioning, exact runtime tuple, and real owner-issued cloud receipt remain required.
