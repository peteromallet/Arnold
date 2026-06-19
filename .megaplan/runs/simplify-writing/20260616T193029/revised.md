```yaml
---
name: new arnold pipeline
description: Scaffold a new Megaplan-style Arnold pipeline.
---

# Creating a new Arnold pipeline (Megaplan-style)

Use this skill when you need a new pipeline in the Arnold harness that follows Megaplan's planning structure: an initial prep phase, a plan stage, a critique→gate→revise quality loop that repeats until the plan passes, and a final execute→review chain.

```
prep → plan → critique → gate → revise → finalize → execute → review
                              ↑___________|
```

The **critique→gate→revise** loop is the quality-control heart of the pipeline. `critique` evaluates the current plan; `gate` decides whether to iterate or proceed; if it decides to iterate, `revise` improves the plan and sends it back to `critique`. Two helpers from Megaplan's pattern library handle this: `phase_zero_gate` validates prerequisites before the main graph runs, and `critique_revise_gate_loop` builds the quality cycle with built-in routing.

This guide covers: scaffolding the module, declaring the module contract, wiring the full graph, validation, and optional extensions (prompts and profiles).

## 1. Scaffold the module

From the repo root:

```bash
python -m arnold pipelines new my-planning-pipeline --driver graph
```

This creates a **sibling-file** module — a `.py` file alongside a same-named directory that holds `SKILL.md` and optional resources:

```
arnold/pipelines/megaplan/pipelines/
├── my_planning_pipeline.py
└── my-planning-pipeline/
    ├── SKILL.md
    └── prompts/          # optional; add later
        └── plan.md
```

The CLI-visible name is the hyphenated form: `my-planning-pipeline`.

**⚠️ Discovery silently skips files and directories starting with `_` or `.`.** The scaffold uses compliant names; don't rename them with a leading underscore.

## 2. Understand the module contract

Before you replace the skeleton, the static manifest reader (which scans your file at import time without executing it) expects several module-level literals. These must be plain values — no function calls, variables, or computed expressions.

**Manifest fields (static reader):**

| Field | Required? | Notes |
|---|---|---|
| `name` | yes | CLI-visible name. Must match the hyphenated form derived from the file name. |
| `description` | yes | One-liner shown in `arnold pipelines list`. |
| `arnold_api_version` | yes | Keep `"1.0"` unless targeting a newer SDK. |
| `capabilities` | yes | Non-empty tuple of labels, e.g. `("planning",)`. |
| `default_profile` | yes* | Declare as `None` if unused. Required by the static reader. |
| `supported_modes` | yes* | Declare as `()` if unused. Required by the static reader. |

\* The runtime validator only warns if these are missing, but the static reader rejects the package.

**Runtime contract (executor / registry):**

| Field | Required? | Notes |
|---|---|---|
| `driver` | yes | `("graph", "dispatch+emit")` publishes stage transitions over the message bus for multi-process execution. Use `("graph", "in_process")` for a single-process graph. |
| `entrypoint` | yes | Bare name `"build_pipeline"` or fully-qualified `"module:name"`. |
| `build_pipeline` | yes | A function that takes no arguments and returns a `Pipeline`. |

## 3. Replace the skeleton module

Open `arnold/pipelines/megaplan/pipelines/my_planning_pipeline.py` and replace the entire contents with the module below.

**What to notice as you read:**
- Each step class follows the same `run(ctx: StepContext) -> StepResult` pattern.
- `StepResult.next` routes to the next stage name.
- `phase_zero_gate` wraps `prep`, routing to `plan` on success or `halt` on failure.
- `critique_revise_gate_loop` builds the critique→gate→revise cycle. The `loop_condition` caps iterations at 3 so the loop always terminates and the validator accepts the graph.

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

# ── Module-level contract fields ──────────────────────────────────────────

name: str = "my-planning-pipeline"
description: str = (
    "A minimal planning pipeline with prep, plan, critique, gate, "
    "revise, finalize, execute, review."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("code",)
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("planning",)

# Directory where prompt templates, profiles, and SKILL.md live.
_PIPELINE_DIR: Path = Path(__file__).parent / "my-planning-pipeline"

# ── Step implementations ─────────────────────────────────────────────────
# Each step exposes `name`, `kind`, and `run(ctx: StepContext) -> StepResult`.
# Replace the stub bodies with real logic; for now, notice how they chain
# stages via `next=`.

@dataclass
class PrepStep:
    name: str = "prep"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        # Replace with: inspect the repository, gather context, write a prep artifact.
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
    """Return the default my-planning-pipeline graph."""

    prep_stage = phase_zero_gate(
        PrepStep(), name="prep", on_pass="plan", on_fail="halt"
    )

    plan_stage = Stage(
        name="plan",
        step=PlanStep(),
        edges=(Edge(label="critique", target="critique"),),
    )

    max_iterations = 3

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

    # Guard the critique→gate→revise cycle so the validator accepts it.
    # Halt the loop after max_iterations passes.
    cycle["gate"] = dataclasses.replace(
        cycle["gate"],
        loop_condition=lambda loop_state: int(
            getattr(loop_state, "iteration", 0) or 0
        ) >= max_iterations,
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

## 4. Validate and run

Once the module is in place, check it:

```bash
# Must pass with zero defects.
python -m arnold pipelines check my-planning-pipeline
```

List it:

```bash
python -m arnold pipelines list
```

Run it:

```bash
python -m arnold run my-planning-pipeline "Implement a dark mode toggle"
```

`arnold run` maps the positional argument to `ctx.inputs["draft"]`. If the check passed and the run succeeded, your skeleton is live.

## 5. Optional: Add prompts and profiles

### Prompts
For model-backed stages, place prompt files in the pipeline directory:

```
arnold/pipelines/megaplan/pipelines/my-planning-pipeline/
├── SKILL.md
└── prompts/
    ├── plan.md
    ├── critique.md
    └── execute.md
