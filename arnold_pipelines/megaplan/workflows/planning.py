"""Canonical Megaplan Python-shaped planning workflow source."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold.manifest import (
    AuthorityRequirement,
    BudgetPolicy,
    ControlTransitionSlot,
    EffectRef,
    EscalationPolicy,
    LoopPolicy,
    RetryPolicy,
    SuspensionRoute,
    TimingPolicy,
    TopologyOverlaySlot,
    WorkflowPolicy,
)
from arnold.workflow.authoring import ComponentProvenance, StepComponent
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step
from arnold.workflow.source_compiler import lower_workflow_file
from arnold_pipelines.megaplan.workflows.components import (
    ALL_STEP_COMPONENTS,
    ARTIFACT_CONTRACT_POLICY,
    CAPABILITY_REQUIREMENTS,
    DEFAULT_POLICY,
    M4_LOOP_MAX_ITERATIONS,
    MODEL_ROUTING_POLICY,
    REVISE,
    ROBUSTNESS_POLICY,
    STEP_COMPONENTS_BY_ID,
    SUSPENSION_POLICY,
    TIEBREAKER_DECIDE,
)

AUTHORING_SOURCE_PATH = Path(__file__).with_name("workflow.pypeline")
PYPELINE_AUTHORING_SOURCE_PATH = AUTHORING_SOURCE_PATH
WORKFLOW_MODULE_PATH = Path(__file__).with_name("workflow.py")


AUTHOR_REVISE = StepComponent(
    id=REVISE.id,
    provenance=ComponentProvenance(
        module=__name__,
        qualname="AUTHOR_REVISE",
        export_name="AUTHOR_REVISE",
    ),
    step_type=REVISE.step_type,
    metadata={
        "handler_ref": REVISE.metadata["handler_ref"],
        "route_bindings": (
            {
                "id": "revise:critique",
                "label": "default",
                "condition_ref": "revise:loop",
                "target_ref": "critique",
            },
        ),
    },
)
AUTHOR_TIEBREAKER_DECIDE = StepComponent(
    id=TIEBREAKER_DECIDE.id,
    provenance=ComponentProvenance(
        module=__name__,
        qualname="AUTHOR_TIEBREAKER_DECIDE",
        export_name="AUTHOR_TIEBREAKER_DECIDE",
    ),
    step_type=TIEBREAKER_DECIDE.step_type,
    metadata={
        "handler_ref": TIEBREAKER_DECIDE.metadata["handler_ref"],
        "route_bindings": (
            {
                "id": "tiebreaker_decide:critique",
                "label": "iterate",
                "condition_ref": "tiebreaker:loop",
                "target_ref": "critique",
            },
        ),
    },
)


def _component_io(items: Sequence[Mapping[str, str]], io_type: type[Input] | type[Output]) -> tuple[Any, ...]:
    values: list[Any] = []
    for item in items:
        kwargs = dict(item)
        values.append(io_type(**kwargs))
    return tuple(values)


def _policy_from_config(config: Mapping[str, Any], *, timeout_seconds: float | None) -> WorkflowPolicy:
    suspension_routes = tuple(
        SuspensionRoute(
            route_id=route["route_id"],
            capability_id=route.get("capability_id"),
            reentry_id=route.get("reentry_id"),
            payload_schema_hash=route.get("payload_schema_hash"),
            resume_schema_hash=route.get("resume_schema_hash"),
            resume_schema_ref=route.get("resume_schema_ref"),
            resume_payload_ref=route.get("resume_payload_ref"),
        )
        for route in config.get("suspension_routes", ())
    )
    control_transitions = tuple(
        ControlTransitionSlot(
            transition_id=transition["transition_id"],
            transition_type=transition["transition_type"],
            trigger_ref=transition.get("trigger_ref"),
            target_ref=transition.get("target_ref"),
            policy_ref=transition.get("policy_ref"),
        )
        for transition in config.get("control_transitions", ())
    )
    retry = None
    if isinstance(config.get("retry"), Mapping):
        retry_config = config["retry"]
        retry = RetryPolicy(
            max_attempts=int(retry_config.get("max_attempts", 1)),
            backoff=str(retry_config.get("backoff", "none")),
            retry_on=tuple(str(item) for item in retry_config.get("retry_on", ())),
        )
    escalation = None
    if isinstance(config.get("escalation"), Mapping):
        escalation_config = config["escalation"]
        escalation = EscalationPolicy(
            targets=tuple(str(item) for item in escalation_config.get("targets", ())),
            escalate_after_attempts=escalation_config.get("escalate_after_attempts"),
            policy_ref=escalation_config.get("policy_ref"),
            backoff=str(escalation_config.get("backoff", "none")),
        )
    budget = None
    if isinstance(config.get("budget"), Mapping):
        budget_config = config["budget"]
        budget = BudgetPolicy(
            max_cost=budget_config.get("max_cost"),
            max_seconds=budget_config.get("max_seconds"),
            max_attempts=budget_config.get("max_attempts"),
            token_budget=budget_config.get("token_budget"),
        )
    effects = tuple(
        EffectRef(
            effect_id=str(effect["effect_id"]),
            route=str(effect.get("route", "default")),
            payload_ref=effect.get("payload_ref"),
            payload_schema_hash=effect.get("payload_schema_hash"),
        )
        for effect in config.get("effects", ())
    )
    topology_overlays = tuple(
        TopologyOverlaySlot(
            overlay_id=str(overlay["overlay_id"]),
            overlay_type=str(overlay["overlay_type"]),
            source_ref=overlay.get("source_ref"),
            target_refs=tuple(str(item) for item in overlay.get("target_refs", ())),
            condition_ref=overlay.get("condition_ref"),
            payload_schema_hash=overlay.get("payload_schema_hash"),
        )
        for overlay in config.get("topology_overlays", ())
    )
    authority = tuple(
        AuthorityRequirement(
            authority_id=str(requirement["authority_id"]),
            action=str(requirement["action"]),
            evidence_schema_hash=requirement.get("evidence_schema_hash"),
            capability_id=requirement.get("capability_id"),
        )
        for requirement in config.get("authority", ())
    )
    loop_policy = None
    if "max_iterations" in config or "until_ref" in config:
        loop_policy = LoopPolicy(
            max_iterations=config.get("max_iterations"),
            until_ref=config.get("until_ref"),
        )
    effective_timeout = timeout_seconds if "timeout_seconds_ref" in config else None
    timing = None
    if effective_timeout is not None or "deadline_ref" in config or "ttl_seconds" in config:
        timing = TimingPolicy(
            timeout_seconds=effective_timeout,
            deadline_ref=config.get("deadline_ref"),
            ttl_seconds=config.get("ttl_seconds"),
        )
    return WorkflowPolicy(
        budget=budget,
        retry=retry,
        timing=timing,
        loop=loop_policy,
        effects=effects,
        escalation=escalation,
        suspension_routes=suspension_routes,
        control_transitions=control_transitions,
        topology_overlays=topology_overlays,
        authority=authority,
    )


def _policy_for_step(step_id: str, *, timeout_seconds: float | None) -> WorkflowPolicy:
    component = STEP_COMPONENTS_BY_ID[step_id]
    policy = component.policy or DEFAULT_POLICY
    return _policy_from_config(policy.config, timeout_seconds=timeout_seconds)


def _metadata_for_step(step_id: str) -> dict[str, Any]:
    component = STEP_COMPONENTS_BY_ID[step_id]
    metadata: dict[str, Any] = {}
    handler_ref = component.metadata.get("handler_ref")
    if isinstance(handler_ref, str):
        metadata["handler_ref"] = handler_ref
    if component.metadata.get("terminal") is True:
        metadata["terminal"] = True
    if step_id == "revise":
        metadata["max_iterations"] = M4_LOOP_MAX_ITERATIONS
    for key in ("policy_refs", "override_actions"):
        value = component.metadata.get(key)
        if value:
            metadata[key] = list(value) if isinstance(value, tuple) else value
    return metadata


def _merge_policies(*policies: WorkflowPolicy) -> WorkflowPolicy:
    return WorkflowPolicy(
        budget=next((policy.budget for policy in reversed(policies) if policy.budget is not None), None),
        retry=next((policy.retry for policy in reversed(policies) if policy.retry is not None), None),
        loop=next((policy.loop for policy in reversed(policies) if policy.loop is not None), None),
        fanout=next((policy.fanout for policy in reversed(policies) if policy.fanout is not None), None),
        timing=next((policy.timing for policy in reversed(policies) if policy.timing is not None), None),
        idempotency=next(
            (policy.idempotency for policy in reversed(policies) if policy.idempotency is not None),
            None,
        ),
        effects=tuple(effect for policy in policies for effect in policy.effects),
        reducers=tuple(reducer for policy in policies for reducer in policy.reducers),
        compensation=next(
            (policy.compensation for policy in reversed(policies) if policy.compensation is not None),
            None,
        ),
        escalation=next(
            (policy.escalation for policy in reversed(policies) if policy.escalation is not None),
            None,
        ),
        control_transitions=tuple(
            transition for policy in policies for transition in policy.control_transitions
        ),
        topology_overlays=tuple(
            overlay for policy in policies for overlay in policy.topology_overlays
        ),
        authority=tuple(requirement for policy in policies for requirement in policy.authority),
        suspension_routes=tuple(route for policy in policies for route in policy.suspension_routes),
    )


def _manifest_policy(*, timeout_seconds: float | None) -> WorkflowPolicy:
    return _merge_policies(
        _policy_from_config(DEFAULT_POLICY.config, timeout_seconds=timeout_seconds),
        _policy_from_config(MODEL_ROUTING_POLICY.config, timeout_seconds=None),
        _policy_from_config(ROBUSTNESS_POLICY.config, timeout_seconds=None),
        _policy_from_config(ARTIFACT_CONTRACT_POLICY.config, timeout_seconds=None),
        _policy_from_config(SUSPENSION_POLICY.config, timeout_seconds=None),
    )


def _canonical_steps(*, timeout_seconds: float | None) -> tuple[Step, ...]:
    steps = []
    for component in ALL_STEP_COMPONENTS:
        step_id = component.id.removeprefix("megaplan:")
        steps.append(
            Step(
                id=step_id,
                kind=component.step_type,
                inputs=_component_io(component.metadata.get("inputs", ()), Input),
                outputs=_component_io(component.metadata.get("outputs", ()), Output),
                policy=_policy_for_step(step_id, timeout_seconds=timeout_seconds),
                metadata=_metadata_for_step(step_id),
            )
        )
    return tuple(steps)


def _canonical_routes() -> tuple[Route, ...]:
    routes: list[Route] = []
    for component in ALL_STEP_COMPONENTS:
        source = component.id.removeprefix("megaplan:")
        for binding in component.metadata.get("route_bindings", ()):
            routes.append(
                Route(
                    id=str(binding["id"]),
                    source=source,
                    target=str(binding["target_ref"]),
                    label=str(binding.get("label", "default")),
                    condition_ref=(
                        str(binding["condition_ref"])
                        if binding.get("condition_ref") is not None
                        else None
                    ),
                    metadata={},
                )
            )
    return tuple(routes)


def _canonical_capabilities() -> tuple[Capability, ...]:
    return tuple(
        Capability(
            id=capability_id,
            route=config["route"],
            required=config["required"],
        )
        for capability_id, config in CAPABILITY_REQUIREMENTS.items()
    )


def build_pipeline(
    *,
    timeout_seconds: float | None = 300.0,
    max_critique_iterations: int = 4,
) -> Pipeline:
    """Return the canonical Megaplan planning workflow as a DSL pipeline."""

    lowered = lower_workflow_file(AUTHORING_SOURCE_PATH)
    return Pipeline(
        id=lowered.id,
        version=lowered.version,
        steps=_canonical_steps(timeout_seconds=timeout_seconds),
        routes=_canonical_routes(),
        capabilities=_canonical_capabilities(),
        policy=_manifest_policy(timeout_seconds=timeout_seconds),
        metadata={
            "product": "megaplan",
            "max_critique_iterations": max_critique_iterations,
            "policy_refs": [
                DEFAULT_POLICY.id,
                MODEL_ROUTING_POLICY.id,
                ROBUSTNESS_POLICY.id,
                ARTIFACT_CONTRACT_POLICY.id,
                SUSPENSION_POLICY.id,
            ],
        },
    )


__all__ = [
    "AUTHORING_SOURCE_PATH",
    "PYPELINE_AUTHORING_SOURCE_PATH",
    "WORKFLOW_MODULE_PATH",
    "build_pipeline",
]
