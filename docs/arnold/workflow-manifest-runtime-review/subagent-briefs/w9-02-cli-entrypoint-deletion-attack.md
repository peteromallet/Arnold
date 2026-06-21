Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 9 focus: deletion attack.

Assume M6 is green. How could old CLI/entrypoint behavior still survive through `pyproject.toml`, `arnold/cli/__init__.py`, package `__main__`, lazy dispatch, shell completions, parser snapshots, help text, or operator scripts?

Return:
- top ways CLI deletion could falsely pass
- exact gates/plan edits needed
- what evidence would prove only the final event-backed CLI remains

Use judgement. Return under 900 words.
