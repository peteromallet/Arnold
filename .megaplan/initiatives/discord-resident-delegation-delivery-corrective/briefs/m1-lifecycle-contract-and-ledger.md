# M1 — Lifecycle Contract and Unified Delivery Ledger

## Outcome

Define and implement the versioned canonical lifecycle ledger/state machine that will become the single authority for a Discord resident request from ingress through terminal reply. Establish immutable provenance and executable transition validation without switching production traffic yet.

## Scope

In scope: inventory current state/provenance authorities; define request/message/turn/execution/outbox/attempt identities; implement additive storage records and APIs; define state/transition table, causal references, record versions, leases/fences, timestamps, and terminal rules; provide projections needed by existing manifest/status readers; add schema and transition tests. This sprint must remain within roughly two human-weeks.

Out of scope: changing live burst behavior, launching agents through the new ledger, sending Discord messages from an outbox, backfilling all legacy data, or production cutover.

## Locked decisions

- Follow `NORTHSTAR.md` and `decisions/lifecycle-architecture-constraints.md`.
- One canonical append-safe ledger/state machine is authoritative; mutable cursors and manifests are projections only.
- Per-message provenance is persisted before coalescing and never mutated.
- Storage changes are additive and versioned; no legacy deletion.

## Open questions for the plan

- Which existing store implementation best provides atomic create/compare-and-set and indexed recovery queries with minimal new substrate?
- What minimal state decomposition avoids a single overloaded enum while still producing one coherent lifecycle view?
- Which compatibility projections must be maintained synchronously versus derived on read?

## Constraints

Preserve secrets, authorization, existing public behavior, and unrelated active chains. Prefer deterministic clocks/ids in tests. Document every legal transition and rejection reason. Do not infer transport provenance from conversation history or last-message fields.

## Done criteria and acceptance evidence

- A checked-in schema/contract names immutable ingress identity, resident request id, burst membership, execution uniqueness key, outbox idempotency key, attempt receipt, lease/fence, and causal parent.
- Executable transition validation rejects illegal regressions, stale versions/fences, duplicate terminal commits, and missing causal provenance.
- Repository tests prove create/re-read stability, concurrent compare-and-set behavior, terminal monotonicity, and projection compatibility.
- A focused authority inventory names every existing writer/reader and the migration treatment; no undocumented competing authority remains.
- Evidence is recorded in plan/review artifacts with exact test commands and results.

## Touchpoints

Expected areas include `arnold_pipelines/megaplan/resident/` storage/models/runtime/subagent surfaces, `tests/resident/`, and resident boundary documentation. The planner must refine these after repository inspection.

## Anti-scope

Do not redesign the general Arnold workflow runtime, alter unrelated cloud-chain state, replace Discord libraries, or perform broad cleanup/refactors.
