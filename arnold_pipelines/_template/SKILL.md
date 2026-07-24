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

Package authors should treat `native_program` as the execution-level
contract: a non-null program proves the package is native-runnable, but
the exact shape of how composition is rendered for end users, agents, or
Capsules is not finalised at this layer.

## Example

```python
from arnold.pipeline.native import compile_pipeline, phase, pipeline, project_graph
from arnold.pipeline.types import Pipeline


@phase(name="draft")
def draft(ctx: object) -> StepResult:
    return StepResult(outputs={"draft": "TODO"}, next="publish")


@phase(name="publish")
def publish(ctx: object) -> StepResult:
    return StepResult(outputs={"final_artifact": "TODO"}, next="halt")


@pipeline(name="my-pipeline", description="draft → publish")
def my_pipeline_native(ctx: object) -> Any:
    state = yield draft(ctx)
    state = yield publish(ctx)
    return state


def build_pipeline() -> Pipeline:
    native = compile_pipeline(my_pipeline_native)
    return project_graph(native, key_mode="phase")
```

The returned `Pipeline` carries a non-null `native_program`. The runtime
uses that program directly; the projected shell is for discovery and
validation, not for hand-authored graph construction.

## Validation

- Validate import: `arnold_pipelines.my_pipeline:build_pipeline`
- Contract: `build_pipeline()` returns `arnold.pipeline.types.Pipeline`
  with a non-null `native_program`.
- Metadata: `driver` starts with `"native"`; `supported_modes` contains
  `"native"`.

Run through the Arnold native checker:

```bash
arnold pipelines check --module arnold_pipelines.my_pipeline:build_pipeline
```
