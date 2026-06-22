# Skill: Pipeline Template Reference

The canonical scaffold is `arnold_pipelines/_template/`. It shows the minimum
required contract for a workflow pipeline:

- `build_pipeline()` returns `arnold.workflow.Pipeline`.
- Module-level metadata variables.
- Explicit `Step`/`Route` topology with stable ids.

Use explicit `Step` and `Route` declarations; do not use the legacy authoring
primitives in new packages.
