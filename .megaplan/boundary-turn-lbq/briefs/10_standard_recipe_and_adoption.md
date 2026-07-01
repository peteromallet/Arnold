Working directory: /Users/peteromalley/Documents/Arnold

Question 10: Does BoundaryTurn provide a standard recipe other pipeline authors can follow without overfitting to Megaplan?

Context:
- Read docs/arnold/megaplan-boundary-turn-design.md.
- Inspect StepContract/template registry/native pipeline docs enough to judge adoption surface.
- Relevant files: arnold_pipelines/megaplan/step_contracts.py, arnold_pipelines/megaplan/template_registry.py, docs/arnold/workflow-authoring.md, docs/arnold/creating-a-new-pipeline.md, docs/arnold/workflow-runtime.md.

Provisional answer to challenge:
BoundaryTurn should standardize capture/validation/promotion mechanics while keeping stage semantics pluggable. It should become a recipe: define spec, build draft, prompt expected paths, capture, validate, semantically check, promote, emit state/history/receipts, and test wrong-path/invalid/unmodified/resume cases.

Return <600 words:
1. Verdict.
2. Where the recipe is too Megaplan-specific or too vague.
3. Specific design-doc edits or acceptance tests.
