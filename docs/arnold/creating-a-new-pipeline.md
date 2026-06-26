# Creating a New Arnold Pipeline

This is the M7 copy-paste guide for adding a new Arnold pipeline. New converted
pipelines should be native-authored first, then projected to a validation graph.

## 1. Scaffold the Module

From the repo root:

```bash
arnold pipelines new my-planning-pipeline
```

This creates a native-first module and a sibling `SKILL.md` stub. The
CLI-visible name is the hyphenated form: `my-planning-pipeline`.

## 2. Replace the Skeleton

Open the generated module and keep the native declaration shape. A minimal
planning-style pipeline looks like this:

```python
from __future__ import annotations

from typing import Any

from arnold.pipeline.native import (
    compile_pipeline,
    decision,
    native_panel,
    parallel,
    phase,
    pipeline,
    project_graph,
)
from arnold.pipeline.subpipeline import run_subpipeline
from arnold.pipeline.types import Pipeline


name: str = "my-planning-pipeline"
description: str = "A minimal native planning pipeline."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("code",)
driver: tuple[str, str] = ("native", "project+validate")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("planning",)


@phase(name="prep")
def prep(ctx: Any) -> dict[str, Any]:
    return {"prepped": True}


@phase(name="plan")
def plan(ctx: Any) -> dict[str, Any]:
    return {"planned": True}


@phase(name="review_fast")
def review_fast(ctx: Any) -> dict[str, Any]:
    return {"fast_review": "TODO"}


@phase(name="review_deep")
def review_deep(ctx: Any) -> dict[str, Any]:
    return {"deep_review": "TODO"}


@decision(name="gate", vocabulary=frozenset({"proceed", "revise"}))
def gate(ctx: Any) -> str:
    state = getattr(ctx, "state", {}) if not isinstance(ctx, dict) else ctx.get("state", {})
    return "revise" if isinstance(state, dict) and state.get("needs_revision") else "proceed"


@phase(name="revise")
def revise(ctx: Any) -> dict[str, Any]:
    return {"revised": True}


@phase(name="execute")
def execute(ctx: Any) -> dict[str, Any]:
    return {"executed": True}


@phase(name="review")
def review(ctx: Any) -> dict[str, Any]:
    return {"reviewed": True}


@pipeline("my-planning-pipeline", description=description)
def my_planning_pipeline(ctx: Any) -> Any:
    yield prep(ctx)
    yield plan(ctx)
    for branch in parallel([review_fast, review_deep], name="planning_panel"):
        yield branch(ctx)
    for branch in native_panel(
        "editorial_panel",
        (("fast", review_fast), ("deep", review_deep)),
    ):
        yield branch(ctx)
    if gate(ctx) == "revise":
        yield revise(ctx)
    yield execute(ctx)
    yield review(ctx)


def build_pipeline() -> Pipeline:
    program = compile_pipeline(my_planning_pipeline)
    return project_graph(program, key_mode="phase")


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
```

Use `run_subpipeline(...)` inside a `@phase` when the work should delegate to a
child pipeline with an explicit parent/child resume boundary. Keep that call in
one phase rather than hiding child workflow state in a graph edge.

## 3. Validate and Run

```bash
arnold pipelines check my-planning-pipeline
arnold pipelines list
arnold pipelines run my-planning-pipeline "Implement a dark mode toggle"
```

Fresh runs execute on the native runtime.

## 4. Profiles and Prompts

Profiles are still keyed by public stage name:

```toml
[profiles.default]
prep = "hermes:deepseek:deepseek-v4-pro"
plan = "claude"
execute = "hermes:deepseek:deepseek-v4-pro"
review = "claude"
```

Static prompt files, callable prompt builders, and model-backed steps can still
live behind the phase implementation. The native declaration owns topology;
the phase body owns how work is performed.

## 5. Resume and Old Graph Plans

Native runs write native-owned `resume_cursor.json` files. Graph-born in-flight
plans keep resuming on graph unless you explicitly upgrade the cursor:

```bash
arnold pipelines upgrade-cursor <plan-dir>
arnold pipelines upgrade-cursor <plan-dir> --write
```

The first command is a dry run. The write command keeps a graph cursor backup
and fails without mutation if the graph stage cannot map to exactly one native
reentry point.

## 6. Common Gotchas

- `build_pipeline()` must be callable with no arguments.
- Keep module metadata as simple literals so no-import discovery can parse it.
- Use `@decision` vocabularies that match the labels your workflow branches on.
- Use `parallel(...)` and `native_panel(...)` only for fixed branch sets.
- Keep runtime-sized fanout or profile-sized panels inside a delegating phase
  until the native compiler/runtime explicitly supports that shape.
- Graph scaffolds are not available for new packages; new work must use the
  native-first scaffold.

## 7. Reference Implementations

- `arnold_pipelines/megaplan/pipeline.py` - native Megaplan planning topology.
- `arnold_pipelines/megaplan/pipelines/epic_blitz.py` - native panels.
- `arnold_pipelines/megaplan/pipelines/select_tournament/__init__.py` - fixed
  native parallel branches with typed ports.
- `docs/arnold/authoring-guide.md` and
  `docs/arnold/package-authoring-contract.md` - full contract details.
