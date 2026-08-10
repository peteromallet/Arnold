# Megaplan As A Clean Arnold Plugin

## Intent

Arnold is the package and platform. Megaplan is Arnold's built-in robust planning and execution pipeline. The current `planning` pipeline should become the `megaplan` plugin, not a privileged special case in the platform runtime.

This cleanup is allowed to be breaking. Do not assume compatibility shims. Old names such as `planning` and the `megaplan` Python package are historical migration surfaces, not permanent contracts.

## Clean Target Shape

```text
arnold/
  pipeline/
    types.py
    registry.py
    executor.py
    prompts.py
    artifacts.py
    control.py
    patterns/
      fanout.py
      gate.py
      joins.py
      loop.py
      topology.py
    steps/
      agent.py
      artifact.py
      command.py
      human_gate.py
      panel.py
      reducer.py

  pipelines/
    megaplan/
      plugin.toml
      __init__.py
      pipeline.py
      state.py
      artifacts.py
      control.py
      stages/
        prep.py
        plan.py
        critique.py
        gate.py
        revise.py
        finalize.py
        execute.py
        review.py
      prompts/
        prep.md
        plan.md
        critique.md
        gate.md
        revise.md
        finalize.md
        execute.md
        review.md
      profiles/
      skills/
      tests/
```

Arnold owns generic mechanics:

- graph execution
- stage and step contracts
- plugin discovery
- prompt loading
- artifact storage interfaces
- agent dispatch
- fanout and joins
- gate routing
- loop control
- control binding protocols
- CLI module routing

Megaplan owns planning policy:

- the stage graph: `prep -> plan -> critique -> gate -> revise loop -> finalize -> execute -> review`
- prompt text
- output schemas
- critique lenses
- gate decisions and iteration policy
- robustness levels
- model profile defaults
- artifact names
- Megaplan-specific overrides and recovery actions

## What Megaplan Should Look Like

The plugin's `pipeline.py` should read like composition, not infrastructure:

```python
def build_pipeline() -> Pipeline:
    return Pipeline(
        name="megaplan",
        entry="prep",
        stages={
            "prep": PrepStage(),
            "plan": PlanStage(),
            "critique": CritiquePanel(),
            "gate": GateDecision(),
            "revise": RevisePlan(),
            "finalize": FinalizeExecutionPlan(),
            "execute": ExecuteBatches(),
            "review": ReviewPanel(),
        },
        edges=[
            edge("prep", "plan"),
            edge("plan", "critique"),
            edge("critique", "gate"),
            gate_edge("gate", "proceed", "finalize"),
            gate_edge("gate", "iterate", "revise"),
            gate_edge("gate", "escalate", "finalize"),
            edge("revise", "critique"),
            edge("finalize", "execute"),
            edge("execute", "review"),
            edge("review", "halt"),
        ],
    )
```

Each stage should be a thin use of Arnold primitives:

```python
PlanStage = AgentStep(
    name="plan",
    prompt="plan.md",
    output_schema=PlanOutput,
    writes=["plan.md", "plan.meta.json"],
)

CritiquePanel = PanelStep(
    name="critique",
    prompt="critique.md",
    reviewers=megaplan_critique_lenses(),
    output_schema=CritiqueFinding,
    writes=["critique.json"],
)

GateDecision = GateStep(
    name="gate",
    prompt="gate.md",
    decisions=["proceed", "iterate", "escalate", "abort"],
    input_artifacts=["plan.md", "critique.json"],
    writes=["gate.json"],
)
```

## Current Shape

The current branch is not plugin-clean. It is pipeline-shaped but not self-contained.

Visible plugin wrapper:

- `megaplan/pipelines/planning/__init__.py` composes a first-class discovered pipeline.
- `megaplan/pipelines/planning/steps.py` re-exports stage classes.
- `megaplan/pipelines/planning/SKILL.md` stores plugin-adjacent instructions.

Planning implementation outside the plugin:

