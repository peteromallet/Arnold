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


def _issues_by_code(exc: ManifestValidationError, code: str):
    return [issue for issue in exc.issues if issue.code == code]


def _assert_issue(
    exc: ManifestValidationError,
    *,
    code: str,
    message_contains: str,
    field: str,
    node_id: str | None = None,
    edge_id: str | None = None,
) -> None:
    matches = _issues_by_code(exc, code)
    assert matches, exc.issues
    issue = matches[0]
    assert message_contains in issue.message
    assert issue.field == field
    assert issue.node_id == node_id
    assert issue.edge_id == edge_id


def test_validation_structures_duplicate_node_id_issues_and_preserves_message() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"), WorkflowNode("plan", "effect")),
    )

    with pytest.raises(ManifestValidationError, match="node ids must be unique") as exc_info:
        validate_manifest(manifest)

    _assert_issue(
        exc_info.value,
        code="duplicate_node_id",
        message_contains="node ids must be unique",
        field="nodes[].id",
        node_id="plan",
    )
    assert "node ids must be unique" in str(exc_info.value)


def test_validation_structures_dangling_route_issues_and_preserves_message() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"),),
        edges=(
            WorkflowEdge("missing-source", "missing", "plan"),
            WorkflowEdge("missing-target", "plan", "missing"),
        ),
    )

    with pytest.raises(ManifestValidationError, match="dangling") as exc_info:
        validate_manifest(manifest)

    _assert_issue(
        exc_info.value,
        code="dangling_edge_source",
        message_contains="source 'missing' is dangling",
        field="edges[].source",
        edge_id="missing-source",
    )
    _assert_issue(
        exc_info.value,
        code="dangling_edge_target",
        message_contains="target 'missing' is dangling",
        field="edges[].target",
        edge_id="missing-target",
    )
    assert "edge 'missing-source' source 'missing' is dangling" in str(exc_info.value)
    assert "edge 'missing-target' target 'missing' is dangling" in str(exc_info.value)


def test_validation_structures_invalid_node_field_issues_and_preserves_message() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("bad id", "agent", outputs=("draft/out",)),),
    )

    with pytest.raises(ManifestValidationError, match="invalid ref format") as exc_info:
        validate_manifest(manifest)

    _assert_issue(
        exc_info.value,
        code="invalid_node_id",
        message_contains="node id has invalid ref format",
        field="nodes[].id",
        node_id="bad id",
    )
    _assert_issue(
        exc_info.value,
        code="invalid_node_output",
        message_contains="output has invalid ref format",
        field="nodes[].outputs[]",
        node_id="bad id",
    )
    assert "node id has invalid ref format: 'bad id'" in str(exc_info.value)
    assert "node 'bad id' output has invalid ref format: 'draft/out'" in str(exc_info.value)


def test_validation_structures_reserved_metadata_issues_and_preserves_message() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent", metadata={"nested": {"event_journal": []}}),),
    )

    with pytest.raises(ManifestValidationError, match="reserved metadata key") as exc_info:
        validate_manifest(manifest)

    _assert_issue(
        exc_info.value,
        code="reserved_metadata_key",
        message_contains="reserved metadata key: 'event_journal'",
        field="nodes[].metadata.nested.event_journal",
        node_id="plan",
    )
    assert "reserved metadata key: 'event_journal'" in str(exc_info.value)


def test_validation_structures_hash_and_canonical_json_failures() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"),),
    )
    tampered = replace(
        manifest,
        topology_hash="sha256:" + "0" * 64,
        manifest_hash="sha256:" + "1" * 64,
    )

    with pytest.raises(ManifestValidationError, match="canonical") as exc_info:
        object.__setattr__(tampered, "to_json", lambda: '{"schema_version":"not-canonical"}')
        validate_manifest(tampered)

    _assert_issue(
        exc_info.value,
        code="topology_hash_mismatch",
        message_contains="topology_hash does not match canonical topology",
        field="topology_hash",
    )
    _assert_issue(
        exc_info.value,
        code="manifest_hash_mismatch",
        message_contains="manifest_hash does not match canonical manifest",
        field="manifest_hash",
    )
    _assert_issue(
        exc_info.value,
        code="manifest_json_not_canonical",
        message_contains="manifest JSON is not canonical",
        field="manifest",
    )
    assert "topology_hash does not match canonical topology" in str(exc_info.value)
    assert "manifest_hash does not match canonical manifest" in str(exc_info.value)
    assert "manifest JSON is not canonical" in str(exc_info.value)


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
