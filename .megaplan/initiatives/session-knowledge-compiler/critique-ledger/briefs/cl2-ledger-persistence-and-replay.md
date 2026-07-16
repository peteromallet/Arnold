# CL2 — Append-only ledger persistence, compatibility, and replay

## Outcome

Implement the CL1 record contract through existing WBC/plan-local persistence
seams, with atomic append, idempotent retry, rebuildable projections, read-only
replay, and mixed-version compatibility. Leave CL3 a stable API and fixtures.

## In scope

- Persist critic start/result and immutable occurrence envelopes with WBC
  attempt/payload references and current raw/custody artifacts.
- Append reconciliation/disposition events and publish a ledger revision only
  after complete occurrence accounting validates.
- Build cumulative/domain projections and deterministic read-only replay.
- Add legacy-only, dual-write, new-only, rollback, future-version, corrupt,
  redacted, unavailable, duplicate, out-of-order, concurrent, and crash fixtures.
- Add additive schema/version readers and explicit `legacy_unknown` behavior;
  preserve current flag/gate/finalize compatibility.
- Implement freshness vectors and governed tombstone/unavailable handling.

## Out of scope

Evaluator selection, critic prompt changes, semantic auto-merge policy, reviser
or gate consumption, live shadow/canary, old artifact deletion, or production
backfill of historical semantic relationships.

## Locked decisions

- Start persistence precedes critic dispatch; terminal persistence failure is
  visible `persistence_failed|indeterminate`, never clean success.
- Occurrences are never merged away. Semantic identity and occurrence identity
  remain distinct.
- Projections are rebuildable and carry no positive authority.
- Historical gaps stay explicit; migration never invents duplicate, resolution,
  evidence, or reopen relationships.
- WBC inline/reference, retention, redaction, ordering, and effect rules are
  reused, not reimplemented.

## Open questions

- Which landed backend satisfies one transaction, and where is durable
  prepare/outbox reconciliation required?
- What plan-local compatibility files remain necessary for old readers?
- How are partially parseable failed attempts admitted without promoting an
  invalid whole payload?
- What indexes are necessary within the two-week scope for domain/round replay?

## Constraints

Consume only an accepted CL1 handoff. Do not widen schema or ownership without a
new reviewed CL1 decision. All writes are idempotent, content-safe, access-
controlled, and fault-tested. Replay issues no model call or external effect.

## Done criteria

- Schema/golden, property, concurrency, crash/fault, compatibility, privacy,
  WBC ledger/evidence, and existing critique-custody suites pass.
- Every accepted producer occurrence appears once; duplicate replay is a no-op;
  partial publication cannot expose an accepted incomplete ledger revision.
- Projections rebuild byte-equivalently from retained inputs and surface
  missing/redacted evidence as unknown.
- Mixed-version downgrade and disable preserve legacy behavior and all evidence.
- Negative tests prove ledger/replay cannot mutate plan, gate, lifecycle, queue,
  Git/provider, delivery, or external-effect state.

## Touchpoints

`arnold/workflow/execution_attempt_ledger.py`, `payload_policy.py`, boundary
evidence/compatibility/conformance; Megaplan critique custody/runtime, schemas,
artifact writers, flag registry readers, and focused WBC/critique tests.

## Anti-scope

No new database service, event bus, authority plane, generalized knowledge
store, embeddings, broad historical backfill, or old-reader retirement.

## Written handoff to CL3

Write and review `docs/critique-ledger/handoffs/cl2-ledger-replay.json` with API/
schema hashes, backend/atomicity decision, compatibility matrix, replay hashes,
fixture index, freshness rules, fault results, disable/rollback procedure, and
unresolved limits. CL3 must validate the handoff and replay fixtures before
constructing a briefing.
