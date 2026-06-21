from __future__ import annotations

from dataclasses import replace

import pytest

from arnold.workflow import (
    LoopPolicy,
    ManifestValidationError,
    SubpipelineRef,
    SuspensionRoute,
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
