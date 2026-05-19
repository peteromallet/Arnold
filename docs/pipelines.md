# Defining a pipeline in megaplan

This document describes how to compose pipelines in megaplan 0.22.0+ using
the Python composition framework. The previous YAML runtime was removed in
0.22.0; see `docs/yaml-pipelines-migration.md` for the experiment write-up.

## Conceptual model

A megaplan pipeline is a small directed graph executed by
`megaplan._pipeline.executor.run_pipeline`. Three primitives compose it:

* **Stage** — a node holding a `Step` implementation (the actual work) and
  a tuple of outgoing `Edge` instances. A `ParallelStage` is the same idea
  with a tuple of `Step` instances run concurrently plus a `join` callable
  that folds their `StepResult`s into one.
* **Edge** — a labelled transition. `Edge(label, target, kind="normal",
  recommendation=None)` matches `StepResult.next == label` when
  `kind="normal"`. `Edge(... kind="gate", recommendation="proceed")` matches
  the **typed** `Verdict.recommendation` ahead of any label fallback.
* **Verdict** — an optional structured outcome on a `StepResult`
  (`score`, `recommendation ∈ {"proceed","iterate","tiebreaker","escalate"}`).
  Gate Steps emit it; the executor's typed dispatch routes on it.

Two more concepts round the model out:

* **Pattern** — a stateless function from `megaplan._pipeline.patterns`
  that returns the appropriate primitive (`Stage`, `ParallelStage`,
  `dict[str, Stage]`, or a `join` callable). Patterns encode the recurring
  topologies — critique loops, panels, subpipeline calls, mode overlays —
  so individual pipelines stay short.
* **Overlay** — a `Pipeline → Pipeline` transform stashed on
  `Pipeline.overlays`. Used for runtime variants (mode prompts,
  robustness levels) that rewrite Steps without changing topology.

A pipeline runs from `Pipeline.entry`. Each Stage's Step emits a
`StepResult`; the executor picks the outgoing edge whose typed
recommendation (or, failing that, label) matches and advances to the
target. The pipeline terminates when the chosen target is the magic
sentinel `"halt"` (or `"done"` if explicitly wired to it).

## Builder basics

`Pipeline.builder(name, description="", *, default_profile=None,
supported_modes=())` returns a chained `PipelineBuilder`. The builder is
sugar over `Pipeline / Stage / Edge`; `.build()` returns a plain frozen
`Pipeline`. Pipeline-level metadata (description, default_profile,
supported_modes) is held on the builder and surfaced through
`PipelineRegistry.metadata`, not on the `Pipeline` dataclass.

```python
from megaplan._pipeline.types import Pipeline

pipeline = (
    Pipeline.builder("my-pipeline", description="...")
        .input("draft", file=True)
        .agent("plan", prompt="prompts/plan.md", inputs=["draft"])
        .agent("revise", prompt="prompts/revise.md", inputs=["plan"])
        .build()
)
```

`.agent` / `.panel` / `.subpipeline` auto-link from the previously added
stage using that stage's natural emit label (`"done"` for `AgentStep`,
`"next"` for `panel_parallel`'s join, `"proceed"` for `SubloopStep`).
`.gate` / `.human_gate` / `.tiebreaker` own their outgoing edges
explicitly — they do not auto-link, so the caller wires every transition
via the method's own `extra_edges` / `edges` argument.

The first added stage becomes `Pipeline.entry`.

## Pattern library

The nine functions in `megaplan._pipeline.patterns` cover the shapes the
existing pipelines reuse and the shapes the six worked examples below
require.

### `critique_revise_gate_loop(critique_step, gate_step, revise_step, *, on_proceed, on_iterate, on_tiebreaker, on_escalate, critique_fallback_edges=(), gate_extra_edges=(), revise_target="critique")`

Composes the critique → gate → revise cycle as three `Stage`s. The gate
stage carries the four required `kind="gate"` recommendation edges
(iterate / proceed / tiebreaker / escalate) followed by any
caller-supplied `gate_extra_edges`. `revise` loops to `revise_target`
(default `"critique"`). This is the load-bearing shape behind
`compile_planning_pipeline()`.

```python
stages = critique_revise_gate_loop(
    CritiqueStep(), GateStep(), ReviseStep(),
    on_proceed="finalize", on_iterate="revise",
    on_tiebreaker="tiebreaker", on_escalate="finalize",
    gate_extra_edges=(Edge("override force-proceed", "finalize"),),
)
```

### `panel_parallel(name, reviewers, *, edges=(), merge_strategy="none", max_workers=None, next_label="next")`

