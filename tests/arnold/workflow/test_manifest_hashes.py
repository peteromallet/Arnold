from __future__ import annotations

from dataclasses import replace

from arnold.workflow import (
    ControlTransitionSlot,
    EffectRef,
    IdempotencyPolicy,
    TopologyOverlaySlot,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
)


def test_manifest_hash_excludes_hash_fields() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"),),
    )
    with_explicit_hashes = replace(
        manifest,
        manifest_hash=manifest.manifest_hash,
        topology_hash=manifest.topology_hash,
    )

    assert with_explicit_hashes.manifest_hash == manifest.manifest_hash


def test_topology_hash_ignores_non_topology_metadata_but_manifest_hash_changes() -> None:
    base = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent", metadata={"label": "old"}),),
    )
    changed_metadata = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent", metadata={"label": "new"}),),
    )
    changed_topology = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"), WorkflowNode("review", "agent")),
        edges=(WorkflowEdge("plan-review", "plan", "review"),),
    )

    assert base.topology_hash == changed_metadata.topology_hash
    assert base.manifest_hash != changed_metadata.manifest_hash
    assert base.topology_hash != changed_topology.topology_hash


def test_runtime_reserved_policy_slots_affect_manifest_hash_not_topology_hash() -> None:
    base = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"),),
    )
    changed_policy = WorkflowManifest(
        id="planning",
        nodes=(
            WorkflowNode(
                "plan",
                "agent",
                policy=WorkflowPolicy(effects=(EffectRef("artifact.write"),)),
            ),
        ),
    )

    assert base.topology_hash == changed_policy.topology_hash
    assert base.manifest_hash != changed_policy.manifest_hash


def test_control_transition_and_overlay_slots_are_manifest_hash_inputs_not_topology() -> None:
    base = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"), WorkflowNode("review", "agent")),
        edges=(WorkflowEdge("plan-review", "plan", "review"),),
    )
    with_control_slots = WorkflowManifest(
        id="planning",
        nodes=(
            WorkflowNode(
                "plan",
                "agent",
                policy=WorkflowPolicy(
                    control_transitions=(
                        ControlTransitionSlot(
                            "fallback",
                            "fallback",
                            trigger_ref="plan.failed",
                            target_ref="review",
                            payload_schema_hash="sha256:" + "a" * 64,
                            policy_ref="policy:fallback",
                            idempotency=IdempotencyPolicy(key_template="fallback:{run_id}"),
                        ),
                    ),
                    topology_overlays=(
                        TopologyOverlaySlot(
                            "dynamic-review",
                            "dynamic",
                            source_ref="plan",
                            target_refs=("review",),
                            condition_ref="condition:needs-review",
                            payload_schema_hash="sha256:" + "b" * 64,
                        ),
                    ),
                ),
            ),
            WorkflowNode("review", "agent"),
        ),
        edges=(WorkflowEdge("plan-review", "plan", "review"),),
    )

    assert base.topology_hash == with_control_slots.topology_hash
    assert base.manifest_hash != with_control_slots.manifest_hash


def test_inspect_hash_inputs_match_manifest_identity() -> None:
    from arnold.workflow import compile_pipeline, inspect_manifest
    from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step

    pipeline = Pipeline(
        id="planning",
        version="v1",
        steps=(
            Step(
                id="plan",
                kind="agent",
                outputs=(Output("draft"),),
                capabilities=(Capability("agent:planner"),),
            ),
            Step(
                id="review",
                kind="agent",
                inputs=(Input("draft", value_ref="plan.draft"), Input("criteria")),
            ),
        ),
        routes=(Route(id="plan-review", source="plan", target="review", label="review"),),
    )
    manifest = compile_pipeline(pipeline)
    view = inspect_manifest(manifest)

    assert view["hash_inputs"]["id"] == manifest.id
    assert view["hash_inputs"]["schema_version"] == manifest.schema_version
    assert view["hash_inputs"]["version"] == manifest.version
    assert view["hash_inputs"]["topology_hash"] == manifest.topology_hash
    assert view["hash_inputs"]["manifest_hash"] == manifest.manifest_hash
    assert view["hash_inputs"]["manifest_hash"].startswith("sha256:")
