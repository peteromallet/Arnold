# S5 - Review, Rework, Finalize

## Objective

Extract review fanout/fanin, review outcome routing, rework cycle, retry caps,
force-proceed, blocked outcomes, human verification, and finalize fallback
semantics into canonical source and declared policy.

## Legacy 10-Sprint Source Mapping

- Absorbs `m7-review-rework-caps.md`.
- Pulls finalize fallback/no-review closure from the final end-state scope so
  it is proven before compatibility collapse.

## Work Required

- Replace `REVIEW_PANEL_WORKFLOW(...)` as the semantic proof carrier.
- Make review fanout/fanin and reducer visible in source.
- Replace revise-and-return behavior with an explicit execute/review/rework
  cycle.
- Move review cap and blocked/force-proceed routing into source or declared
  policy.
- Make human verification gates declared with authority requirements.
- Make finalize baseline fallback and task shaping/scrubbing boundaries clear:
  phase-local shaping may stay in handlers, fallback routing must be visible.
- Declare boundary contracts for review child outputs, fanin/reducer
  promotion, rework-cycle effects, cap authority decisions, human verification
  records, finalize canonical artifacts, finalize fallback, and final state
  projection.
- Quarantine or delete review/finalize component metadata for implemented rows.

## Verifiable Completion Criterion

- Review rework visibly cycles back through execute/review.
- Scenarios pass:
  - review needs rework, scoped re-execute, re-review passes;
  - blocking review cap blocks;
  - advisory-only review cap force-proceeds;
  - human verification suspension/resume behaves through declared gates;
  - finalize fallback follows visible routing.
- Semantic checker rejects single-handler review fanout, handler-owned cap
  thresholds, and hidden finalize fallback routing.
- Semantic-health tests reject review/finalize source topology with missing
  child/reducer receipts, missing human authority, stale finalize artifacts, or
  final state/history projection drift.

## Do Not Close If

- Review or finalize routing is still inferred from state fields written by
  handlers.
- No-review terminal behavior depends on handler/private robustness overrides
  instead of source/policy-visible branches.
- Review/finalize boundary evidence can mark completion without the native
  reducer/fallback route being source-visible.
