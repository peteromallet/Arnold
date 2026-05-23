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
  topologies — critique loops, panels, subpipeline calls, prompt variants —
  so individual pipelines stay short.
* **Overlay** — a `Pipeline → Pipeline` transform stashed on
  `Pipeline.overlays`. This remains an optional low-level primitive for
  local graph transforms. The built-in `planning`, `doc`, and `creative`
  pipelines are first-class registered graphs, not rewrites of one shared
  planning topology.

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

## Built-in first-class pipelines

The in-tree pipelines are selected by name from the registry:

* `planning` is compiled by
  `megaplan._pipeline.planning.compile_planning_pipeline()`.
* `doc` lives under `megaplan/pipelines/doc/` and owns its document
  topology and prompt registrations.
* `creative` lives under `megaplan/pipelines/creative/` and owns its
  form-aware topology and prompt registrations.

Registry builders remain nullary. CLI-only inputs such as creative
`--form` and `--primary-criterion` are handled at the command boundary
and passed into the creative steps; they do not change the public
registry builder contract.

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

## Dynamic primitives (0.23+)

The 0.23 release adds five primitives whose width or topology is decided
at **run time** rather than at compile time. They live in
`megaplan._pipeline.patterns` alongside the existing nine. All five are
composed from existing primitives (`Step`, `Stage`, `ParallelStage`,
`SubloopStep`, `Edge`, `Overlay`, `JoinFn`) — `_pipeline/types.py` is
untouched.

The committed `SubloopStep` shape is load-bearing for the two
fan-out-shaped primitives: `ParallelStage.steps` is materialised at
compile time (see `executor.py:171/179/295/298`), so dynamism must be
encapsulated inside a `SubloopStep` whose `run()` performs the per-spec
dispatch when the pipeline actually executes — not by mutating a
`ParallelStage` at run time.

### `panel_from_artifact(artifact_ref, base_template, join, *, name) -> SubloopStep`

Reads a JSON list of reviewer specs from an upstream artifact at
`artifact_ref`, specialises `base_template` per spec (via
`dataclasses.replace` over the intersection of spec keys and template
fields), runs each specialised step, and folds the results through
`join`.

### `dynamic_fanout(generator, base_prompt, join, *, name) -> SubloopStep`

Runs `generator` once, harvests the specs it emits (either
`result.state_patch['specs']` in-memory, or a path on
`result.outputs['specs']`), fans `base_prompt` per spec, then folds via
`join`. This is the primitive the new `doc` pipeline's `section_drafts`
stage uses to turn a runtime-decided list of sections into a per-section
draft step (see `megaplan/pipelines/doc/__init__.py`).

### `weighted_vote(weights) -> JoinFn`

Variant of `majority_vote` that weighs each panellist's verdict by the
caller-supplied `weights[reviewer_id]`. Missing reviewer ids contribute
zero. Ties and empty panels resolve to `"tiebreaker"`, matching
`majority_vote`'s shape so the two are drop-in interchangeable as a
`ParallelStage` `join`.

### `iterate_until_consensus(panel, min_agreement=0.8, max_iters=3, *, name) -> SubloopStep`

Wraps a panel `Step` or `Stage` in a self-loop that exits as soon as the
per-reviewer recommendation agreement ratio crosses `min_agreement`, or
after `max_iters` passes — whichever happens first. Agreement is read
off the panel's emitted `verdict.payload["per_reviewer_recommendations"]`.
Emits `consensus:<name>:agreement` and `consensus:<name>:iterations`
state-patch keys.

### `paired_round(advocates, *, sees_other=True, name) -> Stage`

Extends `alternating_turns` so that, with `sees_other=True`, each role's
`StepContext.inputs` is augmented with `prior.<label>` keys carrying the
previous turn's outputs from the other advocate. With `sees_other=False`
the chaining devolves to topology-only semantics, matching
`alternating_turns`.

### Worked example: dynamic-prompt-generation panel

