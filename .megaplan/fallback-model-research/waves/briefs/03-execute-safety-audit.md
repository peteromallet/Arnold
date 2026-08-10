# DeepSeek Audit 03: Execute Safety Audit

Working directory: `/Users/peteromalley/Documents/Arnold`

Read first:
- `.megaplan/fallback-model-research/model-fallback-design.md`
- `.megaplan/fallback-model-research/gpt55-review-synthesis.md`

Task: inspect execute orchestration, batch execution, timeout recovery, merge/evidence handling, and any tree mutation boundaries. Determine exactly when automatic fallback from one execute model to another is safe.

Return:
1. The execute call graph from route selection to worker invocation to result merge.
2. The earliest and latest safe points for fallback.
3. Signals that prove no accepted output/no mutation happened.
4. Signals that must permanently block fallback.
5. A v1 policy recommendation: include execute fallback now or defer it, and why.
6. Specific tests needed for `execute` and `loop_execute`.

Do not implement code. Be conservative and cite files/functions. Keep the final answer under 1200 words.
