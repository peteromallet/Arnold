Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 7 focus: semantic parity for durable state.

Question: Does the plan guarantee that resume/replay behavior lines up with the final manifest version for every pipeline/run that survives the migration, including old `.megaplan` state, locks, artifacts, receipts, nested runs, event journals, and future manifest hash/topology changes?

Look for ambiguity in state authority, migration exclusions, stale locks, replay cursors, projections, and old mutable state files. Return:
- confidence score 0-100
- top state/resume risks
- exact plan edits needed
- what should be tested before deletion

Use judgement. Return under 900 words.
