Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 9 focus: deletion attack.

Assume each milestone branch passed alone. How could the final merge result still reintroduce deleted surfaces, stale docs, stale generated artifacts, stale tests, or inconsistent manifest versions? Attack merge order, branch/worktree leftovers, generated outputs, and final installed-wheel conformance.

Return:
- top ways final merge could falsely pass
- exact gates/plan edits needed
- evidence needed to prove the final merged state is the actual clean-break state

Use judgement. Return under 900 words.
