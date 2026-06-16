Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent investigating whether this repository's megaplan plan/revise boundaries are friendly to fast/open models.

Scope:
- Read the plan/revise prompt and handler paths.
- Focus on strictness, output shape, recovery, and whether a model can reasonably comply.
- Do not modify files.

Suggested starting files:
- arnold/pipelines/megaplan/prompts/planning.py
- arnold/pipelines/megaplan/prompts/finalize.py only if needed for contrast
- arnold/pipelines/megaplan/handlers/plan.py
- arnold/pipelines/megaplan/handlers/critique.py, specifically handle_revise
- arnold/pipelines/megaplan/workers/_impl.py output parsing paths
- tests/test_prompts.py

Return a concise report:
1. Boundary verdict: good / risky / broken for MiMo.
2. Concrete failure modes likely for MiMo.
3. Small changes that would make it easier, especially template-fill or staged-output ideas.
4. Any tests that should be added.