The user's scenario: one stage designs five critique personas at run
time, a second stage runs those five reviewers as a specialised
critique panel, a third stage synthesises via `weighted_vote`. About
30 LOC of Python composed entirely from the new and existing
primitives:

```python
from dataclasses import dataclass
from megaplan._pipeline.patterns import (
    panel_from_artifact, weighted_vote,
)
from megaplan._pipeline.types import Edge, Pipeline, Stage
from megaplan._pipeline.steps.agent import AgentStep


@dataclass(frozen=True)
class _PersonaCritique(AgentStep):
    persona_id: str = ""
    persona_brief: str = ""


design_personas = AgentStep(
    name="design_personas",
    prompt_key="design_personas",  # emits personas.json: [{persona_id, persona_brief, weight}, …]
)

critique_panel = panel_from_artifact(
    artifact_ref="personas.json",
    base_template=_PersonaCritique(name="critique", prompt_key="critique_with_persona"),
    join=weighted_vote(weights={"p1": 1.0, "p2": 1.0, "p3": 1.5, "p4": 1.0, "p5": 1.0}),
    name="critique",
)

pipeline = Pipeline(
    stages={
        "design_personas": Stage(name="design_personas", step=design_personas,
                                 edges=(Edge("done", "critique"),)),
        "critique":        Stage(name="critique", step=critique_panel,
                                 edges=(Edge("proceed",    "halt", kind="gate", recommendation="proceed"),
                                        Edge("iterate",    "design_personas", kind="gate", recommendation="iterate"),
                                        Edge("tiebreaker", "halt", kind="gate", recommendation="tiebreaker"))),
    },
    entry="design_personas",
    overlays=(),
)
```

`panel_from_artifact` reads the five persona specs from
`personas.json`, builds five `_PersonaCritique` clones (one per
persona, via `dataclasses.replace`), runs them, and folds the per-
reviewer verdicts through `weighted_vote` so the third persona's
opinion counts 1.5× the others. The outgoing gate edges then dispatch
on the synthetic `Verdict.recommendation`.

## The `doc` pipeline

`megaplan run doc <brief>` runs a five-stage linear pipeline:

```
outline → section_drafts → critique → revise → assembly
```

There is no gate stage — the topology is a single forward pass.
`section_drafts` is the real in-tree consumer of `dynamic_fanout`:
`outline` emits a sections JSON artifact, then `section_drafts` fans a
per-section draft step out across however many sections `outline`
produced, joining the results into a single artifact for `critique` to
read. `critique` and `revise` are plain `Step`s — there is **no**
`critique_revise_gate_loop` and **no** `tiebreaker` subpipeline.
`assembly` returns `next='halt'` directly (per `executor.py:218-220` a
halt-labelled edge would be unreachable).

Prompts live alongside the pipeline under
`megaplan/pipelines/doc/prompts/` and register with the pipeline-scoped
`PromptRegistry` slot `doc/<key>` for each of the five stages
(`outline_doc`, `execute_doc`, `critique_doc`, `revise_doc`,
`assemble_doc`). The old `megaplan/prompts/{prep_doc, review_doc}.py`
modules are **not** consumed by the first-class `doc` pipeline.

**Iteration semantics differ from planning.** The first-class
`megaplan run doc` topology is a **single linear pass**: no gate, no
loop, no tiebreaker. If you need another pass, re-run the doc pipeline
with the previous output as input.

## The `creative` pipeline

`megaplan run creative <brief> --form <id>` runs a five-stage linear
pipeline with form-specialised prompts:

```
prep → execute_creative → critique_creative → revise_creative → finalize
```

`--form` is a **first-class input**, not a mode. The form is validated
against `megaplan.forms.available_form_ids()` — the same canonical
registry the init handler consults at `megaplan/handlers/init.py:62-64`
— and an unknown form raises `CliError('invalid_args')`. Each stage's
`prompt_key` is form-specialised as `<base_key>:<form>` (e.g.
`execute_creative:joke`, `revise_creative:poem`); both the generic
`creative/<key>` slot and the `creative/<key>:<form>` slot are
registered so the `PromptRegistry` resolves the form-aware variant
when one is registered and falls back to the generic creative renderer
otherwise.

