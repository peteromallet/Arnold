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
    TIEBREAKER_POLICY,
)
from arnold_pipelines.megaplan.workflows.planning import (
    AUTHOR_REVISE,
    AUTHOR_TIEBREAKER_DECIDE,
)


def planning_prep_subworkflow(brief: str) -> object:
    """Source-visible planning setup boundary.

    The canonical compiled graph keeps the public ``prep`` and ``plan`` stage
    IDs. This named body makes the interface boundary explicit without giving
    handlers ownership of the transition.
    """

    prep_signal = SOURCE_PREP(id="prep", brief=brief)
    plan_payload = SOURCE_PLAN(id="plan", prep_payload=prep_signal)
    return plan_payload


def critique_gate_revise_subworkflow(plan_payload: object) -> object:
    """Source-visible critique/gate/revise loop boundary."""

    loop(policy=REVISE_LOOP_POLICY, reentry_id="critique")
    while True:
        critique_payload = SOURCE_CRITIQUE(id="critique", plan_payload=plan_payload)
        gate_route_signal = SOURCE_GATE(id="gate", critique_payload=critique_payload)

        if gate_route_signal == "iterate":
            AUTHOR_REVISE(id="revise", gate_payload=gate_route_signal)
        else:
            return gate_route_signal


def tiebreaker_subworkflow(gate_route_signal: object) -> object:
    """Source-visible tiebreaker routing boundary."""

    loop(policy=TIEBREAKER_POLICY, reentry_id="critique")
    tiebreaker_payload = SOURCE_TIEBREAKER_RUN(
        id="tiebreaker_run",
        gate_payload=gate_route_signal,
    )
    decision = AUTHOR_TIEBREAKER_DECIDE(
        id="tiebreaker_decide",
        tiebreaker_payload=tiebreaker_payload,
    )

    if decision == "iterate":
        return decision
    elif decision == "proceed":
        return decision
    else:
        return "escalate"


def finalize_execute_review_subworkflow(gate_route_signal: object) -> object:
    """Source-visible finalize/execute/review boundary."""

    finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=gate_route_signal)
    execute_payload = SOURCE_EXECUTE(id="execute", finalize_payload=finalize_payload)
    review_route_signal = SOURCE_REVIEW(id="review", execute_payload=execute_payload)

    if review_route_signal == "pass":
        SOURCE_HALT(id="halt", review_payload=review_route_signal)
        return "done"
    elif review_route_signal == "rework":
        SOURCE_REVISE(id="review_revise", gate_payload=review_route_signal)
        return "rework"
    else:
        SOURCE_HALT(id="review_halt", review_payload=review_route_signal)
        return "blocked"


def override_escalation_subworkflow(gate_route_signal: object) -> object:
    """Source-visible override/escalation routing boundary."""

    override_result = SOURCE_OVERRIDE(id="override", gate_payload=gate_route_signal)
    if override_result == "abort":
        SOURCE_HALT(id="override_halt", override_result=override_result)
        return "abort"
    elif override_result == "force_proceed":
        finalize_payload = SOURCE_FINALIZE(id="override_finalize", gate_payload=override_result)
        SOURCE_EXECUTE(id="override_execute", finalize_payload=finalize_payload)
        return "force_proceed"
    elif override_result == "replan":
        SOURCE_REVISE(id="override_revise", gate_payload=override_result)
        return "replan"
    else:
        SOURCE_HALT(id="override_unknown", override_result=override_result)
        return "unknown"


@workflow(id="megaplan", version="m4-phase3", policy=DEFAULT_POLICY)
def planning_workflow(brief: str) -> None:
    # The V1 source compiler lowers only the decorated workflow body, so this
    # route-compatible spine remains the compiled public-stage authority until
    # neutral subworkflow calls can be inlined without stage-name suffixing.
    prep_signal = SOURCE_PREP(id="prep", brief=brief)
    plan_payload = SOURCE_PLAN(id="plan", prep_payload=prep_signal)

    loop(policy=REVISE_LOOP_POLICY, reentry_id="critique")
    while True:
        critique_payload = SOURCE_CRITIQUE(id="critique", plan_payload=plan_payload)
        gate_route_signal = SOURCE_GATE(id="gate", critique_payload=critique_payload)

        if gate_route_signal == "proceed":
            finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=gate_route_signal)
            execute_payload = SOURCE_EXECUTE(id="execute", finalize_payload=finalize_payload)
            review_route_signal = SOURCE_REVIEW(id="review", execute_payload=execute_payload)
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
            AUTHOR_REVISE(id="revise", gate_payload=gate_route_signal)
        elif gate_route_signal == "tiebreaker":
            tiebreaker_payload = SOURCE_TIEBREAKER_RUN(id="tiebreaker_run", gate_payload=gate_route_signal)
            decision = AUTHOR_TIEBREAKER_DECIDE(id="tiebreaker_decide", tiebreaker_payload=tiebreaker_payload)
            if decision == "proceed":
                finalize_payload = SOURCE_FINALIZE(id="tiebreaker_finalize", gate_payload=decision)
                SOURCE_EXECUTE(id="tiebreaker_execute", finalize_payload=finalize_payload)
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
