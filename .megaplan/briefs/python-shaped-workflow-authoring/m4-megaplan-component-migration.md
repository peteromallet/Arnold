# M4: Megaplan Component Migration

## Outcome

Make the actual Megaplan planning workflow readable and editable as Python-shaped source, with `arnold_pipelines.megaplan.workflows.planning.py` as the canonical product-facing workflow.

## Source Material

- M1-M3 outputs.
- `.megaplan/briefs/workflow-manifest-runtime-cleanup/codex-end-state-megaplan-planning.py`
- Existing `arnold_pipelines.megaplan.pipeline.build_pipeline()`.
- Current Megaplan handlers, prompts, policies, settings, and manifest/golden fixtures.

## Scope

Implement:

- Megaplan step component exports for prep, plan, critique, gate, revise, tiebreaker, override, finalize, execute, review, and halt/suspend behavior.
- Prompt components and prompt provenance for current prompt builders/resources.
- Policy/schema components for model routing, robustness, iteration limits, approval boundaries, suspension, and artifact contracts.
- `arnold_pipelines.megaplan.workflows.planning.py` as the canonical authored workflow.
- A thin `pipeline.py` loader/compiler facade that compiles from the authored workflow source.
- Shape/golden tests proving behavior and manifest identity against the previous explicit DSL pipeline.

## Constraints

- The authored workflow is the file users and agents should read and edit.
- Generated DSL/manifest artifacts are backend products.
- Do not expose a separate registry as the user-maintained source of truth.

## Done Criteria

- Megaplan’s real workflow is understandable from `workflows/planning.py`.
- Existing settings, prompts, steps, policies, loops, tiebreakers, overrides, and review/rework paths are represented.
- `build_pipeline()` continues to provide the public product API while deriving from the authored source.
