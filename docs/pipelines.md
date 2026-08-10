# Defining a pipeline on the Arnold substrate

This document describes how to compose pipelines using the generic Arnold graph-execution
substrate (`arnold.pipeline`) and how the Megaplan built-in planning/execution plugin
consumes that substrate as one regular pipeline package.

## Architecture

Arnold provides the **mechanics**: graph execution, evidence recording, typed routing,
fan-out/fan-in, loops, subpipelines, plugin discovery, and runtime services. It answers
"how do pipelines compose, run, pause, route, fan out, persist artifacts, or validate
data?"

Megaplan is a **consumer plugin** (`arnold_pipelines.megaplan`) that provides robust
planning and execution intent: prep → plan → critique → gate → revise → tiebreaker →
finalize → execute → review → feedback. It answers "how should a robust planning
workflow behave?" Megaplan reads like composition of Arnold primitives and owns its
own decision vocabulary, stage implementations, prompts, profiles, and control policy.

Other plugins (doc, creative, custom pipelines) consume the same generic substrate
without importing Megaplan policy.

## Generic substrate (graph execution + evidence)

### Conceptual model

An Arnold pipeline is a small directed graph executed by the neutral executor. Three
primitives compose it:

* **Stage** — a node holding a `Step` implementation (the actual work) and a tuple of
  outgoing `Edge` instances. A `ParallelStage` runs multiple `Step` instances concurrently
  with a `join` callable that folds their results into one.
* **Edge** — a labelled transition. `Edge(label, target, kind="normal")` matches
  `StepResult.next == label`. `Edge(... kind="gate", recommendation="proceed")` matches
  the typed `PipelineVerdict.recommendation` before any label fallback. Decision keys
  (`"proceed"`, `"iterate"`, etc.) are plugin-owned — Arnold never hardcodes them.
* **PipelineVerdict** — an optional structured outcome on a `StepResult`
  (`score`, `recommendation: str | None`, `override: str | None`). Gate and decision steps
  emit it; the executor's typed dispatch routes on it.

Two more concepts round the model out:

* **Pattern** — a stateless function from `arnold.pipeline.patterns` that returns the
  appropriate primitive (`Stage`, `ParallelStage`, `dict[str, Stage]`, or a `join`
  callable). Patterns encode recurring topologies — critique loops, panels, subpipeline
  calls, prompt variants — so individual pipelines stay short.
* **Overlay** — a `Pipeline → Pipeline` transform stashed on `Pipeline.overlays`. This
  remains an optional low-level primitive for local graph transforms.

A pipeline runs from `Pipeline.entry`. Each Stage's Step emits a `StepResult`; the
executor picks the outgoing edge whose typed recommendation (or, failing that, label)
matches and advances to the target. The pipeline terminates when the chosen target is the
magic sentinel `"halt"` (or via `result.next == "halt"`).

### Evidence recording

Arnold records evidence at every step — what ran, what it produced, how it routed — in a
neutral envelope that does not interpret plugin semantics. The Evidence-First authority
and provenance system (`TrustClass`, completion contracts, evidence gates) operates on
this neutral record. Megaplan consumes evidence through its own completion contracts and
review policy, but the substrate itself carries no planning semantics.

### Builder basics

`Pipeline.builder(name, description="", *, default_profile=None, supported_modes=())`
returns a chained `PipelineBuilder`. The builder is sugar over `Pipeline / Stage / Edge`;
`.build()` returns a plain frozen `Pipeline`. Pipeline-level metadata (description,
default_profile, supported_modes) is held on the builder and surfaced through
`PipelineRegistry.metadata`, not on the `Pipeline` dataclass.

```python
from arnold.pipeline.types import Pipeline

pipeline = (
    Pipeline.builder("my-pipeline", description="...")
        .input("draft", file=True)
        .agent("plan", prompt="prompts/plan.md", inputs=["draft"])
        .agent("revise", prompt="prompts/revise.md", inputs=["plan"])
        .build()
)
```

`.agent` / `.panel` / `.subpipeline` auto-link from the previously added stage using that
stage's natural emit label. `.gate` / `.human_gate` / `.tiebreaker` own their outgoing edges
explicitly — they do not auto-link, so the caller wires every transition via the method's
own `extra_edges` / `edges` argument.

