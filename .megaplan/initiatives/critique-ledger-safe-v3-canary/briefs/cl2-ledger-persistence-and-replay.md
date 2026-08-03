# CL2 — WBC-backed ledger persistence, import, and replay

## Outcome

Implement the CL1 record contract through existing WBC/plan-local persistence
seams, with atomic append, idempotent retry, rebuildable projections, read-only
replay, and one-time import from retained legacy artifacts. Leave CL3 one stable
target API and fixtures.

## Locked first-pass plan requirements

The first plan must include all eight requirements below unchanged. They are
copied from attempt 13's root-sealed `gate.json` (SHA-256
`81156da5f1fcce5d7eb5df970de3d97f18f59e7ac1668b633f0bd84c116c2bd3`,
`north_star_actions[*].required_change`). They are input constraints, not proof
that the product work is complete.

1. Insert a Phase 0 checkpoint forbidding database creation and publication until the accepted CL1 artifact is present, blocker-free, version-supported, and hash-valid; defer contract-dependent steps until its decisions replace every provisional assumption.
2. Define CL1 admission using baseline ancestry and schema hashes, then record a separate content-addressed CL2 runtime commit/tree in the CL2 handoff. Add unrelated-ancestry and stale-schema tests.
3. Add a mandatory payload-policy/access context derived from CL1, reject absent or mismatched scope before preparing bytes, and test protected/private, cross-tenant, cross-workflow, encryption-unavailable, retention, and tombstone cases.
4. Persist or reference a content-addressed selection roster before dispatch; bind starts and occurrences to it; include its hash in the manifest; and test selected-but-never-started, missing-outcome, and unrostered-producer cases.
5. Add _core/worker_fanout.py and the common dispatch failure contract to scope; define a public success/failure carrier for WBC start and terminal references; preserve it through callbacks and reducers; and test both paths end to end.
6. Thread an explicit per-dispatch retry ordinal through WorkerUnit, fan-out serialization, repair construction, and dispatch identity derivation. Test initial, fallback, and repair attempts for distinct starts, terminals, and occurrences.
7. Split importer inventory from publication; sequential custody construction from state-ordering integration; parallel carrier/identity work from reducer persistence; and fixture construction from crash, concurrency, privacy, negative-authority, and regression gates.
8. Add a post-gate, pre-execution requirement for the ordinary finalizer to regenerate deterministic source-bound feasibility artifacts. Finalize and execute must fail closed on missing, stale, mismatched, or negative admission.

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