Pure `ParallelStage` fan-out: each `(reviewer_id, Step)` pair runs
concurrently. The built-in join collates per-reviewer outputs into
`{reviewer_id}.{label}` keys preserving reviewer-list order, so a
downstream agent referencing `<panel>.*` resolves them in order.

```python
stage = panel_parallel(
    "panel_review",
    reviewers=(
        ("pessimist",    PanelReviewerStep(...)),
        ("optimist",     PanelReviewerStep(...)),
        ("structuralist",PanelReviewerStep(...)),
    ),
)
```

### `alternating_turns(roles, *, history_strategy="append", max_rounds=10, until_condition=None, loop_target=None)`

Linear N-agent chain `role_0 → role_1 → ... → role_(N-1)` where the
terminal role loops back to `loop_target` (default: first role). Use for
two-agent debates or workshop turns. Wrap with `iterate_until` to add a
counting / escape stage.

```python
stages = alternating_turns(roles=(
    ("writer",  AgentStep(name="writer",  ...)),
    ("editor",  AgentStep(name="editor",  ...)),
))
```

### `subpipeline_call(child_pipeline, *, promote, artifact_subdir=None, name="subpipeline")`

Thin wrapper around `SubloopStep`. Runs `child_pipeline` as a nested
pipeline; `promote` maps the child's terminal `state` dict to a
`GateRecommendation` on the parent's `Verdict`. The child runs against a
copy of the parent state — its state patches do **not** flow back
in-process. Anything the parent needs back must be read from on-disk
artifacts under `artifact_subdir`.

```python
step = subpipeline_call(
    build_tiebreaker_pipeline(),
    promote=lambda s: "iterate" if s["current_state"] == "critiqued" else "proceed",
    artifact_subdir="tiebreaker",
)
```

### `mode_prompts(modes_dict)`

Returns `Callable[[mode_name], Overlay]`. The overlay rewrites each
matching `Stage`'s Step via `dataclasses.replace` setting a new
`prompt_key` per the `{mode: {stage: prompt_key}}` map. Topology is
untouched; non-dataclass Steps and `ParallelStage`s pass through.

```python
overlay_for_polish = mode_prompts({
    "polish":     {"revise": "revise_polish"},
    "restructure":{"revise": "revise_restructure"},
})("polish")
```

### `iterate_until(stage, *, condition, max_iterations=10, iterate_label="iterate", halt_label="halt")`

Adds a self-loop edge and a halt edge to *stage*. The wrapped Step's
`run()` consults `condition` against `StepContext.state` and emits
`next=iterate_label` to continue or `next=halt_label` to terminate.

```python
counted = iterate_until(stage_x, condition=lambda s: s["round"] < 3)
```

### `escalate_if(condition, escalation_handler)`

Returns the `(handler_step, escape_edge)` pair. `escape_edge` is a
`kind="gate"` `recommendation="escalate"` edge the caller appends to the
host stage's edges; the handler is added to the graph as a standalone
stage. `condition` documents when the host Step should emit a `Verdict`
with `recommendation="escalate"`.

```python
handler, escape = escalate_if(
    condition=lambda s: s.get("blocked"),
    escalation_handler=EscalateStep(name="escalate"),
)
```

### `majority_vote(panel_output_key="verdict")`

Returns a `join` callable for `panel_parallel(..., join=majority_vote())`
patterns. Tallies each reviewer's `verdict.recommendation`; the majority
wins, ties resolve to `"tiebreaker"`, empty panels also yield
`"tiebreaker"`. The synthetic result carries a `Verdict` plus
`next=<recommendation>` so a downstream gate stage can dispatch on
either typed or label-fallback edges.

```python
panel = panel_parallel(
    "judges",
    reviewers=(("a", JudgeStep(...)), ("b", JudgeStep(...)), ("c", JudgeStep(...))),
)
# Replace the default join with majority_vote() when constructing the
# pipeline manually:
panel = ParallelStage(name="judges", steps=panel.steps, join=majority_vote())
```

### `phase_zero_gate(step, *, name="prep", on_pass="plan", on_fail="halt", criteria=None)`

Phase-0 objective gate. Runs *step* and routes its emitted next-label to
`on_pass` or `on_fail`. Carries three edges so it handles explicit
`"pass"` / `"fail"` labels plus the bare next-label fallback used by
megaplan's existing `PrepStep` (`next=on_pass`).

```python
prep = phase_zero_gate(PrepStep(), name="prep", on_pass="plan", on_fail="halt")
```

## Subloop edges: a load-bearing convention

