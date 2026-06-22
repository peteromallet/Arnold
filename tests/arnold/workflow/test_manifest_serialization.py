from __future__ import annotations

from arnold.workflow import (
    AuthorityRequirement,
    BudgetPolicy,
    CapabilityRequirement,
    CompensationPolicy,
    CompensationTarget,
    ControlTransitionSlot,
    EffectRef,
    EscalationPolicy,
    IdempotencyPolicy,
    ReducerRef,
    RetryPolicy,
    SourceSpan,
    SuspensionRoute,
    TimingPolicy,
    TopologyOverlaySlot,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
    validate_manifest,
)


def test_workflow_manifest_round_trips_canonical_json() -> None:
    manifest = WorkflowManifest(
        id="planning",
        nodes=(
            WorkflowNode(
                id="finalize",
                kind="agent",
                capabilities=(CapabilityRequirement("artifact:write"),),
                policy=WorkflowPolicy(
                    budget=BudgetPolicy(max_seconds=60),
                    retry=RetryPolicy(max_attempts=2, retry_on=("transient",)),
                    suspension_routes=(
                        SuspensionRoute(
                            route_id="operator",
                            capability_id="human:review",
                            reentry_id="resume-finalize",
                        ),
                    ),
                ),
                source_span=SourceSpan("pipeline.py", 10),
            ),
            WorkflowNode(id="plan", kind="agent", outputs=("draft",)),
        ),
        edges=(WorkflowEdge(id="plan-finalize", source="plan", target="finalize"),),
        version="authoring-v1",
    )

    restored = WorkflowManifest.from_json(manifest.to_json())

    assert restored == manifest
    assert manifest.to_json() == restored.to_json()
    validate_manifest(restored)


def test_manifest_constructor_sorts_nodes_and_edges_for_stable_serialization() -> None:
    first = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("b", "agent"), WorkflowNode("a", "agent")),
        edges=(WorkflowEdge("b-a", "b", "a"),),
    )
    second = WorkflowManifest(
        id="planning",
        nodes=(WorkflowNode("a", "agent"), WorkflowNode("b", "agent")),
        edges=(WorkflowEdge("b-a", "b", "a"),),
    )

    assert first.to_json() == second.to_json()
    assert first.manifest_hash == second.manifest_hash


def test_manifest_round_trips_m3_runtime_reserved_fields() -> None:
    schema_hash = "sha256:" + "a" * 64
    effect = EffectRef(
        effect_id="artifact.write",
        payload_ref="artifact.payload",
        payload_schema_hash=schema_hash,
        idempotency=IdempotencyPolicy(key_ref="effect.key"),
    )
    manifest = WorkflowManifest(
        id="runtime-slots",
        nodes=(
            WorkflowNode(
                id="execute",
                kind="effect",
                policy=WorkflowPolicy(
                    timing=TimingPolicy(timeout_seconds=30, deadline_ref="run.deadline", ttl_seconds=300),
                    idempotency=IdempotencyPolicy(key_template="run:execute"),
                    effects=(effect,),
                    reducers=(ReducerRef("panel.reducer", input_ref="panel.outputs", output_ref="summary"),),
                    compensation=CompensationPolicy(
                        targets=(
                            CompensationTarget(
                                target_id="undo-write",
                                effect=EffectRef("artifact.delete", idempotency=IdempotencyPolicy("undo.key")),
                            ),
                        ),
                        scope_ref="execute.scope",
                        trigger_on=("node.failed",),
                    ),
                    escalation=EscalationPolicy(
                        targets=("operator",),
                        escalate_after_attempts=2,
                        policy_ref="escalation.policy",
                    ),
                    control_transitions=(
                        ControlTransitionSlot(
                            transition_id="fallback",
                            transition_type="fallback",
                            trigger_ref="execute.failed",
                            target_ref="recover",
                            payload_schema_hash=schema_hash,
                            idempotency=IdempotencyPolicy("transition.key"),
                        ),
                    ),
                    topology_overlays=(
                        TopologyOverlaySlot(
                            overlay_id="promote",
                            overlay_type="supervisor-promotion",
                            source_ref="execute",
                            target_refs=("supervisor",),
                            payload_schema_hash=schema_hash,
                        ),
                    ),
                    authority=(
                        AuthorityRequirement(
                            authority_id="execute-authority",
                            action="resume",
                            evidence_schema_hash=schema_hash,
                            capability_id="artifact:write",
                        ),
                    ),
                    suspension_routes=(
                        SuspensionRoute(
                            route_id="external-resume",
                            reentry_id="resume-execute",
                            payload_schema_hash=schema_hash,
                            resume_schema_hash=schema_hash,
                            resume_schema_ref="resume.payload",
                            resume_payload_ref="resume.value",
                        ),
                    ),
                ),
            ),
        ),
    )

    restored = WorkflowManifest.from_json(manifest.to_json())

    assert restored == manifest
    validate_manifest(restored)
    policy = restored.nodes[0].policy
    assert policy is not None
    assert policy.effects[0].idempotency is not None
    assert policy.compensation is not None
    assert policy.escalation is not None
    assert policy.suspension_routes[0].resume_schema_hash == schema_hash
