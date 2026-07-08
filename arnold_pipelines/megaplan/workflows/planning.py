"""Canonical Megaplan Python-shaped planning workflow source."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from arnold.workflow import source_compiler as workflow_source_compiler
from arnold.manifest import (
    AuthorityRequirement,
    BudgetPolicy,
    ControlTransitionSlot,
    EffectRef,
    EscalationPolicy,
    IdempotencyPolicy,
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
from arnold_pipelines.megaplan.workflows import components as workflow_components_module
from arnold_pipelines.megaplan.workflows.components import (
    ALL_STEP_COMPONENTS,
    ARTIFACT_CONTRACT_POLICY,
    CAPABILITY_REQUIREMENTS,
    DEFAULT_POLICY,
    M4_LOOP_MAX_ITERATIONS,
    MODEL_ROUTING_POLICY,
    REVISE,
    TIEBREAKER_CHALLENGER,
    ROBUSTNESS_POLICY,
    SUSPENSION_POLICY,
    TIEBREAKER_DECIDE,
    TIEBREAKER_DECISION,
    TIEBREAKER_RESEARCHER,
    TIEBREAKER_SYNTHESIS,
)

AUTHORING_SOURCE_PATH = Path(__file__).with_name("workflow.pypeline")
PYPELINE_AUTHORING_SOURCE_PATH = AUTHORING_SOURCE_PATH
WORKFLOW_MODULE_PATH = Path(__file__).with_name("workflow.py")
# Front-half step IDs used by boundary contracts and routing alike.
# Boundary contracts reference these step IDs only to correlate durable
# effects (receipts, findings) with implemented source rows.  They do
# NOT own route topology — route selection is the exclusive province of
# source-level Route declarations and runtime signal handlers.
FRONT_HALF_ROUTING_STEP_IDS = frozenset(
    {
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
        "tiebreaker_synthesis",
        "tiebreaker_decision",
    }
)

_PIPELINE_STEP_COMPONENTS_LIST = []
for _component in ALL_STEP_COMPONENTS:
    if _component.id == "megaplan:revise":
        _PIPELINE_STEP_COMPONENTS_LIST.append(_component)
        _PIPELINE_STEP_COMPONENTS_LIST.extend(
            (
                TIEBREAKER_RESEARCHER,
                TIEBREAKER_CHALLENGER,
                TIEBREAKER_SYNTHESIS,
                TIEBREAKER_DECISION,
            )
        )
        continue
    if _component.id in {
        "megaplan:tiebreaker_run",
        "megaplan:tiebreaker_decide",
        "megaplan:tiebreaker_researcher",
        "megaplan:tiebreaker_challenger",
        "megaplan:tiebreaker_synthesis",
        "megaplan:tiebreaker_decision",
    }:
        continue
    _PIPELINE_STEP_COMPONENTS_LIST.append(_component)
PIPELINE_STEP_COMPONENTS = tuple(_PIPELINE_STEP_COMPONENTS_LIST)
PIPELINE_STEP_COMPONENTS_BY_ID = {
    component.id.removeprefix("megaplan:"): component for component in PIPELINE_STEP_COMPONENTS
}
_POLICY_ROUTE_SURFACE_EXPORTS_BY_STEP_ID = {
    "execute": "EXECUTE_POLICY",
    "finalize": "FINALIZE_POLICY",
    "gate": "GATE_POLICY",
    "override": "OVERRIDE_POLICY",
    "review": "REVIEW_POLICY",
    "tiebreaker_decision": "TIEBREAKER_POLICY",
}
_WORKFLOW_TOPOLOGY_EXPORTS_BY_WORKFLOW_ID = {
    "critique_panel": "SOURCE_CRITIQUE_PANEL_WORKFLOW",
    "execute_batch": "SOURCE_EXECUTE_BATCH_WORKFLOW",
    "review_panel": "SOURCE_REVIEW_PANEL_WORKFLOW",
    "tiebreaker_child": "SOURCE_TIEBREAKER_WORKFLOW",
}

_LOWERED_STEP_ID_ALIASES = {
    "blocked_override": "override",
    "critique-fanout": "critique",
    "execute-batches": "execute",
    "fallback_execute": "execute",
    "fallback_finalize": "finalize",
    "force_execute": "execute",
    "force_finalize": "finalize",
    "gate_abort": "halt",
    "gate_reprompt_revise": "revise",
    "gate_retry_revise": "revise",
    "gate_suspend": "halt",
    "override_halt": "halt",
    "override_revise": "revise",
    "override_unknown": "halt",
    "review-fan-in": "review",
    "review_deferred_human": "halt",
    "review_halt": "halt",
    "review_override": "override",
    "review_revise": "revise",
    "tiebreaker_decide": "tiebreaker_decision",
    "tiebreaker_fallback_override": "override",
    "tiebreaker_finalize": "finalize",
    "tiebreaker_iterate_revise": "revise",
    "tiebreaker_override": "override",
    "tiebreaker_override_finalize": "finalize",
    "tiebreaker_override_revise": "revise",
    "tiebreaker_replan_revise": "revise",
    "tiebreaker_run": "tiebreaker_researcher",
}

_ROUTE_LABEL_BY_TRANSITION_ID = {
    "gate": {
        "gate:abort": "abort",
        "gate:escalate": "escalate",
        "gate:iterate": "iterate",
        "gate:proceed": "proceed",
        "gate:tiebreaker": "tiebreaker",
    },
    "tiebreaker_decision": {
        "tiebreaker:escalate": "escalate",
        "tiebreaker:iterate": "iterate",
        "tiebreaker:proceed": "proceed",
    },
}


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


@lru_cache(maxsize=1)
def _lowered_workflow() -> Pipeline:
    return lower_workflow_file(AUTHORING_SOURCE_PATH)


def _canonical_step_id(step_id: str) -> str:
    return _LOWERED_STEP_ID_ALIASES.get(step_id, step_id)


def _topology_step_id(step_id: str) -> str:
    canonical_step_id = _canonical_step_id(step_id)
    if canonical_step_id != step_id:
        return canonical_step_id
    if "review" in step_id:
        if step_id.endswith(("-execute-batches", "_execute_batches")):
            return "execute"
        if step_id.endswith(("-fan-in", "_fan_in")):
            return "review"
    return step_id


def _lowered_step_aliases(
    lowered_steps: Sequence[Step],
    *,
    step_id_fn: Callable[[str], str] = _canonical_step_id,
) -> dict[str, tuple[str, ...]]:
    aliases: dict[str, set[str]] = {}
    for lowered in lowered_steps:
        canonical_step_id = step_id_fn(lowered.id)
        if canonical_step_id == lowered.id:
            continue
        aliases.setdefault(canonical_step_id, set()).add(lowered.id)
    return {
        canonical_step_id: tuple(sorted(alias_ids))
        for canonical_step_id, alias_ids in sorted(aliases.items())
    }


def _canonical_lowered_steps(lowered_steps: Sequence[Step]) -> dict[str, Step]:
    canonical_steps: dict[str, Step] = {}
    for lowered in lowered_steps:
        step_id = _canonical_step_id(lowered.id)
        if step_id not in PIPELINE_STEP_COMPONENTS_BY_ID or step_id in canonical_steps:
            continue
        canonical_steps[step_id] = lowered
    return canonical_steps


def _route_id_for_lowered_route(
    route: Route,
    *,
    source: str,
    target: str,
    label: str | None = None,
) -> str:
    route_label = route.label if label is None else label
    component = PIPELINE_STEP_COMPONENTS_BY_ID.get(source)
    if component is not None:
        bindings = declared_step_route_bindings(source) or component.metadata.get("route_bindings", ())
        for binding in bindings:
            if (
                str(binding.get("label", "default")) == route_label
                and _canonical_step_id(str(binding.get("target_ref", ""))) == target
            ):
                return str(binding["id"])
        for binding in bindings:
            if str(binding.get("label", "default")) == route_label:
                return str(binding["id"])
    suffix = target if route_label == "default" else route_label
    return f"{source}:{suffix}"


def _canonical_lowered_routes(lowered_routes: Sequence[Route]) -> tuple[Route, ...]:
    seen: set[tuple[str, str, str, str | None]] = set()
    seen_route_ids: set[str] = set()
    routes: list[Route] = []
    for lowered in lowered_routes:
        source = _canonical_step_id(lowered.source)
        target = _canonical_step_id(lowered.target)
        if source not in PIPELINE_STEP_COMPONENTS_BY_ID or target not in PIPELINE_STEP_COMPONENTS_BY_ID:
            continue
        signature = (source, target, lowered.label, lowered.condition_ref)
        if signature in seen:
            continue
        seen.add(signature)
        route = Route(
            id=_route_id_for_lowered_route(lowered, source=source, target=target),
            source=source,
            target=target,
            label=lowered.label,
            condition_ref=lowered.condition_ref,
            metadata={},
        )
        if route.id in seen_route_ids:
            continue
        seen_route_ids.add(route.id)
        routes.append(route)
    return tuple(routes)


def _topology_lowered_routes(lowered_routes: Sequence[Route]) -> tuple[Route, ...]:
    seen: set[tuple[str, str, str, str | None]] = set()
    seen_route_ids: set[str] = set()
    routes: list[Route] = []
    for lowered in lowered_routes:
        source = _topology_step_id(lowered.source)
        target = _topology_step_id(lowered.target)
        if source not in PIPELINE_STEP_COMPONENTS_BY_ID or target not in PIPELINE_STEP_COMPONENTS_BY_ID:
            continue
        signature = (source, target, lowered.label, lowered.condition_ref)
        if signature in seen:
            continue
        seen.add(signature)
        route = Route(
            id=_route_id_for_lowered_route(lowered, source=source, target=target),
            source=source,
            target=target,
            label=lowered.label,
            condition_ref=lowered.condition_ref,
            metadata={},
        )
        if route.id in seen_route_ids:
            continue
        seen_route_ids.add(route.id)
        routes.append(route)
    return tuple(routes)


def _canonical_lowered_route_targets_by_source(lowered_routes: Sequence[Route]) -> dict[str, dict[str, str]]:
    grouped: dict[str, dict[str, str]] = {}
    for route in _canonical_lowered_routes(lowered_routes):
        grouped.setdefault(route.source, {})[route.label] = route.target
    return grouped


def _supported_pipeline_route_labels_by_source() -> dict[str, set[str]]:
    supported: dict[str, set[str]] = {}
    for step_id, component in PIPELINE_STEP_COMPONENTS_BY_ID.items():
        labels = {
            str(binding.get("label", "default"))
            for binding in (
                declared_step_route_bindings(step_id) or component.metadata.get("route_bindings", ())
            )
        }
        if labels:
            supported[step_id] = labels
    return supported


def _component_io(items: Sequence[Mapping[str, str]], io_type: type[Input] | type[Output]) -> tuple[Any, ...]:
    values: list[Any] = []
    for item in items:
        kwargs = dict(item)
        values.append(io_type(**kwargs))
    return tuple(values)


def declared_step_interface(step_id: str) -> Mapping[str, Any]:
    component = PIPELINE_STEP_COMPONENTS_BY_ID.get(step_id)
    if component is None:
        return {}
    return workflow_source_compiler._megaplan_step_declared_interface(component)


def declared_handler_binding(step_id: str) -> str | None:
    handler_ref = declared_step_interface(step_id).get("handler_ref")
    return handler_ref if isinstance(handler_ref, str) and handler_ref else None


def declared_step_policy_refs(step_id: str) -> tuple[str, ...]:
    policy_refs = declared_step_interface(step_id).get("policy_refs")
    if isinstance(policy_refs, Sequence) and not isinstance(policy_refs, (str, bytes)):
        return tuple(str(policy_ref) for policy_ref in policy_refs if isinstance(policy_ref, str))
    return ()


def declared_step_capabilities(step_id: str) -> tuple[Capability, ...]:
    raw_capabilities = declared_step_interface(step_id).get("capability_requirements")
    if not isinstance(raw_capabilities, Sequence) or isinstance(raw_capabilities, (str, bytes)):
        return ()
    capabilities: list[Capability] = []
    for raw_capability in raw_capabilities:
        if not isinstance(raw_capability, Mapping):
            continue
        capability_id = raw_capability.get("id")
        route = raw_capability.get("route", "default")
        required = raw_capability.get("required", True)
        if isinstance(capability_id, str) and isinstance(route, str) and isinstance(required, bool):
            capabilities.append(Capability(id=capability_id, route=route, required=required))
    return tuple(capabilities)


def declared_step_route_bindings(step_id: str) -> tuple[Mapping[str, Any], ...]:
    raw_bindings = declared_step_interface(step_id).get("route_bindings")
    if not isinstance(raw_bindings, Sequence) or isinstance(raw_bindings, (str, bytes)):
        return ()
    return tuple(binding for binding in raw_bindings if isinstance(binding, Mapping))


def declared_route_surface(step_id: str) -> Mapping[str, Any]:
    if step_id == "critique":
        route_surface = getattr(workflow_components_module, "CRITIQUE_ROUTE_SURFACE", {})
        return route_surface if isinstance(route_surface, Mapping) else {}
    export_name = _POLICY_ROUTE_SURFACE_EXPORTS_BY_STEP_ID.get(step_id)
    if export_name is None:
        return {}
    return workflow_source_compiler._megaplan_policy_route_surface(export_name)


def declared_workflow_topology_contract(workflow_id: str) -> Mapping[str, Any]:
    export_name = _WORKFLOW_TOPOLOGY_EXPORTS_BY_WORKFLOW_ID.get(workflow_id)
    if export_name is None:
        return {}
    return workflow_source_compiler._megaplan_workflow_topology_contract(export_name)


def declared_fanout_contract(*, step_id: str | None = None, workflow_id: str | None = None) -> Mapping[str, Any]:
    if step_id is not None:
        route_surface = declared_route_surface(step_id)
        fanout_contract = route_surface.get("fanout_contract")
        if isinstance(fanout_contract, Mapping):
            return fanout_contract
    if workflow_id is None:
        return {}
    topology_contract = declared_workflow_topology_contract(workflow_id)
    fanout_contract = topology_contract.get("fanout_contract")
    return fanout_contract if isinstance(fanout_contract, Mapping) else {}


def declared_fan_in_contract(*, step_id: str | None = None, workflow_id: str | None = None) -> Mapping[str, Any]:
    if step_id is not None:
        route_surface = declared_route_surface(step_id)
        fan_in_contract = route_surface.get("fan_in_contract")
        if isinstance(fan_in_contract, Mapping):
            return fan_in_contract
    if workflow_id is None:
        return {}
    topology_contract = declared_workflow_topology_contract(workflow_id)
    fan_in_contract = topology_contract.get("fan_in_contract")
    return fan_in_contract if isinstance(fan_in_contract, Mapping) else {}


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
            idempotency=(
                IdempotencyPolicy(
                    key_ref=effect["idempotency"].get("key_ref"),
                    key_template=effect["idempotency"].get("key_template"),
                    required=bool(effect["idempotency"].get("required", True)),
                )
                if isinstance(effect.get("idempotency"), Mapping)
                else None
            ),
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
    component = PIPELINE_STEP_COMPONENTS_BY_ID[step_id]
    policy = component.policy or DEFAULT_POLICY
    canonical_policy = _policy_from_config(policy.config, timeout_seconds=timeout_seconds)
    route_targets = _canonical_lowered_route_targets_by_source(_lowered_workflow().routes).get(step_id, {})
    transition_labels = _ROUTE_LABEL_BY_TRANSITION_ID.get(step_id, {})
    control_transitions = []
    for transition in canonical_policy.control_transitions:
        target_ref = transition.target_ref
        route_label = transition_labels.get(transition.transition_id)
        if route_label is not None:
            target_ref = route_targets.get(route_label, target_ref)
        trigger_ref = transition.trigger_ref
        if step_id == "tiebreaker_decision" and isinstance(trigger_ref, str):
            trigger_ref = trigger_ref.replace("tiebreaker_decide.", "tiebreaker_decision.")
        control_transitions.append(
            replace(
                transition,
                trigger_ref=trigger_ref,
                target_ref=target_ref,
            )
        )
    if control_transitions == list(canonical_policy.control_transitions):
        return canonical_policy
    return replace(canonical_policy, control_transitions=tuple(control_transitions))


def _metadata_for_step(step_id: str) -> dict[str, Any]:
    component = PIPELINE_STEP_COMPONENTS_BY_ID[step_id]
    declared = declared_step_interface(step_id)
    metadata: dict[str, Any] = {}
    handler_ref = declared.get("handler_ref", component.metadata.get("handler_ref"))
    if isinstance(handler_ref, str):
        metadata["handler_ref"] = handler_ref
    if declared.get("terminal", component.metadata.get("terminal")) is True:
        metadata["terminal"] = True
    if step_id == "revise":
        metadata["max_iterations"] = M4_LOOP_MAX_ITERATIONS
    for key in ("policy_refs", "override_actions"):
        value = declared.get(key, component.metadata.get(key))
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and value:
            metadata[key] = tuple(value)
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


def _canonical_steps(
    *,
    timeout_seconds: float | None,
    lowered_steps: Sequence[Step] = (),
) -> tuple[Step, ...]:
    lowered_by_id = _canonical_lowered_steps(lowered_steps)
    steps = []
    for component in PIPELINE_STEP_COMPONENTS:
        step_id = component.id.removeprefix("megaplan:")
        if step_id not in lowered_by_id:
            continue
        canonical = Step(
            id=step_id,
            kind=component.step_type,
            inputs=_component_io(component.metadata.get("inputs", ()), Input),
            outputs=_component_io(component.metadata.get("outputs", ()), Output),
            policy=_policy_for_step(step_id, timeout_seconds=timeout_seconds),
            metadata=_metadata_for_step(step_id),
        )
        lowered = lowered_by_id.get(step_id)
        if lowered is not None:
            canonical = replace(
                canonical,
                inputs=lowered.inputs or canonical.inputs,
                outputs=lowered.outputs or canonical.outputs,
                source_span=lowered.source_span,
                metadata={**lowered.metadata, **canonical.metadata},
            )
        steps.append(canonical)
    return tuple(steps)

def _canonical_routes(*, lowered_routes: Sequence[Route] = ()) -> tuple[Route, ...]:
    supported_labels = _supported_pipeline_route_labels_by_source()
    return tuple(
        route
        for route in _canonical_lowered_routes(lowered_routes)
        if route.source not in supported_labels
        or route.label in supported_labels[route.source]
    )


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

    lowered = _lowered_workflow()
    return Pipeline(
        id=lowered.id,
        version=lowered.version,
        steps=_canonical_steps(timeout_seconds=timeout_seconds, lowered_steps=lowered.steps),
        routes=_canonical_routes(lowered_routes=lowered.routes),
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


def lowered_workflow_topology() -> dict[str, Any]:
    """Return a source-derived topology view for front-half boundary checks.

    The returned topology captures step IDs and route declarations from
    the lowered workflow source.  Boundary contracts consume this topology
    to correlate durable effects (receipts, findings) with implemented
    source rows, but they do **not** own, alter, or substitute for product
    route topology.  Route selection remains the exclusive province of
    source-level ``Route`` declarations and runtime signal handlers.
    """

    lowered = _lowered_workflow()
    canonical_routes = _topology_lowered_routes(lowered.routes)
    return {
        "workflow_id": lowered.id,
        "workflow_version": lowered.version,
        "source_path": str(AUTHORING_SOURCE_PATH),
        "steps": tuple(step.id for step in _canonical_steps(timeout_seconds=None, lowered_steps=lowered.steps)),
        "step_aliases": _lowered_step_aliases(lowered.steps, step_id_fn=_topology_step_id),
        "routes": tuple(
            {
                "id": route.id,
                "source": route.source,
                "target": route.target,
                "label": route.label,
                "condition_ref": route.condition_ref,
            }
            for route in canonical_routes
        ),
    }


def lowered_route_bindings_by_step(
    *, step_ids: set[str] | frozenset[str] | None = None
) -> dict[str, tuple[dict[str, str | None], ...]]:
    """Group source-derived route bindings by source step id."""

    grouped: dict[str, list[dict[str, str | None]]] = {}
    wanted_step_ids = None if step_ids is None else set(step_ids)
    for route in _topology_lowered_routes(_lowered_workflow().routes):
        if wanted_step_ids is not None and route.source not in wanted_step_ids:
            continue
        grouped.setdefault(route.source, []).append(
            {
                "id": route.id,
                "label": route.label,
                "target_ref": route.target,
                "condition_ref": route.condition_ref,
            }
        )
    return {source: tuple(routes) for source, routes in grouped.items()}


def resolve_lowered_route_target_for_signal(source: str, signal: str) -> str | None:
    """Resolve a source-derived route target for a route signal."""

    for route in _topology_lowered_routes(_lowered_workflow().routes):
        if route.source == source and route.label == signal:
            return route.target
    return None


__all__ = [
    "AUTHORING_SOURCE_PATH",
    "FRONT_HALF_ROUTING_STEP_IDS",
    "PYPELINE_AUTHORING_SOURCE_PATH",
    "WORKFLOW_MODULE_PATH",
    "build_pipeline",
    "lowered_route_bindings_by_step",
    "lowered_workflow_topology",
    "resolve_lowered_route_target_for_signal",
]