Pipelines using `subpipeline_call`, the `PipelineBuilder.subpipeline`
method, or the canonical `TiebreakerStep` (planning's
`tiebreaker` stage) **MUST** declare `kind="gate"` recommendation edges
on the host stage, not `kind="normal"` label edges. The executor's typed
dispatch resolves the `Verdict.recommendation` produced by the subloop's
`promote` callable; label-only edges will never match. The planning
pipeline's tiebreaker stage is the canonical example:

```python
Stage(
    name="tiebreaker",
    step=TiebreakerStep(),
    edges=(
        Edge(label="", target="critique", kind="gate", recommendation="iterate"),
        Edge(label="", target="finalize", kind="gate", recommendation="proceed"),
        Edge(label="", target="finalize", kind="gate", recommendation="escalate"),
    ),
)
```

`PipelineBuilder.tiebreaker()` plugs in this exact edge tuple by
default. For user-built subpipeline stages, mirror the shape.

## Panel → agent fan-in convention

`PipelineBuilder.panel("p", reviewers=[("a", ...), ("b", ...), ("c", ...)])`
records the reviewer order on the builder. Every downstream
`.agent("synth", inputs=["p.*"])` call receives that ordering as a
`_panel_reviewer_order` mapping on the constructed `AgentStep`. At
runtime, `step_helpers.resolve_inputs` expands `<panel>.*` references
into the per-reviewer artifact paths in reviewer-list order
(`p/a/v<N>.md`, `p/b/v<N>.md`, `p/c/v<N>.md`).

The mapping uses a **private** dataclass field
(`_panel_reviewer_order`) — this is a deliberate locked decision so the
underscore-prefixed config fields on `AgentStep` /
`PanelReviewerStep` (`_prompt_ref`, `_pipeline_dir`, `_input_refs`,
`_worker`, ...) stay consistent. Builders inject it; user code should
not read or set it directly.

## Writing a user-installed pipeline

Drop a single Python module at `~/.megaplan/pipelines/<name>.py`. The
registry's `discover_python_pipelines()` runs lazily on first registry
access. The module must expose a `build_pipeline()` callable returning a
`Pipeline`; the following module-level constants are optional and
surface through `PipelineRegistry.metadata`:

