from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

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
    Pipeline,
    ReducerRef,
    Route,
    RuntimeRef,
    Step,
    SubpipelineRef,
    SuspensionRoute,
    TimingPolicy,
    TopologyOverlaySlot,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
    check_workflow_file,
    compile_pipeline,
    SourceSpan,
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
    source_span = SourceSpan("workflow.py", 8, 5, 8, 42)
    manifest = WorkflowManifest(
        id="planning",
        nodes=(
            WorkflowNode(
                "plan",
                "agent",
                source_span=source_span,
                metadata={"nested": {"event_journal": []}},
            ),
        ),
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
    assert _issues_by_code(exc_info.value, "reserved_metadata_key")[0].source_span == source_span
    assert "reserved metadata key: 'event_journal'" in str(exc_info.value)


def test_validation_structures_source_backed_edge_issues() -> None:
    source_span = SourceSpan("workflow.py", 9, 9, 9, 37)
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent"),),
        edges=(
            WorkflowEdge(
                "missing-target",
                "plan",
                "missing",
                source_span=source_span,
            ),
        ),
    )

    with pytest.raises(ManifestValidationError, match="dangling") as exc_info:
        validate_manifest(manifest)

    issue = _issues_by_code(exc_info.value, "dangling_edge_target")[0]
    assert issue.edge_id == "missing-target"
    assert issue.node_id is None
    assert issue.source_span == source_span


def test_validation_keeps_global_invariants_spanless() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("plan", "agent", source_span=SourceSpan("workflow.py", 7)),),
    )
    tampered = replace(manifest, manifest_hash="sha256:" + "0" * 64)

    with pytest.raises(ManifestValidationError, match="manifest_hash") as exc_info:
        validate_manifest(tampered)

    issue = _issues_by_code(exc_info.value, "manifest_hash_mismatch")[0]
    assert issue.node_id is None
    assert issue.edge_id is None
    assert issue.source_span is None


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


def test_runtime_ref_exposes_stable_identity_and_metadata() -> None:
    ref = RuntimeRef(
        node_id="plan",
        output="draft",
        dependencies=("research.note",),
        fallback_route="fallback.draft",
        metadata={"schema_hash": "sha256:" + "a" * 64},
    )

    assert ref.identity == "plan.draft"
    assert ref.node_id == "plan"
    assert ref.output == "draft"
    assert ref.dependencies == ("research.note",)
    assert ref.fallback_route == "fallback.draft"
    assert ref.metadata["schema_hash"] == "sha256:" + "a" * 64


def test_runtime_ref_rejects_python_truthiness() -> None:
    ref = RuntimeRef(node_id="plan", output="draft")

    with pytest.raises(TypeError, match="inert reference"):
        bool(ref)

    with pytest.raises(TypeError, match="inert reference"):
        if ref:  # type: ignore[truthy-bool]
            pass


def test_runtime_ref_rejects_iteration_and_length() -> None:
    ref = RuntimeRef(node_id="plan", output="draft")

    with pytest.raises(TypeError, match="not iterable"):
        iter(ref)

    with pytest.raises(TypeError, match="no length"):
        len(ref)

    with pytest.raises(TypeError, match="not iterable"):
        for _ in ref:  # type: ignore[attr-defined]
            pass


def test_runtime_ref_rejects_arithmetic() -> None:
    ref = RuntimeRef(node_id="plan", output="draft")

    for op in (lambda: ref + 1, lambda: ref - 1, lambda: ref * 2, lambda: ref / 2, lambda: 1 + ref):
        with pytest.raises(TypeError, match="arithmetic"):
            op()

    with pytest.raises(TypeError, match="coerced to a number"):
        int(ref)

    with pytest.raises(TypeError, match="coerced to a number"):
        float(ref)


def test_runtime_ref_rejects_attribute_probing_and_indexing() -> None:
    ref = RuntimeRef(node_id="plan", output="draft")

    with pytest.raises(AttributeError, match="declared"):
        ref.some_attribute  # type: ignore[attr-defined]

    with pytest.raises(TypeError, match="indexing"):
        ref[0]  # type: ignore[index]

    with pytest.raises(TypeError, match="membership"):
        "x" in ref  # type: ignore[operator]


