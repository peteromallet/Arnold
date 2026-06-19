```yaml
---
name: new arnold pipeline
description: Create a new Arnold pipeline module from scratch.
---

# Creating a new Arnold pipeline

Use this skill when the user wants to add a new, named, runnable pipeline to the Arnold harness.

This guide walks you through creating a pipeline from scratch. Arnold discovers modules under `arnold/pipelines/`. There are two module forms:

1. **Graph-driven sibling-file** — a single `.py` file created with `arnold pipelines new`. Designed for stage graphs, loops, and quick CLI workflows. These live under `arnold/pipelines/megaplan/pipelines/` and run on Megaplan's graph executor.
2. **Typed package module** — a directory created by copying `arnold/pipelines/_template`. Designed for typed ports, hooks, resume/continuation, and model-less adapters. These live as packages directly under `arnold/pipelines/`.

Both forms expose the same module-level contract fields and must pass `arnold pipelines check`.

**Choose your path:** Need a quick CLI workflow or branching graph? Start with §1. Need typed schemas, pause/resume, or lifecycle hooks? Jump to §2. Before you scaffold, study the closest example: `arnold/pipelines/_template` for a minimal package, `arnold/pipelines/evidence_pack` for a full-featured package, or `arnold/pipelines/megaplan/pipeline.py` for a canonical sibling-file graph.

## Module contract (both forms)

All pipeline modules must declare these top-level fields as plain literals. The static manifest reader parses them without executing your code, so use only strings, tuples, and `None` — no variables, function calls, or computed values.

| Field | Required? | Notes |
|---|---|---|
| `name` | **yes** | CLI-visible pipeline name. Do not change it after release. |
| `description` | **yes** | Single-line description displayed in `arnold pipelines list`. |
| `driver` | **yes** | `"in_process"` or `("graph", "dispatch+emit")` are common. |
| `entrypoint` | **yes** | Bare name `"build_pipeline"` or `"module:name"`. |
| `build_pipeline` | **yes** | Zero-argument callable returning a `Pipeline`. |
| `arnold_api_version` | **yes** | Keep `"1.0"` unless targeting a newer SDK. |
| `capabilities` | **yes** | Non-empty tuple of labels. |
| `default_profile` | **yes** | Set to `None` if unused. |
| `supported_modes` | **yes** | Set to `()` if unused. |

Always include `default_profile` and `supported_modes`, even if empty. The static manifest reader rejects modules that omit them.

## 1. Graph-driven sibling-file module

Use this form for simple linear or branching flows, stage graphs, loops, and quick CLI workflows.

### Key concepts
A graph-driven pipeline defines **steps** that run inside **stages**, connected by **edges**. The runtime passes three objects through each step:

- `ctx.inputs` — receives positional CLI arguments and `--inputs key=value` pairs as **strings**.
- `ctx.state` — the graph executor's mutable run state. Pass data downstream with `state_patch`.
- `ctx.plan_dir` — the run's artifact directory for writing outputs.

### Scaffold the module
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

The CLI-visible name is the hyphenated form `my-pipeline`. **Do not use leading `_` or `.` in module or directory names** — discovery silently skips them.

### Minimal module
Replace the generated `my_pipeline.py` with the following. The step dataclasses define the work; the `build_pipeline` function wires stages into a graph.

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

# ── Module-level contract ────────────────────────────────────────────────

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

### Graph-specific pitfalls
- **Guard every cycle.** If a stage routes back to an earlier stage (creating a loop), attach a `loop_condition` to at least one stage in that loop. Otherwise `arnold pipelines check` fails with `unguarded_cycle_detected`.
- **Decision routing** requires `kind="decide"` steps that return `StepResult(verdict=PipelineVerdict(recommendation="..."))`. The executor matches that against `kind="decision"` edges. See `arnold/pipelines/megaplan/pipeline.py` for a worked example.
- **Use absolute paths when spawning subagent launchers.** Pass fully resolved paths for `--project-dir`, `--briefs-dir`, and file arguments. Do not mix relative CLI arguments with `cwd=...`.

If your workflow requires typed schemas, resume logic, or lifecycle hooks instead, use the package module form below.

## 2. Typed package module

Use this form when you need structured input/output ports, resume/continuation, lifecycle hooks, or model-less adapters.

### Scaffold the module
Copy the template:

```bash
cp -r arnold/pipelines/_template arnold/pipelines/my_pipeline
```

**Do not use leading `_` or `.` in the directory name** — discovery silently skips it.

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

### Extend the pipeline
Replace the skeleton with real stages in `arnold/pipelines/my_pipeline/pipelines.py` using `arnold.pipeline.builder.PipelineBuilder`. For a complete example with typed ports, hooks, and resume, see `arnold/pipelines/evidence_pack/`.

## 3. Add resources (optional)

Both forms can bundle prompts, profiles, and extra files. In sibling-file modules, place them next to `SKILL.md`. In package modules, place them inside the package directory. Resolve paths from `_PIPELINE_DIR` in sibling-file modules, or from the package directory in package modules.

Example layout for a sibling-file module:

```
my-pipeline/
├── SKILL.md
├── prompts/
│   └── process.md
└── profiles/
    └── default.toml
```

## 4. Validate and run

Once your module is complete, validate and run it:

```bash
python -m arnold pipelines check my-pipeline
python -m arnold pipelines list
python -m arnold run my-pipeline path/to/input.md
```

The positional argument is available as `ctx.inputs["draft"]`. `--inputs key=value` binds to `ctx.inputs["key"]` as a string. If you need a list (e.g., `perspectives=a,b,c`), parse it inside the step with `value.split(",")`.

## 5. General pitfalls

Before shipping, watch for these recurring issues:

- `build_pipeline()` must be callable with zero arguments from the registry.
- Keep module-level metadata as simple literals. The static manifest reader cannot follow aliases or function calls.
- `--inputs` values are always strings.

## 6. Reference implementations

For deeper patterns beyond these basics, study the following examples:

- `arnold/pipelines/_template` — minimal package module.
- `arnold/pipelines/evidence_pack` — full package module with typed ports, hooks, and resume.
- `arnold/pipelines/megaplan/pipeline.py` — canonical sibling-file graph topology.

For deeper documentation, see `docs/arnold/authoring-guide.md` (hands-on guidance) and `docs/arnold/package-authoring-contract.md` (authoritative field-level contract).
