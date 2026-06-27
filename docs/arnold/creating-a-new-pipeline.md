# Creating a New Arnold Pipeline

This is the workflow-first copy-paste guide for adding a new Arnold pipeline.
New pipelines are authored as explicit-node `arnold.workflow.Pipeline` data and
validated through the `arnold workflow` CLI.

## 1. Scaffold the Package

Copy the workflow-first template and rename it:

```bash
cp -r arnold_pipelines/_template arnold_pipelines/my_pipeline
```

Inside `arnold_pipelines/my_pipeline/` you will find:

- `__init__.py` — package metadata and the canonical `build_pipeline()` entrypoint.
- `SKILL.md` — agent-facing instructions for the pipeline.
- `skills/` — optional skill bundles for Codex/Claude/Cursor.

Replace every `my-pipeline` placeholder with the real pipeline id.

## 2. Replace the Skeleton

Open `__init__.py` and keep the explicit-node workflow shape. A minimal
pipeline looks like this:

```python
from __future__ import annotations

from arnold.workflow import Pipeline, Route, Step


name: str = "my-pipeline"
description: str = "A minimal explicit-node workflow pipeline."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("graph",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("graph", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("skeleton",)


def build_pipeline() -> Pipeline:
    """Build the workflow graph."""
    return Pipeline(
        id="my-pipeline",
        version="1.0",
        steps=(
            Step(id="plan", kind="agent"),
            Step(id="execute", kind="agent"),
            Step(id="review", kind="agent"),
        ),
        routes=(
            Route(id="plan-execute", source="plan", target="execute"),
            Route(id="execute-review", source="execute", target="review"),
        ),
    )


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
```

`build_pipeline()` must be callable with no arguments and must return an
`arnold.workflow.Pipeline`. The compiler lowers that object to a
`WorkflowManifest` with deterministic hashes; do not hand-author the manifest.

## 3. Validate and Run

```bash
arnold workflow check --module arnold_pipelines.my_pipeline:build_pipeline
arnold workflow dry-run --module arnold_pipelines.my_pipeline:build_pipeline
arnold workflow run --module arnold_pipelines.my_pipeline:build_pipeline --backend fake
```

For a local (non-fake) backend run, omit `--backend fake`.

## 4. Profiles and Prompts

Profiles are still keyed by step id:

```toml
[profiles.default]
plan = "claude"
execute = "hermes:deepseek:deepseek-v4-pro"
review = "claude"
```

Static prompt files, callable prompt builders, and model-backed steps can live
behind component imports. The workflow declaration owns topology; the step
implementation owns how work is performed.

## 5. Resume

Workflow runs write event journals. Resume from a cursor with:

```bash
arnold workflow resume --module arnold_pipelines.my_pipeline:build_pipeline \
                       --artifact-root ./runs/my-pipeline
```

## 6. Common Gotchas

- `build_pipeline()` must be callable with no arguments.
- Keep module metadata as simple literals so no-import discovery can parse it.
- Use only `arnold.workflow` explicit-node data (`Pipeline`, `Step`, `Route`,
  `Input`, `Output`, `Capability`) for topology.
- Do not import `arnold.pipeline`, `arnold.pipeline.native`, `Stage`, `Edge`,
  `PipelineBuilder`, or other graph/native surfaces into the canonical builder.
- Do not add `_legacy.py`, native fallback builders, or compatibility wrappers
  for new work.

## 7. Reference Implementations

- `arnold_pipelines/_template/__init__.py` — canonical workflow scaffold.
- `arnold_pipelines/evidence_pack/__init__.py` — migrated workflow pipeline.
- `docs/arnold/workflow-authoring.md` and
  `docs/arnold/package-authoring-contract.md` — full contract details.