- `megaplan/_pipeline/stages/prep.py`
- `megaplan/_pipeline/stages/plan.py`
- `megaplan/_pipeline/stages/critique.py`
- `megaplan/_pipeline/stages/gate.py`
- `megaplan/_pipeline/stages/revise.py`
- `megaplan/_pipeline/stages/finalize.py`
- `megaplan/_pipeline/stages/execute.py`
- `megaplan/_pipeline/stages/review.py`
- `megaplan/_pipeline/stages/tiebreaker.py`
- `megaplan/handlers/plan.py`
- `megaplan/handlers/critique.py`
- `megaplan/handlers/gate.py`
- `megaplan/handlers/finalize.py`
- `megaplan/handlers/execute.py`
- `megaplan/handlers/review.py`
- `megaplan/prompts/planning.py`
- `megaplan/prompts/critique.py`
- `megaplan/prompts/finalize.py`
- `megaplan/prompts/execute.py`
- `megaplan/prompts/review.py`
- `megaplan/planning/control_binding.py`
- `megaplan/_pipeline/planning.py`
- `megaplan/_pipeline/planning_bindings.py`

Platform code still knows planning by name:

- `megaplan/auto.py` calls `PipelineRegistry().get("planning")`.
- `megaplan/_core/workflow.py` defaults missing pipeline state to `"planning"`.
- `megaplan/cli/arnold.py` special-cases `planning` for `auto` and `override`.
- Tests and docs assert that `planning` is the built-in production pipeline.

## Distance From Plugin-Clean

The current state is best described as a strangler stage:

- Good: the graph is discoverable as a pipeline package.
- Good: generic-looking runtime primitives exist.
- Bad: the pipeline package is mostly an import hub.
- Bad: concrete stage behavior is still in platform-ish locations.
- Bad: prompt ownership is global, not plugin-local.
- Bad: control binding and override semantics are outside the plugin.
- Bad: generic runtime modules still contain planning literals and legacy compiler paths.
- Bad: public CLI and docs still treat `planning` as a privileged built-in.

The gap is not just a rename. The extraction requires moving policy into the plugin and making the platform runtime oblivious to Megaplan.

## Proposed Milestones

1. **Define Arnold package skeleton**
   - Introduce `arnold/` as the only package namespace.
   - Move generic runtime modules under `arnold/pipeline`, `arnold/runtime`, `arnold/store`, etc.
   - No `megaplan` import shims.

2. **Rename plugin identity**
   - Move `pipelines/planning` to `pipelines/megaplan`.
   - Rename metadata from `planning` to `megaplan`.
   - Update CLI and tests to expect `megaplan` as the built-in pipeline.

3. **Move planning-owned code into plugin**
   - Move planning stage classes from `_pipeline/stages/*` into `pipelines/megaplan/stages/`.
   - Move planning prompts into `pipelines/megaplan/prompts/`.
   - Move `megaplan/planning/control_binding.py` into `pipelines/megaplan/control.py`.
   - Move planning schemas/state constants into `pipelines/megaplan/state.py` or `schemas.py`.

4. **Extract reusable primitives**
   - Keep only generic `AgentStep`, `PanelStep`, `GateStep`, `Loop`, `Reducer`, `ArtifactStep`, and executor code in `arnold/pipeline`.
   - Remove planning literals such as `proceed/iterate/tiebreaker/escalate` from generic modules unless represented as plugin-provided decisions.

5. **Delete privileged planning paths**
   - Remove `_pipeline/planning.py`.
   - Remove `_pipeline/planning_bindings.py`.
   - Remove hardcoded `"planning"` defaults from auto, workflow resume, Arnold CLI, docs, and tests.

6. **Add boundary gates**
   - Static test: generic `arnold/pipeline/**` must not import `arnold.pipelines.megaplan`.
   - Static test: generic pipeline runtime must not contain the string `"planning"` except in historical docs.
   - Registry test: `arnold pipelines list` discovers `megaplan`.
   - Execution test: `arnold run megaplan --describe` works.
   - Composition test: another toy plugin uses the same primitives without importing Megaplan.

## Open Questions For Review

- Which current `orchestration/*` modules are generic enough for `arnold/pipeline` and which are Megaplan policy?
- Should profiles be platform-level model-routing presets, plugin-level stage maps, or both?
- Should `execute` be a generic batch primitive or Megaplan-specific execution policy?
- Which CLI should own direct pipeline execution: `arnold run megaplan ...`, `megaplan ...`, or both?
- Can the embedded agent runtime under `megaplan/agent` become an integration dependency rather than package-local source?
