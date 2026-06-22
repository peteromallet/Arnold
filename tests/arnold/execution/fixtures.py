"""Reusable manifest builders for execution scenario tests.

These builders are plain functions that return compiled ``WorkflowManifest``
instances.  They are intentionally product-neutral and avoid any dynamic
importing or pipeline-specific policy meanings.
"""

from __future__ import annotations

from arnold.manifest import (
    CompensationPolicy,
    CompensationTarget,
    ControlTransitionSlot,
    EffectRef,
    EscalationPolicy,
    FanoutPolicy,
    IdempotencyPolicy,
    LoopPolicy,
    RetryPolicy,
    SubpipelineRef,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
)


def linear_manifest() -> WorkflowManifest:
    """Three-node linear chain: a -> b -> c."""

    return WorkflowManifest(
        id="linear",
        nodes=(
            WorkflowNode(id="a", kind="task"),
            WorkflowNode(id="b", kind="task"),
            WorkflowNode(id="c", kind="task"),
        ),
        edges=(
            WorkflowEdge(id="e1", source="a", target="b"),
            WorkflowEdge(id="e2", source="b", target="c"),
        ),
    )


def branch_manifest() -> WorkflowManifest:
    """Branch node with two conditional targets."""

    return WorkflowManifest(
        id="branch",
        nodes=(
            WorkflowNode(id="gate", kind="branch"),
            WorkflowNode(id="left", kind="task"),
            WorkflowNode(id="right", kind="task"),
        ),
        edges=(
            WorkflowEdge(
                id="e-left", source="gate", target="left", condition_ref="cond-left"
            ),
            WorkflowEdge(
                id="e-right", source="gate", target="right", condition_ref="cond-right"
            ),
        ),
    )


def loop_manifest() -> WorkflowManifest:
    """Bounded loop node."""

    return WorkflowManifest(
        id="loop",
        nodes=(
            WorkflowNode(
                id="loop",
                kind="loop",
                policy=WorkflowPolicy(loop=LoopPolicy(max_iterations=3)),
            ),
        ),
    )


def fanout_manifest() -> WorkflowManifest:
    """Fanout node with a reducer."""

    return WorkflowManifest(
        id="fanout",
        nodes=(
            WorkflowNode(
                id="fan",
                kind="fanout",
                policy=WorkflowPolicy(
                    fanout=FanoutPolicy(width=3, reducer_ref="reducer.concat")
                ),
            ),
        ),
    )


def retry_manifest() -> WorkflowManifest:
    """Retry node with multiple attempts."""

    return WorkflowManifest(
        id="retry",
        nodes=(
            WorkflowNode(
                id="fragile",
                kind="task",
                policy=WorkflowPolicy(retry=RetryPolicy(max_attempts=3)),
            ),
        ),
    )


def subpipeline_manifest(child_hash: str = "sha256:" + "c" * 64) -> WorkflowManifest:
    """Parent node referencing a child manifest by hash."""

    return WorkflowManifest(
        id="subpipeline",
        nodes=(
            WorkflowNode(
                id="parent",
                kind="subpipeline",
                subpipeline=SubpipelineRef(manifest_hash=child_hash, alias="child"),
            ),
        ),
    )


def external_effect_manifest() -> WorkflowManifest:
    """Node that declares an external effect."""

    return WorkflowManifest(
        id="external-effect",
        nodes=(
            WorkflowNode(
                id="fx",
                kind="task",
                policy=WorkflowPolicy(
                    effects=(
                        EffectRef(
                            effect_id="fx.write",
                            idempotency=IdempotencyPolicy(key_ref="fx-write"),
                        ),
                    )
                ),
            ),
        ),
    )


def suspension_manifest() -> WorkflowManifest:
    """Node that suspends, followed by a downstream task."""

    return WorkflowManifest(
        id="suspension",
        nodes=(
            WorkflowNode(
                id="ask",
                kind="human",
            ),
            WorkflowNode(id="after", kind="task"),
        ),
        edges=(WorkflowEdge(id="e1", source="ask", target="after"),),
    )


def replay_manifest() -> WorkflowManifest:
    """Node with an idempotent effect suitable for replay tests."""

    return WorkflowManifest(
        id="replay",
        nodes=(
            WorkflowNode(
                id="idempotent",
                kind="task",
                policy=WorkflowPolicy(
                    idempotency=IdempotencyPolicy(key_ref="node-idem"),
                    effects=(
                        EffectRef(
                            effect_id="fx.idempotent",
                            idempotency=IdempotencyPolicy(key_ref="fx-idem"),
                        ),
                    ),
                ),
            ),
        ),
    )


def control_transition_manifest() -> WorkflowManifest:
    """Node declaring a control transition to an isolated target."""

    return WorkflowManifest(
        id="control-transition",
        nodes=(
            WorkflowNode(
                id="src",
                kind="task",
                policy=WorkflowPolicy(
                    control_transitions=(
                        ControlTransitionSlot(
                            transition_id="ctrl.override",
                            transition_type="override",
                            target_ref="target",
                        ),
                    )
                ),
            ),
            WorkflowNode(id="target", kind="task"),
        ),
    )


def compensation_manifest() -> WorkflowManifest:
    """Linear chain where the final node declares compensation targets."""

    return WorkflowManifest(
        id="compensation",
        nodes=(
            WorkflowNode(id="reserve", kind="task"),
            WorkflowNode(id="charge", kind="task"),
            WorkflowNode(
                id="notify",
                kind="task",
                policy=WorkflowPolicy(
                    compensation=CompensationPolicy(
                        targets=(
                            CompensationTarget(
                                target_id="reserve",
                                effect=EffectRef(
                                    effect_id="fx.release",
                                    idempotency=IdempotencyPolicy(key_ref="release"),
                                ),
                            ),
                        )
                    )
                ),
            ),
        ),
        edges=(
            WorkflowEdge(id="e1", source="reserve", target="charge"),
            WorkflowEdge(id="e2", source="charge", target="notify"),
        ),
    )


def escalation_manifest() -> WorkflowManifest:
    """Retry node with an escalation target."""

    return WorkflowManifest(
        id="escalation",
        nodes=(
            WorkflowNode(
                id="fragile",
                kind="task",
                policy=WorkflowPolicy(
                    retry=RetryPolicy(max_attempts=2),
                    escalation=EscalationPolicy(targets=("escalation_target",)),
                ),
            ),
            WorkflowNode(id="escalation_target", kind="task"),
        ),
    )


__all__ = [
    "branch_manifest",
    "compensation_manifest",
    "control_transition_manifest",
    "escalation_manifest",
    "external_effect_manifest",
    "fanout_manifest",
    "linear_manifest",
    "loop_manifest",
    "replay_manifest",
    "retry_manifest",
    "subpipeline_manifest",
    "suspension_manifest",
]  # type: ignore[unterminated]