The first added stage becomes `Pipeline.entry`.

## Megaplan as a consumer plugin

Megaplan lives at `arnold_pipelines/megaplan/` and is discovered by the generic plugin
registry like any other pipeline package. It exposes `build_pipeline()` returning a
`Pipeline` graph that composes generic Arnold primitives (`AgentStep`, `PanelStep`,
decision routing, subpipelines, loops) with Megaplan-owned policy:

- **Decision vocabulary:** `proceed`, `iterate`, `tiebreaker`, `escalate` — owned by
  Megaplan's gate stage, not by generic Arnold types.
- **Override actions:** `force_proceed`, `abort`, `replan`, `add_note` — owned by
  Megaplan's control binding.
- **Robustness topology:** prep → plan → critique → gate → revise/tiebreaker → finalize
  → execute → review → feedback, with loop depth and reviewer counts determined by
  the robustness level (`bare`, `light`, `full`, `thorough`, `extreme`).
- **Stage implementations:** All concrete planning stages (`prep.py`, `plan.py`,
  `critique.py`, `gate.py`, `revise.py`, `tiebreaker.py`, `finalize.py`, `execute.py`,
  `review.py`) live under `arnold_pipelines/megaplan/stages/`.
- **Prompts:** Megaplan prompt builders live under `arnold_pipelines/megaplan/prompts/`.
- **Profiles:** Megaplan model-routing defaults and stage-key validation live under
  `arnold_pipelines/megaplan/profiles/`.
- **State and control:** `PlanState`, robustness state machine, `ControlBinding`, and
  status/override projection live in the plugin.

The generic Arnold runtime has no imports from Megaplan stages, handlers, prompts, or
state constants. It has no hardcoded `"planning"` string literals, no Megaplan gate
labels as type-level policy, and no Megaplan phase lists as platform constants.

### CLI invocation

```bash
# NOTE: the legacy `arnold run megaplan <brief>` / `arnold pipelines list` forms
# are obsolete — `run` is not an `arnold` verb and `pipelines` is not an `arnold` command.
# Megaplan is driven by its own CLI:
python -m arnold_pipelines.megaplan init <brief>   # plan and run a brief
# The workflow runtime runs the compiled megaplan pipeline as:
arnold workflow run --module arnold_pipelines.megaplan.pipeline:build_pipeline
# Pipeline discovery/inspection is via the megaplan `pipelines` command (new|check|doctor).
```

## Built-in pipelines

The in-tree pipelines are selected by name from the registry:

* `megaplan` is compiled by `arnold_pipelines.megaplan.pipeline.build_pipeline()` — the
  flagship robust planning and execution plugin.
* `doc` lives under `arnold/pipelines/doc/` and owns its document topology and prompt
  registrations.
* `creative` lives under `arnold/pipelines/creative/` and owns its form-aware topology
  and prompt registrations.

All three consume the same generic Arnold substrate without special-cased dispatch.

## Pattern library

The pattern library in `arnold.pipeline.patterns` provides reusable topology shapes
parameterized by plugin-owned routing keys — not by hardcoded planning vocabulary.

### `critique_revise_gate_loop(critique_step, gate_step, revise_step, *, on_proceed, on_iterate, on_tiebreaker, on_escalate, critique_fallback_edges=(), gate_extra_edges=(), revise_target="critique")`

Composes the critique → gate → revise cycle as three `Stage`s. The gate stage carries the
four required `kind="gate"` recommendation edges (iterate / proceed / tiebreaker / escalate)
followed by any caller-supplied `gate_extra_edges`. `revise` loops to `revise_target`
(default `"critique"`). Megaplan's planning pipeline is the canonical consumer.

```python
stages = critique_revise_gate_loop(
    CritiqueStep(), GateStep(), ReviseStep(),
    on_proceed="finalize", on_iterate="revise",
    on_tiebreaker="tiebreaker", on_escalate="finalize",
    gate_extra_edges=(Edge("override force-proceed", "finalize"),),
)
```

### `panel_parallel(name, reviewers, *, edges=(), merge_strategy="none", max_workers=None, next_label="next")`

Pure `ParallelStage` fan-out: each `(reviewer_id, Step)` pair runs concurrently.

### `decision(name, decisions, overrides=(), *, prompt=None, ...)`

