# CL2 — WBC-backed ledger persistence, import, and replay

## Outcome

Implement the CL1 record contract through existing WBC/plan-local persistence
seams, with atomic append, idempotent retry, rebuildable projections, read-only
replay, and one-time import from retained legacy artifacts. Leave CL3 one stable
target API and fixtures.

## In scope

- Persist critic start/result and immutable occurrence envelopes with WBC
  attempt/payload references and current raw/custody artifacts.
- Append reconciliation/disposition events and publish a ledger revision only
  after complete occurrence accounting validates.
- Build cumulative/domain projections and deterministic read-only replay.
- Add current-source import, target-only, future-version, corrupt, redacted,
  unavailable, duplicate, out-of-order, concurrent, and crash fixtures.
- Add the target schema reader and explicit `legacy_unknown` import behavior;
  retain current flag/gate/finalize inputs only until the coordinated cutover.
- Implement freshness vectors and governed tombstone/unavailable handling.

## Out of scope

Evaluator selection, critic prompt changes, semantic auto-merge policy, reviser
or gate consumption, live cutover, old artifact deletion, or production
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
- The one-time importer preserves all available legacy evidence, marks semantic
  gaps unknown, and rejects unsupported target versions without partial publish.
- Negative tests prove ledger/replay cannot mutate plan, gate, lifecycle, queue,
  Git/provider, delivery, or external-effect state.

## Touchpoints

`arnold/workflow/execution_attempt_ledger.py`, `payload_policy.py`, boundary
evidence/compatibility/conformance; Megaplan critique custody/runtime, schemas,
artifact writers, flag registry readers, and focused WBC/critique tests.

## Anti-scope

No new database service, event bus, authority plane, generalized knowledge
store, embeddings, broad historical backfill, dual-write window, or old-reader
retirement before CL5.

## Written handoff to CL3

Write and review `docs/critique-ledger/handoffs/cl2-ledger-replay.json` with API/
schema hashes, backend/atomicity decision, one-time import map, replay hashes,
fixture index, freshness rules, fault results, backup/restore prerequisites, and
unresolved limits. CL3 must validate the handoff and replay fixtures before
constructing a briefing.
