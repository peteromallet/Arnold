# Megaplan After The Python-Shaped Epic

After M1-M8 of `python-shaped-workflow-authoring`, Megaplan's canonical planning workflow can move from a hand-authored explicit-node `Pipeline` into restricted Python-shaped source that compiles to the same DSL and `WorkflowManifest` runtime shape. This document shows the workflow as it should be authored immediately after that epic: component imports are the source of truth, linear phase calls become steps, decision branches become manifest routes, bounded `while True` regions become loop backedges, and the remaining dynamic orchestration stays inside typed components or subworkflow handlers.

## Supported Construct Checklist

- You can import typed workflow components: steps, prompts, policies, schemas, and subflows.
- You can write one `@workflow(...)` function with ordered positional parameters only.
- You can write a linear sequence of component calls with assignment or tuple assignment outputs.
- You can pass previous outputs to later components by local variable name.
- You can write `if` / `elif` / `else` branches over declared decision outputs compared to literal strings.
- You can write `loop(policy=..., reentry_id=...)` immediately followed by `while True:`.
- You can use imported subworkflow references as typed components when they lower to manifest subpipeline refs.
- You can use `halt(...)` and `suspend(...)` compiler intrinsics where they lower to existing policy slots.
- You cannot write `for` loops, runtime-list iteration, dynamic `parallel_map`, or `foreach`.
- You cannot write `while <condition>`, `break`, `continue`, arbitrary Python calls, lambdas, decorators beyond `workflow`, runtime introspection, or call-site `retry(...)`, `timeout=...`, or `model=...` policy syntax.

## The Authored Megaplan Pipeline

```python
from __future__ import annotations

from arnold.workflow.authoring import halt, loop, suspend, workflow
from arnold_pipelines.megaplan.workflows.components import (
    CRITIQUE,
    EXECUTE,
    FINALIZE,
    GATE,
    OVERRIDE,
    PLAN,
    PREP,
    REVIEW,
    REVISE,
)
from arnold_pipelines.megaplan.workflows.policies import (
    CRITIQUE_REVISE_LOOP,
    MEGAPLAN_CONTROL_POLICY,
    REVIEW_REWORK_LOOP,
)
from arnold_pipelines.megaplan.workflows.subflows import TIEBREAKER


@workflow(
    id="megaplan",
    version="m4-phase3",
    policies=[MEGAPLAN_CONTROL_POLICY],
)
def planning():
    prep_payload, prep_decision = PREP(id="prep")

    if prep_decision == "ready":
        plan_payload = PLAN(id="plan", prep_payload=prep_payload)
    elif prep_decision == "needs_human":
        suspend(
            route_id="prep:human",
            capability_id="human:prep",
            reentry_id="prep:clarified",
        )
        plan_payload = PLAN(id="plan_after_clarification", prep_payload=prep_payload)
    else:
        override_result, override_action = OVERRIDE(
            id="prep_override",
            prep_payload=prep_payload,
        )
        if override_action == "force_proceed":
            plan_payload = PLAN(id="plan_after_prep_override", prep_payload=prep_payload)
        elif override_action == "abort":
            halt(id="prep_abort", trigger_ref="prep_override.override_action")
        else:
            halt(id="prep_blocked", trigger_ref="prep_override.override_action")

    loop(policy=CRITIQUE_REVISE_LOOP, reentry_id="critique_revise")
    while True:
        critique_payload = CRITIQUE(id="critique", plan_payload=plan_payload)
        gate_payload, recommendation = GATE(
            id="gate",
            critique_payload=critique_payload,
        )

        if recommendation == "iterate":
            plan_payload = REVISE(id="revise", gate_payload=gate_payload)
        elif recommendation == "tiebreaker":
            tiebreaker_payload, tiebreaker_decision = TIEBREAKER(
                id="tiebreaker",
                gate_payload=gate_payload,
            )
            if tiebreaker_decision == "iterate":
                plan_payload = REVISE(
                    id="tiebreaker_revise",
                    gate_payload=gate_payload,
                    tiebreaker_payload=tiebreaker_payload,
                )
            elif tiebreaker_decision == "proceed":
                finalize_payload = FINALIZE(id="tiebreaker_finalize", gate_payload=gate_payload)
                execute_payload = EXECUTE(id="tiebreaker_execute", finalize_payload=finalize_payload)
                review_payload, review_verdict = REVIEW(id="tiebreaker_review", execute_payload=execute_payload)
                if review_verdict == "pass":
                    halt(id="tiebreaker_done", trigger_ref="tiebreaker_review.review_verdict")
                elif review_verdict == "rework":
                    plan_payload = REVISE(
                        id="tiebreaker_review_revise",
                        gate_payload=gate_payload,
                        review_payload=review_payload,
                    )
                else:
                    halt(id="tiebreaker_review_blocked", trigger_ref="tiebreaker_review.review_verdict")
            else:
                override_result, override_action = OVERRIDE(
                    id="tiebreaker_override",
                    gate_payload=gate_payload,
                    tiebreaker_payload=tiebreaker_payload,
                )
                if override_action == "force_proceed":
                    finalize_payload = FINALIZE(id="override_finalize", gate_payload=gate_payload)
                elif override_action == "replan":
                    plan_payload = REVISE(id="override_replan", gate_payload=gate_payload)
                else:
                    halt(id="override_abort", trigger_ref="tiebreaker_override.override_action")
        elif recommendation == "proceed":
            finalize_payload = FINALIZE(id="finalize", gate_payload=gate_payload)
            execute_payload = EXECUTE(id="execute", finalize_payload=finalize_payload)

            loop(policy=REVIEW_REWORK_LOOP, reentry_id="review_rework")
            while True:
                review_payload, review_verdict = REVIEW(id="review", execute_payload=execute_payload)
                if review_verdict == "pass":
                    halt(id="done", trigger_ref="review.review_verdict")
                elif review_verdict == "rework":
                    plan_payload = REVISE(
                        id="review_revise",
                        gate_payload=gate_payload,
                        review_payload=review_payload,
                    )
                    finalize_payload = FINALIZE(id="review_refinalize", gate_payload=gate_payload)
                    execute_payload = EXECUTE(id="review_reexecute", finalize_payload=finalize_payload)
                elif review_verdict == "needs_human":
                    suspend(
                        route_id="review:human",
                        capability_id="human:review",
                        reentry_id="review:verified",
                    )
                    halt(id="awaiting_human_review", trigger_ref="review.review_verdict")
                else:
                    override_result, override_action = OVERRIDE(
                        id="review_override",
                        review_payload=review_payload,
                    )
                    if override_action == "force_proceed":
                        halt(id="review_force_proceed", trigger_ref="review_override.override_action")
                    elif override_action == "replan":
                        plan_payload = REVISE(
                            id="review_override_replan",
                            gate_payload=gate_payload,
                            review_payload=review_payload,
                        )
                    else:
                        halt(id="review_blocked", trigger_ref="review_override.override_action")
        elif recommendation == "force_proceed":
            finalize_payload = FINALIZE(id="force_finalize", gate_payload=gate_payload)
            execute_payload = EXECUTE(id="force_execute", finalize_payload=finalize_payload)
            review_payload, review_verdict = REVIEW(id="force_review", execute_payload=execute_payload)
            if review_verdict == "pass":
                halt(id="force_done", trigger_ref="force_review.review_verdict")
            elif review_verdict == "rework":
                plan_payload = REVISE(
                    id="force_review_revise",
                    gate_payload=gate_payload,
                    review_payload=review_payload,
                )
            else:
                halt(id="force_review_blocked", trigger_ref="force_review.review_verdict")
        elif recommendation == "suspend":
            suspend(
                route_id="gate:human",
                capability_id="human:gate",
                reentry_id="gate:resolved",
            )
            override_result, override_action = OVERRIDE(id="gate_human_override", gate_payload=gate_payload)
            if override_action == "force_proceed":
                finalize_payload = FINALIZE(id="human_finalize", gate_payload=gate_payload)
                execute_payload = EXECUTE(id="human_execute", finalize_payload=finalize_payload)
            elif override_action == "replan":
                plan_payload = REVISE(id="human_replan", gate_payload=gate_payload)
            else:
                halt(id="human_gate_abort", trigger_ref="gate_human_override.override_action")
        else:
            override_result, override_action = OVERRIDE(id="gate_override", gate_payload=gate_payload)
            if override_action == "force_proceed":
                finalize_payload = FINALIZE(id="gate_override_finalize", gate_payload=gate_payload)
                execute_payload = EXECUTE(id="gate_override_execute", finalize_payload=finalize_payload)
            elif override_action == "replan":
                plan_payload = REVISE(id="gate_override_replan", gate_payload=gate_payload)
            else:
                halt(id="gate_abort", trigger_ref="gate_override.override_action")
```

