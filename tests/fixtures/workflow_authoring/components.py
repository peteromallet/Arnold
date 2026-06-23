from __future__ import annotations

from arnold.workflow.authoring import (
    ComponentProvenance,
    PolicyComponent,
    PromptComponent,
    SchemaComponent,
    StepComponent,
    SubflowComponent,
)


def _provenance(name: str) -> ComponentProvenance:
    return ComponentProvenance(
        module="tests.fixtures.workflow_authoring.components",
        qualname=name,
        export_name=name,
    )


plan_output = SchemaComponent(
    id="plan_output",
    provenance=_provenance("plan_output"),
    schema_type="python-type",
    schema={"type": "Plan"},
)
review_prompt = PromptComponent(
    id="review_prompt",
    provenance=_provenance("review_prompt"),
    template="Review the execution evidence.",
    parameters=("evidence",),
)

plan = StepComponent(id="plan", provenance=_provenance("plan"), output_schema=plan_output)
execute = StepComponent(id="execute", provenance=_provenance("execute"))
review = StepComponent(id="review", provenance=_provenance("review"), prompt=review_prompt)
route = StepComponent(id="route", provenance=_provenance("route"), output_schema=plan_output)
revise = StepComponent(id="revise", provenance=_provenance("revise"))

fast_retry = PolicyComponent(
    id="fast_retry",
    provenance=_provenance("fast_retry"),
    policy_type="retry",
    config={"max_attempts": 2, "retry_on": ("transient",)},
)
review_timeout = PolicyComponent(
    id="review_timeout",
    provenance=_provenance("review_timeout"),
    policy_type="timing",
    config={"timeout_seconds": 60},
)
review_approval = PolicyComponent(
    id="review_approval",
    provenance=_provenance("review_approval"),
    policy_type="approval",
    config={
        "authority_id": "review-approval",
        "action": "approve-review",
        "capability_id": "human.review",
    },
)
handoff_transition = PolicyComponent(
    id="handoff_transition",
    provenance=_provenance("handoff_transition"),
    policy_type="control-transition",
    config={
        "transition_id": "handoff",
        "transition_type": "approval-handoff",
        "trigger_ref": "review.needs_approval",
        "target_ref": "reviewer",
        "policy_ref": "review_approval",
    },
)
operator_suspend = PolicyComponent(
    id="operator_suspend",
    provenance=_provenance("operator_suspend"),
    policy_type="suspension",
    config={
        "route_id": "operator",
        "capability_id": "human.review",
        "reentry_id": "execute",
        "resume_schema_ref": "operator.resume",
    },
)
bounded_review_loop = PolicyComponent(
    id="bounded_review_loop",
    provenance=_provenance("bounded_review_loop"),
    policy_type="loop",
    config={"max_iterations": 3, "reentry_id": "execute", "until_ref": "review.approved"},
)
unbounded_review_loop = PolicyComponent(
    id="unbounded_review_loop",
    provenance=_provenance("unbounded_review_loop"),
    policy_type="loop",
    config={"reentry_id": "execute", "until_ref": "review.approved"},
)
dynamic_model_router = PolicyComponent(
    id="dynamic_model_router",
    provenance=_provenance("dynamic_model_router"),
    policy_type="model-routing",
    config={"selector_ref": "runtime.model_selector"},
)
robustness_guard = PolicyComponent(
    id="robustness_guard",
    provenance=_provenance("robustness_guard"),
    policy_type="robustness",
    config={"strategy": "self-consistency"},
)
reprompt_guard = PolicyComponent(
    id="reprompt_guard",
    provenance=_provenance("reprompt_guard"),
    policy_type="reprompt",
    config={"max_reprompts": 2},
)
review_subflow = SubflowComponent(
    id="review_subflow",
    provenance=_provenance("review_subflow"),
    workflow_id="nested-review",
    version="1.0",
    metadata={"manifest_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"},
)
