---
name: pipeline-template-reference
description: Reference contract for the canonical Arnold native-first pipeline template scaffold.
---

# Skill: Pipeline Template Reference

The canonical scaffold is `arnold_pipelines/_template/`. It shows the minimum
required contract for a native-first pipeline:

- `build_pipeline()` returns `arnold.pipeline.types.Pipeline` with a
  **non-null** `native_program`.
- Module-level metadata with `driver=("native", "<kind>")` and
  `supported_modes` containing `"native"`.
- Native declarations in `pipelines.py` using `@pipeline`, `@phase`,
  `@decision`, `parallel`, `compile_pipeline`, and `project_graph`.

## Native-First Authoring Shape

For native-first authoring, organise components as package-local exports:
`pipelines.py` owns the native declaration topology. Supporting modules
(`steps.py`, `prompts.py`, `policies.py`, `schemas.py`, `subflows.py`)
may be imported by the native declaration, but the declaration itself
is the single source of topology truth.

The `build_pipeline()` entrypoint compiles the native program and projects
it into a `Pipeline` shell. The shell exists for discovery and validation.
The runtime executes the native program directly.

## Dispatch Substrate Boundary

The `native_program` field is a **dispatch substrate**, not a final
compositional surface. It proves the package is executable by the native
runtime, but it does not lock in panel synthesis, join delegation,
parallel merge strategy, subpipeline ownership, or Capsule projection.
Those concerns belong to later Megaplan layers above the dispatch
boundary.

## What NOT to Use

Do **not** use these patterns in new packages built from the template:

- Graph-first authoring with `arnold.workflow.Pipeline`, `Step`, `Route`.
- Native-as-opt-in or dual-mode (graph + native) packages — the template
  is native-first and single-mode.
- `_legacy.py`, graph fallback builders, compatibility namespaces, shim
  packages, or temporary wrapper modules.
- `--driver graph` scaffolding or manual graph construction.
- Hand-authored `WorkflowManifest`, `NativeProgram` builder objects, or
  `_forward_m2_m3` graph objects in `build_pipeline()`.

Derived manifests, catalogs, and projection artifacts are compiler output,
not package source.
