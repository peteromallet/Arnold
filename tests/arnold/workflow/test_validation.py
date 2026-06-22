from __future__ import annotations

from dataclasses import replace

import pytest

from arnold.workflow import (
    AuthorityRequirement,
    CompensationPolicy,
    CompensationTarget,
    ControlTransitionSlot,
    EffectRef,
    EscalationPolicy,
    IdempotencyPolicy,
    LoopPolicy,
    ManifestValidationError,
    ReducerRef,
    SubpipelineRef,
    SuspensionRoute,
    TimingPolicy,
    TopologyOverlaySlot,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
    validate_manifest,
)


def test_validation_rejects_dangling_edges() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"),),
        edges=(WorkflowEdge("dangling", "plan", "missing"),),
    )

    with pytest.raises(ManifestValidationError, match="dangling"):
        validate_manifest(manifest)


def test_validation_rejects_reserved_runtime_slots() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent", metadata={"runtime_state": {}}),),
    )

    with pytest.raises(ManifestValidationError, match="reserved metadata"):
        validate_manifest(manifest)


def test_validation_rejects_hash_mismatch() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"),),
    )
    tampered = replace(manifest, manifest_hash="sha256:" + "0" * 64)

    with pytest.raises(ManifestValidationError, match="manifest_hash"):
        validate_manifest(tampered)


def test_validation_rejects_bad_id_and_ref_formats() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("bad id", "agent", outputs=("draft/out",)),),
    )

    with pytest.raises(ManifestValidationError, match="invalid ref format"):
        validate_manifest(manifest)


def test_validation_rejects_non_json_metadata() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent", metadata={"labels": ("draft",)}),),
    )

    with pytest.raises(ManifestValidationError, match="non-JSON-serializable"):
        validate_manifest(manifest)


def test_validation_rejects_reserved_runtime_metadata_recursively() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent", metadata={"nested": {"event_journal": []}}),),
    )

    with pytest.raises(ManifestValidationError, match="reserved metadata key"):
        validate_manifest(manifest)


def test_validation_rejects_bad_subpipeline_hash() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent", subpipeline=SubpipelineRef("not-a-hash")),),
    )

    with pytest.raises(ManifestValidationError, match="subpipeline manifest_hash"):
        validate_manifest(manifest)


def test_validation_rejects_arbitrary_cycles() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"), WorkflowNode("revise", "agent")),
        edges=(
            WorkflowEdge("plan-revise", "plan", "revise"),
            WorkflowEdge("revise-plan", "revise", "plan"),
        ),
    )

    with pytest.raises(ManifestValidationError, match="arbitrary graph cycles"):
        validate_manifest(manifest)


def test_validation_accepts_explicit_bounded_reentry_cycle() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(
            WorkflowNode("plan", "agent"),
            WorkflowNode(
                "revise",
                "agent",
                policy=WorkflowPolicy(
                    loop=LoopPolicy(max_iterations=3),
                    suspension_routes=(
                        SuspensionRoute(route_id="revise-loop", reentry_id="retry-plan"),
                    ),
                ),
            ),
        ),
        edges=(
            WorkflowEdge("plan-revise", "plan", "revise"),
            WorkflowEdge("revise-plan", "revise", "plan", condition_ref="retry-plan"),
        ),
    )

    validate_manifest(manifest)


def test_validation_accepts_m3_runtime_reserved_policy_slots() -> None:
    schema_hash = "sha256:" + "b" * 64
    manifest = WorkflowManifest(
        id="runtime-slots",
        nodes=(
            WorkflowNode(
                "execute",
                "effect",
                policy=WorkflowPolicy(
                    timing=TimingPolicy(timeout_seconds=10, deadline_ref="run.deadline", ttl_seconds=60),
                    idempotency=IdempotencyPolicy(key_ref="execute.key"),
                    effects=(
                        EffectRef(
                            "external.write",
                            payload_ref="execute.payload",
                            payload_schema_hash=schema_hash,
                            idempotency=IdempotencyPolicy(key_template="write.key"),
                        ),
                    ),
                    reducers=(ReducerRef("fanout.reducer", input_ref="fanout.children"),),
                    compensation=CompensationPolicy(
                        targets=(CompensationTarget("undo", EffectRef("external.undo")),),
                        trigger_on=("node.failed",),
                    ),
                    escalation=EscalationPolicy(targets=("operator",), escalate_after_attempts=2),
                    control_transitions=(
                        ControlTransitionSlot(
                            "override",
                            "override",
                            trigger_ref="operator.signal",
                            payload_schema_hash=schema_hash,
                        ),
                    ),
                    topology_overlays=(
                        TopologyOverlaySlot(
                            "overlay",
                            "dynamic",
                            source_ref="execute",
                            target_refs=("review",),
                            payload_schema_hash=schema_hash,
                        ),
                    ),
                    authority=(
                        AuthorityRequirement(
                            "execute-authority",
                            "complete",
                            evidence_schema_hash=schema_hash,
                        ),
                    ),
                    suspension_routes=(
                        SuspensionRoute(
                            "resume",
                            reentry_id="resume-execute",
                            resume_schema_hash=schema_hash,
                            resume_schema_ref="resume.schema",
                        ),
                    ),
                ),
            ),
            WorkflowNode("review", "agent"),
        ),
        edges=(WorkflowEdge("execute-review", "execute", "review"),),
    )

    validate_manifest(manifest)


def test_validation_rejects_bad_m3_runtime_reserved_policy_slots() -> None:
    manifest = WorkflowManifest(
        id="runtime-slots",
        nodes=(
            WorkflowNode(
                "execute",
                "effect",
                policy=WorkflowPolicy(
                    timing=TimingPolicy(timeout_seconds=0, ttl_seconds=-1),
                    effects=(
                        EffectRef("external.write", payload_schema_hash="not-a-hash"),
                        EffectRef("external.write"),
                    ),
                    reducers=(ReducerRef("fanout.reducer"), ReducerRef("fanout.reducer")),
                    compensation=CompensationPolicy(
                        targets=(
                            CompensationTarget("undo", EffectRef("external.undo")),
                            CompensationTarget("undo", EffectRef("external.undo.again")),
                        ),
                    ),
                    escalation=EscalationPolicy(),
                    control_transitions=(
                        ControlTransitionSlot("override", "fallback"),
                        ControlTransitionSlot("override", "fallback"),
                    ),
                    topology_overlays=(
                        TopologyOverlaySlot("overlay", "dynamic"),
                        TopologyOverlaySlot("overlay", "dynamic"),
                    ),
                    authority=(
                        AuthorityRequirement("execute-authority", "complete"),
                        AuthorityRequirement("execute-authority", "complete"),
                    ),
                    suspension_routes=(
                        SuspensionRoute("resume", resume_schema_hash="not-a-hash"),
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(ManifestValidationError) as exc_info:
        validate_manifest(manifest)

    message = str(exc_info.value)
    assert "timeout_seconds" in message
    assert "payload_schema_hash" in message
    assert "effect_id 'external.write' is duplicated" in message
    assert "reducer_id 'fanout.reducer' is duplicated" in message
    assert "target_id 'undo' is duplicated" in message
    assert "escalation.targets must include at least one target" in message
    assert "transition_id 'override' is duplicated" in message
    assert "overlay_id 'overlay' is duplicated" in message
    assert "authority/action pair 'execute-authority'/'complete' is duplicated" in message
    assert "resume_schema_hash" in message
