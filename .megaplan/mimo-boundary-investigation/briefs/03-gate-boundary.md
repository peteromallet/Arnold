Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent investigating the gate boundary: gate signals input size, prompt shape, schema, and recovery.

Context:
- A full-robustness MiMo run reached gate and hit a model input budget error: about 88k prompt tokens > 32k route budget.
- A light run skips full gate and uses a minimal gate artifact.

Scope:
- Read gate prompt/handler/signals/tests.
- Do not modify files.

Suggested starting files:
- arnold/pipelines/megaplan/prompts/gate.py
- arnold/pipelines/megaplan/handlers/gate.py
- arnold/pipelines/megaplan/orchestration/gate_signals.py
- arnold/pipelines/megaplan/orchestration/gate_checks.py
- arnold/pipelines/megaplan/model_seam.py
- tests/test_gate.py
- tests/test_pipeline_planning_parity.py

Return a concise report:
1. Boundary verdict: good / risky / broken for MiMo.
2. Why the prompt can blow budget and what should be compacted first.
3. Whether a smaller decision template can replace freeform gate JSON generation.
4. Tests that should be added.
