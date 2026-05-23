# Pipeline architecture — the elegance writeup

Post-Sprint-4. The `megaplan/_pipeline/` package is the orchestration
layer. This document maps the surface, the extension axes, the runtime,
and how the first-class built-in pipelines fit in.

## Primitive surface

Eight frozen dataclasses + one Protocol. ~190 LOC in
`megaplan/_pipeline/types.py`.

```
Edge          (label, target, kind, recommendation)
Verdict       (score, flags, notes, payload, recommendation, override)
StepContext   (plan_dir, state, profile, mode, inputs, budget)
StepResult    (outputs, verdict, next, state_patch)
Step          (Protocol: name, kind, prompt_key, slot, run)
Stage         (name, step, edges)
ParallelStage (name, steps, join, edges, max_workers)
Pipeline      (stages, entry, overlays)
Overlay       (name, apply)
```

**Step.kind** is a Literal of five values:

- `produce`: writes an artifact (prep, plan, revise, finalize, execute).
- `judge`: emits a Verdict (critique, review).
- `decide`: maps verdicts to a typed recommendation (gate).
- `subloop`: carries a nested Pipeline; its child runs as a sub-program.
- `override`: reserved for escape-edge dispatch.

**Edge.kind** is a Literal of three values:

- `normal`: matches when `Edge.label == StepResult.next`.
- `gate`: matches when `Edge.recommendation == StepResult.verdict.recommendation`.
- `override`: matches when `StepResult.verdict.override` is set to a
  matching `OverrideAction`.

Override dispatch takes precedence over gate dispatch, which takes
precedence over normal label dispatch. This means an emergency
escape (`override force_proceed`) always fires even if a gate verdict
is also present.

## Three orthogonal extension axes

The primitive surface stays tiny because three axes carry the
variability:

1. **Prompt variant** (`ctx.mode`) → resolves a prompt via
   `megaplan/_pipeline/prompts.py::PromptRegistry`. Keys are
   `"<step_name>"` or `"<step_name>:<variant>"`. A custom pipeline can
   register `"critique:scientific-paper"` and the existing `CritiqueStep`
   picks it up — no subclass.
2. **Slot** (`step.slot`) → resolves a model spec via
   `megaplan/_pipeline/profile.py::Profile.model_for(slot)`. Each
   profile TOML's slot keys (`plan`, `critique`, …) are unchanged.
   Profile.with_slot/with_overrides returns an immutable copy for
   on-the-fly swaps.
3. **Pipeline identity** → selects a registered graph. The built-ins are
   first-class pipelines: `planning` is compiled by
   `compile_planning_pipeline()`, while `doc` and `creative` live under
   `megaplan/pipelines/`. `Pipeline.overlays` remains an optional
   low-level primitive for local graph transforms, but the in-tree
   built-ins are not assembled through compatibility graph rewrites.

These axes don't tangle. A new workflow type changes one — say
prompt resolution — without touching the others.

## Runtime layering

`megaplan/_pipeline/executor.py` exposes two entry points:

- `run_pipeline(pipeline, ctx, *, artifact_root)` — bare executor.
  Hermetic, no external imports beyond stdlib + the pipeline
  package. Demos use this.
- `run_pipeline_with_policy(pipeline, ctx, *, artifact_root, policy)`
  — wraps the bare executor with stall detection, cost capping,
  escalate-policy resolution. The policy lives in
  `megaplan/_pipeline/runtime.py::RuntimePolicy` and bundles five
  composable modules: `StallDetector`, `CostTracker`,
  `EscalatePolicy`, `ContextRetry`, `BlockedRetry`.

The `MEGAPLAN_PIPELINE_AUTO=1` env var (see
`runtime.py::pipeline_runtime_enabled()`) gates experiments that route
through `run_pipeline_with_policy`. The built-in pipeline definitions
are always importable as Python values, regardless of that runtime flag.

## Subloop + Override edges

A `SubloopStep` carries a `child_pipeline`. At dispatch time the
executor runs the child via `run_pipeline` (or `_with_policy`) under
a subdir of `ctx.plan_dir`, then promotes the child's final state
into a Verdict on the parent via a configurable `promote` callable.
This is the elegance fix for tiebreaker: two state-machine states
collapse into one Step.

