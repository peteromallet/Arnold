---
name: new-arnold-pipeline-template
description: Scaffold a new Arnold pipeline package from the _template skeleton.
---

# New Arnold Pipeline Template

Copy `arnold_pipelines/_template/` to a new package under `arnold_pipelines/`,
rename it (remove the leading underscore), and replace the skeleton native
declaration body with your workflow entrypoint.

## Contract

- `build_pipeline(...) -> arnold.pipeline.Pipeline` with `native_program` set.
- Module-level metadata: `name`, `description`, `driver`, `entrypoint`,
  `arnold_api_version`, `capabilities`
- Optional: `default_profile`, `supported_modes`, `recommended_profiles`

New packages must be native-first. Use `@phase` and `@pipeline` declarations
from `arnold.pipeline.native`, compile them with `compile_pipeline`, and return
the result of `project_graph(...)`. Do not add `_legacy.py`, graph fallback
builders, compatibility namespaces, or temporary wrapper modules for new work.

`build_pipeline()` remains the current package entrypoint used by discovery and
`arnold workflow check`.

## Example

```python
from arnold.pipeline.native import compile_pipeline, phase, pipeline, project_graph
from arnold.pipeline.types import Pipeline


@phase(name="start")
def start(ctx):
    return {"intermediate": "TODO"}


@phase(name="finish")
def finish(ctx):
    return {"result": "TODO"}


@pipeline("my-pipeline")
def my_pipeline(ctx):
    yield start(ctx)
    yield finish(ctx)


def build_pipeline() -> Pipeline:
    return project_graph(compile_pipeline(my_pipeline), key_mode="phase")
```

## Validation

- Validate import: `arnold_pipelines.my_pipeline:build_pipeline`
- Contract: `build_pipeline()` returns `arnold.pipeline.Pipeline` with `NativeProgram` set.

Run through the Arnold pipeline checker:

```bash
arnold pipelines check my-pipeline
```
