# DeepSeek Audit 01: Scalar Contract Inventory

Working directory: `/Users/peteromalley/Documents/Arnold`

Read first:
- `.megaplan/fallback-model-research/model-fallback-design.md`
- `.megaplan/fallback-model-research/gpt55-review-synthesis.md`

Task: inspect the repo for every place Megaplan assumes a model route is a single scalar string. Focus on real implementation touchpoints for profile-level and tier-level ordered fallback chains.

Return:
1. A ranked list of scalar contracts that must change, with file/function references.
2. Which contracts should stay scalar externally and decode internally.
3. Which contracts can safely accept `FallbackSpecChain` or `str | FallbackSpecChain`.
4. Any surfaces missing from the current design doc.
5. A minimal implementation order that avoids breaking existing single-string behavior.

Do not implement code. Be concrete and adversarial. Keep the final answer under 1200 words.