The provocations registry, stance contract, and director's-notes sidecar
are shared with the rest of the application. `megaplan/forms/` was
**not** relocated (it's consumed by 25+ non-creative modules) and the
creative pipeline imports from it like any other consumer.

`--primary-criterion <text>` is a first-class creative-pipeline input
and threads through to every stage's Step via the `primary_criterion`
dataclass field on `_CreativeStep`.

## How modes work in the new system

There is no single `--mode` axis that rewrites the planning pipeline
with in-tree prompt sets. The architecture splits the responsibility:

- **`planning` has no modes.** The `code` mode is the only effective
  mode and it is the default; the pipeline is built from a single
  prompt set.
- **`doc` and `creative` are first-class atomic pipelines**, reached
  via `megaplan run doc` and `megaplan run creative`. Each is a
  distinct module under `megaplan/pipelines/` with its own topology
  and pipeline-scoped prompt registry.
- **`--form` (creative only)** is a first-class input on the
  `creative` pipeline, validated against the canonical
  `megaplan.forms.available_form_ids()` registry.
- **The `Pipeline.builder(...).mode({...})` / `mode_prompts(...)`
  pattern is retained** for future custom pipelines where the topology
  is shared across variants but the prompts swap (worked example 6
  above).
  Use it inline inside the pipeline module that owns those variants;
  there is no separate registry.

## `--mode` deprecation migration table (0.22 → 0.23)

`megaplan init --mode <X>` is a deprecated state-initialization path.
**There is no `--mode` flag on
`megaplan plan|execute|review`** — those subparsers never accepted it,
so any documentation referring to `megaplan plan --mode <X>` is wrong.
Use `megaplan run <pipeline>` for first-class pipeline execution.

| Old (0.22)                                                  | New (0.23+)                                                  | 0.23 limitation                                                                                                                                                                          |
| ----------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `megaplan init --mode doc <brief>`                          | `megaplan run doc <brief>`                                   | `init --mode doc` is deprecated; use the first-class `doc` pipeline for document generation.                                                                                             |
| `megaplan init --mode creative --form <id> <brief>`         | `megaplan run creative <brief> --form <id>`                  | `init --mode creative` is deprecated; use the first-class `creative` pipeline for creative generation.                                                                                    |
| `megaplan init --mode metaplan <brief>`                     | `megaplan run doc <brief>`                                   | `metaplan` was always an alias for `doc`; use the first-class `doc` pipeline.                                                                                                             |
| `megaplan init --mode joke <brief>`                         | `megaplan run creative <brief> --form joke`                  | `init --mode joke` still works in 0.23 with a deprecation warning; state config keeps `mode='joke'` (not rewritten) to preserve legacy `is_prose_mode`/`creative_form_id` semantics for `--auto-start`. |
| `megaplan bakeoff run --mode metaplan …`                    | `megaplan bakeoff run --mode doc …`                          | The bake-off `metaplan` alias is **removed** in 0.23. `--mode metaplan` and `--mode joke` are rejected at the bake-off argparse layer.                                                    |

The deprecation warning printed to stderr on each deprecated
`init --mode` invocation is:

```
[deprecation] megaplan init --mode <X> is deprecated; use
"megaplan run <pipeline> [--form …]" instead. NOTE: in 0.23,
first-class pipeline execution is reached via "megaplan run <pipeline>".
```

`--mode code` is unchanged: no warning, `state.config.mode='code'`,
and `state.config.pipeline` / `state.config.form` left unset.

**Hard `--form` contract on init.** Passing `--form` on `--mode
doc|metaplan` raises `CliError('invalid_args')`. Omitting `--form` on
`--mode creative` raises `CliError('invalid_args')`. `--mode joke`
implicitly sets `form='joke'` and the existing reject-on-explicit-
`--form-joke` behaviour at `init.py:60` is preserved.

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
# The builder records the prompt-variant map on the pipeline that owns it.
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
