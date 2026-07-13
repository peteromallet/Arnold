# C6: Non-Megaplan Conformance And Rollout Evidence

## Outcome

The pinned `arnold.pipeline.native.runtime.run_native_pipeline` adapter through
`NativePersistenceBackend` is a required adopter of the
same kernel execution-attempt ledger and boundary contract surface. Megaplan
remains fully compatible, and the epic finishes with reproducible universal
query/replay/audit/conformance evidence for every declared supported surface
rather than enabling broad production dispatch.

## Entry Gate

C5 profile/template compatibility is stable and all Megaplan legacy/current
fixtures pass. `arnold.pipelines.evidence_pack.pipeline:build_pipeline`, API
`1.0`, and the pinned native persistence/runtime symbols exist at the C1 source
and schema version vector; drift fails closed.

## Scope

IN:

- Add a public or semi-public boundary authoring/discovery API over the existing
  shared vocabulary and versioned template registry. Workflows using a declared
  supported runtime cannot bypass ledgering or contract discovery; workflows
  wholly outside the support manifest remain genuinely out of scope.
- Use the real native-only `evidence_pack` workflow, extending only its
  conformance fixture as needed, with fan-out, peer
  join/fan-in, external witness, partial or conditional acceptance, authority
  evidence, and separate staleness/deadline/observation-sufficiency/expiry
  policy.
- Use at least one authority-bearing template and one artifact/evidence-bearing
  template.
- Prove runtime receipts/evidence can satisfy contracts without embedding
  Megaplan phase/state conventions in the generic core.
- Prove every native step/attempt records start, completion/failure, retry,
  suspension/resume, and cancellation where exercised, with immutable identity/
  provenance/order and retained or policy-governed references for inputs,
  outputs/results, verdicts, state deltas, artifacts, and external effects.
- Emit clear diagnostics for missing declarations, undeclared durable effects,
  incompatible template versions, missing required fields, stale authority
  refs, and unsupported native-only metadata.
- Run the complete Megaplan legacy/current, producer, cloud custody, chain/PR,
  repair/verification, audit, template, and non-Megaplan conformance suite.
- Document authoring, template selection/extension/versioning, authority
  adapters, evidence profiles, findings, exemptions, migration, and rollout
  modes.
- Produce a final evidence manifest listing covered boundaries, explicit
  out-of-scope systems, compatibility versions, test commands/results, query/
  replay/audit proof, and remaining non-authoritative historical readers. It
  must show zero exemptions or bypasses for supported producers/consumers.

OUT:

- Migration of workflows wholly outside the declared supported runtimes.
- Making every workflow cloud-repairable.
- Production-wide dispatch/autonomy enablement.
- A generic workflow builder, route engine, status reducer, or repair system.
- Hiding Megaplan-only semantics in the generic contract.

## Locked Ownership

- Native workflow source owns graph/control-flow semantics.
- WBC owns contract/profile/template authoring, the shared attempt ledger, and
  semantic findings for supported runtimes.
- Run Authority owns authority mechanics when the workflow adopts them.
- Maintenance-owned observation, transition, repair, status, and audit services
  are reused only through explicit adapters.
- Conformance executes automatically in isolated audit-only/fake/fenced mode;
  production dispatch is a separate policy decision and is not a milestone
  gate.

## Compatibility Fixtures

- real native graph with fan-out/fan-in and partial acceptance;
- external witness with provenance/trust and observation window;
- approval/waiver with current and stale authority refs;
- producer missing a required template field;
- consumer expecting an incompatible template version;
- undeclared durable output and native-only metadata bypass attempt;
- existing Megaplan legacy and combined-current fixture corpus.

## Required Acceptance Evidence

1. The non-Megaplan workflow is discovered, evaluated, and diagnosed through
   the same generic contract/profile/template surface as Megaplan adapters.
2. Graph, external witness, partial acceptance, authority, and temporal policies
   are exercised end to end.
3. Missing contracts, undeclared effects, missing fields, stale authority, and
   incompatible versions fail with stable diagnostics and no mutation.
4. Existing Megaplan contracts and all C1-C5 fixtures remain green.
5. Conformance execution is deterministic for immutable inputs and records the
   source/runtime/template version vector.
6. Documentation and final evidence manifest identify every exemption and
   remaining compatibility surface with an owner and follow-up condition.
7. No production dispatch/autonomy setting is enabled by this milestone.
8. A machine-generated coverage check joins the runtime registry, step catalog,
   support manifest, and observed conformance traces and reports zero missing or
   compatibility-only supported steps.
9. Fault injection proves native and Megaplan adapters both fail closed before
   dispatch on start-store failure and expose, quarantine, and reconcile
   terminal/result persistence failure without false success.
10. Authorized query reconstructs complete causal attempt histories; replay
    reproduces deterministic projections from retained data; audit export
    verifies ordering, provenance, authority, retention/redaction, and object
    availability for golden cross-runtime traces.

## Automatic Failure Conditions

Fail validation and abort through `stop_chain` if the example requires Megaplan-only fields in core, if discovery changes
workflow routing, if diagnostics mutate runtime state, if generic conformance
bypasses prerequisite authority/transition contracts, if any supported producer
retains an opt-out/exemption/hash-only result path, or if the full Megaplan
compatibility suite regresses.

The human-review boundary uses a pinned signed fixture decision and the
external-witness paths use fakes or fenced dry runs. No conformance case may
pause for a person or issue an unfenced production effect.

## Likely Touchpoints

- generic workflow boundary authoring/discovery API
- native workflow/runtime evidence adapters and conformance fixture
- shared boundary/template diagnostics
- Megaplan adapter compatibility suite
- authoring, migration, and final evidence documentation
