Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent investigating the finalize boundary.

Context:
- MiMo repeatedly failed finalize by emitting malformed output, unrelated prose/code, or valid-ish JSON without a non-empty `tasks` list.
- Recent local changes clarified doc-mode finalize prompt and added MiMo model-family budget support.

Scope:
- Read finalize prompt/schema/handler/recovery/doc-mode assembly.
- Do not modify files.

Suggested starting files:
- arnold/pipelines/megaplan/prompts/finalize.py
- arnold/pipelines/megaplan/handlers/finalize.py
- arnold/pipelines/megaplan/runtime/doc_assembly.py
- arnold/pipelines/megaplan/model_seam.py
- arnold/pipelines/megaplan/schemas/runtime.py
- tests/test_finalize.py
- tests/test_doc_mode.py
- tests/test_doc_assembly.py
- tests/test_prompts.py

Return a concise report:
1. Boundary verdict: good / risky / broken for MiMo.
2. Whether template-fill can make finalize reliable; be specific.
3. Whether finalize should be split into outline -> structured conversion.
4. Any schema/prompt contradictions remaining.
5. Tests that should be added.
