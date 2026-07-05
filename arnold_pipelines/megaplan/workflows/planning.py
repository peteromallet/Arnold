"""Canonical Megaplan Python-shaped planning workflow source."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
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
FRONT_HALF_SOURCE_PATH = Path(__file__).with_name("front_half.pypeline")
WORKFLOW_MODULE_PATH = Path(__file__).with_name("workflow.py")
FRONT_HALF_ROUTING_STEP_IDS = frozenset({"prep", "plan", "critique", "gate", "revise"})
LOWERED_FRONT_HALF_STEP_ID_ALIASES = MappingProxyType(
    {
        "prep": "prep",
        "plan": "plan",
        "critique-fanout": "critique",
        "gate": "gate",
        "revise": "revise",
    }
)
LOWERED_FRONT_HALF_ROUTE_ID_ALIASES = MappingProxyType(
    {
        "critique-fanout": "critique",
        "gate_retry_revise": "revise",
        "gate_reprompt_revise": "revise",
        "gate_abort": "halt",
        "gate_suspend": "halt",
        "blocked_override": "override",
        "force_finalize": "finalize",
        "fallback_finalize": "finalize",
        "tiebreaker": "tiebreaker_run",
    }
)


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
            metadata[key] = value
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


def _step_from_component(step_id: str, *, timeout_seconds: float | None) -> Step:
    component = STEP_COMPONENTS_BY_ID[step_id]
    return Step(
        id=step_id,
        kind=component.step_type,
        inputs=_component_io(component.metadata.get("inputs", ()), Input),
        outputs=_component_io(component.metadata.get("outputs", ()), Output),
        policy=_policy_for_step(step_id, timeout_seconds=timeout_seconds),
        metadata=_metadata_for_step(step_id),
    )


def _front_half_step_from_lowered(
    step: Step,
    *,
    step_id: str,
    timeout_seconds: float | None,
) -> Step:
    adapter = _step_from_component(step_id, timeout_seconds=timeout_seconds)
    metadata = {
        **dict(step.metadata),
        **dict(adapter.metadata),
        "lowered_step_id": step.id,
    }
    return replace(
        step,
        id=step_id,
        policy=step.policy or adapter.policy,
        metadata=metadata,
    )


def _lowered_front_half_steps(
    lowered: Pipeline,
    *,
    timeout_seconds: float | None,
) -> Mapping[str, Step]:
    steps: dict[str, Step] = {}
    for step in lowered.steps:
        step_id = LOWERED_FRONT_HALF_STEP_ID_ALIASES.get(step.id)
        if step_id is None:
            continue
        steps[step_id] = _front_half_step_from_lowered(
            step,
            step_id=step_id,
            timeout_seconds=timeout_seconds,
        )
    return steps


def _canonical_steps(*, timeout_seconds: float | None, lowered: Pipeline | None = None) -> tuple[Step, ...]:
    lowered_front_half = (
        {}
        if lowered is None
        else _lowered_front_half_steps(lowered, timeout_seconds=timeout_seconds)
    )
    steps = []
    for component in ALL_STEP_COMPONENTS:
        step_id = component.id.removeprefix("megaplan:")
        steps.append(lowered_front_half.get(step_id) or _step_from_component(step_id, timeout_seconds=timeout_seconds))
    return tuple(steps)


def _canonical_route_from_binding(source: str, binding: Mapping[str, Any]) -> Route:
    return Route(
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


def _lowered_front_half_routes(lowered: Pipeline) -> tuple[Route, ...]:
    routes: list[Route] = []
    seen: set[tuple[str, str, str]] = set()
    for route in lowered.routes:
        source = LOWERED_FRONT_HALF_ROUTE_ID_ALIASES.get(route.source, route.source)
        target = LOWERED_FRONT_HALF_ROUTE_ID_ALIASES.get(route.target, route.target)
        if source == "critique-fanout":
            source = "critique"
        if target == "critique-fanout":
            target = "critique"
        if source not in FRONT_HALF_ROUTING_STEP_IDS or route.label == "else":
            continue
        route_id = f"{source}:{target}" if route.label == "default" else f"{source}:{target}:{route.label}"
        key = (source, target, route.label)
        if key in seen:
            continue
        seen.add(key)
        routes.append(
            Route(
                id=route_id,
                source=source,
                target=target,
                label=route.label,
                condition_ref=route.condition_ref,
                source_span=route.source_span,
                metadata={
                    "lowered_route_id": route.id,
                    "source_of_truth": str(AUTHORING_SOURCE_PATH),
                },
            )
        )
    if not any(route.source == "revise" and route.target == "critique" for route in routes):
        for binding in AUTHOR_REVISE.metadata["route_bindings"]:
            routes.append(_canonical_route_from_binding("revise", binding))
    return tuple(routes)


def _canonical_routes(*, lowered: Pipeline | None = None) -> tuple[Route, ...]:
    routes: list[Route] = []
    if lowered is not None:
        routes.extend(_lowered_front_half_routes(lowered))
    for component in ALL_STEP_COMPONENTS:
        source = component.id.removeprefix("megaplan:")
        if source in FRONT_HALF_ROUTING_STEP_IDS:
            continue
        for binding in component.metadata.get("route_bindings", ()):
            routes.append(_canonical_route_from_binding(source, binding))
    return tuple(routes)


@lru_cache(maxsize=1)
def lowered_workflow_topology() -> Pipeline:
    """Return the canonical lowered authored workflow topology once per process."""

    return lower_workflow_file(AUTHORING_SOURCE_PATH)


def lowered_route_bindings_by_step(
    *,
    step_ids: frozenset[str] | set[str] | None = None,
) -> Mapping[str, tuple[Mapping[str, str | None], ...]]:
    """Expose lowered route bindings grouped by source step id.

    Front-half routing uses these lowered bindings as the semantic authority so
    component metadata mutations cannot silently reroute authored behavior.
    """

    selected = None if step_ids is None else frozenset(step_ids)
    bindings: dict[str, list[Mapping[str, str | None]]] = {}
    for route in lowered_workflow_topology().routes:
        if selected is not None and route.source not in selected:
            continue
        bindings.setdefault(route.source, []).append(
            {
                "id": route.id,
                "label": route.label,
                "target_ref": route.target,
                "condition_ref": route.condition_ref,
            }
        )
    return {
        source: tuple(source_bindings)
        for source, source_bindings in bindings.items()
    }


def resolve_lowered_route_target_for_signal(step: str, route_signal: str) -> str | None:
    """Resolve a route target from lowered authored topology for ``step``."""

    for binding in lowered_route_bindings_by_step(step_ids={step}).get(step, ()):
        if binding.get("label") == route_signal:
            target_ref = binding.get("target_ref")
            if isinstance(target_ref, str) and target_ref:
                return target_ref
    return None


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
        steps=_canonical_steps(timeout_seconds=timeout_seconds, lowered=lowered),
        routes=_canonical_routes(lowered=lowered),
        capabilities=_canonical_capabilities(),
        policy=_manifest_policy(timeout_seconds=timeout_seconds),
        metadata={
            "product": "megaplan",
            "max_critique_iterations": max_critique_iterations,
            "policy_refs": (
                DEFAULT_POLICY.id,
                MODEL_ROUTING_POLICY.id,
                ROBUSTNESS_POLICY.id,
                ARTIFACT_CONTRACT_POLICY.id,
                SUSPENSION_POLICY.id,
            ),
        },
    )


__all__ = [
    "AUTHORING_SOURCE_PATH",
    "FRONT_HALF_ROUTING_STEP_IDS",
    "PYPELINE_AUTHORING_SOURCE_PATH",
    "FRONT_HALF_SOURCE_PATH",
    "WORKFLOW_MODULE_PATH",
    "build_pipeline",
    "lowered_route_bindings_by_step",
    "lowered_workflow_topology",
    "resolve_lowered_route_target_for_signal",
]
