# S2.5 - Boundary Evidence Alignment

## Objective

Preserve the completed S1 and S2 native parity work, then add the narrow
boundary/evidence spine needed before S3 and later reducer/execute/review
milestones build on the front-half topology.

This is a corrective bridge, not a restart of S1 or S2 and not the full
`workflow-boundary-contracts` epic. Native parity still owns source-visible
workflow topology. Boundary contracts own durable proof that a source-visible
boundary completed with coherent artifacts, state/history effects, receipts,
authority records, and external-effect evidence.

## Relationship To Completed Sprints

S1 and S2 are kept. Do not revert them unless an audit proves an incompatible
abstraction that cannot be adapted.

This sprint audits the completed S1/S2 outputs, adds boundary evidence around
the already-moved front-half surface, and gives S3-S7 a shared vocabulary for
new work.

## Scope

In scope:

- Introduce the minimal native-parity vocabulary for `BoundaryContract`,
  `BoundaryReceipt` / `BoundaryEvidence`, `AuthorityRecord`, and
  `SemanticFinding`.
- Define the invariant that `.pypeline` and named native subworkflows own
  product topology, while boundary contracts declare/check durable effects.
- Extend checker row evidence so implemented rows can cite source/policy,
  pure-body evidence, boundary receipts, and authority records.
- Audit the completed S1/S2 runtime slices and add boundary proof for the
  front-half surfaces already moved, especially prep/plan/critique/gate/revise
  artifact promotion, phase results, state/history effects, gate authority,
  debt effects, and revise-loop re-entry.
- Add semantic-health checks for the completed front-half slice that detect
  missing canonical artifact, missing state/history effect, missing receipt,
  stale phase result, or missing authority record where applicable.
- Document the follow-up contract with `workflow-boundary-contracts`: native
  parity builds the Megaplan-facing spine; the follow-up generalizes it for
  chain/cloud custody, repair/status/auditor consumption, and non-Megaplan
  authoring.

Out of scope:

- Reworking S1/S2 topology unless the audit finds a concrete incompatibility.
- Migrating every later phase to boundary contracts.
- Public/non-Megaplan workflow authoring.
- Cloud custody, PR/CI, and chain boundary coverage except as documented future
  consumers.
- Letting `BoundaryContract`, `BoundaryTurn`, semantic health, or repair logic
  decide product routes.

## Work Required

- Add or reserve the native home for the minimal boundary/evidence records used
  by Megaplan parity.
- Wire checker evidence rows to accept durable-boundary evidence refs without
  allowing boundary evidence to replace source-topology proof.
- Add contract instances and receipt/evidence emission for the completed S1/S2
  front-half boundaries.
- Add a failing fixture for source-visible front-half routes with incomplete
  durable effects, proving source topology alone is not enough to mark a
  boundary-crossing row done.
- Add a failing fixture for a boundary/evidence record that tries to smuggle
  routing authority without `.pypeline` source support.
- Update docs/comments near the checker and native builder to state the
  division of authority.

## Verifiable Completion Criterion

- S1 and S2 behavior still pass without reverting the completed implementations.
- Completed front-half runtime slices have source-topology evidence and matching
  durable boundary evidence.
- Checker output can distinguish:
  - missing source topology;
  - source topology present but missing boundary evidence;
  - boundary evidence present but no source-authoritative route;
  - stale or incoherent state/history/receipt evidence.
- S3-S7 briefs can depend on this vocabulary without importing the full
  workflow-boundary follow-up.

## Do Not Close If

- S1 or S2 is restarted or reverted without a specific incompatibility finding.
- Boundary records become a second route table.
- A boundary-crossing row can pass with only `.pypeline` topology and no
  durable effects.
- A row can pass with only receipts/evidence and no source-visible topology.
