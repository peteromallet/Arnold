# S2: Contract Foundation And Authority

> Superseded as an executable milestone by C1-C6. Preserved as historical
> checklist material; see the 2026-07-10 corrective reshape decision.

## Outcome

Build the shared boundary vocabulary and apply it to the first producer and
authority surfaces. Contracts, receipts/evidence, semantic findings, reusable
templates, BoundaryTurn promotion, and TransitionWriter authority become one
coherent model without making any single class own execution, observation,
judgment, and repair.

This sprint collapses the detailed briefs:

- `m3-boundary-contract-foundation.md`
- `m4-boundaryturn-template-promotion-integration.md`
- `m5-transition-writer-authority-integration.md`

## Scope

IN:

- Define `BoundaryContract`, `BoundaryReceipt` / `BoundaryEvidence`,
  `SemanticFinding`, `BoundaryGraph`, `BoundaryOutcome`, `EvidenceProfile`,
  `TemporalPolicy`, and `AuthorityRecord`.
- Define required-field profiles for artifact promotion, lifecycle transition,
  reducer, external effect, execution custody, human approval/waiver, graph
  join/fan-out, and external witness boundaries.
- Define reusable typed boundary templates as named required-field profiles:
  `RevisionBoundary`, `ValidationBoundary`, `ArtifactHandoffBoundary`, and
  `ApprovalBoundary`.
- Add registry/provider lookup for contract instances and reusable template ids
  and versions, including compatibility metadata for structural diff and
  deliberate re-pin/upgrade flows.
- Express the S1 prep rule as a contract instance.
- Integrate structured-output template registry entries and BoundaryTurn
  promotion with `BoundaryContract` and reusable templates.
- Align `TransitionDecision` / `TransitionPolicy` with boundary transition
  fields and `AuthorityRecord` for approvals, denials, waivers, overrides,
  revocations, expiry, checked evidence, and stale-input rejection.
- Preserve all detailed acceptance criteria from the three source briefs as the
  sprint checklist.

OUT:

- Migrating every Megaplan phase.
- Chain/PR/cloud custody contracts.
- Making BoundaryTurn or boundary templates own routing.
- Forcing all workflows to implement every field immediately.

## Locked Decisions

- Contracts declare durable effects; they do not execute or observe them.
- Templates declare reusable boundary shapes; they are not runtime control-flow
  objects, route tables, generic stage dispatch, or a product-specific schema
  hierarchy.
- Human approval and waiver are authority records, not booleans.
- Producers/promoters write receipts/evidence; transition writers authorize;
  semantic health verifies; repair/status/auditor consume.
- `state.json` is a projection, not the source of all truth.

## Done Criteria

1. Prep semantic-health can run through the contract/evidence/finding
   vocabulary.
2. Contract and evidence records serialize, look up, and preserve existing
   step-IO, event, transition-evidence, warrant, and manifest/runtime concepts
   where available.
3. Reusable templates document required fields, optional extensions, expected
   evidence, valid outcomes, and semantic-finding failure modes.
4. Template compatibility distinguishes at least one breaking required-field
   change from a non-breaking optional extension.
5. Structured-output promotion records enough evidence to distinguish scratch
   written but not promoted, canonical promoted without receipt, receipt without
   phase result, and model-written wrong path.
6. At least two structured-output paths use reusable boundary templates rather
   than ad hoc phase-local metadata.
7. Transition decisions reference boundary ids and checked evidence refs.
8. Missing, denied, stale, waived, partial, degraded, or irreversible
   authority transitions are structured and visible to operators/auditors.
9. Existing transition, template-boundary, and prep parity tests pass.

## Touchpoints

- `arnold_pipelines/megaplan/cloud/boundary_contracts.py` or equivalent
- `arnold_pipelines/megaplan/template_registry.py`
- `arnold_pipelines/megaplan/orchestration/transition_policy.py`
- `arnold_pipelines/megaplan/orchestration/evidence_contract.py`
- `arnold_pipelines/megaplan/handlers/structured_output.py`
- critique/gate/finalize/execute/review handlers
- `arnold_pipelines/megaplan/auto.py`
- tests under `tests/cloud/` and `tests/arnold/pipeline/`
