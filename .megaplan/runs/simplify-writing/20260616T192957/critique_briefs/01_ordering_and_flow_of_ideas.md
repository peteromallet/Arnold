You are a sharp, concise writing critic. Look at the following piece of writing **only from the perspective of ordering and flow of ideas** and give concrete, actionable feedback. Be specific: quote weak spots and suggest improvements. Keep your response under 800 words.

---
---
name: new arnold pipeline
description: Scaffold and wire a new Megaplan-style Arnold pipeline from scratch.
---

# Creating a new Arnold pipeline (Megaplan-style)

Use this skill when the user wants a new pipeline in the Arnold harness that follows the same planning topology as Megaplan:

```
prep → plan → critique → gate → revise → finalize → execute → review
                              ↑___________|
```

## 1. Scaffold the module

From the repo root:

```bash
python -m arnold pipelines new my-planning-pipeline --driver graph
```

This creates:

```
arnold/pipelines/megaplan/pipelines/
├── my_planning_pipeline.py                 # the Python module
└── my-planning-pipeline/
    └── SKILL.md                            # agent-facing docs
```

The CLI-visible name is the hyphenated form: `my-planning-pipeline`.

## 2. Replace the skeleton `build_pipeline()`

Open `arnold/pipelines/megaplan/pipelines/my_planning_pipeline.py` and paste the following complete module.

```python
"""Python composition of the my-planning-pipeline pipeline."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from arnold.pipelines.megaplan._pipeline.patterns import (
    critique_revise_gate_loop,
    phase_zero_gate,
)
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    PipelineVerdict,
    Stage,
    StepContext,
    StepResult,
)


# ── Module-level contract fields (required + recommended) ────────────────

name: str = "my-planning-pipeline"
description: str = "A minimal planning pipeline with prep, plan, critique, gate, revise, finalize, execute, review."
default_profile: str | None = None          # required by the static manifest reader
supported_modes: tuple[str, ...] = ("code",)  # required by the static manifest reader
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("planning",)


# Directory where prompts and other resources live.
_PIPELINE_DIR: Path = Path(__file__).parent / "my-planning-pipeline"


# ── Step implementations ─────────────────────────────────────────────────
# Each step must expose `name`, `kind`, and a `run(ctx: StepContext) -> StepResult`
# method.  In a real pipeline these runs call models, read/write artifacts,
# and inspect ctx.inputs / ctx.state.


@dataclass
class PrepStep:
    name: str = "prep"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        # Real work: inspect repo, gather context, write a prep artifact.
        return StepResult(next="plan", state_patch={"prepped": True})


@dataclass
class PlanStep:
    name: str = "plan"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="critique", state_patch={"planned": True})


@dataclass
class CritiqueStep:
    name: str = "critique"
    kind: str = "judge"

    def run(self, ctx: StepContext) -> StepResult:
        iteration = int(ctx.state.get("iteration", 0))
        recommendation = "iterate" if iteration < 1 else "proceed"
        return StepResult(
            next="gate",
            state_patch={
                "iteration": iteration + 1,
                "gate_rec": recommendation,
            },
        )


@dataclass
class GateStep:
    name: str = "gate"
    kind: str = "decide"

    def run(self, ctx: StepContext) -> StepResult:
        rec = ctx.state.get("gate_rec", "proceed")
        return StepResult(
            next="gate",
            verdict=PipelineVerdict(score=0.5, recommendation=rec),
        )


@dataclass
class ReviseStep:
    name: str = "revise"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="critique")


@dataclass
class FinalizeStep:
    name: str = "finalize"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="execute")


@dataclass
class ExecuteStep:
    name: str = "execute"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="review")


@dataclass
class ReviewStep:
    name: str = "review"
    kind: str = "judge"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="halt")


# ── Pipeline assembly ────────────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    """Return the canonical my-planning-pipeline graph."""

    prep_stage = phase_zero_gate(
        PrepStep(), name="prep", on_pass="plan", on_fail="halt"
    )

    plan_stage = Stage(
        name="plan",
        step=PlanStep(),
        edges=(Edge(label="critique", target="critique"),),
    )

    cycle = critique_revise_gate_loop(
        CritiqueStep(),
        GateStep(),
        ReviseStep(),
        on_proceed="finalize",
        on_iterate="revise",
        on_tiebreaker="halt",
        on_escalate="halt",
        revise_target="critique",
    )
    # Guard the critique→gate→revise cycle so validation does not complain
    # about an unguarded loop.  The lambda receives the executor's loop state.
    cycle["gate"] = dataclasses.replace(
        cycle["gate"],
        loop_condition=lambda loop_state: int(
            getattr(loop_state, "iteration", 0) or 0
        )
        >= 3,
    )

    finalize_stage = Stage(
        name="finalize",
        step=FinalizeStep(),
        edges=(Edge(label="execute", target="execute"),),
    )
    execute_stage = Stage(
        name="execute",
        step=ExecuteStep(),
        edges=(Edge(label="review", target="review"),),
    )
    review_stage = Stage(
        name="review",
        step=ReviewStep(),
        edges=(Edge(label="halt", target="halt"),),
    )

    return Pipeline(
        stages={
            "prep": prep_stage,
            "plan": plan_stage,
            "critique": cycle["critique"],
            "gate": cycle["gate"],
            "revise": cycle["revise"],
            "finalize": finalize_stage,
            "execute": execute_stage,
            "review": review_stage,
        },
        entry="prep",
    )


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

### What the pieces mean

| Field | Required? | Notes |
|---|---|---|
| `name` | **yes** | CLI-visible name. Must match the hyphenated form derived from the file name. |
| `description` | **yes** | One-liner shown in `arnold pipelines list`. |
| `arnold_api_version` | **yes** | Keep `"1.0"` unless targeting a newer SDK. |
| `capabilities` | **yes** | Non-empty tuple of labels. |
| `driver` | **yes** | Use `("graph", "dispatch+emit")` for graph-driven pipelines; `"in_process"` for simple in-process graphs. |
| `entrypoint` | **yes** | Bare name `"build_pipeline"` or fully-qualified `"module:name"`. |
| `build_pipeline` | **yes** | Nullary callable returning a `Pipeline`. |
| `default_profile` | recommended | Declare even as `None`; the static manifest reader requires it. |
| `supported_modes` | recommended | Declare even as `()`; the static manifest reader requires it. |

## 3. Add prompts (optional)

For model-backed stages, place prompt files next to `SKILL.md`:

```
arnold/pipelines/megaplan/pipelines/my-planning-pipeline/
├── SKILL.md
└── prompts/
    ├── plan.md
    ├── critique.md
    └── execute.md
