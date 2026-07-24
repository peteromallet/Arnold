---
name: new-arnold-pipeline
description: Steps to create a new Arnold native-first pipeline package from the template.
---

# Skill: Create a New Arnold Native-First Pipeline

1. Copy `arnold_pipelines/_template/` to `arnold_pipelines/<your_pipeline>/`.
2. Edit `__init__.py`: set `name`, `description`, `capabilities`, keep
   `driver=("native", "project+validate")` and `supported_modes=("native",)`,
   and ensure `build_pipeline()` compiles the native program and returns a
   projected `Pipeline` with a non-null `native_program`.
3. Edit `pipelines.py`: replace the skeleton `@phase` functions with real
   logic. Use `@pipeline`, `@phase`, `@decision`, `parallel`,
   `compile_pipeline`, and `project_graph` from `arnold.pipeline.native`.
4. Run `arnold pipelines check <your_pipeline>` to validate the package
   against the native-first authoring contract (metadata, driver, native
   program, and graph projection).
5. Add tests that compile the native program, project the graph, and assert
   the returned `Pipeline` carries a non-null `native_program`.

## Dispatch Substrate Note

The `native_program` compiled by `build_pipeline()` is a **dispatch
substrate** — it describes how the runtime executes the pipeline, but it
does **not** define the final visible compositional semantics. Panel
synthesis, join delegation, parallel merge strategy, subpipeline
ownership, and Capsule projection are deferred to later Megaplan layers.

Do **not** add `_legacy.py`, graph fallback builders, compatibility
namespaces, shim packages, or temporary wrapper modules. The template and
this workflow are native-first only. Generated manifests and catalogs are
outputs of the authoring path, not editable source.
