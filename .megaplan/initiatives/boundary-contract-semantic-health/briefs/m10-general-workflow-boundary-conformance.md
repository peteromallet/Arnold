# M10: General Workflow Boundary Conformance

## Outcome

New Arnold workflows can define boundaries using the same contract vocabulary and
automatically gain promotion verification, transition checks, semantic-health
status, and repair/audit integration where available.

Megaplan is the flagship adopter, not the only implementation.

## Scope

IN:

- Add public or semi-public boundary contract authoring surface for workflows.
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

## Done Criteria

1. A non-Megaplan graph-shaped test workflow defines boundary contracts and gets
   semantic verification.
2. Contract docs explain how to add new boundaries.
3. Conformance tests fail when a new boundary writes artifacts without declared
   durable effects.
4. Existing Megaplan contracts remain valid through the generic surface.
5. Adapters can express physical/external evidence and partial acceptance
   without changing core schema.

## Touchpoints

- Arnold workflow/runtime contract modules
- workflow conformance tests
- Megaplan boundary-contract adapter
- docs
