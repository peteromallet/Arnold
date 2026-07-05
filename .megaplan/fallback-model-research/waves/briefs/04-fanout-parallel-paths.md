# DeepSeek Audit 04: Fanout and Parallel Paths

Working directory: `/Users/peteromalley/Documents/Arnold`

Read first:
- `.megaplan/fallback-model-research/model-fallback-design.md`
- `.megaplan/fallback-model-research/gpt55-review-synthesis.md`

Task: inspect prep research fanout, parallel critique, parallel review, tiebreakers, worker fanout helpers, and any Hermes/OpenRouter 429 fallback helpers. Find how ordered model fallback should apply without changing topology.

Return:
1. Every fanout/parallel path that creates `WorkerUnit` or pre-resolved `AgentMode`.
2. Whether fallback should happen per unit, per batch, or not in v1.
3. Where fallback chains can be threaded without changing `AgentMode.__iter__`.
4. Existing fallback helpers that should be kept, replaced, or wrapped.
5. Missing observability fields for fanout attempts.
6. Tests needed to prevent topology-changing fallback.

Do not implement code. Keep the final answer under 1200 words.
