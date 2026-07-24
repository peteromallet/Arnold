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
execute_with_artifact_capability = StepComponent(
    id="execute",
    provenance=_provenance("execute_with_artifact_capability"),
    metadata={
        "capability_requirements": (
            {"id": "artifact:write", "route": "default", "required": True},
        ),
        "handler_ref": "tests.fixtures.workflow_authoring.components:execute",
    },
)
execute_with_malformed_capability = StepComponent(
    id="execute",
    provenance=_provenance("execute_with_malformed_capability"),
    metadata={"capability_requirements": ({"id": "", "required": "yes"},)},
)
review = StepComponent(id="review", provenance=_provenance("review"), prompt=review_prompt)
static_prompt_missing = StepComponent(
    id="static_prompt_missing",
    provenance=_provenance("static_prompt_missing"),
    metadata={"prompt_key": "review"},
)
static_resource_missing = StepComponent(
    id="static_resource_missing",
    provenance=_provenance("static_resource_missing"),
    metadata={"resource_dependencies": ("model",), "resources": {"cache": "local-cache"}},
)
route = StepComponent(id="route", provenance=_provenance("route"), output_schema=plan_output)
route_with_duplicate_bindings = StepComponent(
    id="route",
    provenance=_provenance("route_with_duplicate_bindings"),
    output_schema=plan_output,
    metadata={
        "route_bindings": (
            {
                "id": "route:execute",
                "target_ref": "execute",
                "label": "approve",
                "condition_ref": "route.approve",
            },
            {
                "id": "route:execute:duplicate",
                "target_ref": "execute",
                "label": "approve",
                "condition_ref": "route.approve.again",
            },
        )
    },
)
route_with_mismatched_binding = StepComponent(
    id="route",
    provenance=_provenance("route_with_mismatched_binding"),
    output_schema=plan_output,
    metadata={
        "route_bindings": (
            {
                "id": "route:missing",
                "target_ref": "missing-target",
                "label": "approve",
                "condition_ref": "route.missing",
            },
        )
    },
)
revise = StepComponent(id="revise", provenance=_provenance("revise"))

fast_retry = PolicyComponent(
    id="fast_retry",
    provenance=_provenance("fast_retry"),
    policy_type="retry",
    config={"max_attempts": 2, "retry_on": ("transient",)},
)
malformed_retry = PolicyComponent(
    id="malformed_retry",
    provenance=_provenance("malformed_retry"),
    policy_type="retry",
    config={"max_attempts": 0, "retry_on": "transient"},
)
review_timeout = PolicyComponent(
    id="review_timeout",
    provenance=_provenance("review_timeout"),
    policy_type="timing",
    config={"timeout_seconds": 60},
)
malformed_timing = PolicyComponent(
    id="malformed_timing",
    provenance=_provenance("malformed_timing"),
    policy_type="timing",
    config={"timeout_seconds": "soon"},
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
