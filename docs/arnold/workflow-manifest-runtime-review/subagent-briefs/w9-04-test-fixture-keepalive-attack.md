Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 9 focus: deletion attack.

Assume M6 is green. How could tests, fixtures, characterization files, oracle traces, root `test_*.py`, xfails, skips, or whitelist rows keep old native/runtime semantics alive or hide missing parity after deletion?

Return:
- top ways test/fixture deletion could falsely pass
- exact gates/plan edits needed
- evidence needed before deleting old tests or old runtime code

Use judgement. Return under 900 words.
