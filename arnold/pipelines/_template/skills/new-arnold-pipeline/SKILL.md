---
name: new arnold pipeline
description: Create a new Arnold pipeline module from scratch.
---

# Creating a new Arnold pipeline

Use this skill when the user wants to add a new, named, runnable pipeline to the Arnold harness.

This guide walks you through creating a pipeline from scratch. Arnold discovers modules under `arnold/pipelines/`. There are two module forms:

1. **Graph-driven package** — a directory created with `arnold pipelines new`. Designed for stage graphs, loops, and quick CLI workflows. These live as packages directly under `arnold/pipelines/`.
2. **Typed package module** — a directory created by copying `arnold/pipelines/_template`. Designed for typed ports, hooks, resume/continuation, and model-less adapters. These also live as packages directly under `arnold/pipelines/`.

Both forms expose the same module-level contract fields and must pass `arnold pipelines check`.

The retired `arnold/pipelines/megaplan/pipelines/` plugin root is no longer scanned. Do not create new pipelines there.

**Choose your path:** Need a quick CLI workflow or branching graph? Start with §1. Need typed schemas, pause/resume, or lifecycle hooks? Jump to §2. Before you scaffold, study the closest example: `arnold/pipelines/_template` for a minimal typed package, `arnold/pipelines/evidence_pack` for a full-featured typed package, or `arnold/pipelines/epic_blitz` for a graph-driven package with parallel panels.

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

## 1. Graph-driven package

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
arnold/pipelines/
└── my_pipeline/
    ├── __init__.py          # the Python module
    └── skills/
        └── my-pipeline/
            └── SKILL.md     # agent-facing docs
```

The CLI-visible name is the hyphenated form `my-pipeline`. **Do not use leading `_` or `.` in directory names** — discovery silently skips them.

### Minimal module
Replace the generated `arnold/pipelines/my_pipeline/__init__.py` with the following. The step dataclasses define the work; the `build_pipeline` function wires stages into a graph.

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

_PIPELINE_DIR: Path = Path(__file__).parent


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

If your workflow requires typed schemas, resume logic, or lifecycle hooks instead, use the typed package module form below.

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

Both forms bundle prompts, profiles, and extra files inside the package directory. Resolve paths from `_PIPELINE_DIR` in graph-driven packages, or from the package directory in typed packages.

Example layout for a graph-driven package:

```
my_pipeline/
├── __init__.py
├── skills/
│   └── my-pipeline/
│       └── SKILL.md
├── prompts/
│   └── process.md
└── profiles/
    └── default.toml
```

### Profiles

Profiles are TOML files that map stage names to agent specs. They live in `profiles/` inside the package directory.

1. Create `arnold/pipelines/my_pipeline/profiles/default.toml`:

```toml
[profiles.default]
run = "claude"
```

2. Reference the profile from your module:

```python
default_profile: str | None = "@my-pipeline:default"
supported_modes: tuple[str, ...] = ()
```

3. At runtime the executor loads `@my-pipeline:default` and binds the `run` stage to `claude`.

Profile names use the pipeline's CLI name (`my-pipeline`) and the profile basename (`default`), joined as `@my-pipeline:default`. If you only need a single profile, `default.toml` is conventional. For multi-profile pipelines, add more files and pick one with `--profile` at runtime.

> **Important:** profiles select models, but they do **not** automatically inject a model-calling callable into `AgentStep`. See §7 below for how to wire a worker.

For worked examples, see:

- `arnold/pipelines/epic_blitz/profiles/`
- `arnold/pipelines/writing_panel_strict/profiles/`

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
- If you ship profiles, set `default_profile` to `@<pipeline-name>:<profile-name>` and make sure the file exists at `profiles/<profile-name>.toml`.
- `--inputs` values are always strings.

## 6. Reference implementations

For deeper patterns beyond these basics, study the following examples:

- `arnold/pipelines/_template` — minimal typed package module.
- `arnold/pipelines/evidence_pack` — full typed package module with typed ports, hooks, and resume.
- `arnold/pipelines/epic_blitz` — graph-driven package with parallel review panels.
- `arnold/pipelines/megaplan/pipeline.py` — canonical Megaplan planning graph topology.

For deeper documentation, see `docs/arnold/authoring-guide.md` (hands-on guidance) and `docs/arnold/package-authoring-contract.md` (authoritative field-level contract).

## 7. Wiring a model worker into `AgentStep`

Profiles name *which* model a stage should use, but they **do not** automatically create the callable that invokes the model. If you build a graph pipeline with `AgentStep` stages, you must supply a worker function at construction time; otherwise the step writes a placeholder instead of calling a model.

### The worker contract

`AgentStep` expects a callable with this signature:

```python
def worker(*, prompt: str, step_name: str, pipeline_name: str, inputs: dict[str, str], mode: str) -> Any:
    ...
