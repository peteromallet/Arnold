# DeepSeek Audit 02: Failure Classification Matrix

Working directory: `/Users/peteromalley/Documents/Arnold`

Read first:
- `.megaplan/fallback-model-research/model-fallback-design.md`
- `.megaplan/fallback-model-research/gpt55-review-synthesis.md`

Task: inspect worker dispatch, provider adapters, `CliError` usage, Codex/Claude/Hermes error handling, and existing ambient fallback code. Produce a practical retryability matrix for sequential model fallback.

Questions to answer:
1. What concrete error codes/classes/messages currently exist for timeout, stall, auth, rate limit, context, malformed output, schema failure, blocked result, and execute failure?
2. Which should trigger `RETRY_NEXT_SPEC`, which should not, and which need new normalized error codes?
3. Where should the classifier live and what inputs must it receive?
4. How should it distinguish same-provider auth/config failure from independent-provider quota/rate-limit failure?
5. What tests should pin the matrix?

Do not implement code. Return actionable findings with file/function references. Keep the final answer under 1200 words.
