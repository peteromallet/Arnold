Working directory: /Users/peteromalley/Documents/Arnold

Question 3: How should BoundaryTurn interact with Hermes/model-seam recovery paths without regressing flaky-provider behavior?

Context:
- Read docs/arnold/megaplan-boundary-turn-design.md.
- Inspect worker and model seam recovery behavior.
- Relevant files: arnold_pipelines/megaplan/workers/hermes.py, arnold_pipelines/megaplan/model_seam.py, arnold_pipelines/megaplan/handlers/structured_output.py, arnold_pipelines/megaplan/template_registry.py.

Provisional answer to challenge:
BoundaryTurn should use explicit fallback policies: strict_file_fill, legacy_recovery, inline_only. Existing phases should start with legacy_recovery, then tighten per phase only after tests prove provider behavior is preserved.

Return <600 words:
1. Verdict.
2. Recovery behavior that must remain.
3. Specific design-doc edits or acceptance tests.
