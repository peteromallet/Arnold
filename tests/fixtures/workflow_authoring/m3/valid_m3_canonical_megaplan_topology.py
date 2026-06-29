from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    DEFAULT_POLICY,
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
    SOURCE_TIEBREAKER_DECIDE,
    SOURCE_TIEBREAKER_RUN,
)


@workflow(id="megaplan", version="m4-phase3", policy=DEFAULT_POLICY)
def flow(brief):
    prep_payload = SOURCE_PREP(id="prep", brief=brief)
    plan_payload = SOURCE_PLAN(id="plan", prep_payload=prep_payload)
    critique_payload = SOURCE_CRITIQUE(id="critique", plan_payload=plan_payload)
    gate_payload = SOURCE_GATE(id="gate", critique_payload=critique_payload)
    if gate_payload == "proceed":
        finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=gate_payload)
        execute_payload = SOURCE_EXECUTE(id="execute", finalize_payload=finalize_payload)
        review_payload = SOURCE_REVIEW(id="review", execute_payload=execute_payload)
        if review_payload == "pass":
            SOURCE_HALT(id="halt", review_payload=review_payload)
        else:
            revise_payload = SOURCE_REVISE(id="revise", gate_payload=review_payload)
            SOURCE_CRITIQUE(id="critique", plan_payload=revise_payload)
    elif gate_payload == "iterate":
        revise_payload = SOURCE_REVISE(id="revise", gate_payload=gate_payload)
        SOURCE_CRITIQUE(id="critique", plan_payload=revise_payload)
    elif gate_payload == "tiebreaker":
        tiebreaker_payload = SOURCE_TIEBREAKER_RUN(id="tiebreaker_run", gate_payload=gate_payload)
        decision = SOURCE_TIEBREAKER_DECIDE(id="tiebreaker_decide", tiebreaker_payload=tiebreaker_payload)
        if decision == "iterate":
            SOURCE_CRITIQUE(id="critique", plan_payload=decision)
        elif decision == "proceed":
            finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=decision)
            SOURCE_EXECUTE(id="execute", finalize_payload=finalize_payload)
        else:
            SOURCE_OVERRIDE(id="override", gate_payload=decision)
    elif gate_payload == "escalate":
        override_result = SOURCE_OVERRIDE(id="override", gate_payload=gate_payload)
        if override_result == "abort":
            SOURCE_HALT(id="halt", override_result=override_result)
        elif override_result == "force_proceed":
            finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=override_result)
            SOURCE_EXECUTE(id="execute", finalize_payload=finalize_payload)
        else:
            SOURCE_REVISE(id="revise", gate_payload=override_result)
    elif gate_payload == "abort":
        SOURCE_HALT(id="halt", gate_payload=gate_payload)
    elif gate_payload == "suspend":
        SOURCE_HALT(id="halt", gate_payload=gate_payload)
    elif gate_payload == "blocked_preflight":
        SOURCE_OVERRIDE(id="override", gate_payload=gate_payload)
    else:
        finalize_payload = SOURCE_FINALIZE(id="finalize", gate_payload=gate_payload)
        SOURCE_EXECUTE(id="execute", finalize_payload=finalize_payload)
