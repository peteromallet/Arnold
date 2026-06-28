# Python-Shaped Megaplan Planning Preview

Python-shaped authoring in Arnold means the product workflow is written as a constrained, statically parsed Python source file: imports name typed workflow components, assignments name step outputs, normal-looking calls name steps, and bounded `if`/`while` control flow describes route topology. The compiler does not execute the source to discover the graph; it parses the AST, resolves imported `StepComponent`/`PolicyComponent` metadata, lowers that source to the existing explicit-node `Pipeline`, and then emits the same normalized `WorkflowManifest` runtime already consumes.

## Imagined Authored Workflow

The current explicit DSL in `arnold_pipelines/megaplan/workflows/planning.py` builds a graph with stable nodes and explicit routes. Below is the intended Python-shaped version of the same topology, using the current component names from `arnold_pipelines.megaplan.workflows.components` plus policy exports M4 still needs to provide.

```python
"""Canonical Megaplan planning workflow source."""

from __future__ import annotations

from arnold.workflow.authoring import halt, loop, suspend, transition, workflow

from arnold_pipelines.megaplan.workflows.components import (
    CRITIQUE,
    EXECUTE,
    FINALIZE,
    GATE,
    HALT,
    OVERRIDE,
    PLAN,
    PREP,
    REVIEW,
    REVISE,
    TIEBREAKER_DECIDE,
    TIEBREAKER_RUN,
)
from arnold_pipelines.megaplan.workflows.policies import (
    common_timeout,
    gate_control,
    gate_human_suspend,
    review_control,
    review_human_suspend,
    revise_loop,
    tiebreaker_loop,
)


@workflow(id="megaplan", version="m4-phase3", policy=common_timeout)
def planning() -> None:
    prep_payload = PREP(id="prep")
    plan_payload = PLAN(id="plan", prep_payload=prep_payload)

    loop(policy=revise_loop, reentry_id="revise:loop")
    while True:
        critique_payload = CRITIQUE(id="critique", plan_payload=plan_payload)
        gate_payload, recommendation = GATE(
            id="gate",
            critique_payload=critique_payload,
            policies=[gate_control, gate_human_suspend],
        )

        if recommendation == "proceed":
            finalize_payload = FINALIZE(id="finalize", gate_payload=gate_payload)
        elif recommendation == "iterate":
            revise_payload = REVISE(id="revise", gate_payload=gate_payload)
            plan_payload = revise_payload
        elif recommendation == "tiebreaker":
            loop(policy=tiebreaker_loop, reentry_id="tiebreaker:loop")
            while True:
                tiebreaker_payload = TIEBREAKER_RUN(
                    id="tiebreaker_run",
                    gate_payload=gate_payload,
                )
                decision = TIEBREAKER_DECIDE(
                    id="tiebreaker_decide",
                    tiebreaker_payload=tiebreaker_payload,
                )
                if decision == "iterate":
                    critique_payload = CRITIQUE(id="critique", plan_payload=plan_payload)
                elif decision == "proceed":
                    finalize_payload = FINALIZE(id="finalize", gate_payload=gate_payload)
                elif decision == "escalate":
                    override_result = OVERRIDE(id="override", gate_payload=gate_payload)
                else:
                    suspend(route_id="tiebreaker:human", capability_id="human:gate")
        elif recommendation == "escalate":
            override_result = OVERRIDE(id="override", gate_payload=gate_payload)
        elif recommendation == "abort":
            status = HALT(id="halt")
            halt(id="gate:abort", target_ref="halt", trigger_ref="gate.recommendation")
        elif recommendation == "suspend":
            suspend(route_id="gate:human", capability_id="human:gate")
            status = HALT(id="halt")
        elif recommendation == "blocked_preflight":
            override_result = OVERRIDE(id="override", gate_payload=gate_payload)
        elif recommendation == "force_proceed":
            finalize_payload = FINALIZE(id="finalize", gate_payload=gate_payload)
        else:
            suspend(route_id="gate:human", capability_id="human:gate")

        if "override_result" in locals():
            if override_result == "abort":
                status = HALT(id="halt")
                halt(id="override:abort", target_ref="halt", trigger_ref="override.override_result")
            elif override_result == "force_proceed":
                finalize_payload = FINALIZE(id="finalize", gate_payload=gate_payload)
            elif override_result == "replan":
                revise_payload = REVISE(id="revise", gate_payload=gate_payload)
                plan_payload = revise_payload
            else:
                suspend(route_id="override:human", capability_id="human:gate")

        execute_payload = EXECUTE(id="execute", finalize_payload=finalize_payload)
        review_payload = REVIEW(
            id="review",
            execute_payload=execute_payload,
            policies=[review_control, review_human_suspend],
        )

        if review_payload == "pass":
            status = HALT(id="halt")
            halt(id="review:done", target_ref="halt", trigger_ref="review.verdict")
        elif review_payload == "rework":
            revise_payload = REVISE(id="revise", gate_payload=gate_payload)
            plan_payload = revise_payload
        else:
            suspend(route_id="review:human", capability_id="human:review")
```

## Construct Mapping

| Explicit-node DSL today | Python-shaped equivalent |
| --- | --- |
| `Step(id="plan", kind="megaplan:plan", inputs=..., outputs=...)` | `plan_payload = PLAN(id="plan", prep_payload=prep_payload)` |
| `Route(id="prep:plan", source="prep", target="plan", label="default")` | Adjacent statements: `prep_payload = PREP(...)` followed by `plan_payload = PLAN(...)` |
| Gate route tuple with `label`/`condition_ref` per branch | `if recommendation == "proceed": ... elif recommendation == "iterate": ...` |
| `WorkflowPolicy(control_transitions=(ControlTransitionSlot(...),))` | Imported policy components passed through `policy=`/`policies=` or reserved `transition(...)` intrinsics |
| `LoopPolicy(max_iterations=..., until_ref=...)` plus backedge route | `loop(policy=revise_loop, reentry_id="revise:loop")` immediately followed by `while True:` |

## Not Yet Compileable As Written

This is a visualization of the desired M4 authored file, not a source file that should replace `planning.py` today. The source compiler currently supports direct component calls, assignment outputs, literal equality branches, intrinsic `halt`/`suspend`/`transition`, and adjacent `loop(...)` plus `while True`, but the full Megaplan graph still needs M2/M3/M4 work before this exact shape can compile.

The missing pieces are graph joins and stable node identity across branches, because repeatedly calling `FINALIZE`, `REVISE`, `OVERRIDE`, or `HALT` in multiple arms would currently lower as duplicate step calls rather than routes into one canonical node. The compiler also needs first-class support for route labels and condition refs that preserve the existing manifest strings (`proceed`, `iterate`, `revise:loop`, `tiebreaker:loop`, `blocked`, `force_proceed`, and so on), richer step-level policy lowering for suspension/control slots, and component exports for all Megaplan policies, schemas, prompts, capabilities, iteration limits, and approval boundaries. Finally, runtime-looking checks such as `"override_result" in locals()` are only preview notation; a compileable authoring grammar needs a static merge/join form for optional branch outputs instead of Python runtime introspection.
