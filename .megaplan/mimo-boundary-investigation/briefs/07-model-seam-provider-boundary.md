Working directory: /Users/peteromalley/Documents/megaplan

You are a MiMo subagent investigating model-seam/provider boundaries for adding new Hermes providers like MiMo.

Context:
- MiMo needed provider/key-pool/preflight support.
- It also needed model-family budget support in arnold/pipeline/model_seam.py.

Scope:
- Read provider resolution, key pool, preflight, model seam, and tests.
- Do not modify files.

Suggested starting files:
- arnold/pipelines/megaplan/runtime/key_pool.py
- arnold/pipelines/megaplan/_pipeline/preflight.py
- arnold/pipelines/megaplan/cloud/preflight.py
- arnold/agent/adapters/deepseek.py
- arnold/agent/providers/pool.py
- arnold/pipeline/model_seam.py
- arnold/pipelines/megaplan/model_seam.py
- tests/test_key_pool_claude_block.py
- tests/test_cloud_preflight.py
- tests/arnold/pipeline/test_model_seam_neutral.py
- tests/arnold/agent/test_deepseek_adapter.py

Return a concise report:
1. Boundary verdict: good / risky / broken for new providers.
2. All places a new Hermes provider must be registered today.
3. Missing central abstraction, if any.
4. Tests that should be added.
