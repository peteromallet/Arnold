Working directory: /Users/peteromalley/Documents/Arnold

Question 6: Does the BoundaryTurn plan preserve finalize behavior while standardizing model output promotion?

Context:
- Read docs/arnold/megaplan-boundary-turn-design.md.
- Inspect finalize handler and prompt.
- Relevant files: arnold_pipelines/megaplan/handlers/finalize.py, arnold_pipelines/megaplan/prompts/finalize.py, arnold_pipelines/megaplan/handlers/structured_output.py.

Provisional answer to challenge:
Finalize can be an early high-value BoundaryTurn phase because it already uses finalize_output.json. But the promotion must preserve finalize.json, final.md, contract.json, user_actions.md, finalize_snapshot.json, capability claims, baseline/cache behavior, validation computation, and finalize-to-revise feedback artifacts.

Return <600 words:
1. Verdict.
2. Finalize behavior at risk.
3. Specific design-doc edits or acceptance tests.