## What Still Looks Awkward Or Remains In Handlers

This is more readable than the explicit route table, but it is not the aspirational native workflow. Dynamic critique lens fanout remains inside `CRITIQUE`, because M1-M8 do not support `parallel_map` over a runtime-selected list. Execute task batching remains inside `EXECUTE`, because there is no `foreach`, DAG batch loop, or runtime-list iteration syntax. Review's internal parallel checks, retry/repair behavior, and rework classification remain in `REVIEW` for the same reason. The loop exits also look awkward: M1-M8 gives bounded `while True` backedges with policy, not source-level `break`, `continue`, typed loop outcomes, or `while recommendation != "proceed"` conditions.

## Side-By-Side With The Aspirational Native Report

| Construct | M1-M8 Python-shaped authoring | Full native vision |
| --- | --- | --- |
| Component dependencies | Explicit typed imports from component modules | Ordinary-looking durable phase/subworkflow definitions plus imports |
| Branching | `if` / `elif` / `else` over declared output names and literal strings | Rich typed decisions and predicates over structured values |
| Loops | `loop(policy=..., reentry_id=...)` followed by bounded `while True` | `while <condition>`, `break`, `continue`, typed loop results, and clearer exits |
| Critique and review fanout | Hidden inside `CRITIQUE` and `REVIEW` components | Source-level `parallel_map` with reducers and fallback policy |
| Execute task batches | Hidden inside the `EXECUTE` component | Source-level dependency-aware `foreach` / DAG batch iteration |
| Runtime policy | Imported workflow and loop policy components | Source-level retry, timeout, model routing, effects, and escalation syntax |
| Human intervention | `suspend(...)` intrinsic plus override branches | First-class human gates with typed resume payloads and local continuation values |
