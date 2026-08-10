Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 9 focus: deletion attack.

Assume M6 is green. How could packaging still ship deleted code, stale package data, stale `py.typed`, top-level compatibility packages, entrypoints, or namespace package conflicts in wheel/sdist even if source-tree scans pass?

Return:
- top ways packaging deletion could falsely pass
- exact gates/plan edits needed
- wheel/sdist evidence needed for confidence

Use judgement. Return under 900 words.
