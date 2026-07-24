Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent cross-checking the full phase topology for template-fill support.

Question to answer:
- List every model-produced structured JSON boundary in the normal megaplan workflow, including substeps such as critique_evaluator, parallel critique units, parallel review units, batch execute, compact review, repair prompts, tiebreaker, prep/distill, or feedback.
- Which should be in the first "all structured templates" sprint, and which should be deferred?

Suggested files:
- arnold/pipelines/megaplan/prompts/__init__.py
- arnold/pipelines/megaplan/handlers/*.py
- arnold/pipelines/megaplan/orchestration/parallel_critique.py
- arnold/pipelines/megaplan/orchestration/parallel_review.py
- arnold/pipelines/megaplan/workers/_impl.py
- arnold/pipelines/megaplan/model_seam.py
- arnold/pipelines/megaplan/step_contracts.py

Return:
1. Full list of structured model output boundaries.
2. First-sprint include/defer recommendation.
3. Template path naming convention.
4. Biggest unknowns.