```

Return a string (or anything that `str()` serializes well). The step writes that value as the versioned artifact.

### Using the native agent dispatcher (recommended)

Arnold provides a default dispatcher via `arnold.agent.dispatch` that already registers the built-in backends (`codex`, `claude`, `shannon`, `hermes`). Use `parse_agent_spec` to turn a profile spec like `codex:gpt-5.5` or `claude:low` into its components, then dispatch an `AgentRequest`:

```python
from typing import Any

from arnold.agent import dispatch
from arnold.agent.contracts import AgentRequest, parse_agent_spec


def _worker(
    *,
    prompt: str,
    step_name: str,
    pipeline_name: str,
    inputs: dict[str, str],
    mode: str,
    spec: str = "codex",
    **kwargs: Any,
) -> str:
    agent_spec = parse_agent_spec(spec)
    request = AgentRequest(
        agent=agent_spec.agent,
        mode="default",
        model=agent_spec.model or "gpt-5.5",
        resolved_model=agent_spec.model,
        effort=agent_spec.effort,
        read_only=True,
        prompt=prompt,
    )
    return dispatch(request).raw_output
```

Agent families (all pre-registered on `arnold.agent.dispatch`):

| Agent key | What it actually runs |
|---|---|
| `codex` | The official OpenAI `codex` CLI. |
| `claude` | Arnold's vendored Shannon/Claude stack (tmux + Claude CLI). |
| `shannon` | Generic vendored Shannon session. |
| `hermes` | In-process `AIAgent` against OpenRouter / native providers. |

Only create your own `ArnoldDispatcher` if you need to register custom adapters. Avoid importing a single adapter (e.g., `CodexAdapter`) and calling it directly — that bypasses retries, sandboxing, timeouts, idle watchdogs, and output parsing handled by the dispatcher.

If you specifically need the **official `claude -p` binary** rather than the Shannon stack, or if you are using a custom local model that has no adapter, use a manual subprocess worker (see below).

> **Free-form vs. structured output:** When `AgentRequest` has no `output_schema` hint, the dispatcher returns plain prose (`result.raw_output`). If you supply `metadata={"output_schema": <schema>}`, the dispatcher enforces that schema and the parsed result lands in `result.payload`.

### Pass the worker through `Pipeline.builder`

```python
def build_pipeline() -> Pipeline:
    builder = Pipeline.builder(
        "my-pipeline",
        description=description,
        pipeline_dir=_PIPELINE_DIR,
        worker=_worker,
    )
    builder.add_stage(
        Stage(
            name="audit",
            step=AgentStep(name="audit", prompt_key="audit_chunk"),
            edges=(Edge(label="done", target="emit"),),
        ),
    )
    return builder.build()
```

`Pipeline.builder(..., worker=...)` copies the callable into every `AgentStep` and `PanelReviewerStep` it creates.

### Manual subprocess fallback

If the native adapters don't fit (e.g., you need the official `claude -p` binary or a custom local model), you can still build a worker that shells out directly:

```python
import subprocess


