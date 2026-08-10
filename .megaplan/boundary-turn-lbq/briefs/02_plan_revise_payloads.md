Working directory: /Users/peteromalley/Documents/Arnold

Question 2: Should plan and revise become Markdown draft boundaries, or must they first remain structured payload boundaries containing Markdown plus metadata?

Context:
- Read docs/arnold/megaplan-boundary-turn-design.md.
- Inspect plan/revise handlers and prompts.
- Relevant files: arnold_pipelines/megaplan/handlers/plan.py, arnold_pipelines/megaplan/prompts/planning.py, arnold_pipelines/megaplan/prompts/critique.py, arnold_pipelines/megaplan/model_seam.py.

Provisional answer to challenge:
Do not switch directly to Markdown-only drafts. Current plan/revise carry structured metadata such as questions, assumptions, success criteria, test blast radius, plan meta, deltas, imported criteria, and flag updates. BoundaryTurn should wrap existing structured payloads first.

Return <600 words:
1. Verdict.
2. Metadata or behavior at risk.
3. Specific design-doc edits or acceptance tests.
