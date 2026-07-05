# M5 - Tiebreaker Source Extraction

## Objective

Make tiebreaker a real native subworkflow with visible researcher, challenger,
synthesis, and decision phases.

## Files To Change And Instructions

- Replace `TIEBREAKER_WORKFLOW(...)` as the semantic proof carrier.
- Move decision routing out of tiebreaker runtime/handler code into native
  source and typed outcomes.
- Preserve path-addressed child phase traces.
- Delete or quarantine tiebreaker route/topology metadata in `components.py`.

## Verifiable Completion Criterion

- Source shows researcher, challenger, synthesis, and decision phases.
- Tiebreaker proceed/iterate/escalate/replan scenarios pass.
- Tiebreaker replan rejoins the normal planning/finalize path rather than a
  one-off branch.
- Handler/runtime tiebreaker code is pure phase body or quarantined legacy.

