"""Megaplan's canonical authored workflow source."""

from __future__ import annotations

from arnold.pipeline import parallel_map
from arnold.workflow.authoring import loop, workflow
from arnold_pipelines.megaplan.workflows.components import (
    DEFAULT_POLICY,
    REVISE_LOOP_POLICY,
    SOURCE_CRITIQUE,
    SOURCE_CRITIQUE_PANEL_WORKFLOW,
    SOURCE_EXECUTE,
    SOURCE_EXECUTE_BATCH_WORKFLOW,
    SOURCE_FINALIZE,
    SOURCE_GATE,
    SOURCE_HALT,
    SOURCE_OVERRIDE,
    SOURCE_PLAN,
    SOURCE_PREP,
    SOURCE_REVIEW,
    SOURCE_REVIEW_PANEL_WORKFLOW,
    SOURCE_REVISE,
    SOURCE_TIEBREAKER_WORKFLOW,
)


@workflow(id="megaplan", version="m4-phase3", policy=DEFAULT_POLICY)
def planning_workflow(brief: str) -> None:
    # The V1 source compiler lowers only the decorated workflow body, so this
    # route-compatible spine remains the compiled public-stage authority until
    # neutral subworkflow calls can be inlined without stage-name suffixing.
    prep_signal = SOURCE_PREP(id="prep", brief=brief)
    plan_payload = SOURCE_PLAN(id="plan", prep_payload=prep_signal)

    loop(policy=REVISE_LOOP_POLICY, reentry_id="critique")
    while True:
        critique_payload = parallel_map(
            id="critique-fanout",
            items="megaplan.policy.critique_lenses",
            step=SOURCE_CRITIQUE_PANEL_WORKFLOW,
            reducer=SOURCE_CRITIQUE,
            path_template="critique/{item_id}",
        )
        gate_route_signal = SOURCE_GATE(
            id="gate",
            critique_payload=critique_payload,
        )

        if gate_route_signal == "proceed":
            finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=gate_route_signal)
            execute_payload = parallel_map(
                id="execute-batches",
                items="megaplan.execute.batches",
                step=SOURCE_EXECUTE_BATCH_WORKFLOW,
                reducer=SOURCE_EXECUTE,
                path_template="execute/{index}",
            )
            review_route_signal = parallel_map(
                id="review-fan-in",
                items=execute_payload,
                step=SOURCE_REVIEW_PANEL_WORKFLOW,
                reducer=SOURCE_REVIEW,
                path_template="review/{item_id}",
            )
            if review_route_signal == "pass":
                SOURCE_HALT(id="halt", review_payload=review_route_signal)
                return None
            elif review_route_signal == "rework":
                SOURCE_REVISE(id="review_revise", gate_payload=review_route_signal)
                return None
            else:
                SOURCE_HALT(id="review_halt", review_payload=review_route_signal)
                return None
        elif gate_route_signal == "iterate":
            SOURCE_REVISE(id="revise", gate_payload=gate_route_signal)
        elif gate_route_signal == "tiebreaker":
            # Internal pick/replan/escalate semantics stay on the declared child
            # workflow contract so topology can prove them from the authored call site.
            decision = SOURCE_TIEBREAKER_WORKFLOW(id="tiebreaker", gate_payload=gate_route_signal)
            if decision == "proceed":
                finalize_payload = SOURCE_FINALIZE(id="tiebreaker_finalize", gate_payload=decision)
                parallel_map(
                    id="tiebreaker-execute-batches",
                    items="megaplan.execute.batches",
                    step=SOURCE_EXECUTE_BATCH_WORKFLOW,
                    reducer=SOURCE_EXECUTE,
                    path_template="execute/{index}",
                )
                return None
            elif decision == "escalate":
                SOURCE_OVERRIDE(id="tiebreaker_override", gate_payload=decision)
                return None
        elif gate_route_signal == "escalate":
            override_result = SOURCE_OVERRIDE(id="override", gate_payload=gate_route_signal)
            if override_result == "abort":
                SOURCE_HALT(id="override_halt", override_result=override_result)
                return None
            elif override_result == "force_proceed":
                finalize_payload = SOURCE_FINALIZE(id="override_finalize", gate_payload=override_result)
                SOURCE_EXECUTE(id="override_execute", finalize_payload=finalize_payload)
                return None
            elif override_result == "replan":
                SOURCE_REVISE(id="override_revise", gate_payload=override_result)
                return None
            else:
                SOURCE_HALT(id="override_unknown", override_result=override_result)
                return None
        elif gate_route_signal == "abort":
            SOURCE_HALT(id="gate_abort", gate_payload=gate_route_signal)
            return None
        elif gate_route_signal == "suspend":
            SOURCE_HALT(id="gate_suspend", gate_payload=gate_route_signal)
            return None
        elif gate_route_signal == "blocked_preflight":
            SOURCE_OVERRIDE(id="blocked_override", gate_payload=gate_route_signal)
            return None
        elif gate_route_signal == "force_proceed":
            finalize_payload = SOURCE_FINALIZE(id="force_finalize", gate_payload=gate_route_signal)
            SOURCE_EXECUTE(id="force_execute", finalize_payload=finalize_payload)
            return None
        else:
            finalize_payload = SOURCE_FINALIZE(id="fallback_finalize", gate_payload=gate_route_signal)
            SOURCE_EXECUTE(id="fallback_execute", finalize_payload=finalize_payload)
            return None
