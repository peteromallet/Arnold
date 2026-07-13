# C1: Contract Reality Reconciliation

## Outcome

Rebase Workflow Boundary Contracts on the fully landed Run Authority result,
then prove what current producers actually write before any shared runtime
writer or consumer is changed. Inspect any landed Megaplan Maintenance contracts
as current-runtime inputs, but do not require that independent initiative to finish.

The milestone leaves a versioned contract-to-producer matrix, an ownership
matrix, a machine-readable supported-surface manifest, a frozen execution-
attempt ledger schema, and replayable legacy/current compatibility fixtures.
Every supported boundary is assigned a migration milestone. Temporary
exceptions require an owner, reason, expiry/removal milestone, and visible
non-conformant status; none may survive C6.

## Prerequisite Inputs

- A matching completion manifest for all three Run Authority milestones.
- A clean `main` containing the completed Run Authority history.
- Run Authority's final migration report and any Maintenance rollout/audit
  evidence already present at the pinned launch revision.
- Existing WBC notes and historical briefs as research, not source truth.

If any input is absent or stale, stop before implementation.

## Mutation Class

Observe-only outside boundary-local declarations, adapters, tests, fixtures,
and documentation. Do not change producer completion ordering, lifecycle
mutation, watchdog dispatch, repair queues, cloud status, chain advancement, or
auditor behavior in C1.

All inventory and fixture capture must be read-only. Do not call helpers that
normalize by writing, materialize event projections, recover journals, save
chain state, emit drift events, or persist status.

## Scope

IN:

- Inventory current boundary declarations and every real producer for prep,
  plan/revise, critique/gate, tiebreaker/reducer, execute, finalize, review,
  override/human-gate, chain, PR/publication, cloud, repair, and audit surfaces.
- Enumerate every step/attempt executed by `arnold.workflow`, every Megaplan
  adapter listed above, and the pinned `arnold.pipeline.native` runtime adapter
  and `evidence_pack` conformance workflow. Mark manual
  out-of-runtime work, third-party internal execution, and historical read-only
  runs explicitly out of scope while keeping supported-step external effects in
  scope.
- Freeze explicit versioned schemas for an append-only execution-attempt stream:
  immutable identity/provenance and causal/per-attempt ordering; started,
  completed, failed, retry-scheduled, suspended, resumed, cancelled,
  external-effect intent/outcome, and persistence-failure/reconciliation events;
  and typed refs for inputs, outputs/results, verdicts, state deltas, artifacts,
  checkpoints, authority, and effects.
- Validate and freeze `wbc.inline.v1`'s 16 KiB canonical-JSON threshold and
  classification rules plus durable-ref
  fields for store/locator, digest, schema/media type, size, encryption/access,
  privacy, retention, and availability. State explicitly that a digest without
  retained retrievable bytes does not preserve a result.
- Specify append/idempotency, write-ahead start, transaction or outbox/prepare-
  commit publication, external-effect fencing, crash reconciliation, and fail-
  visible behavior. Start-store failure blocks dispatch; terminal-store failure
  blocks success/authority advance and yields queryable `persistence_failed` or
  `indeterminate` state.
- Validate `wbc.retention.v1` retention, default-on redaction/tombstone,
  deletion/legal-hold, tenant/workflow
  isolation, encryption, least privilege, secret exclusion, and access-audit
  behavior, plus query and replay guarantees and limits.
- Reconcile dynamic/versioned artifact names, applicability/current-invocation
  rules, state/history shape, `phase_result`, receipt timing, authority refs,
  and exemptions.
- Treat the existing boundary registry and shared `arnold.workflow` vocabulary
  as the starting surface; migrate/extend it in place rather than adding a
  parallel cloud registry.
- Classify every input as observation, claim, decision, or projection using Run
  Authority. Record the canonical owner and whether WBC may declare, emit,
  evaluate, adapt, or only consume it.
