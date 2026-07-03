"""Canonical Megaplan Python-shaped planning workflow source."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold.manifest import (
    ControlTransitionSlot,
    LoopPolicy,
    SuspensionRoute,
    TimingPolicy,
    WorkflowPolicy,
)
from arnold.workflow.authoring import ComponentProvenance, StepComponent
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step
from arnold.workflow.source_compiler import lower_workflow_file
from arnold_pipelines.megaplan.workflows.components import (
    ALL_STEP_COMPONENTS,
    CAPABILITY_REQUIREMENTS,
    DEFAULT_POLICY,
    M4_LOOP_MAX_ITERATIONS,
    REVISE,
    STEP_COMPONENTS_BY_ID,
    TIEBREAKER_DECIDE,
)

AUTHORING_SOURCE_PATH = Path(__file__).with_name("workflow.py")


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
    loop_policy = None
    if "max_iterations" in config or "until_ref" in config:
        loop_policy = LoopPolicy(
            max_iterations=config.get("max_iterations"),
            until_ref=config.get("until_ref"),
        )
    timing = TimingPolicy(timeout_seconds=timeout_seconds) if timeout_seconds is not None else None
    return WorkflowPolicy(
        timing=timing,
        loop=loop_policy,
        suspension_routes=suspension_routes,
        control_transitions=control_transitions,
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
    return metadata


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
        policy=_policy_from_config(DEFAULT_POLICY.config, timeout_seconds=timeout_seconds),
        metadata={
            "product": "megaplan",
            "max_critique_iterations": max_critique_iterations,
        },
    )


__all__ = ["AUTHORING_SOURCE_PATH", "build_pipeline"]