```python
# ~/.megaplan/pipelines/my_pipeline.py
from pathlib import Path

from megaplan._pipeline.types import Pipeline
from megaplan._pipeline.steps.agent import AgentStep

description: str = "One-shot draft → polish."
default_profile: str = "@my-pipeline:standard"
supported_modes: tuple[str, ...] = ("polish", "restructure")
recommended_profiles: tuple[str, ...] = ("@my-pipeline:standard",)

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

The CLI-visible pipeline name is the file stem with underscores rewritten
to hyphens (`my_pipeline.py` → `my-pipeline`). A co-located
`<cli-visible-name>/SKILL.md` sibling, if present, surfaces through
`PipelineRegistry.read_skill_md(name)`; if absent the registry returns
`None` (no `FileNotFoundError`).

Three names are reserved for the hardcoded built-ins: `planning`,
`doc-critique`, `judges`. Discovery emits a `UserWarning` and skips any
sibling that would collide.

## Six worked-example pipeline shapes

These are **documentation examples**, not runnable pipelines. They show
how the pattern library composes to cover the scenario shapes surveyed
during the v0.22.0 design work. Each example is a build sketch — fill in
your own Step implementations.

### 1. Panel-of-7

A wide adversarial panel feeding a synthesiser, then a single gate.

```python
pipeline = (
    Pipeline.builder("panel-of-7")
        .input("draft", file=True)
        .panel(
            "panel",
            reviewers=[
                ("p1", PanelReviewerStep(...)), ("p2", PanelReviewerStep(...)),
                ("p3", PanelReviewerStep(...)), ("p4", PanelReviewerStep(...)),
                ("p5", PanelReviewerStep(...)), ("p6", PanelReviewerStep(...)),
                ("p7", PanelReviewerStep(...)),
            ],
            inputs=["draft"],
        )
        .agent("synth", prompt="prompts/synth.md", inputs=["panel.*"])
        .gate(
            "gate", step=GateStep(),
            on_proceed="halt", on_iterate="panel",
            on_tiebreaker="halt", on_escalate="halt",
        )
        .build()
)
```

### 2. Creative workshop

Two-agent alternating turns with an iteration cap.

```python
stages = alternating_turns(roles=(
    ("writer", AgentStep(name="writer", ...)),
    ("editor", AgentStep(name="editor", ...)),
))
stages["editor"] = iterate_until(
    stages["editor"], condition=lambda s: s["round"] < 3,
)
pipeline = Pipeline(stages=stages, entry="writer", overlays=())
```

### 3. Debate → judge

Two debaters take alternating turns, then a judge panel votes.

```python
debate = alternating_turns(roles=(
    ("pro", AgentStep(name="pro", ...)),
    ("con", AgentStep(name="con", ...)),
))
judges = ParallelStage(
    name="judges",
    steps=(JudgeStep(name="j1", ...), JudgeStep(name="j2", ...), JudgeStep(name="j3", ...)),
    join=majority_vote(),
    edges=(
        Edge(label="proceed",    target="halt",     kind="gate", recommendation="proceed"),
        Edge(label="iterate",    target="pro",      kind="gate", recommendation="iterate"),
        Edge(label="tiebreaker", target="halt",     kind="gate", recommendation="tiebreaker"),
        Edge(label="escalate",   target="halt",     kind="gate", recommendation="escalate"),
    ),
)
debate["con"] = Stage(
    name="con", step=debate["con"].step,
    edges=debate["con"].edges + (Edge(label="judges", target="judges"),),
)
pipeline = Pipeline(stages={**debate, "judges": judges}, entry="pro", overlays=())
```

### 4. Code review

A critique → gate → revise loop wrapped around an executor with an
escalation handler.

```python
loop = critique_revise_gate_loop(
    CritiqueStep(), GateStep(), ReviseStep(),
    on_proceed="execute", on_iterate="revise",
    on_tiebreaker="execute", on_escalate="escalate",
)
loop["execute"] = Stage(
    name="execute", step=ExecuteStep(),
    edges=(Edge(label="done", target="halt"),),
)
handler, _ = escalate_if(
    condition=lambda s: bool(s.get("blocked")),
    escalation_handler=EscalateStep(name="escalate"),
)
pipeline = Pipeline(
    stages={**loop, "execute": loop["execute"], handler.name: Stage(
        name=handler.name, step=handler, edges=(Edge("done", "halt"),),
    )},
    entry="critique",
    overlays=(),
)
```

### 5. Refinement + tiebreaker

A critique loop whose gate can dispatch to a tiebreaker subpipeline.

```python
loop = critique_revise_gate_loop(
    CritiqueStep(), GateStep(), ReviseStep(),
    on_proceed="finalize", on_iterate="revise",
    on_tiebreaker="tiebreaker", on_escalate="finalize",
)
tiebreaker_stage = Stage(
    name="tiebreaker",
    step=subpipeline_call(
        build_tiebreaker_pipeline(),
        promote=lambda s: "iterate" if s["current_state"] == "critiqued" else "proceed",
        artifact_subdir="tiebreaker",
    ),
    edges=(
        Edge(label="", target="critique", kind="gate", recommendation="iterate"),
        Edge(label="", target="finalize", kind="gate", recommendation="proceed"),
        Edge(label="", target="finalize", kind="gate", recommendation="escalate"),
    ),
)
finalize = Stage(name="finalize", step=FinalizeStep(), edges=(Edge("done", "halt"),))
pipeline = Pipeline(
    stages={**loop, "tiebreaker": tiebreaker_stage, "finalize": finalize},
    entry="critique",
    overlays=(),
)
```

(The planning pipeline is the production instance of this shape; see
`megaplan/_pipeline/planning.py`.)

### 6. Mode variants

A fixed topology whose prompts swap per `--mode` flag.

```python
pipeline = (
    Pipeline.builder("mode-variant", supported_modes=("polish","restructure","provoke"))
        .input("draft", file=True)
        .agent("revise", prompt="prompts/revise.md", inputs=["draft"])
        .mode({
            "polish":      {"revise": "revise_polish"},
            "restructure": {"revise": "revise_restructure"},
            "provoke":     {"revise": "revise_provoke"},
        })
        .build()
)
# At dispatch time the executor applies
# `mode_prompts(builder._modes_dict)(active_mode)` as an overlay.
```

## Where to look next

* `megaplan/_pipeline/patterns.py` — pattern source with module docstring
  describing the executor contracts the patterns rely on.
* `megaplan/_pipeline/builder.py` — chained-builder source with the
  auto-link rules.
* `megaplan/_pipeline/planning.py` — production use of every pattern
  except `alternating_turns`, `mode_prompts`, `iterate_until`, and
  `majority_vote`.
* `megaplan/pipelines/writing_panel_strict.py` — minimal end-to-end
  Python pipeline composed via the builder.
* `tests/_pipeline/test_patterns.py` and `tests/_pipeline/test_builder.py`
  — assert the produced Stage/Edge graphs and locked invariants
  (gate-kind edge ordering, panel reviewer-order plumbing, human-gate
  edge wiring).
