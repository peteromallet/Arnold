---
name: new-arnold-pipeline-template
description: Scaffold a new Arnold workflow pipeline package from the _template skeleton.
---

# New Arnold Pipeline Template

Copy `arnold_pipelines/_template/` to a new package under `arnold_pipelines/`,
rename it (remove the leading underscore), and replace the skeleton explicit-node
workflow with your pipeline logic.

## Contract

- `build_pipeline(...) -> arnold.workflow.Pipeline` returning explicit-node data.
- Module-level metadata: `name`, `description`, `driver`, `entrypoint`,
  `arnold_api_version`, `capabilities`
- Optional: `default_profile`, `supported_modes`, `recommended_profiles`

New packages must be workflow-first. Use `arnold.workflow.Pipeline`, `Step`,
`Route`, `Input`, `Output`, and `Capability` to declare the graph. Do not add
`_legacy.py`, native fallback builders, compatibility namespaces, or temporary
wrapper modules for new work.

`build_pipeline()` remains the current package entrypoint used by discovery and
`arnold workflow check`.

## Example

```python
from arnold.workflow import Pipeline, Route, Step


def build_pipeline() -> Pipeline:
    return Pipeline(
        id="my-pipeline",
        version="1.0",
        steps=(
            Step(id="start", kind="agent"),
            Step(id="finish", kind="agent"),
        ),
        routes=(
            Route(id="start-finish", source="start", target="finish"),
        ),
    )
```

## Validation

- Validate import: `arnold_pipelines.my_pipeline:build_pipeline`
- Contract: `build_pipeline()` returns `arnold.workflow.Pipeline`.

Run through the Arnold workflow checker:

```bash
arnold workflow check --module arnold_pipelines.my_pipeline:build_pipeline
```
