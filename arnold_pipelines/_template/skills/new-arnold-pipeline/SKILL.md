# Skill: Create a New Arnold Workflow Pipeline

1. Copy `arnold_pipelines/_template/` to `arnold_pipelines/<your_pipeline>/`.
2. Edit `__init__.py`: set `name`, `description`, `capabilities`, and implement `build_pipeline()`.
3. For Python-shaped authoring, export typed step/prompt/policy/schema/subflow
   components from package-local modules and import them from workflow source.
   While using the current DSL directly, use `arnold.workflow.dsl.Pipeline`,
   `Step`, `Route`, `Input`, `Output`, `Capability`.
4. Run `arnold workflow check --module arnold_pipelines.<your_pipeline>:build_pipeline`.
5. Add tests that compile, dry-run, fake-run, and assert manifest hash determinism.

`build_pipeline()` is still the package entrypoint. Generated manifests and
catalogs are outputs of the authoring path, not editable workflow source.
