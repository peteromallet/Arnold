"""Structural diff classification for shared native pack exports.

Compares exported units by stable ID, declared interface schemas, static
topology paths, and routed control-flow edges. The result is a structured
diff report that callers can use to decide whether a deliberate re-pin is
safe or breaking.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipeline.native.graph_projection import derive_topology
from arnold.pipeline.native.ir import NativeProgram, NativeTopology, TopologyEdge, TopologyNode
from arnold.pipeline.native.pack_metadata import ExportEntry, PackManifest


def _canonical_json(obj: Any) -> str:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _normalize_schema(schema: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if schema is None:
        return None
    if not schema:
        return {}
    return json.loads(_canonical_json(schema))


@dataclass(frozen=True)
class DiffEntry:
    """A single classified structural diff entry."""

    category: str
    change: str
    breaking: bool
    stable_id: str | None = None
    node_kind: str | None = None
    old_path: str | None = None
    new_path: str | None = None
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "category": self.category,
            "change": self.change,
            "breaking": self.breaking,
        }
        if self.stable_id is not None:
            result["stable_id"] = self.stable_id
        if self.node_kind is not None:
            result["node_kind"] = self.node_kind
        if self.old_path is not None:
            result["old_path"] = self.old_path
        if self.new_path is not None:
            result["new_path"] = self.new_path
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = json.loads(_canonical_json(self.details))
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DiffEntry:
        return cls(
            category=data["category"],
            change=data["change"],
            breaking=bool(data["breaking"]),
            stable_id=data.get("stable_id"),
            node_kind=data.get("node_kind"),
            old_path=data.get("old_path"),
            new_path=data.get("new_path"),
            message=data.get("message", ""),
            details=data.get("details", {}),
        )


@dataclass(frozen=True)
class DiffReport:
    """A complete structural diff report between two export versions."""

    old_stable_id: str | None = None
    new_stable_id: str | None = None
    entries: tuple[DiffEntry, ...] = ()

    @property
    def has_breaking_changes(self) -> bool:
        return any(entry.breaking for entry in self.entries)

    @property
    def breaking_entries(self) -> tuple[DiffEntry, ...]:
        return tuple(entry for entry in self.entries if entry.breaking)

    @property
    def non_breaking_entries(self) -> tuple[DiffEntry, ...]:
        return tuple(entry for entry in self.entries if not entry.breaking)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "entries": [entry.to_dict() for entry in self.entries],
            "has_breaking_changes": self.has_breaking_changes,
        }
        if self.old_stable_id is not None:
            result["old_stable_id"] = self.old_stable_id
        if self.new_stable_id is not None:
            result["new_stable_id"] = self.new_stable_id
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DiffReport:
        return cls(
            old_stable_id=data.get("old_stable_id"),
            new_stable_id=data.get("new_stable_id"),
            entries=tuple(DiffEntry.from_dict(entry) for entry in data.get("entries", ())),
        )


def diff_pack_exports(
    *,
    old_export: ExportEntry,
    new_export: ExportEntry,
    old_program: NativeProgram,
    new_program: NativeProgram,
    old_topology: NativeTopology | None = None,
    new_topology: NativeTopology | None = None,
) -> DiffReport:
    """Compare two versions of one exported step or workflow."""
    entries: list[DiffEntry] = []

    old_stable_id = old_export.stable_id
    new_stable_id = new_export.stable_id
    if old_stable_id != new_stable_id:
        entries.append(
            DiffEntry(
                category="rename",
                change="stable_id_changed",
                breaking=True,
                stable_id=old_stable_id or new_stable_id,
                message=(
                    f"Export stable ID changed from {old_stable_id!r} to {new_stable_id!r}."
                ),
                details={
                    "old_stable_id": old_stable_id,
                    "new_stable_id": new_stable_id,
                },
            )
        )

    if old_export.kind != new_export.kind:
        entries.append(
            DiffEntry(
                category="unit",
                change="export_kind_changed",
                breaking=True,
                stable_id=new_stable_id or old_stable_id,
                message=(
                    f"Export kind changed from {old_export.kind!r} to {new_export.kind!r}."
                ),
                details={
                    "old_kind": old_export.kind,
                    "new_kind": new_export.kind,
                },
            )
        )

    if old_export.name != new_export.name:
        entries.append(
            DiffEntry(
                category="rename",
                change="export_name_changed",
                breaking=False,
                stable_id=new_stable_id or old_stable_id,
                message=(
                    f"Export display name changed from {old_export.name!r} to {new_export.name!r}."
                ),
                details={
                    "old_name": old_export.name,
                    "new_name": new_export.name,
                },
            )
        )

    entries.extend(
        _compare_export_interfaces(
            stable_id=new_stable_id or old_stable_id,
            old_export=old_export,
            new_export=new_export,
        )
    )
    entries.extend(
        _compare_export_body_hash(
            stable_id=new_stable_id or old_stable_id,
            old_export=old_export,
            new_export=new_export,
        )
    )

    old_topology = old_topology if isinstance(old_topology, NativeTopology) else _topology_for(old_program)
    new_topology = new_topology if isinstance(new_topology, NativeTopology) else _topology_for(new_program)
    entries.extend(_compare_topologies(old_topology=old_topology, new_topology=new_topology))

    return DiffReport(
        old_stable_id=old_stable_id,
        new_stable_id=new_stable_id,
        entries=tuple(entries),
    )


def diff_pack_manifests(
    *,
    old_manifest: PackManifest,
    new_manifest: PackManifest,
    old_programs: Mapping[str, NativeProgram],
    new_programs: Mapping[str, NativeProgram],
) -> DiffReport:
    """Compare two pack manifests and their registered providers."""
    entries: list[DiffEntry] = []
    old_exports = {export.stable_id: export for export in old_manifest.exports}
    new_exports = {export.stable_id: export for export in new_manifest.exports}

    old_by_name_kind = {(export.name, export.kind): export for export in old_manifest.exports}
    new_by_name_kind = {(export.name, export.kind): export for export in new_manifest.exports}

    removed_ids = set(old_exports) - set(new_exports)
    added_ids = set(new_exports) - set(old_exports)

    matched_renames: set[str] = set()
    for removed_id in sorted(removed_ids):
        old_export = old_exports[removed_id]
        replacement = new_by_name_kind.get((old_export.name, old_export.kind))
        if replacement is None or replacement.stable_id not in added_ids:
            continue
        matched_renames.add(removed_id)
        matched_renames.add(replacement.stable_id)
        entries.append(
            DiffEntry(
                category="rename",
                change="stable_id_changed",
                breaking=True,
                stable_id=removed_id,
                message=(
                    f"Export {old_export.name!r} changed stable ID from "
                    f"{removed_id!r} to {replacement.stable_id!r}."
                ),
                details={
                    "old_stable_id": removed_id,
                    "new_stable_id": replacement.stable_id,
                    "name": old_export.name,
                    "kind": old_export.kind,
                },
            )
        )

    for stable_id in sorted(removed_ids - matched_renames):
        old_export = old_exports[stable_id]
        entries.append(
            DiffEntry(
                category="unit",
                change="export_removed",
                breaking=True,
                stable_id=stable_id,
                message=f"Export {old_export.name!r} ({stable_id!r}) was removed.",
                details={
                    "name": old_export.name,
                    "kind": old_export.kind,
                },
            )
        )

    for stable_id in sorted(added_ids - matched_renames):
        new_export = new_exports[stable_id]
        entries.append(
            DiffEntry(
                category="unit",
                change="export_added",
                breaking=False,
                stable_id=stable_id,
                message=f"Export {new_export.name!r} ({stable_id!r}) was added.",
                details={
                    "name": new_export.name,
                    "kind": new_export.kind,
                },
            )
        )

    for stable_id in sorted(set(old_exports) & set(new_exports)):
        old_program = old_programs[stable_id]
        new_program = new_programs[stable_id]
        report = diff_pack_exports(
            old_export=old_exports[stable_id],
            new_export=new_exports[stable_id],
            old_program=old_program,
            new_program=new_program,
        )
        entries.extend(report.entries)

    old_stable_id = old_manifest.stable_id or old_manifest.name
    new_stable_id = new_manifest.stable_id or new_manifest.name
    if old_stable_id != new_stable_id:
        entries.append(
            DiffEntry(
                category="rename",
                change="pack_stable_id_changed",
                breaking=True,
                stable_id=old_stable_id,
                message=(
                    f"Pack stable ID changed from {old_stable_id!r} to {new_stable_id!r}."
                ),
                details={
                    "old_stable_id": old_stable_id,
                    "new_stable_id": new_stable_id,
                },
            )
        )

    return DiffReport(
        old_stable_id=old_stable_id,
        new_stable_id=new_stable_id,
        entries=tuple(entries),
    )


def _topology_for(program: NativeProgram) -> NativeTopology:
    topology = program.topology
    if isinstance(topology, NativeTopology):
        return topology
    return derive_topology(program)


def _compare_export_interfaces(
    *,
    stable_id: str | None,
    old_export: ExportEntry,
    new_export: ExportEntry,
) -> list[DiffEntry]:
    entries: list[DiffEntry] = []
    old_inputs = _normalize_schema(old_export.inputs_schema)
    new_inputs = _normalize_schema(new_export.inputs_schema)
    if old_inputs != new_inputs:
        if _is_additive_optional_input_change(old_inputs, new_inputs):
            entries.append(
                DiffEntry(
                    category="interface",
                    change="optional_inputs_added",
                    breaking=False,
                    stable_id=stable_id,
                    message="Only optional input fields were added.",
                    details={
                        "old_inputs_schema": old_inputs,
                        "new_inputs_schema": new_inputs,
                    },
                )
            )
        else:
            entries.append(
                DiffEntry(
                    category="interface",
                    change="inputs_schema_changed",
                    breaking=True,
                    stable_id=stable_id,
                    message="Declared input schema changed incompatibly.",
                    details={
                        "old_inputs_schema": old_inputs,
                        "new_inputs_schema": new_inputs,
                    },
                )
            )

    old_outputs = _normalize_schema(old_export.outputs_schema)
    new_outputs = _normalize_schema(new_export.outputs_schema)
    if old_outputs != new_outputs:
        entries.append(
            DiffEntry(
                category="interface",
                change="outputs_schema_changed",
                breaking=True,
                stable_id=stable_id,
                message="Declared output schema changed.",
                details={
                    "old_outputs_schema": old_outputs,
                    "new_outputs_schema": new_outputs,
                },
            )
        )
    return entries


def _compare_export_body_hash(
    *,
    stable_id: str | None,
    old_export: ExportEntry,
    new_export: ExportEntry,
) -> list[DiffEntry]:
    old_hash = old_export.body_hash
    new_hash = new_export.body_hash
    if old_hash == new_hash:
        return []
    if old_hash is None or new_hash is None:
        return [
            DiffEntry(
                category="body",
                change="body_hash_opt_in_changed",
                breaking=False,
                stable_id=stable_id,
                message="Body-hash opt-in changed; body-only changes remain advisory.",
                details={
                    "old_body_hash": old_hash,
                    "new_body_hash": new_hash,
                },
            )
        ]
    return [
        DiffEntry(
            category="body",
            change="body_hash_changed",
            breaking=True,
            stable_id=stable_id,
            message="Committed export body hash changed.",
            details={
                "old_body_hash": old_hash,
                "new_body_hash": new_hash,
            },
        )
    ]


def _is_additive_optional_input_change(
    old_schema: Mapping[str, Any] | None,
    new_schema: Mapping[str, Any] | None,
) -> bool:
    if not isinstance(old_schema, Mapping) or not isinstance(new_schema, Mapping):
        return False
    if old_schema.get("type") != "object" or new_schema.get("type") != "object":
        return False

    old_required = set(old_schema.get("required", ()))
    new_required = set(new_schema.get("required", ()))
    if old_required != new_required:
        return False

    old_properties = old_schema.get("properties")
    new_properties = new_schema.get("properties")
    if not isinstance(old_properties, Mapping) or not isinstance(new_properties, Mapping):
        return False

    for key, old_value in old_properties.items():
        if key not in new_properties:
            return False
        if _normalize_schema(old_value) != _normalize_schema(new_properties[key]):
            return False

    old_without_props = {
        key: value for key, value in old_schema.items() if key not in {"properties", "required"}
    }
    new_without_props = {
        key: value for key, value in new_schema.items() if key not in {"properties", "required"}
    }
    return _normalize_schema(old_without_props) == _normalize_schema(new_without_props)


def _compare_topologies(
    *,
    old_topology: NativeTopology,
    new_topology: NativeTopology,
) -> list[DiffEntry]:
    entries: list[DiffEntry] = []
    old_groups = _nodes_by_stable_id(old_topology)
    new_groups = _nodes_by_stable_id(new_topology)

    for stable_id in sorted(set(old_groups) | set(new_groups)):
        old_nodes = old_groups.get(stable_id, ())
        new_nodes = new_groups.get(stable_id, ())
        entries.extend(
            _compare_node_group(
                stable_id=stable_id,
                old_nodes=old_nodes,
                new_nodes=new_nodes,
                old_topology=old_topology,
                new_topology=new_topology,
            )
        )
    return entries


def _nodes_by_stable_id(topology: NativeTopology) -> dict[str, tuple[TopologyNode, ...]]:
    grouped: dict[str, list[TopologyNode]] = {}
    for node in topology.nodes:
        if node.stable_id:
            grouped.setdefault(node.stable_id, []).append(node)
    return {
        stable_id: tuple(sorted(nodes, key=lambda node: (node.path, node.kind, node.label, node.node_id)))
        for stable_id, nodes in grouped.items()
    }


def _compare_node_group(
    *,
    stable_id: str,
    old_nodes: tuple[TopologyNode, ...],
    new_nodes: tuple[TopologyNode, ...],
    old_topology: NativeTopology,
    new_topology: NativeTopology,
) -> list[DiffEntry]:
    if not old_nodes:
        return [
            DiffEntry(
                category="unit",
                change="node_added",
                breaking=False,
                stable_id=stable_id,
                node_kind=node.kind,
                new_path=node.path,
                message=f"Topology node {stable_id!r} was added at {node.path!r}.",
            )
            for node in new_nodes
        ]
    if not new_nodes:
        return [
            DiffEntry(
                category="unit",
                change="node_removed",
                breaking=True,
                stable_id=stable_id,
                node_kind=node.kind,
                old_path=node.path,
                message=f"Topology node {stable_id!r} was removed from {node.path!r}.",
            )
            for node in old_nodes
        ]

    entries: list[DiffEntry] = []
    exact_old = {node.path: node for node in old_nodes}
    exact_new = {node.path: node for node in new_nodes}
    matched_old_paths = set(exact_old) & set(exact_new)
    pairs: list[tuple[TopologyNode, TopologyNode]] = [
        (exact_old[path], exact_new[path]) for path in sorted(matched_old_paths)
    ]

    remaining_old = [node for node in old_nodes if node.path not in matched_old_paths]
    remaining_new = [node for node in new_nodes if node.path not in matched_old_paths]
    remaining_old.sort(key=lambda node: (node.kind, node.path, node.label, node.node_id))
    remaining_new.sort(key=lambda node: (node.kind, node.path, node.label, node.node_id))

    for old_node, new_node in zip(remaining_old, remaining_new):
        pairs.append((old_node, new_node))
        if old_node.path != new_node.path:
            entries.append(
                DiffEntry(
                    category="path",
                    change="node_path_changed",
                    breaking=True,
                    stable_id=stable_id,
                    node_kind=new_node.kind,
                    old_path=old_node.path,
                    new_path=new_node.path,
                    message=(
                        f"Stable node {stable_id!r} moved from {old_node.path!r} "
                        f"to {new_node.path!r}."
                    ),
                )
            )

    for old_node, new_node in pairs:
        entries.extend(
            _compare_matched_nodes(
                stable_id=stable_id,
                old_node=old_node,
                new_node=new_node,
                old_topology=old_topology,
                new_topology=new_topology,
            )
        )

    if len(remaining_old) > len(remaining_new):
        for node in remaining_old[len(remaining_new):]:
            entries.append(
                DiffEntry(
                    category="unit",
                    change="node_removed",
                    breaking=True,
                    stable_id=stable_id,
                    node_kind=node.kind,
                    old_path=node.path,
                    message=f"Topology node {stable_id!r} was removed from {node.path!r}.",
                )
            )
    elif len(remaining_new) > len(remaining_old):
        for node in remaining_new[len(remaining_old):]:
            entries.append(
                DiffEntry(
                    category="unit",
                    change="node_added",
                    breaking=False,
                    stable_id=stable_id,
                    node_kind=node.kind,
                    new_path=node.path,
                    message=f"Topology node {stable_id!r} was added at {node.path!r}.",
                )
            )
    return entries


def _compare_matched_nodes(
    *,
    stable_id: str,
    old_node: TopologyNode,
    new_node: TopologyNode,
    old_topology: NativeTopology,
    new_topology: NativeTopology,
) -> list[DiffEntry]:
    entries: list[DiffEntry] = []

    if old_node.kind != new_node.kind:
        entries.append(
            DiffEntry(
                category="unit",
                change="node_kind_changed",
                breaking=True,
                stable_id=stable_id,
                node_kind=new_node.kind,
                old_path=old_node.path,
                new_path=new_node.path,
                message=(
                    f"Stable node {stable_id!r} changed kind from {old_node.kind!r} "
                    f"to {new_node.kind!r}."
                ),
                details={
                    "old_kind": old_node.kind,
                    "new_kind": new_node.kind,
                },
            )
        )

    if old_node.label != new_node.label:
        entries.append(
            DiffEntry(
                category="rename",
                change="node_label_changed",
                breaking=False,
                stable_id=stable_id,
                node_kind=new_node.kind,
                old_path=old_node.path,
                new_path=new_node.path,
                message=(
                    f"Stable node {stable_id!r} changed label from "
                    f"{old_node.label!r} to {new_node.label!r}."
                ),
                details={
                    "old_label": old_node.label,
                    "new_label": new_node.label,
                },
            )
        )

    entries.extend(
        _compare_node_interfaces(
            stable_id=stable_id,
            old_node=old_node,
            new_node=new_node,
        )
    )
    entries.extend(
        _compare_node_routes(
            stable_id=stable_id,
            old_node=old_node,
            new_node=new_node,
            old_topology=old_topology,
            new_topology=new_topology,
        )
    )
    return entries


def _compare_node_interfaces(
    *,
    stable_id: str,
    old_node: TopologyNode,
    new_node: TopologyNode,
) -> list[DiffEntry]:
    entries: list[DiffEntry] = []
    for label in ("inputs_schema", "outputs_schema"):
        old_schema = _normalize_schema(old_node.metadata.get(label))
        new_schema = _normalize_schema(new_node.metadata.get(label))
        if old_schema == new_schema:
            continue
        if label == "inputs_schema" and _is_additive_optional_input_change(old_schema, new_schema):
            entries.append(
                DiffEntry(
                    category="interface",
                    change="optional_inputs_added",
                    breaking=False,
                    stable_id=stable_id,
                    node_kind=new_node.kind,
                    old_path=old_node.path,
                    new_path=new_node.path,
                    message="Only optional input fields were added for a stable node.",
                    details={
                        "old_inputs_schema": old_schema,
                        "new_inputs_schema": new_schema,
                    },
                )
            )
            continue
        entries.append(
            DiffEntry(
                category="interface",
                change=f"{label}_changed",
                breaking=True,
                stable_id=stable_id,
                node_kind=new_node.kind,
                old_path=old_node.path,
                new_path=new_node.path,
                message=f"Declared {label} changed for a stable node.",
                details={
                    f"old_{label}": old_schema,
                    f"new_{label}": new_schema,
                },
            )
        )
    return entries


def _compare_node_routes(
    *,
    stable_id: str,
    old_node: TopologyNode,
    new_node: TopologyNode,
    old_topology: NativeTopology,
    new_topology: NativeTopology,
) -> list[DiffEntry]:
    old_routes = _control_routes(old_topology, old_node.node_id)
    new_routes = _control_routes(new_topology, new_node.node_id)
    old_labels = set(old_routes)
    new_labels = set(new_routes)
    old_vocab = set(old_node.metadata.get("vocabulary", ()))
    new_vocab = set(new_node.metadata.get("vocabulary", ()))

    entries: list[DiffEntry] = []
    for label in sorted(old_labels - new_labels):
        entries.append(
            DiffEntry(
                category="branch",
                change="branch_removed",
                breaking=True,
                stable_id=stable_id,
                node_kind=new_node.kind,
                old_path=old_node.path,
                new_path=new_node.path,
                message=f"Branch {label!r} was removed from stable node {stable_id!r}.",
                details={"label": label, "old_target": old_routes[label]},
            )
        )

    for label in sorted(new_labels - old_labels):
        entries.append(
            DiffEntry(
                category="branch",
                change="branch_added",
                breaking=False,
                stable_id=stable_id,
                node_kind=new_node.kind,
                old_path=old_node.path,
                new_path=new_node.path,
                message=f"Branch {label!r} was added to stable node {stable_id!r}.",
                details={"label": label, "new_target": new_routes[label]},
            )
        )

    for label in sorted(old_labels & new_labels):
        if old_routes[label] == new_routes[label]:
            continue
        change = "branch_target_changed" if label != "next" else "edge_target_changed"
        category = "branch" if label != "next" else "path"
        entries.append(
            DiffEntry(
                category=category,
                change=change,
                breaking=True,
                stable_id=stable_id,
                node_kind=new_node.kind,
                old_path=old_node.path,
                new_path=new_node.path,
                message=(
                    f"Route {label!r} changed target from {old_routes[label]!r} "
                    f"to {new_routes[label]!r} for stable node {stable_id!r}."
                ),
                details={
                    "label": label,
                    "old_target": old_routes[label],
                    "new_target": new_routes[label],
                },
            )
        )

    for label in sorted((old_vocab - new_vocab) - old_labels):
        entries.append(
            DiffEntry(
                category="branch",
                change="branch_vocabulary_removed",
                breaking=False,
                stable_id=stable_id,
                node_kind=new_node.kind,
                old_path=old_node.path,
                new_path=new_node.path,
                message=(
                    f"Unwired branch vocabulary label {label!r} was removed from "
                    f"stable node {stable_id!r}."
                ),
                details={"label": label},
            )
        )

    for label in sorted((new_vocab - old_vocab) - new_labels):
        entries.append(
            DiffEntry(
                category="branch",
                change="branch_vocabulary_added",
                breaking=False,
                stable_id=stable_id,
                node_kind=new_node.kind,
                old_path=old_node.path,
                new_path=new_node.path,
                message=(
                    f"Unwired branch vocabulary label {label!r} was added to "
                    f"stable node {stable_id!r}."
                ),
                details={"label": label},
            )
        )
    return entries


def _control_routes(topology: NativeTopology, node_id: str) -> dict[str, str]:
    node_map = {node.node_id: node for node in topology.nodes}
    routes: dict[str, str] = {}
    for edge in topology.edges:
        if edge.source != node_id or edge.kind != "control_flow":
            continue
        routes[edge.label] = _edge_target_identity(node_map, edge)
    return routes


def _edge_target_identity(node_map: Mapping[str, TopologyNode], edge: TopologyEdge) -> str:
    target = node_map.get(edge.target)
    if target is None:
        return edge.target
    if target.stable_id:
        return f"{target.stable_id}@{target.path}"
    return target.path or target.node_id


__all__ = [
    "DiffEntry",
    "DiffReport",
    "diff_pack_exports",
    "diff_pack_manifests",
]