Override edges (`Edge(kind="override", ...)`) move the legacy CLI
escape hatches (`override force-proceed` / `abort` / `replan` /
`add-note`) into the typed edge model. A Step returning a
Verdict with `override="force_proceed"` causes the executor to find
and follow the matching `kind="override"` edge.

## How a prompt variant is added (in <20 lines)

```python
from megaplan._pipeline.prompts import register_prompt

# 1. Register the variant-specific prompt(s).
register_prompt(
    "critique:scientific-paper",
    lambda ctx, params: "You are a peer reviewer. Be technical.",
)
register_prompt(
    "revise:scientific-paper",
    lambda ctx, params: "Apply the reviewer's flags.",
)

# 2. (Optional) Override one slot for this variant.
from megaplan._pipeline.profile import Profile, load_profile
profile = load_profile("all-claude").with_slot("critique", "hermes:openai/gpt-5")

# 3. Run a pipeline with mode="scientific-paper" in its StepContext.
from megaplan._pipeline.demos.doc_critique import run_demo
run_demo(fixture_path, artifact_root, mode="scientific-paper")
```

That's it. No Step subclass, no Edge surgery, no Pipeline rewrite.

## Built-in pipelines

`megaplan/_pipeline/planning.py::compile_planning_pipeline()` is the
canonical compiler for the core planning graph. It returns the phase
graph directly: prep, plan, critique, gate, revise, finalize, execute,
review, and tiebreaker. The pipeline registry exposes that graph under
the `planning` name.

`doc` and `creative` are separate first-class pipelines under
`megaplan/pipelines/`. They have their own topologies, prompt
registrations, and CLI entry points; they are not derived by rewriting
the planning graph.

## Worked example — a 3× critique → revise loop from scratch

```python
from megaplan._pipeline import Edge, Pipeline, Stage, StepContext, StepResult, Verdict
from megaplan._pipeline.executor import run_pipeline

class Critic:
    name = "critique"; kind = "judge"; prompt_key = "critique"; slot = "critique"
    def run(self, ctx):
        n = int(ctx.state.get("iter", 0)) + 1
        return StepResult(
            verdict=Verdict(score=0.5, recommendation="iterate" if n < 3 else "proceed"),
            next="iterate",
            state_patch={"iter": n},
        )

class Reviser:
    name = "revise"; kind = "produce"; prompt_key = "revise"; slot = "revise"
    def run(self, ctx):
        return StepResult(next="to_critique")

pipeline = Pipeline(
    stages={
        "critique": Stage(
            name="critique", step=Critic(),
            edges=(
                Edge(label="iterate", target="revise", kind="gate", recommendation="iterate"),
                Edge(label="proceed", target="halt", kind="gate", recommendation="proceed"),
            ),
        ),
        "revise": Stage(
            name="revise", step=Reviser(),
            edges=(Edge(label="to_critique", target="critique"),),
        ),
    },
    entry="critique",
)

result = run_pipeline(pipeline, ctx, artifact_root=tmp)
assert result["state"]["iter"] == 3
```

That's the entire pipeline. The loop falls out of the
`critique → revise → critique` backwards edge; termination is a
typed `recommendation="proceed"` from the critic on iter 3.

## File map

```
megaplan/_pipeline/
├── __init__.py                # public exports
├── types.py                   # 8 frozen dataclasses + Step protocol
├── executor.py                # run_pipeline + run_pipeline_with_policy
├── runtime.py                 # RuntimePolicy + 5 policy classes
├── profile.py                 # Profile + load_profile + slot binding
├── prompts.py                 # PromptRegistry + per-mode lookup
├── planning.py                # compile_planning_pipeline()
├── subloop.py                 # SubloopStep + child Pipeline dispatch
├── override.py                # override_edge helper + lookup
├── demo_judges.py             # fan-out judges demo
├── demos/
│   └── doc_critique.py        # 3× critique→revise loop
└── stages/
    ├── handler_step.py        # subprocess-shim HandlerStep
    ├── inprocess_step.py      # in-process generic Step
    ├── prep.py                # PrepStep
    ├── plan.py                # PlanStep
    ├── critique.py            # CritiqueStep
    ├── gate.py                # GateStep (decide kind)
    ├── revise.py              # ReviseStep
    ├── finalize.py            # FinalizeStep
    ├── execute.py             # ExecuteStep
    └── review.py              # ReviewStep
```
