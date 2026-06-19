---
name: new arnold pipeline
description: Create a new Arnold pipeline module from scratch.
---

# Creating a new Arnold pipeline

Use this skill when the user wants to add a new, named, runnable pipeline to the Arnold harness.

Arnold discovers pipeline modules under `arnold/pipelines/`. There are two common shapes:

1. **Graph-driven sibling-file module** — created with `arnold pipelines new`. Best for stage graphs, loops, and quick CLI workflows. These live under `arnold/pipelines/megaplan/pipelines/` and are executed by the Megaplan graph executor.
2. **Typed package module** — created by copying `arnold/pipelines/_template`. Best for typed ports, hooks, resume/continuation, and model-less adapters. These live as packages directly under `arnold/pipelines/`.

Both shapes expose the same module-level contract fields and both must pass `arnold pipelines check`.

## 1. Quick start: graph-driven sibling-file module

From the repo root:

```bash
python -m arnold pipelines new my-pipeline --driver graph
```

This creates:

```
arnold/pipelines/megaplan/pipelines/
├── my_pipeline.py          # the Python module
└── my-pipeline/
    └── SKILL.md            # agent-facing docs
```

The CLI-visible name is the hyphenated form: `my-pipeline`.

### Minimal module

Replace the scaffolded `arnold/pipelines/megaplan/pipelines/my_pipeline.py` with:

```python
"""Minimal graph-driven Arnold pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)

# ── Module-level contract fields ─────────────────────────────────────────

name: str = "my-pipeline"
description: str = "A minimal graph-driven pipeline."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("example",)

_PIPELINE_DIR: Path = Path(__file__).parent / "my-pipeline"


# ── Steps ────────────────────────────────────────────────────────────────

@dataclass
class IngestStep:
    name: str = "ingest"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        draft_path = ctx.inputs.get("draft")
        if not draft_path:
            raise ValueError("Pass a file path: arnold run my-pipeline <file>")
        text = Path(str(draft_path)).expanduser().resolve().read_text(encoding="utf-8")
        return StepResult(next="process", state_patch={"text": text})


@dataclass
class ProcessStep:
    name: str = "process"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        text = ctx.state["text"]
        out_path = ctx.plan_dir / "result.md"
        out_path.write_text(text.upper(), encoding="utf-8")
        return StepResult(next="halt", outputs={"result": str(out_path)})


# ── Pipeline assembly ────────────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    return Pipeline(
        stages={
            "ingest": Stage(
                name="ingest",
                step=IngestStep(),
                edges=(Edge(label="process", target="process"),),
            ),
            "process": Stage(
                name="process",
                step=ProcessStep(),
                edges=(Edge(label="halt", target="halt"),),
            ),
        },
        entry="ingest",
    )
```

Notes:

- `ctx.inputs` receives the positional CLI argument as `"draft"` and `--inputs key=value` as string values.
- `ctx.state` is the graph executor's mutable run state; use `state_patch` to write values for downstream steps.
- `ctx.plan_dir` is the run's artifact directory.

## 2. Typed package module

For typed ports, hooks, resume, or non-model adapters, copy the template package:

```bash
cp -r arnold/pipelines/_template arnold/pipelines/my_pipeline
```

Then edit `arnold/pipelines/my_pipeline/__init__.py`:

```python
from arnold.pipelines._authoring import build_skeleton_pipeline
from arnold.pipeline.types import Pipeline

name = "my-pipeline"
description = "A minimal typed Arnold pipeline."
driver = "in_process"
entrypoint = "arnold.pipelines.my_pipeline:build_pipeline"
arnold_api_version = "1.0"
capabilities = ("example",)
default_profile = None
supported_modes = ()


def build_pipeline() -> Pipeline:
    return build_skeleton_pipeline(name, description)
```

Replace the skeleton with real stages in `arnold/pipelines/my_pipeline/pipelines.py` using `arnold.pipeline.builder.PipelineBuilder`. See `arnold/pipelines/evidence_pack/` for a complete example with ports, hooks, and resume.

## 3. Module contract (both shapes)

| Field | Required? | Notes |
|---|---|---|
| `name` | **yes** | CLI-visible pipeline name. Keep it stable. |
| `description` | **yes** | One-liner shown in `arnold pipelines list`. |
| `arnold_api_version` | **yes** | Keep `"1.0"` unless targeting a newer SDK. |
| `capabilities` | **yes** | Non-empty tuple of labels. |
| `driver` | **yes** | String or tuple. `"in_process"` or `("graph", "dispatch+emit")` are common. |
| `entrypoint` | **yes** | Bare name `"build_pipeline"` or `"module:name"`. |
| `build_pipeline` | **yes** | Nullary callable returning a `Pipeline`. |
| `default_profile` | recommended | Declare as `None`; the static manifest reader requires it. |
| `supported_modes` | recommended | Declare as `()`; the static manifest reader requires it. |

Keep module-level metadata as simple literals. The static manifest reader parses them with AST literal eval; it cannot follow function calls, aliases, or computed values.

## 4. Add resources (optional)

Place prompts, profiles, and extra files next to `SKILL.md` (sibling-file) or inside the package directory (package module):

```
my-pipeline/
├── SKILL.md
├── prompts/
│   └── process.md
└── profiles/
    └── default.toml
```

Resolve paths from `_PIPELINE_DIR` in sibling-file modules, or from the package directory in package modules.

## 5. Validate and run

```bash
python -m arnold pipelines check my-pipeline
python -m arnold pipelines list
python -m arnold run my-pipeline path/to/input.md
```

- The positional argument maps to `ctx.inputs["draft"]`.
- `--inputs key=value` maps to `ctx.inputs["key"]` as a string.

## 6. Common gotchas

- **No leading `_` or `.`** in module or directory names; discovery silently skips them.
- **`build_pipeline()` must be callable with no arguments** from the registry's perspective.
- **Declare `default_profile` and `supported_modes` even if empty.** The runtime validator only warns, but the static manifest reader rejects packages that omit them.
- **Guard every cycle.** If your graph has a back-edge, attach a `loop_condition` to a stage in the cycle, otherwise `arnold pipelines check` fails with `unguarded_cycle_detected`.
- **Decision routing uses `PipelineVerdict.recommendation`.** Gate stages need `kind="decide"` steps that return `StepResult(verdict=PipelineVerdict(recommendation="..."))`. The executor matches that against `kind="decision"` edges.
- **Use absolute paths when shelling out to subagent launchers.** Pass fully-resolved paths for `--project-dir`, `--briefs-dir`, `--output-dir`, and file arguments (`Path(...).resolve()`). Do not mix relative CLI arguments with `cwd=...`.
- **`--inputs` values are strings.** If you need a list (e.g. `perspectives=a,b,c`), parse it inside the step with `value.split(",")`.

## 7. Where to look for reference implementations

- `arnold/pipelines/_template/` — minimal package module template.
- `arnold/pipelines/evidence_pack/` — full package module with typed ports, hooks, and resume.
- `arnold/pipelines/megaplan/pipeline.py` — Megaplan's canonical planning topology (a specific sibling-file graph).
- `docs/arnold/authoring-guide.md` — hands-on authoring guidance.
- `docs/arnold/package-authoring-contract.md` — authoritative field-level contract.
