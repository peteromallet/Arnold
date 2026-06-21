from __future__ import annotations

from dataclasses import replace

import pytest

from arnold.workflow import (
    ManifestValidationError,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
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
