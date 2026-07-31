---
name: new-arnold-pipeline
description: Steps to create a new Arnold native-first pipeline package from the template.
---

# Skill: Create a New Arnold Native-First Pipeline

1. Copy `arnold_pipelines/_template/` to `arnold_pipelines/<your_pipeline>/`.
2. Edit the package metadata and point it at the public workflow entrypoint.
3. Edit `workflow.py`: replace the skeleton public `@step`, `@workflow`, and
   `@decision` functions with real logic. The package generator owns runtime
   projection and manifest output.
4. Run `arnold pipelines check <your_pipeline>` to validate the package
   against the authoring contract and regenerate derived package artifacts.
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
