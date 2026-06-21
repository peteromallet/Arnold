from __future__ import annotations

from dataclasses import replace

from arnold.workflow import WorkflowEdge, WorkflowManifest, WorkflowNode


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
