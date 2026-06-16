Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent investigating review boundaries: review prompt/schema, parallel review checks, doc review, rework item routing, and strict JSON output.

Scope:
- Read review prompt/handler/orchestration/tests.
- Do not modify files.

Suggested starting files:
- arnold/pipelines/megaplan/prompts/review.py
- arnold/pipelines/megaplan/prompts/review_doc.py
- arnold/pipelines/megaplan/handlers/review.py
- arnold/pipelines/megaplan/orchestration/parallel_review.py
- arnold/pipelines/megaplan/model_seam.py
- tests/test_review.py
- tests/test_parallel_review.py
- tests/test_handle_review_robustness.py

Return a concise report:
1. Boundary verdict: good / risky / broken for MiMo.
2. The strict-output parts most likely to fail.
3. Template-fill or staged-review ideas.
4. Tests that should be added.
