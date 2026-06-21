from __future__ import annotations

from arnold.workflow import (
    BudgetPolicy,
    CapabilityRequirement,
    RetryPolicy,
    SourceSpan,
    SuspensionRoute,
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
