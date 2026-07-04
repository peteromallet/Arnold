# Native Platform Fit

This note explains how `native-platform-followup` fits the boundary-contract
work and the broader push toward Python-native pipeline graphs.

## Relationship

`native-platform-followup` is not a competing boundary-contract epic. It is the
production substrate that should emit, preserve, and reconcile boundary evidence
for Python-native workflows.

The intended split is:

- native composition / `.pypeline` source owns developer-facing workflow
  semantics: branches, loops, calls, subworkflow calls, dynamic maps, typed
  outcomes, suspension points, and declared policies;
- boundary contracts own the durable proof vocabulary around those semantics:
  expected effects, receipts/evidence, outcomes, authority, temporal policy,
  and semantic findings;
- native platform owns production execution guarantees: idempotent side effects,
  reconcile-on-resume, brokered credentials, durable checkpoints, audit records,
  worker leases, cancellation, and stuck-run supervision.

In other words: Python-native authoring says what the graph is; boundary
contracts say how each graph boundary is proven healthy; native platform makes
those proofs durable and operationally safe.

## Why This Matters For Developers

The developer-facing goal is not a generic graph builder or component registry.
The developer should write ordinary Python-shaped orchestration:

- `if` branches for decisions;
- `while` / typed loop outcomes for bounded loops;
- function and subworkflow calls for composition;
- `parallel_map` for runtime fan-out;
- explicit suspension points for human decisions;
- declared policy objects for retry, timeout, model routing, and authority.

Boundary contracts should attach to that source-level shape without replacing it
with route tables, handler refs, manifest builders, or hidden runtime dispatch.
If a developer has to author product flow through boundary objects directly, the
design has regressed.

## Mapping Between The Two Epics

| Boundary-contract primitive | Native-platform counterpart |
| --- | --- |
| `BoundaryGraph` | native IR paths, graph projection, child workflow paths, `parallel_map`, pack dependency graph |
| `BoundaryOutcome` | native typed outcomes, suspension/cancel/resume states, reconcile outcomes |
| `BoundaryEvidence` / `EvidenceProfile` | native audit records, effect ledger entries, broker logs, checkpoint refs, trace events |
| `TemporalPolicy` | timeout/deadline policy, lease expiry, heartbeat freshness, approval expiry, observation windows |
| `AuthorityRecord` | broker approvals, protected operation gates, override/force-proceed waivers |
| execution custody boundary | worker leases, owner ids, heartbeats, cancellation hooks, stuck-run escalation |
| external effect boundary | idempotency keys, reconcile-action table, brokered git/provider actions |
| semantic finding | status/auditor/repair input derived from contract/evidence mismatch |

## Sequencing Implication

The boundary epic should not wait for all native-platform milestones before
shipping the prep semantic guard. But the generalized M3/M10 foundation should
be designed to consume native-platform evidence cleanly.

Practical sequencing:

1. Boundary M1/M2/M6 can proceed immediately for the known Megaplan prep and
   repair-trigger incident class.
2. Boundary M3 should reserve the graph/evidence/outcome/authority/temporal
   primitives now, because native-platform will need those shapes.
3. Native-platform M1/M2/M4/M5 should emit evidence that can be adapted into
   `BoundaryEvidence` rather than inventing separate proof formats.
4. Boundary M10 should use a native Python / native platform workflow as the
   non-Megaplan conformance case when the prerequisite composition/platform
   substrate exists.

## Important Guardrail

The native platform north star names
`arnold_pipelines/megaplan/workflows/workflow.pypeline` as the canonical source,
but this checkout currently does not contain that file. That appears to be a
prerequisite-output assumption from the native composition chain, not something
the boundary epic should silently rely on.

Until `.pypeline` canonical source exists, boundary integration should target
the current runtime/evidence surfaces and keep the `.pypeline` conformance case
as a dependency-gated acceptance test.

## Judgment

Conceptually these epics should fit together tightly, but not merge:

- native composition/platform is about developer authoring and production
  execution;
- boundary contracts are about semantic proof, repairability, and status/audit
  interpretation.

The connection point should be adapter-level: native runtime, audit, checkpoint,
effect-ledger, broker, and worker-lease records become boundary evidence. The
source-level workflow remains Python-native and readable.

