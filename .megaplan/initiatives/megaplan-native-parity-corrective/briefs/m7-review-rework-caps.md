# M7 - Review Rework Caps

## Objective

Extract review fanout/fanin, review outcome routing, rework cycle, retry caps,
force-proceed, blocked outcomes, and human verification.

## Files To Change And Instructions

- Replace `REVIEW_PANEL_WORKFLOW(...)` as the semantic proof carrier.
- Make review fanout/fanin and reducer visible in source.
- Replace revise-and-return behavior with an explicit execute/review/rework
  cycle.
- Move review cap and blocked/force-proceed routing into source or declared
  policy.
- Quarantine or delete review component metadata for implemented rows.

## Verifiable Completion Criterion

- Review rework visibly cycles back through execute/review.
- Scenarios pass:
  - review needs rework, scoped re-execute, re-review passes;
  - blocking review cap blocks;
  - advisory-only review cap force-proceeds.
- Semantic checker rejects single-handler review fanout and handler-owned cap
  thresholds.