def _codex_worker(*, prompt, step_name, pipeline_name, inputs, mode):
    result = subprocess.run(
        ["codex", "exec", "--sandbox", "read-only", "--ephemeral", "-m", "gpt-5.5", prompt],
        capture_output=True, text=True, timeout=300,
    )
    result.check_returncode()
    return result.stdout
```

### What happens if you forget the worker

If `_worker` is `None`, `AgentStep.run()` falls back to writing the rendered prompt (or a placeholder string) as the artifact. You will see no model call, no error, and no useful output. Always verify that `_worker` is set before real runs.

### Testing with a fake worker

In tests, pass a fake worker so the pipeline runs deterministically without network calls:

```python
def fake_worker(*, prompt, **kwargs):
    return "fake model output"

pipeline = build_pipeline(worker=fake_worker)
```

Or patch it onto an already-built pipeline:

```python
for stage in pipeline.stages.values():
    if isinstance(stage, Stage) and isinstance(stage.step, AgentStep):
        stage.step._worker = fake_worker
```

See `tests/_pipeline/test_executor_bridge.py` and `tests/_pipeline/test_writing_panel_e2e.py` for the in-repo idiom.

### Profiles vs workers

- **Profiles** (`profiles/*.toml`) map stage names to agent specs like `claude:low` or `codex`. They are resolved into `ctx.profile` and are useful for legacy `InProcessHandlerStep` pipelines or for your own worker function to read.
- **Workers** are the actual callable passed to `AgentStep`. If you want profile-aware dispatch, write a worker that inspects `ctx.profile` (or hard-codes the model) and calls the appropriate backend.

Do not assume that declaring a profile is enough to make an `AgentStep` call a real model.

## 8. Prefer Arnold utilities over custom code

Before you write a small helper, check whether Arnold already provides one. Reaching for the shared primitive keeps pipelines consistent and avoids the bugs that come from reimplementing dispatch, parsing, or filesystem mechanics.

| Task | Use this Arnold primitive | Avoid |
|---|---|---|
| Call a model from a worker | `arnold.agent.dispatch` + `arnold.agent.contracts.AgentRequest` | Importing a single adapter (e.g., `CodexAdapter`) and invoking it directly |
| Parse an agent spec string like `codex:gpt-5.5` | `arnold.agent.contracts.parse_agent_spec` | Splitting the string by hand |
| Extract JSON from model output | `arnold.pipeline.llm_json.parse_llm_json` | `json.loads` plus manual fence/block stripping |
| Write JSON artifacts atomically | `arnold.runtime.state_persistence.atomic_write_json` | `path.write_text(json.dumps(...))` |
| Write text artifacts atomically | `arnold.runtime.state_persistence.atomic_write_text` | `path.write_text(...)` when a partial write would be harmful |
| Ship and resolve prompts | `arnold.pipeline.resources.PipelineResourceBundle` | Hard-coding paths like `Path(__file__).parent / "prompts"` |
| Versioned artifact paths | `arnold.pipeline.artifacts.write_versioned` / `next_version` | Hand-rolled `v1`, `v2`, ... scanning |
| Fan out multiple agent calls | `arnold.agent.contracts.scatter_agent_units` | Raw `ThreadPoolExecutor` + your own request dispatch |

Example: resolving a prompt from the pipeline's own resource bundle:

```python
from arnold.pipeline.resources import PipelineResourceBundle

_bundle = PipelineResourceBundle.from_module(__file__)
prompt_text = _bundle.render_prompt("audit_chunk", ctx, params={"data_json": data_json})
```

Example: atomically writing the final audit JSON:

```python
from arnold.runtime.state_persistence import atomic_write_json

atomic_write_json(ctx.plan_dir / "audit.json", audit_data)
```

If no Arnold utility exists for what you need (e.g., a custom directory-tree walker or a domain-specific summary), keep the helper minimal and pipeline-local. If the same helper shows up in two pipelines, consider promoting it to a shared module under `arnold/pipeline/`.
