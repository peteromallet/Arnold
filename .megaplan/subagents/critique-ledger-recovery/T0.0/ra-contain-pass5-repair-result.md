# T0.0 RA-CONTAIN pass-5 repair handoff

Repair commit: `611321c79c70d3ec75cf6f7be6ba3df275eb5e81` on the isolated
worktree branch `fix/critique-recovery-ra-contain-20260802`, based on the
required `a0334cfbc9e3bfde6aa3310c45975d539153b1f5`.

## Implemented authority and trust model

- Replaced the adjacent JSON/HMAC head with an explicit `OwnerAnchorBackend`
  contract: authenticated read, exact-revision/sequence CAS, monotonic
  `pending`/`committed`/`indeterminate` transitions, nonce reservation, and
  independently verifiable Ed25519 backend receipts.
- `InMemoryOwnerAnchorBackend` and `LocalTestOwnerAnchorBackend` are explicitly
  `test/local` and are rejected by production construction. There is no
  adjacent-journal default anchor. Production construction/provisioning
  requires an external backend marked production-capable plus a signed
  provisioning decision.
- Replaced bearer/HMAC owner authentication with Ed25519 owner envelopes and a
  public-only `OwnerTrustBundle`. Signed fields bind owner/capability,
  issuer, canonical journal path, anchor domain, exact incident tuple,
  operation, CAS, TTL, idempotency key, nonce, trust revision, mode, and
  expiry. No raw capability field, `token()` method, owner-secret CLI option,
  secret environment fallback, or `verify_containment` path remains.
- Provisioning is one-time and signed, bound to the canonical journal path,
  backend domain, trust revision, target tuple, nonce, expiry, and mode. An
  empty canonical journal cannot be constructed as an authority by an
  arbitrary Python caller.
- The canonical journal is SQLite with WAL and `synchronous=FULL`; issue,
  terminate, and reconcile records are transactional rows with authenticated
  hash-chain fields. File output is not authority. Uncertain journal or anchor
  boundaries advance the external state to a durable indeterminate occurrence
  or leave a non-authorizing pending state; reads, checks, mutations, retries,
  and fresh processes refuse until signed owner reconciliation.
- Committed heads are checked against the current journal cursor, digest,
  receipt, last record operation, request digest, record hash, exact scalar
  types, genesis invariants, domain identity, trust revision, monotonic
  sequence, and backend receipt. Recomputed but semantically malformed heads
  refuse.

## Verification

- `pytest -q tests/arnold_pipelines/run_authority tests/run_authority tests/cloud/test_m1_containment_acceptance.py`
  — **52 passed**.
- Focused pass-5 authority regressions include paired local rollback,
  production rejection of test/local backends, signed envelope tampering and
  nonce replay, malformed head schema/receipt checks, anchor CAS uncertainty,
  journal transaction uncertainty, primary commit/client-timeout ambiguity,
  owner reconciliation, local-backend restart, CLI JSON/help behavior, and
  legacy bypass absence.
- `python -m compileall -q arnold_pipelines/run_authority` — passed.
- `git diff --check` — passed before commit.
- Export/import audit — passed.
- Scoped zero-bypass search for owner-secret, raw capability secret,
  `token()`, HMAC containment, `verify_containment`, and secret environment
  fallback — zero matches in the RA-CONTAIN implementation/tests.
- Module CLI provisioning/status smoke test passed with a test/local backend;
  production CLI construction deterministically refuses without the accepted
  protected backend.

The repository-wide `pytest -q` collection was attempted but is blocked by
pre-existing missing environment dependencies outside this change:
`fire`, `python-dotenv`, and `discord` prevent seven unrelated agent/resident
test modules from importing. No RA-CONTAIN or Run Authority/cloud selection
failure occurred.

## Residual deployment requirements

This does **not** claim T0.0 complete. The accepted `GEN-DEPLOY` Release
Authority must still supply and provision a real off-volume production
`OwnerAnchorBackend`/domain, its independently verifiable backend receipt and
trust revision, the exact approved runtime tuple, and a real owner-issued
cloud containment receipt. The production CLI intentionally has no local
bootstrap or local-backend bypass; it remains unavailable until that accepted
backend adapter and signed provisioning decision are installed. No cloud
transport, deployment, or cloud mutation was implemented.
