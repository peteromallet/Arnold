"""Megaplan's canonical authored workflow source."""

from __future__ import annotations

from arnold.workflow.authoring import loop, workflow
from arnold_pipelines.megaplan.workflows.components import (
    DEFAULT_POLICY,
    REVISE_LOOP_POLICY,
    SOURCE_CRITIQUE,
    SOURCE_EXECUTE,
    SOURCE_FINALIZE,
    SOURCE_GATE,
    SOURCE_HALT,
    SOURCE_OVERRIDE,
    SOURCE_PLAN,
    SOURCE_PREP,
    SOURCE_REVIEW,
    SOURCE_REVISE,
    SOURCE_TIEBREAKER_RUN,
)
from arnold_pipelines.megaplan.workflows.planning import (
    AUTHOR_REVISE,
    AUTHOR_TIEBREAKER_DECIDE,
)


@workflow(id="megaplan", version="m4-phase3", policy=DEFAULT_POLICY)
def planning_workflow(brief: str) -> None:
    prep_payload = SOURCE_PREP(id="prep", brief=brief)
    plan_payload = SOURCE_PLAN(id="plan", prep_payload=prep_payload)

    loop(policy=REVISE_LOOP_POLICY, reentry_id="critique")
    while True:
        critique_payload = SOURCE_CRITIQUE(id="critique", plan_payload=plan_payload)
        gate_payload = SOURCE_GATE(id="gate", critique_payload=critique_payload)

        if gate_payload == "proceed":
            finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=gate_payload)
            execute_payload = SOURCE_EXECUTE(id="execute", finalize_payload=finalize_payload)
            review_payload = SOURCE_REVIEW(id="review", execute_payload=execute_payload)
            if review_payload == "pass":
                SOURCE_HALT(id="halt", review_payload=review_payload)
                return None
            elif review_payload == "rework":
                SOURCE_REVISE(id="review_revise", gate_payload=review_payload)
                return None
            else:
                SOURCE_HALT(id="review_halt", review_payload=review_payload)
                return None
        elif gate_payload == "iterate":
            AUTHOR_REVISE(id="revise", gate_payload=gate_payload)
        elif gate_payload == "tiebreaker":
            tiebreaker_payload = SOURCE_TIEBREAKER_RUN(id="tiebreaker_run", gate_payload=gate_payload)
            decision = AUTHOR_TIEBREAKER_DECIDE(id="tiebreaker_decide", tiebreaker_payload=tiebreaker_payload)
            if decision == "proceed":
                finalize_payload = SOURCE_FINALIZE(id="tiebreaker_finalize", gate_payload=decision)
                SOURCE_EXECUTE(id="tiebreaker_execute", finalize_payload=finalize_payload)
                return None
            elif decision == "escalate":
                SOURCE_OVERRIDE(id="tiebreaker_override", gate_payload=decision)
                return None
        elif gate_payload == "escalate":
            override_result = SOURCE_OVERRIDE(id="override", gate_payload=gate_payload)
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
        elif gate_payload == "abort":
            SOURCE_HALT(id="gate_abort", gate_payload=gate_payload)
            return None
        elif gate_payload == "suspend":
            SOURCE_HALT(id="gate_suspend", gate_payload=gate_payload)
            return None
        elif gate_payload == "blocked_preflight":
            SOURCE_OVERRIDE(id="blocked_override", gate_payload=gate_payload)
            return None
        elif gate_payload == "force_proceed":
            finalize_payload = SOURCE_FINALIZE(id="force_finalize", gate_payload=gate_payload)
            SOURCE_EXECUTE(id="force_execute", finalize_payload=finalize_payload)
            return None
        else:
            finalize_payload = SOURCE_FINALIZE(id="fallback_finalize", gate_payload=gate_payload)
            SOURCE_EXECUTE(id="fallback_execute", finalize_payload=finalize_payload)
            return None
