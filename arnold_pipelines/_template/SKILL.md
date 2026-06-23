# New Arnold Workflow Pipeline Template

Copy `arnold_pipelines/_template/` to a new package under `arnold_pipelines/`,
rename it (remove the leading underscore), and replace the skeleton
`build_pipeline()` body with your workflow entrypoint.

## Contract

- `build_pipeline(...) -> arnold.workflow.Pipeline`
- Module-level metadata: `name`, `description`, `driver`, `entrypoint`,
  `arnold_api_version`, `capabilities`
- Optional: `default_profile`, `supported_modes`, `recommended_profiles`

For Python-shaped authoring, keep workflow source in a package-local module that
imports typed module-level component exports. Recommended component modules are
`steps.py`, `prompts.py`, `policies.py`, `schemas.py`, and `subflows.py`, though
feature modules are fine when the exports carry typed component metadata. The
workflow imports are the source of truth. Generated manifests and catalogs are
derived artifacts, not editable source.

`build_pipeline()` remains the current package entrypoint used by discovery and
`arnold workflow check`. It may construct explicit-node DSL directly or delegate
to the Python-shaped source compiler once available.

## Example

```python
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step

def build_pipeline() -> Pipeline:
    return Pipeline(
        id="my-pipeline",
        version="1.0",
        steps=(
            Step(id="start", kind="agent", outputs=(Output(name="out"),)),
            Step(id="finish", kind="emit", inputs=(Input(name="out", value_ref="start.out"),)),
        ),
        routes=(Route(id="start:finish", source="start", target="finish"),),
        capabilities=(Capability(id="my-capability"),),
    )
```

## CLI

```bash
arnold workflow check --module arnold_pipelines.my_pipeline:build_pipeline
arnold workflow dry-run --module arnold_pipelines.my_pipeline:build_pipeline
arnold workflow run --module arnold_pipelines.my_pipeline:build_pipeline --backend fake
```
