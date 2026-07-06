# S3 - Tiebreaker And Replan Native Flow

## Objective

Make tiebreaker a real native subworkflow with visible researcher, challenger,
synthesis, and decision phases, then make replan rejoin the normal
planning/finalize path instead of living as a one-off handler branch.

## Legacy 10-Sprint Source Mapping

- Absorbs `m5-tiebreaker-source-extraction.md`.
- Completes the tiebreaker/replan edges implied by S2.

## Work Required

- Replace `TIEBREAKER_WORKFLOW(...)` as the semantic proof carrier.
- Move tiebreaker proceed/iterate/escalate/replan routing out of runtime and
  handler code into native source and typed outcomes.
- Preserve path-addressed child traces for researcher, challenger, synthesis,
  and decision.
- Declare child/reducer boundary evidence for researcher, challenger,
  synthesis, and decision outputs, plus the replan authority record and parent
  rejoin promotion point.
- Make human "replan" reset the right loop state and rejoin the ordinary
  planning/finalize path.
- Delete or quarantine tiebreaker route/topology metadata in `components.py` and
  any handler-owned tiebreaker dispatch.
- Extend checker row-anchor rules so tiebreaker rows require visible
  subworkflow/fanout/decision shape, not a single call.

## Verifiable Completion Criterion

- Source shows researcher, challenger, synthesis, and decision phases.
- Tiebreaker proceed, iterate, escalate, and replan scenarios pass.
- Replan rejoins normal planning/finalize flow and resets/reconciles loop state.
- Handler/runtime tiebreaker code is pure phase body or quarantined legacy.
- Dead-delete mutation coverage proves old tiebreaker carriers do not route the
  corrected flow.
- Boundary evidence proves child outputs did not advance parent state directly
  and that reducer/decision promotion owned the parent-visible effect.

## Do Not Close If

- Tiebreaker source is a cosmetic wrapper around old runtime dispatch.
- Replan remains a terminal or special branch that bypasses normal planning and
  finalization semantics.
- Child receipts, reducer receipts, or semantic-health findings become the
  route authority instead of checked source-visible tiebreaker outcomes.
