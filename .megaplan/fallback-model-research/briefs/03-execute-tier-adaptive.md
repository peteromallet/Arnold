Working directory: /Users/peteromalley/Documents/Arnold

Task: Research all execution paths that consume profile-selected models, especially tiered execute and adaptive critique, to determine how sequential fallback model lists interact with tier_models and phase_model.

User example: partnered-5 has tier_models.execute 4/5 as codex:gpt-5.4 and codex:gpt-5.5. They want list fallback sequentially when the selected model fails.

Inspect at least:
- arnold_pipelines/megaplan/handlers/execute.py
- arnold_pipelines/megaplan/execute/batch.py
- arnold_pipelines/megaplan/_core/dispatch.py
- arnold_pipelines/megaplan/handlers/critique.py
- arnold_pipelines/megaplan/orchestration/parallel_critique.py
- arnold_pipelines/megaplan/_core/worker_fanout.py
- tests/execute and tests/orchestration/profile-related tests.

Return:
- exact call paths where a fallback list must be preserved/resolved
- how tier_models should represent fallback lists
- interaction with phase_model override precedence
- any batch/idempotency concerns
- test plan

Keep final answer under 1000 words. Take a position.
