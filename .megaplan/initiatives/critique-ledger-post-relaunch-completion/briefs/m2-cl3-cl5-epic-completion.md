# F4 — Advance CL3 through CL5 and complete the v3 epic

## Outcome

Advance every remaining v3 milestone from exact predecessor completion
manifests until the Critique Ledger implementation epic is genuinely complete.

## Scope

Implements T6.6 across CL3, CL4 and CL5, including ordinary critique, execution,
publication and independent boundary verification for each milestone.

## Locked decisions

- Successor admission consumes content-addressed predecessor manifests through
  raw Run Authority predicates; projections cannot grant.
- Check each milestone at first transition, 10–15 minutes, every phase boundary
  and before authority expansion.
- Any UNKNOWN, stale fence, missing receipt or incomplete critic set stops the
  chain with one deduplicated actionable incident; it does not spin or notify
  repeatedly.

## Bound inputs

The T6.2 handoff supplies frozen CL3-CL5 brief hashes, completed/unresolved task
IDs and predecessor-manifest requirements. F4 derives work only from that
content-addressed residual set; any mismatch is binding drift and fails closed.

## Constraints

No copied v2 state, recycled plan/branch/PR identity, manual cursor edit,
unowned repair or duplicated effect.

## Done criteria

- CL3–CL5 each have accepted predecessor admission, exact critique, execution,
  publication and completion receipts.
- Real implementation commits are current and dependency-closed.
- The final v3 completion manifest and proof map are reproducible.
- Independent review confirms no false completion or stale/duplicate writer.
- Executed CL3-CL5 task IDs and brief hashes exactly match the frozen T6.2
  residual-work manifest.

## Touchpoints

The v3 milestone briefs/spec, chain owner records, implementation branches/PRs,
completion manifests and `evidence/critique-ledger-recovery/T6.6/`.

## Anti-scope

Do not deploy the product or mark the incident resolved in this milestone.