- Add a redacted legacy fixture representing pre-Run-Authority runtime JSON and
  a current fixture generated from the pinned launch schemas.
- Cover at least: `state.json`, history, `phase_result.json`, step/boundary
  receipts, execution grants/attempts/claims/decisions/quarantine, observation
  envelopes, detection/repair/verification events, repair requests/decisions,
  watchdog reports, status snapshots, chain state, and six-hour audit records.
- Replace synthetic tests that fabricate every declared artifact with real
  producer-output fixtures or producer-driven tests; retain focused synthetic
  unit cases where useful.
- Produce an explicit list of delivered native-parity coverage, stale
  declarations, missing emitters, and intentional exemptions.

OUT:

- Shared-surface mutation or dispatch.
- A new lifecycle, status, queue, repair-custody, or authority schema.
- Silent normalization of legacy fixtures into current authority.
- Broad generic template or non-Megaplan work.
- Implementing the frozen ledger or migrating producers; those begin in C2.

## Locked Ownership

- Run Authority decisions determine accepted execution and authority; raw task
  labels and batch JSON remain claims/projections.
- Maintenance owns coherent observations and all plan/chain mutation through
  `TransitionWriter`.
- WBC owns contract declarations, receipt/evidence profiles, and semantic
  mismatch findings only.
- Receipt presence cannot retroactively authorize a transition, and a semantic
  finding cannot mutate or clear lifecycle state.

## Required Acceptance Evidence

1. A checked-in source-to-owner matrix has one mutating owner for every shared
   surface and names all compatibility readers.
2. A checked-in contract-to-producer matrix proves actual path patterns,
   applicability, invocation identity, state/history effects, and receipt/
   authority relations for every covered boundary.
3. Legacy and current fixtures replay read-only with typed unknown/incompatible
   results; neither is rewritten during evaluation.
4. At least one real producer-driven healthy and broken case exists per phase
   family, including a producer that currently writes versioned artifacts.
5. All Run-Authority-focused and launch-safety regression suites pass from the
   clean pinned base.
6. With the master mutation gate and all dispatch flags off, semantic inspection
   performs zero lifecycle, queue, source, commit, push, or audited-input writes.
7. A milestone handoff records the exact base SHA, Run Authority manifest hash,
   fixture schema versions, and mechanically validated C2
   integration seams. There is no approval step.
8. A checked-in machine-readable support manifest maps 100% of declared
   supported steps and attempt transitions to an owner and C2-C6 migration gate;
   no row is unclassified.
9. Schema fixtures validate every event type, identity/order rule, inline and
   referenced payload mode, retention/redaction class, and persistence-failure
   state, with golden compatibility diagnostics.
10. A written atomicity/failure table covers crash points before dispatch,
    during result/state publication, before/after external effects, and during
    terminal append, naming the visible state and deterministic reconciliation.
11. Query/replay/audit and conformance test plans name machine-produced evidence
    artifacts, required indexes, authorization checks, and non-replayable effect
    behavior.

## Automatic Failure Conditions

Fail validation and abort through `stop_chain` if:

- a prerequisite manifest no longer matches current source;
- any major consumer still independently grants authority from raw
  compatibility JSON without an explicit prerequisite-owned migration mode;
- two components claim mutation authority over the same lifecycle/queue/status
  surface;
- current fixtures cannot be evaluated without mutation or hidden fallback;
- real producers cannot be mapped to declared contracts without inventing
  filenames or authority evidence.
- any supported producer lacks a migration milestone, or the proposed design
  relies on hashes without durable payload retention/retrieval.

Each condition must emit a stable diagnostic and evidence reference. None may
be converted to a clarification, waiver, approval request, or alternate design
selection during the chain.

## Likely Touchpoints

- existing boundary contract/evidence and semantic-health modules
- phase handlers and receipt writers, read-only in this milestone
- Run Authority inventory, contracts, bindings, and views
- Maintenance observation, transition, repair, status, and audit contracts
- focused boundary/receipt/semantic-health compatibility tests
