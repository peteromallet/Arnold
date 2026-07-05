Working directory: /Users/peteromalley/Documents/Arnold

Task: Research how sequential fallback model lists should hook into Megaplan worker execution. We want "try next model" only for infrastructure/provider availability failures such as Codex limits, model timeout, 429/rate-limit, context exhaustion if configured, missing quota, or provider transient failures. We do NOT want fallback for bad model output, validation failures, or a legitimate blocked/task result unless the code already treats it as retryable infra.

Your lens: worker dispatch, worker result/error types, Codex/Shannon/Hermes adapters, timeout handling, retry loops.

Inspect at least:
- arnold_pipelines/megaplan/workers/_impl.py
- arnold_pipelines/megaplan/workers/hermes.py
- arnold_pipelines/megaplan/workers/shannon.py
- arnold_pipelines/megaplan/execute/timeout.py
- arnold_pipelines/megaplan/supervisor/driver.py
- arnold_pipelines/megaplan/auto.py
- tests for codex/hermes adapters and context retry.

Return:
- where fallback wrapper should live
- what failure classes/signals should trigger next fallback
- what should NOT trigger fallback
- how to avoid rerunning non-idempotent work dangerously
- tests that prove behavior

Keep final answer under 1000 words. Take a position.