def test_runtime_ref_rejects_mutation() -> None:
    ref = RuntimeRef(node_id="plan", output="draft")

    with pytest.raises(AttributeError):
        ref.node_id = "other"  # type: ignore[misc]


def test_runtime_ref_validates_ref_segments() -> None:
    with pytest.raises(ValueError, match="node_id"):
        RuntimeRef(node_id="", output="draft")

    with pytest.raises(ValueError, match="output"):
        RuntimeRef(node_id="plan", output="bad/output")

    with pytest.raises(ValueError, match="dependency"):
        RuntimeRef(node_id="plan", output="draft", dependencies=("bad dep",))


def test_runtime_ref_metadata_is_frozen_and_json_serializable() -> None:
    ref = RuntimeRef(
        node_id="plan",
        output="draft",
        metadata={"tags": ["seed"]},
    )

    assert ref.metadata["tags"] == ("seed",)
    with pytest.raises(TypeError):
        ref.metadata["tags"] = ("other",)  # type: ignore[index]


_RUNTIME_REF_FIXTURES = (
    "invalid_runtime_truthiness",
    "invalid_runtime_iteration",
    "invalid_runtime_arithmetic",
    "invalid_runtime_attribute",
)


def _diagnostic_payload(diagnostic) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": diagnostic.code.value,
        "message": diagnostic.message,
    }
    if diagnostic.source_span is not None:
        payload["source_span"] = {
            "start_line": diagnostic.source_span.start_line,
            "start_column": diagnostic.source_span.start_column,
            "end_line": diagnostic.source_span.end_line,
            "end_column": diagnostic.source_span.end_column,
        }
    return payload


def _load_runtime_ref_expected(fixture_name: str) -> dict:
    path = Path(f"tests/fixtures/workflow_authoring/{fixture_name}.expected.json")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture_name", _RUNTIME_REF_FIXTURES)
def test_runtime_ref_rejection_fixtures_pin_source_diagnostics(fixture_name: str) -> None:
    expected = _load_runtime_ref_expected(fixture_name)
    source_path = Path(f"tests/fixtures/workflow_authoring/{fixture_name}.py")

    result = check_workflow_file(source_path)

    assert result.diagnostics
    assert expected["outcome"] == "invalid"
    actual = [_diagnostic_payload(diag) for diag in result.diagnostics]
    assert actual == expected["expected_diagnostics"]


def test_loop_and_retry_control_patterns_validate_as_bounded_reentry() -> None:
    import arnold.patterns as patterns

    pipeline = Pipeline(
        id="control",
        version="v1",
        steps=[
            Step(id="fragile", kind="agent"),
            Step(id="body", kind="agent"),
        ],
        routes=[Route(id="loop-body", source="loop", target="body", label="go")],
    )
    blocks = (
        patterns.loop(
            "loop",
            "body",
            until_ref="tests.arnold.patterns._fixtures:decide_condition",
            max_iterations=3,
            reentry_id="retry",
        ),
        patterns.retry("retry", target_id="fragile", max_attempts=3),
    )

    manifest = compile_pipeline(pipeline, patterns=blocks)

    validate_manifest(manifest)
    assert any(edge.condition_ref == "retry" for edge in manifest.edges)
    assert any(edge.condition_ref == "retry:retry" for edge in manifest.edges)


def test_human_gate_compiles_to_valid_suspension_node() -> None:
    import arnold.patterns as patterns

    gate = patterns.human_gate("gate", capability_id="human:operator", reentry_id="resume")
    manifest = compile_pipeline(Pipeline(id="gate", version="v1", steps=[gate]))

    validate_manifest(manifest)
    node = next(node for node in manifest.nodes if node.id == "gate")
    assert node.kind == "suspension"
    assert node.policy is not None
    assert node.policy.suspension_routes[0].reentry_id == "resume"