```

Prompt paths are resolved relative to `_PIPELINE_DIR`.  A stage can read a prompt directly:

```python
prompt_text = (_PIPELINE_DIR / "prompts" / "plan.md").read_text()
```

Or use the built-in `AgentStep` / `PipelineBuilder.agent(..., prompt="prompts/plan.md")` machinery.  See `arnold/pipelines/megaplan/_pipeline/steps/agent.py` and the `creative` pipeline for real examples.

## 4. Add a profile (optional)

If you want `--profile my-planning-pipeline:default` to work, create:

```
arnold/pipelines/megaplan/pipelines/my-planning-pipeline/profiles/default.toml
```

```toml
[profiles.default]
prep     = "hermes:deepseek:deepseek-v4-pro"
plan     = "claude"
critique = "hermes:deepseek:deepseek-v4-pro"
execute  = "hermes:deepseek:deepseek-v4-pro"
review   = "claude"
```

The keys are your stage names.  Values are agent specs understood by the Megaplan key pool (`claude`, `codex`, `hermes:deepseek:deepseek-v4-pro`, etc.).

## 5. Validate and run

```bash
# Must pass with zero defects.
python -m arnold pipelines check my-planning-pipeline

# List it.
python -m arnold pipelines list

# Run it.
python -m arnold run my-planning-pipeline "Implement a dark mode toggle"
```

`arnold run` maps the positional argument to `ctx.inputs["draft"]`.

## 6. Common gotchas

- **No leading underscore.** Files or directories starting with `_` or `.` are silently skipped by the discovery scanner. The `_template` package is named that way on purpose.
- **`build_pipeline()` must be callable with no arguments.** The registry calls it as `builder()` during discovery and validation.
- **Declare `default_profile` and `supported_modes` even if empty.** The runtime validator only warns about them (`info:`), but the static manifest reader rejects packages that omit them.
- **Guard every cycle.** If your graph has a back-edge, attach a `loop_condition` to a stage in the cycle, otherwise `arnold pipelines check` fails with `unguarded_cycle_detected`.
- **Decision routing uses `PipelineVerdict.recommendation`.** Gate stages need `kind="decide"` steps that return `StepResult(verdict=PipelineVerdict(recommendation="..."))`. The executor matches that against `kind="decision"` edges.
- **Keep module-level metadata as simple literals.** The static manifest reader parses the file with AST literal eval; it cannot follow function calls, aliases, or dynamic values.
- **SKILL.md location matters.** For a sibling-file module like `my_planning_pipeline.py`, the registry looks for `my-planning-pipeline/SKILL.md` next to the file. The scaffold already creates it.

## 7. Where to look for reference implementations

- `arnold/pipelines/megaplan/pipeline.py` — the canonical Megaplan planning graph.
- `arnold/pipelines/megaplan/pipelines/creative/__init__.py` — a model-backed multi-stage pipeline.
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py` — a sibling-file pipeline with panels.
- `arnold/pipelines/evidence_pack/` — a package-style pipeline under `arnold/pipelines/` with typed ports, hooks, and continuation.
- `docs/arnold/authoring-guide.md` and `docs/arnold/package-authoring-contract.md` — full contract details.

---
