# DeepSeek Audit 06: Test Plan and Fixtures

Working directory: `/Users/peteromalley/Documents/Arnold`

Read first:
- `.megaplan/fallback-model-research/model-fallback-design.md`
- `.megaplan/fallback-model-research/gpt55-review-synthesis.md`

Task: inspect existing tests around profiles, worker dispatch, execute routing, prep/critique fanout, state resume, cloud preflight, and chain specs. Produce a focused test plan for implementing ordered model fallback without over-testing irrelevant internals.

Return:
1. Existing test files to extend, with exact proposed test names.
2. New fixtures/helpers needed for fallback chains and failure simulation.
3. A minimal red/green sequence for implementation.
4. The highest-value characterization tests to write before editing production code.
5. Tests that should explicitly prove single-string behavior is unchanged.
6. Any likely brittle tests to avoid.

Do not implement code. Keep the final answer under 1200 words.
