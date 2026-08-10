Working directory: /Users/peteromalley/Documents/Arnold

Question 4: Can BoundaryTurn own next-route selection, or must routing remain a richer workflow/auto-driver policy surface?

Context:
- Read docs/arnold/megaplan-boundary-turn-design.md.
- Inspect workflow graph, transition policy, auto-driver, and handlers.
- Relevant files: arnold_pipelines/megaplan/_core/workflow.py, arnold_pipelines/megaplan/_core/workflow_data.py, arnold_pipelines/megaplan/auto.py, arnold_pipelines/megaplan/orchestration/transition_policy.py, arnold_pipelines/megaplan/handlers/gate.py, arnold_pipelines/megaplan/handlers/review.py.

Provisional answer to challenge:
BoundaryTurn can return a validated workflow transition proposal/result, but it should not flatten routing into a generic string. Gate/review/execute routing depends on robustness, blocking classes, phase_result, auto-driver recovery, and policy-specific state transitions.

Return <600 words:
1. Verdict.
2. Routing behavior at risk.
3. Specific design-doc edits or acceptance tests.
