---
name: new-arnold-pipeline-template
description: Scaffold a new Arnold native-first pipeline package from the _template skeleton.
---

# New Arnold Pipeline Template

Copy `arnold_pipelines/_template/` to a new package under `arnold_pipelines/`,
rename it (remove the leading underscore), and replace the skeleton native
declarations with real pipeline logic.

This template is **native-first**. Every package built from it uses
`@pipeline`, `@phase`, `@decision`, `parallel`, `compile_pipeline`, and
`project_graph` to declare a native program and project it into a
`Pipeline` shell that the runtime executes directly.

## Contract

- `build_pipeline() -> arnold.pipeline.types.Pipeline` returning a projected
  shell with a **non-null** `native_program`.
- Module-level metadata: `name`, `description`, `driver`, `entrypoint`,
  `arnold_api_version`, `capabilities`.
- `driver` must be `("native", "<kind>")` (e.g. `("native", "project+validate")`).
- `supported_modes` must include `"native"` (e.g. `("native",)`).
- Optional: `default_profile`, `recommended_profiles`.

New packages must be native-first. Do **not** add `_legacy.py`, graph
fallback builders, compatibility namespaces, shim packages, or temporary
wrapper modules for new work — those patterns are explicitly disallowed.

## Dispatch Substrate, Not Final Composition

The `native_program` attached to the projected `Pipeline` is a **dispatch
substrate**. It describes how the runtime lowers and executes pipeline
topology, but it does **not** define the final visible compositional
semantics (panel synthesis, join delegation, parallel merge strategy,
subpipeline ownership, or Capsule projection). Those compositional
concerns are deferred to later Megaplan layers above the dispatch
boundary.

Package authors declare the public workflow entrypoint. The generated package
adapter and validation receipt prove that the package is runnable; generated
execution objects are not an authoring surface.

## Example

```python
from arnold.pipeline import step, workflow


@step(id="draft")
def draft(ctx: object) -> dict:
    return {"draft": "TODO"}


@step(id="publish")
def publish(ctx: object) -> dict:
    return {"final_artifact": "TODO"}


@workflow(id="my-pipeline.root")
def my_pipeline(ctx: object):
    yield draft(ctx, id="draft")
    yield publish(ctx, id="publish")
```

The package generator consumes `my_pipeline` and emits the runtime adapter and
manifest. Those generated files are validated but never hand-edited.

## Validation

- Validate import: `arnold_pipelines.my_pipeline.workflow:my_pipeline`
- Contract: the workflow entrypoint compiles through the public authoring API.
- Metadata and generated artifacts satisfy the package schema.

Run through the Arnold native checker:

```bash
arnold pipelines check --module arnold_pipelines.my_pipeline.workflow:my_pipeline
```
