Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 9 focus: deletion attack.

Assume M6 has been implemented and reports green. How could old public import surfaces still survive anyway? Attack `import megaplan`, `arnold.pipelines.megaplan`, `arnold.pipeline`, `arnold.runtime`, `_pipeline`, re-export `__init__` files, type stubs, namespace packages, dynamic import shims, and installed-wheel behavior.

Return:
- top ways deletion could falsely pass
- exact gates/plan edits needed
- what evidence would make you confident the old import surface is truly gone

Use judgement. Return under 900 words.
