Working directory: /Users/peteromalley/Documents/Arnold

Question 7: What is the correct BoundaryTurn shape for execute batches and reducer aggregation?

Context:
- Read docs/arnold/megaplan-boundary-turn-design.md.
- Inspect execute batching, merge/reducer, quality, timeout, and blocked-task paths.
- Relevant files: arnold_pipelines/megaplan/handlers/execute.py, arnold_pipelines/megaplan/execute/batch.py, arnold_pipelines/megaplan/execute/merge.py, arnold_pipelines/megaplan/execute/quality.py, arnold_pipelines/megaplan/prompts/execute.py.

Provisional answer to challenge:
Execute should use child BoundaryTurns for execution_batch_N artifacts and a reducer BoundaryTurn for execution.json. It must record external side effects and preserve stable batch numbering, resume, tier routing, approval gates, preflight, timeout recovery, blocked-task handling, quality gates, finalize.json updates, audits, traces, and skipped-review stubs.

Return <600 words:
1. Verdict.
2. Execute behavior at risk.
3. Specific design-doc edits or acceptance tests.
