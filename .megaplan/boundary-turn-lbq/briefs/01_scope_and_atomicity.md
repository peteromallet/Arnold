Working directory: /Users/peteromalley/Documents/Arnold

Question 1: Does the BoundaryTurn plan draw the right scope boundary between plan-dir artifact promotion and external target-repository mutations?

Context:
- Read docs/arnold/megaplan-boundary-turn-design.md.
- Inspect execute-related code enough to verify whether execute can ever be atomic.
- Relevant files: arnold_pipelines/megaplan/handlers/execute.py, arnold_pipelines/megaplan/execute/*.py, arnold_pipelines/megaplan/handlers/structured_output.py.

Provisional answer to challenge:
BoundaryTurn should govern model-output capture and plan-dir canonical promotion only. It should not promise rollback for external workspace mutations. Execute should record external side effects, evidence, and resumable checkpoints before aggregate promotion.

Return <600 words:
1. Verdict: sound / flawed / incomplete.
2. What functionality would be lost if this scope is wrong?
3. Specific design-doc edits or acceptance tests.
