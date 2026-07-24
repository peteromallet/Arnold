# Creating a New Arnold Pipeline

This is the native-first copy-paste guide for adding a new Arnold pipeline.
New pipelines are authored as native declarations (`@pipeline`, `@phase`,
`@decision`, `parallel`) and validated through the `arnold pipelines` CLI.

## 1. Scaffold the Package

Copy the native-first template and rename it:

```bash
cp -r arnold_pipelines/_template arnold_pipelines/my_pipeline
```

Or use the scaffold command:

```bash
arnold pipelines new my-module
```

Note: `--driver graph` is an unsupported legacy input. The scaffold emits
`driver=("native", "project+validate")` only.

Inside `arnold_pipelines/my_pipeline/` you will find:

- `__init__.py` — package metadata and the canonical `build_pipeline()`
  entrypoint that compiles a native program and returns a projected
  `Pipeline` shell with a non-null `native_program`.
- `pipelines.py` — the native declaration using `@pipeline`, `@phase`,
  `@decision`, `parallel`, `compile_pipeline`, and `project_graph`.
- `SKILL.md` — agent-facing instructions for the pipeline.
- `skills/` — optional skill bundles for Codex/Claude/Cursor.

Replace every `my-pipeline` placeholder with the real pipeline id.

## 2. Replace the Skeleton

Open `__init__.py` and keep the native-first compositional shape. A minimal
native-first package uses `@step`, `@workflow`, `@decision`, and literal
`id=` values at every call site:

```python
from __future__ import annotations

from typing import Any

from arnold.pipeline import step, workflow, decision
from arnold.pipeline.native import compile_pipeline, project_graph
from arnold.pipeline.types import Pipeline


name: str = "my-pipeline"
description: str = "A compositional native-first pipeline."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
driver: tuple[str, str] = ("native", "project+validate")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("skeleton",)
authoring_style: str = "compositional"


@step(
    name="plan",
    id="my-pipeline.plan",
    inputs={"type": "object", "required": ["brief"]},
    outputs={"type": "object", "required": ["plan"]},
)
def plan(ctx: object) -> Any:
    return {"plan": "ready"}


@step(
    name="execute",
    id="my-pipeline.execute",
    inputs={"type": "object", "required": ["plan"]},
    outputs={"type": "object", "required": ["result"]},
)
def execute(ctx: object) -> Any:
    return {"result": "done"}


@step(
    name="review",
    id="my-pipeline.review",
    inputs={"type": "object", "required": ["result"]},
    outputs={"type": "object", "required": ["verdict"]},
)
def review(ctx: object) -> Any:
    return {"verdict": "approved"}


@workflow(
    name="my-pipeline",
    id="my-pipeline.root",
    inputs={"type": "object", "required": ["brief"]},
    outputs={"type": "object", "required": ["verdict"]},
)
def my_pipeline_native(ctx: object) -> Any:
    state = yield plan(ctx, id="plan-step", outputs={"plan": "plan"})
    state = yield execute(ctx, id="execute-step", outputs={"result": "result"})
    state = yield review(ctx, id="review-step", outputs={"verdict": "verdict"})
    return state


def build_pipeline() -> Pipeline:
    """Compile the native program and return a projected Pipeline shell."""
    native = compile_pipeline(my_pipeline_native)
    return project_graph(native, key_mode="phase")


__all__ = [
    "arnold_api_version",
    "authoring_style",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "supported_modes",
]
```

`build_pipeline()` must be callable with no arguments and must return an
`arnold.pipeline.types.Pipeline` with a **non-null** `native_program`. The
`native_program` is a dispatch substrate — the runtime executes it directly.
Do not hand-author the native program as a builder object.

Every `@step` and `@workflow` must declare a stable `id=`, `inputs`, and
`outputs`. Every call site in the workflow body must include a literal `id=`.
These are the durability contract for trace, replay, and resume.

## 3. Validate and Run

```bash
arnold pipelines check my-module
arnold pipelines doctor
```

For dry-run and execution, use the native runtime path:

```bash
arnold pipelines run --module arnold_pipelines.my_pipeline:build_pipeline --backend fake
```

For a local (non-fake) backend run, omit `--backend fake`.

## 4. Profiles and Prompts

Profiles are keyed by phase name:

```toml
[profiles.default]
plan = "claude"
execute = "hermes:deepseek:deepseek-v4-pro"
review = "claude"
```

Static prompt files, callable prompt builders, and model-backed phases can
live behind component imports. The native declaration owns topology; the
phase implementation owns how work is performed.

## 5. M6 Dispatch Substrate

The `native_program` compiled by `build_pipeline()` is a **dispatch
substrate** — it proves the package is executable by the native runtime, but
it does **not** define the final visible compositional semantics. Panel
synthesis, join delegation, parallel merge strategy, subpipeline ownership,
and Capsule projection are deferred to later Megaplan layers above the
dispatch boundary.

## 6. Common Gotchas

- `build_pipeline()` must be callable with no arguments.
- Keep module metadata as simple literals so no-import discovery can parse it.
- `driver` must start with `"native"` (e.g. `("native", "project+validate")`).
- `supported_modes` must include `"native"`.
- The returned `Pipeline` must have a non-null `native_program`.
- Do **not** add `_legacy.py`, graph fallback builders, shim packages,
  compatibility namespaces, or temporary wrapper modules for new work.
- Do **not** use `--driver graph` — it is an unsupported legacy path.
- Do **not** import `arnold.workflow` (`Pipeline`, `Step`, `Route`,
  `Input`, `Output`, `Capability`) for new native-first packages.
- Every `@step` and `@workflow` must declare `id=`, `inputs`, and `outputs`.
- Every call site in a workflow body must include a literal `id=` keyword.
- `authoring_style = "compositional"` enables platform-boundary validation.
- Do **not** read environment variables or secret files in package code.
- Do **not** assume local filesystem paths survive worker migration.

## 7. Reference Implementations

- `arnold_pipelines/_template/__init__.py` — canonical native-first scaffold.
- `arnold_pipelines/_template/pipelines.py` — native declaration example.
- `arnold_pipelines/evidence_pack/__init__.py` — migrated native-first pipeline.
- `docs/arnold/authoring-guide.md` and
  `docs/arnold/package-authoring-contract.md` — full contract details.
