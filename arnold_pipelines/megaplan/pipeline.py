"""Canonical Megaplan planning pipeline.

This module exposes two helpers:

* ``build_pipeline()`` — returns the M3 explicit-node
  :class:`arnold.workflow.dsl.Pipeline`, the canonical authoring surface
  for the manifest runtime.
* ``build_and_compile_pipeline()`` — convenience helper that builds the M3
  pipeline via ``build_pipeline()`` and compiles it to a
  ``WorkflowManifest`` via :func:`arnold.workflow.compiler.compile_pipeline`.

The pipeline is a pure data graph: steps, routes, and policy slots.
Execution semantics live in the manifest backend adapter and the handlers.
"""

from __future__ import annotations

from typing import Any

from arnold.manifest import WorkflowPolicy
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


# ---------------------------------------------------------------------------
# M3 explicit-node pipeline constructor (Phase 3)
# ---------------------------------------------------------------------------

def _node_policy(
    *,
    timeout_seconds: float | None = None,
    max_attempts: int | None = None,
    suspension_routes: list[dict[str, Any]] | None = None,
    control_transitions: list[dict[str, Any]] | None = None,
    topology_overlays: list[dict[str, Any]] | None = None,
    loop: dict[str, Any] | None = None,
) -> WorkflowPolicy:
    """Build a minimal workflow policy for a node."""

    from arnold.manifest import (
        ControlTransitionSlot,
        IdempotencyPolicy,
        LoopPolicy,
        SuspensionRoute,
        TimingPolicy,
        TopologyOverlaySlot,
    )

    policy_kwargs: dict[str, Any] = {}
    if timeout_seconds is not None or max_attempts is not None:
        policy_kwargs["timing"] = TimingPolicy(
            timeout_seconds=timeout_seconds,
        )
    if max_attempts is not None:
        policy_kwargs["retry"] = IdempotencyPolicy(
            key_ref="attempt",
            key_template="{run_id}:{node_ref}:attempt:{attempt}",
            required=True,
        )
    if loop is not None:
        policy_kwargs["loop"] = LoopPolicy(
            max_iterations=loop.get("max_iterations"),
            until_ref=loop.get("until_ref"),
        )
    if suspension_routes:
        policy_kwargs["suspension_routes"] = tuple(
            SuspensionRoute(
                route_id=route["route_id"],
                capability_id=route.get("capability_id"),
                reentry_id=route.get("reentry_id"),
            )
            for route in suspension_routes
        )
    if control_transitions:
        policy_kwargs["control_transitions"] = tuple(
            ControlTransitionSlot(
                transition_id=ct["transition_id"],
                transition_type=ct["transition_type"],
                trigger_ref=ct.get("trigger_ref"),
                target_ref=ct.get("target_ref"),
                policy_ref=ct.get("policy_ref"),
            )
            for ct in control_transitions
        )
    if topology_overlays:
        policy_kwargs["topology_overlays"] = tuple(
            TopologyOverlaySlot(
                overlay_id=ov["overlay_id"],
                overlay_type=ov["overlay_type"],
                source_ref=ov.get("source_ref"),
                target_refs=tuple(ov.get("target_refs", [])),
                condition_ref=ov.get("condition_ref"),
            )
            for ov in topology_overlays
        )
    return WorkflowPolicy(**policy_kwargs)


