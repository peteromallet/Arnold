"""Validation helpers for neutral workflow manifests."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from arnold.workflow.manifests import (
    WorkflowManifest,
    canonical_json,
    compute_manifest_hash,
    compute_topology_hash,
)

FORBIDDEN_PRODUCT_IMPORTS = (
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan",
    "megaplan",
)


class ManifestValidationError(ValueError):
    """Raised when a workflow manifest violates the v1 contract."""


def validate_manifest(manifest: WorkflowManifest) -> None:
    """Validate v1 manifest integrity and deterministic coordinates."""

    errors: list[str] = []
    if manifest.schema_version != WorkflowManifest.SCHEMA_VERSION:
        errors.append(f"unsupported schema_version {manifest.schema_version!r}")
    node_ids = [node.id for node in manifest.nodes]
    edge_ids = [edge.id for edge in manifest.edges]
    if len(node_ids) != len(set(node_ids)):
        errors.append("node ids must be unique")
    if len(edge_ids) != len(set(edge_ids)):
        errors.append("edge ids must be unique")
    known_nodes = set(node_ids)
    for edge in manifest.edges:
        if edge.source not in known_nodes:
            errors.append(f"edge {edge.id!r} source {edge.source!r} is dangling")
        if edge.target not in known_nodes:
            errors.append(f"edge {edge.id!r} target {edge.target!r} is dangling")
    reserved = {"manifest_hash", "topology_hash", "runtime_state", "event_journal"}
    for node in manifest.nodes:
        overlap = reserved.intersection(node.metadata)
        if overlap:
            errors.append(f"node {node.id!r} uses reserved metadata keys: {sorted(overlap)}")
    if manifest.topology_hash != compute_topology_hash(manifest):
        errors.append("topology_hash does not match canonical topology")
    if manifest.manifest_hash != compute_manifest_hash(manifest):
        errors.append("manifest_hash does not match canonical manifest")
    if canonical_json(manifest.to_dict()) != manifest.to_json():
        errors.append("manifest JSON is not canonical")
    if errors:
        raise ManifestValidationError("; ".join(errors))


def check_neutral_import_boundary(paths: Iterable[Path]) -> dict[str, tuple[str, ...]]:
    """Return forbidden product imports by file path for neutral packages."""

    violations: dict[str, tuple[str, ...]] = {}
    for path in paths:
        if not path.exists() or path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        hits: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _record_forbidden_import(alias.name, hits)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    _record_forbidden_import(node.module, hits)
        if hits:
            violations[path.as_posix()] = tuple(sorted(hits))
    return violations


def _record_forbidden_import(module: str, hits: set[str]) -> None:
    for forbidden in FORBIDDEN_PRODUCT_IMPORTS:
        if module == forbidden or module.startswith(forbidden + "."):
            hits.add(forbidden)
