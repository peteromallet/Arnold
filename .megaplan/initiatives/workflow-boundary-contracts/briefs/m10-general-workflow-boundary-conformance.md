# M10: General Workflow Boundary Conformance

> Superseded as an executable milestone by C1-C6. Its opt-in adoption language
> does not apply to the runtimes declared supported by the corrective chain;
> C6 requires their universal ledger/conformance adoption.

## Outcome

New Arnold workflows can define boundaries using the same contract vocabulary and
automatically gain promotion verification, transition checks, semantic-health
status, and repair/audit integration where available.

Megaplan is the flagship adopter, not the only implementation.

## Scope

IN:

- Add public or semi-public boundary contract authoring surface for workflows.
- Add public or semi-public reusable template authoring/selection surface for
  workflows, so common boundaries can opt into `RevisionBoundary`,
  `ValidationBoundary`, `ArtifactHandoffBoundary`, `ApprovalBoundary`, or a
  custom template without bypassing the core contract vocabulary.
- Add conformance tests for a non-Megaplan workflow boundary.
- Define minimal required fields for:
  - pure artifact boundary;
  - state transition boundary;
  - external effect boundary;
  - reducer boundary;
  - authority-increasing transition boundary.
- Add an example graph-shaped workflow that includes:
  - fan-out to multiple producers or vendors;
  - a peer join/fan-in boundary;
  - an external witness;
  - a partial or conditional acceptance outcome;
  - an authority record;
  - a temporal policy that separates staleness, deadline, and observation
    sufficiency.
- Add docs and examples.
- Ensure missing contract coverage is visible in diagnostics.
- Ensure template compatibility diagnostics are visible when a workflow
  producer and consumer disagree about a template id/version, required field,
  or accepted extension profile.

OUT:

- Forcing all existing workflows to migrate in one pass.
- Making every workflow cloud-repairable immediately.

## Locked Decisions

- No boundary without a contract once the workflow opts into conformance.
- Workflows can start with audit-only findings before dispatch integration.
- Megaplan-specific details stay in Megaplan adapters.
- Domain-specific concepts belong in adapters that map onto generic primitives;
  the core should not grow `clinical_safety`, `public_deliberation`,
  `DAW_null_test`, or similar profession-specific families.
- Reusable templates remain selectable profiles over the core contract model.
  A workflow may define a custom template, but every boundary on a declared
  supported runtime must use the shared attempt ledger and declare required
  fields, extension policy, and compatibility semantics.

## Done Criteria

1. A non-Megaplan graph-shaped test workflow defines boundary contracts and gets
   semantic verification.
2. Contract docs explain how to add new boundaries.
3. Contract docs explain how to select, extend, and version reusable templates.
4. The non-Megaplan conformance example uses at least two reusable boundary
   templates, including one authority-bearing template such as
   `ApprovalBoundary` and one artifact/evidence-bearing template such as
   `ArtifactHandoffBoundary` or `ValidationBoundary`.
5. Conformance tests fail when a new boundary writes artifacts without declared
   durable effects.
6. Conformance tests fail when a producer emits a reusable template instance
   missing required fields, or when a consumer expects an incompatible template
   version.
7. Conformance tests fail when an equivalent boundary is implemented with
   native-platform-only metadata instead of a shared boundary contract profile.
8. Existing Megaplan contracts remain valid through the generic surface.
9. Adapters can express physical/external evidence and partial acceptance
   without changing core schema.

## Touchpoints

- Arnold workflow/runtime contract modules
- workflow conformance tests
- Megaplan boundary-contract adapter
- docs