def build_pipeline(
    *,
    timeout_seconds: float | None = 300.0,
    max_critique_iterations: int = 4,
) -> Pipeline:
    """Return the canonical Megaplan pipeline as an M3 explicit-node DSL graph.

    Steps::

        prep -> plan -> critique -> gate
                                  |-- proceed -> finalize -> execute -> review -> halt
                                  |-- iterate -> revise -> critique  (loop)
                                  |-- tiebreaker -> tiebreaker_run -> tiebreaker_decide -> critique
                                  |-- escalate / abort / suspend / force-proceed -> override

    All branch labels are stable strings resolved by the manifest backend and by
    control-transition handlers.  The returned :class:`Pipeline` can be compiled
    with :func:`arnold.workflow.compiler.compile_pipeline`.
    """

    common_policy = _node_policy(timeout_seconds=timeout_seconds)

    prep = Step(
        id="prep",
        kind="megaplan:prep",
        outputs=(Output(name="prep_payload"),),
        policy=common_policy,
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_prep"},
    )
    plan = Step(
        id="plan",
        kind="megaplan:plan",
        inputs=(Input(name="prep_payload", value_ref="prep.prep_payload"),),
        outputs=(Output(name="plan_payload"),),
        policy=common_policy,
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_plan"},
    )
    critique = Step(
        id="critique",
        kind="megaplan:critique",
        inputs=(Input(name="plan_payload", value_ref="plan.plan_payload"),),
        outputs=(Output(name="critique_payload"),),
        policy=common_policy,
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_critique"},
    )
    gate = Step(
        id="gate",
        kind="megaplan:gate",
        inputs=(Input(name="critique_payload", value_ref="critique.critique_payload"),),
        outputs=(Output(name="gate_payload"), Output(name="recommendation")),
        policy=_node_policy(
            timeout_seconds=timeout_seconds,
            control_transitions=[
                {
                    "transition_id": "gate:proceed",
                    "transition_type": "override",
                    "trigger_ref": "gate.recommendation",
                    "target_ref": "finalize",
                    "policy_ref": "megaplan:gate",
                },
                {
                    "transition_id": "gate:iterate",
                    "transition_type": "override",
                    "trigger_ref": "gate.recommendation",
                    "target_ref": "revise",
                    "policy_ref": "megaplan:gate",
                },
                {
                    "transition_id": "gate:tiebreaker",
                    "transition_type": "override",
                    "trigger_ref": "gate.recommendation",
                    "target_ref": "tiebreaker_run",
                    "policy_ref": "megaplan:gate",
                },
                {
                    "transition_id": "gate:escalate",
                    "transition_type": "escalation",
                    "trigger_ref": "gate.recommendation",
                    "target_ref": "override",
                    "policy_ref": "megaplan:gate",
                },
                {
                    "transition_id": "gate:abort",
                    "transition_type": "override",
                    "trigger_ref": "gate.recommendation",
                    "target_ref": "halt",
                    "policy_ref": "megaplan:gate",
                },
            ],
            suspension_routes=[
                {"route_id": "gate:human", "capability_id": "human:gate"},
            ],
        ),
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_gate"},
    )
    revise = Step(
        id="revise",
        kind="megaplan:revise",
        inputs=(Input(name="gate_payload", value_ref="gate.gate_payload"),),
        outputs=(Output(name="revise_payload"),),
        policy=_node_policy(
            timeout_seconds=timeout_seconds,
            loop={"max_iterations": max_critique_iterations, "until_ref": "critique_gate_pass"},
            suspension_routes=[
                {"route_id": "revise:loop", "reentry_id": "revise:loop", "capability_id": "megaplan:planning"},
            ],
        ),
        metadata={
            "handler_ref": "arnold_pipelines.megaplan.handlers:handle_revise",
            "max_iterations": max_critique_iterations,
        },
    )
    tiebreaker_run = Step(
        id="tiebreaker_run",
        kind="megaplan:tiebreaker_run",
        inputs=(Input(name="gate_payload", value_ref="gate.gate_payload"),),
        outputs=(Output(name="tiebreaker_payload"),),
        policy=common_policy,
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_tiebreaker_run"},
    )
    tiebreaker_decide = Step(
        id="tiebreaker_decide",
        kind="megaplan:tiebreaker_decide",
        inputs=(Input(name="tiebreaker_payload", value_ref="tiebreaker_run.tiebreaker_payload"),),
        outputs=(Output(name="decision"),),
        policy=_node_policy(
            timeout_seconds=timeout_seconds,
            loop={"max_iterations": max_critique_iterations, "until_ref": "tiebreaker_resolved"},
            suspension_routes=[
                {"route_id": "tiebreaker:loop", "reentry_id": "tiebreaker:loop", "capability_id": "megaplan:planning"},
            ],
            control_transitions=[
                {
                    "transition_id": "tiebreaker:iterate",
                    "transition_type": "override",
                    "trigger_ref": "tiebreaker_decide.decision",
                    "target_ref": "critique",
                    "policy_ref": "megaplan:tiebreaker",
                },
                {
                    "transition_id": "tiebreaker:proceed",
                    "transition_type": "override",
                    "trigger_ref": "tiebreaker_decide.decision",
                    "target_ref": "finalize",
                    "policy_ref": "megaplan:tiebreaker",
                },
                {
                    "transition_id": "tiebreaker:escalate",
                    "transition_type": "escalation",
                    "trigger_ref": "tiebreaker_decide.decision",
                    "target_ref": "override",
                    "policy_ref": "megaplan:tiebreaker",
                },
            ],
        ),
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_tiebreaker_decide"},
    )
    finalize = Step(
        id="finalize",
        kind="megaplan:finalize",
        inputs=(Input(name="gate_payload", value_ref="gate.gate_payload"),),
        outputs=(Output(name="finalize_payload"),),
        policy=common_policy,
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_finalize"},
    )
    execute = Step(
        id="execute",
        kind="megaplan:execute",
        inputs=(Input(name="finalize_payload", value_ref="finalize.finalize_payload"),),
        outputs=(Output(name="execute_payload"),),
        policy=common_policy,
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_execute"},
    )
    review = Step(
        id="review",
        kind="megaplan:review",
        inputs=(Input(name="execute_payload", value_ref="execute.execute_payload"),),
        outputs=(Output(name="review_payload"),),
        policy=_node_policy(
            timeout_seconds=timeout_seconds,
            suspension_routes=[
                {"route_id": "review:human", "capability_id": "human:review"},
            ],
            control_transitions=[
                {
                    "transition_id": "review:rework",
                    "transition_type": "fallback",
                    "trigger_ref": "review.verdict",
                    "target_ref": "revise",
                    "policy_ref": "megaplan:review",
                },
                {
                    "transition_id": "review:done",
                    "transition_type": "override",
                    "trigger_ref": "review.verdict",
                    "target_ref": "halt",
                    "policy_ref": "megaplan:review",
                },
            ],
        ),
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_review"},
    )
    halt = Step(
        id="halt",
        kind="megaplan:halt",
        outputs=(Output(name="status"),),
        policy=common_policy,
        metadata={"terminal": True},
    )
    override = Step(
        id="override",
        kind="megaplan:override",
        inputs=(Input(name="gate_payload", value_ref="gate.gate_payload"),),
        outputs=(Output(name="override_result"),),
        policy=common_policy,
        metadata={"handler_ref": "arnold_pipelines.megaplan.handlers:handle_override"},
    )

    routes = (
        Route(id="prep:plan", source="prep", target="plan", label="default"),
        Route(id="plan:critique", source="plan", target="critique", label="default"),
        Route(id="critique:gate", source="critique", target="gate", label="default"),
        # Gate branches
        Route(id="gate:finalize", source="gate", target="finalize", label="proceed", condition_ref="proceed"),
        Route(id="gate:revise", source="gate", target="revise", label="iterate", condition_ref="iterate"),
        Route(id="gate:tiebreaker", source="gate", target="tiebreaker_run", label="tiebreaker", condition_ref="tiebreaker"),
        Route(id="gate:override", source="gate", target="override", label="escalate", condition_ref="escalate"),
        Route(id="gate:halt", source="gate", target="halt", label="abort", condition_ref="abort"),
        Route(id="gate:suspend", source="gate", target="halt", label="suspend", condition_ref="suspend"),
        Route(id="gate:blocked", source="gate", target="override", label="blocked_preflight", condition_ref="blocked"),
        Route(id="gate:force_proceed", source="gate", target="finalize", label="force_proceed", condition_ref="force_proceed"),
        # Revise loop
        Route(id="revise:critique", source="revise", target="critique", label="default", condition_ref="revise:loop"),
        # Tiebreaker
        Route(id="tiebreaker_run:decide", source="tiebreaker_run", target="tiebreaker_decide", label="default"),
        Route(id="tiebreaker_decide:critique", source="tiebreaker_decide", target="critique", label="iterate", condition_ref="tiebreaker:loop"),
        Route(id="tiebreaker_decide:finalize", source="tiebreaker_decide", target="finalize", label="proceed", condition_ref="proceed"),
        Route(id="tiebreaker_decide:override", source="tiebreaker_decide", target="override", label="escalate", condition_ref="escalate"),
        # Forward path
        Route(id="finalize:execute", source="finalize", target="execute", label="default"),
        Route(id="execute:review", source="execute", target="review", label="default"),
        Route(id="review:halt", source="review", target="halt", label="default", condition_ref="pass"),
        Route(id="review:revise", source="review", target="revise", label="rework", condition_ref="rework"),
        # Override can abort or force-proceed
        Route(id="override:halt", source="override", target="halt", label="abort", condition_ref="abort"),
        Route(id="override:finalize", source="override", target="finalize", label="force_proceed", condition_ref="force_proceed"),
        Route(id="override:revise", source="override", target="revise", label="replan", condition_ref="replan"),
    )

    pipeline = Pipeline(
        id="megaplan",
        version="m4-phase3",
        steps=(
            prep,
            plan,
            critique,
            gate,
            revise,
            tiebreaker_run,
            tiebreaker_decide,
            finalize,
            execute,
            review,
            halt,
            override,
        ),
        routes=routes,
        capabilities=(
            Capability(id="megaplan:planning", route="default", required=True),
            Capability(id="human:gate", route="default", required=False),
            Capability(id="human:review", route="default", required=False),
        ),
        policy=_node_policy(timeout_seconds=timeout_seconds),
        metadata={
            "product": "megaplan",
            "max_critique_iterations": max_critique_iterations,
        },
    )
    return pipeline


def build_and_compile_pipeline(**kwargs: Any) -> Any:
    """Build the M3 pipeline and compile it to a ``WorkflowManifest``."""
    return compile_pipeline(build_pipeline(**kwargs))


__all__ = [
    "build_and_compile_pipeline",
    "build_pipeline",
]
