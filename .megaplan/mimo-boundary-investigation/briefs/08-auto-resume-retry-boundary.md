Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent investigating auto/resume/retry boundaries after malformed model output.

Context:
- A MiMo auto run retried finalize many times because the state stayed `gated` and finalize kept failing malformed output.
- We want to know whether auto should classify repeated malformed structured-output failures differently.

Scope:
- Read auto driver, resume cursor, phase failure recording, status, and tests.
- Do not modify files.

Suggested starting files:
- arnold/pipelines/megaplan/auto.py
- arnold/pipelines/megaplan/handlers/shared.py
- arnold/pipelines/megaplan/_core/io.py
- arnold/pipelines/megaplan/planning/state.py
- arnold/pipelines/megaplan/model_seam.py
- tests/test_pipeline_run_cli.py
- tests/test_pipeline_resume_cursor.py
- tests/test_lifecycle_states.py
- tests/characterization/auto_drive_corpus/*.json

Return a concise report:
1. Boundary verdict: good / risky / broken for fast models with malformed outputs.
2. Whether auto should stop earlier or switch strategy after repeated malformed JSON.
3. What state/failure metadata is missing to diagnose provider-specific failures.
4. Tests that should be added.