```

Load them directly in your step:

```python
prompt_text = (_PIPELINE_DIR / "prompts" / "plan.md").read_text()
```

Or use the built-in `AgentStep` class and `PipelineBuilder.agent()` helper. For real examples, see `arnold/pipelines/megaplan/pipelines/creative/__init__.py`.

### Profiles
If you want `--profile my-planning-pipeline:default` to resolve, add a TOML file:

```toml
# arnold/pipelines/megaplan/pipelines/my-planning-pipeline/profiles/default.toml
[profiles.default]
prep     = "hermes:deepseek:deepseek-v4-pro"
plan     = "claude"
critique = "hermes:deepseek:deepseek-v4-pro"
execute  = "hermes:deepseek:deepseek-v4-pro"
review   = "claude"
```

Each value is a model identifier: a plain name (`claude`) uses the default provider; a colon-separated spec (`provider:vendor:model`) targets a specific endpoint.

## 6. Common pitfalls

- **`build_pipeline()` must take no arguments.** The registry calls it as `builder()` during discovery.
- **Guard every cycle.** If your graph has a back-edge, attach a `loop_condition` to a stage in the cycle. Without it, `arnold pipelines check` fails with `unguarded_cycle_detected`.
- **Decision routing uses `PipelineVerdict.recommendation`.** Gate stages need `kind="decide"` steps that return `StepResult(verdict=PipelineVerdict(recommendation="..."))`. The executor matches that against the edge label. For example, a recommendation of `"iterate"` follows the edge labeled `iterate`; `"proceed"` follows the edge labeled `proceed`.
- **Keep module-level metadata as simple literals.** The static reader parses the file with AST literal eval; it cannot follow function calls or aliases.

## 7. Reference

Where to look next based on what you're building:

- **The canonical planning graph** — `arnold/pipelines/megaplan/pipeline.py`
- **Model-backed multi-stage pipeline** — `arnold/pipelines/megaplan/pipelines/creative/__init__.py`
- **Sibling-file pipeline with panels** — `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
- **Package-style pipeline with typed ports and hooks** — `arnold/pipelines/evidence_pack/`
- **Full authoring contract** — `docs/arnold/authoring-guide.md` and `docs/arnold/package-authoring-contract.md`
