Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 7 focus: whether the planned tests prove semantic parity.

Question: Are the planned golden, parity, characterization, fake-run, live-smoke, installed-wheel, import-boundary, generated-artifact, and deletion gates strong enough to prove the final pipeline versions line up with the intended manifest semantics?

Look for tests that are too snapshot-shaped, too editable-mode-only, too narrow, or vulnerable to updating goldens for convenience. Return:
- confidence score 0-100
- top evidence weaknesses
- exact plan edits needed
- one concise proposed test matrix

Use judgement. Return under 900 words.