Generic decision routing: accepts plugin-owned decision keys and override actions.
The executor dispatches typed `PipelineVerdict.recommendation` on `kind="gate"` edges.
This is the generic replacement for Megaplan's old four-way `.gate(on_proceed, on_iterate,
on_tiebreaker, on_escalate)`.

```python
gate = p.decision(
    "gate",
    prompt="gate.md",
    decisions=("proceed", "iterate", "tiebreaker", "escalate"),
    overrides=("force_proceed", "abort", "replan", "add_note"),
)
```

### `subpipeline_call(child_pipeline, *, promote, artifact_subdir=None, name="subpipeline")`

Runs `child_pipeline` as a nested pipeline; `promote` maps the child's terminal state to
a recommendation on the parent's `PipelineVerdict`.

### Additional patterns

- `alternating_turns(roles, *, ...)` — linear N-agent chain
- `iterate_until(stage, *, condition, max_iterations=10, ...)` — bounded self-loop
- `escalate_if(condition, escalation_handler)` — conditional escape edge
- `majority_vote(panel_output_key="verdict", *)` — panel join callable
- `weighted_vote(weights, *)` — weighted panel join
- `phase_zero_gate(step, *, on_pass, on_fail, ...)` — preflight pass/fail gate
- `panel_from_artifact(artifact_ref, base_template, join, *, name)` — dynamic panel
- `dynamic_fanout(generator, base_prompt, join, *, name)` — runtime fan-out
- `iterate_until_consensus(panel, min_agreement=0.8, max_iters=3, *, name)` — consensus loop
- `paired_round(advocates, *, sees_other=True, name)` — alternating turns with prior visibility

## Writing a user-installed pipeline

Drop a single Python module at `~/.arnold/pipelines/<name>.py`. The registry's
`discover_python_pipelines()` runs lazily on first registry access. The module must expose
a `build_pipeline()` callable returning a `Pipeline`:

```python
# ~/.arnold/pipelines/my_pipeline.py
from pathlib import Path

from arnold.pipeline.types import Pipeline
from arnold.pipeline.steps.agent import AgentStep

description: str = "One-shot draft → polish."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("polish", "restructure")
name: str = "my-pipeline"
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"

_PIPELINE_DIR = Path(__file__).parent / "my-pipeline"

def build_pipeline() -> Pipeline:
    return (
        Pipeline.builder(
            "my-pipeline",
            description=description,
            default_profile=default_profile,
            supported_modes=supported_modes,
            pipeline_dir=_PIPELINE_DIR,
        )
        .input("draft", file=True)
        .agent("polish", prompt="prompts/polish.md", inputs=["draft"])
        .build()
    )
```

The CLI-visible pipeline name is the file stem with underscores rewritten to hyphens
(`my_pipeline.py` → `my-pipeline`). A co-located `SKILL.md` sibling surfaces through
`PipelineRegistry.read_skill_md(name)`.

## Clean boundary

The generic Arnold runtime (`arnold/pipeline`, `arnold/runtime`) must never:

- Import from `arnold_pipelines.megaplan`
- Contain `"planning"` as a string literal
- Hardcode Megaplan gate labels (`proceed`, `iterate`, `tiebreaker`, `escalate`) as type-level policy
- Hardcode Megaplan phase names (`prep`, `plan`, `critique`, `gate`, `revise`, `finalize`,
  `execute`, `review`, `feedback`) as platform constants
- Reference Megaplan state constants, prompt builders, or profile semantics
- Contain shell commands referencing `.megaplan/plans`, `megaplan init`, `megaplan auto`,
  or `MEGAPLAN_*` environment variables

## Where to look next

* `arnold/pipeline/patterns.py` — pattern library with module docstring
* `arnold/pipeline/builder.py` — chained-builder source with auto-link rules
* `arnold/pipeline/executor.py` — neutral graph executor
* `arnold/pipeline/types.py` — generic pipeline types (no planning vocabulary)
* `arnold_pipelines/megaplan/pipeline.py` — Megaplan plugin composition
* `arnold/pipelines/doc/` — document pipeline (no gate, no planning)
* `arnold/pipelines/creative/` — creative pipeline (form-aware)
* `tests/arnold/pipeline/` — generic substrate tests
* `tests/pipelines/megaplan/` — Megaplan plugin tests
