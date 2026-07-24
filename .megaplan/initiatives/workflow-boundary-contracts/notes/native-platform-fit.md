# Native Platform Fit

This note explains how `native-platform-followup` fits the boundary-contract
work and the broader push toward Python-native pipeline graphs.

> Corrective update (2026-07-10): the canonical native workflow source now
> exists. The conceptual ownership split below remains valid, but the old
> immediate sequencing and absent-file guardrail are superseded by the gated
> C1-C6 chain and the corrective reshape decision.

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
- native platform owns production execution mechanics: idempotent side effects,
  reconcile-on-resume, brokered credentials, durable checkpoints, worker
  leases, cancellation, and stuck-run supervision; its supported adapter must
  write the shared kernel execution-attempt ledger rather than keep a separate
  authoritative audit/effect history.

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

The corrective chain starts only after Run Authority completes. Megaplan
Maintenance proceeds independently and is not a launch condition. C1 reconciles
native and Megaplan evidence surfaces against the pinned source; C5 adds generic
profiles/templates; C6 uses a real native Python-shaped workflow as the
non-Megaplan conformance case. Native runtime evidence should be adapted into
`BoundaryEvidence`, not copied into a parallel proof format.

## Important Guardrail

The native runtime and persistence seam now exist. C6 uses the pinned
`arnold.pipeline.native.runtime.run_native_pipeline` adapter through
`NativePersistenceBackend` and the native-only
`arnold.pipelines.evidence_pack.pipeline:build_pipeline` conformance workflow.
C1 verifies their exact source/API/schema vector at the combined-main SHA; drift
fails closed rather than reopening adapter selection.

## Judgment

Conceptually these epics should fit together tightly, but not merge:

- native composition/platform is about developer authoring and production
  execution;
- boundary contracts are about semantic proof, repairability, and status/audit
  interpretation.

The connection point should be adapter-level: native runtime, audit, checkpoint,
effect-ledger, broker, and worker-lease records feed or reference the shared
execution-attempt ledger and become boundary evidence. The
source-level workflow remains Python-native and readable.

Reusable boundary templates belong in this boundary-contract initiative, not in
`native-platform-followup`. Native platform should emit evidence that can satisfy
template instances such as `ArtifactHandoffBoundary`, `ApprovalBoundary`,
`ValidationBoundary`, `RevisionBoundary`, external-effect boundaries, and
execution-custody boundaries. Pack/versioning and conformance work in native
platform may reference template ids and versions, but the template vocabulary and
compatibility rules stay owned by the boundary-contract layer.
