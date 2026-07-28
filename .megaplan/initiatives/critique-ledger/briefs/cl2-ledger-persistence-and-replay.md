# CL2 — WBC-backed ledger persistence, import, and replay

## Outcome

Implement the CL1 record contract through existing WBC/plan-local persistence
seams, with atomic append, idempotent retry, rebuildable projections, read-only
replay, and one-time import from retained legacy artifacts. Leave CL3 one stable
target API and fixtures.

## In scope

- Persist critic start/result and immutable occurrence envelopes with WBC
  attempt/payload references and current raw/custody artifacts.
- Additively version the CL1 schema so new raw occurrences cannot author
  `semantic_finding_id`; retain the old field only for explicit legacy reads.
- Append reconciliation/disposition events and publish a ledger revision only
  after complete occurrence accounting validates.
- Persist reconciliation corrections/supersession, independent audit events,
  plan-region/dependency anchors, and deterministic tripwire state.
- Persist structured revision-response and independent outcome-verification
  events in the same finding history; do not create a separate revision ledger.
- Build cumulative/domain projections and deterministic read-only replay.
- Build a separate rebuildable active-action projection so closed history does
  not create a monotonically growing reviser workload.
- Project explicit `accepted|review_required|disputed|superseded` decision state
  and `must_act|must_revalidate|context_only` work queues.
- Build a per-round accountability projection from attempts through occurrences,
  logical findings, responses, verified outcomes, and reopen conditions.
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
- Reconciliation decisions are immutable evidence, not unquestionable truth;
  corrections append a superseding decision and replay retains both.
- Semantic finding identity is assigned only by reconciliation events, never by
  a new raw occurrence.
- Similarity and region/dependency changes may trigger re-review but never
  perform semantic merge, closure, or suppression.
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
- Region-anchor changes stale only the affected scoped findings; unknown or
  cross-cutting scope safely defaults to whole-plan freshness.
- Correction, audit-disagreement, tripwire, and bounded active-projection
  fixtures replay deterministically.
- Round receipts account for every occurrence and active finding; reviser
  `addressed` claims remain distinct from independently verified
  `dealt_with|partially_dealt_with|not_dealt_with|unknown` outcomes.
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
fixture index, region/freshness and tripwire rules, audit/correction event rules,
response/outcome event rules, active-projection bounds, round-receipt hashes,
fault results, backup/restore prerequisites, and unresolved limits. CL3 must
validate the handoff and replay fixtures before constructing a briefing.
