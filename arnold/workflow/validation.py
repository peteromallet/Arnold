"""Validation helpers for neutral workflow manifests."""

from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from arnold.manifest.manifests import (
    AuthorityRequirement,
    CompensationPolicy,
    CompensationTarget,
    ControlTransitionSlot,
    EffectRef,
    EscalationPolicy,
    IdempotencyPolicy,
    ReducerRef,
    SuspensionRoute,
    TimingPolicy,
    TopologyOverlaySlot,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
    WorkflowPolicy,
    canonical_json,
    compute_manifest_hash,
    compute_topology_hash,
)

FORBIDDEN_PRODUCT_IMPORTS = (
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan",
    "megaplan",
)
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_RESERVED_METADATA_KEYS = frozenset(
    {
        "manifest_hash",
        "topology_hash",
        "runtime_state",
        "event_journal",
    }
)


class ManifestValidationError(ValueError):
    """Raised when a workflow manifest violates the v1 contract."""


def validate_manifest(manifest: WorkflowManifest) -> None:
    """Validate v1 manifest integrity and deterministic coordinates."""

    errors: list[str] = []
    if manifest.schema_version != WorkflowManifest.SCHEMA_VERSION:
        errors.append(f"unsupported schema_version {manifest.schema_version!r}")
    _validate_id("manifest id", manifest.id, errors)
    node_ids = [node.id for node in manifest.nodes]
    edge_ids = [edge.id for edge in manifest.edges]
    if len(node_ids) != len(set(node_ids)):
        errors.append("node ids must be unique")
    if len(edge_ids) != len(set(edge_ids)):
        errors.append("edge ids must be unique")
    known_nodes = set(node_ids)
    _validate_metadata(f"manifest {manifest.id!r} metadata", manifest.metadata, errors)
    _validate_policy(f"manifest {manifest.id!r} policy", manifest.policy, errors)
    for edge in manifest.edges:
        _validate_id("edge id", edge.id, errors)
        _validate_ref(f"edge {edge.id!r} source", edge.source, errors)
        _validate_ref(f"edge {edge.id!r} target", edge.target, errors)
        _validate_ref(f"edge {edge.id!r} label", edge.label, errors)
        _validate_optional_ref(f"edge {edge.id!r} condition_ref", edge.condition_ref, errors)
        _validate_metadata(f"edge {edge.id!r} metadata", edge.metadata, errors)
        if edge.source not in known_nodes:
            errors.append(f"edge {edge.id!r} source {edge.source!r} is dangling")
        if edge.target not in known_nodes:
            errors.append(f"edge {edge.id!r} target {edge.target!r} is dangling")
    for node in manifest.nodes:
        _validate_id("node id", node.id, errors)
        _validate_ref(f"node {node.id!r} kind", node.kind, errors)
        for value_ref in node.inputs:
            _validate_ref(f"node {node.id!r} input", value_ref, errors)
        for value_ref in node.outputs:
            _validate_ref(f"node {node.id!r} output", value_ref, errors)
        for capability in node.capabilities:
            _validate_ref(f"node {node.id!r} capability_id", capability.capability_id, errors)
            _validate_ref(f"node {node.id!r} capability route", capability.route, errors)
        if node.subpipeline is not None:
            _validate_hash(
                f"node {node.id!r} subpipeline manifest_hash",
                node.subpipeline.manifest_hash,
                errors,
            )
            _validate_optional_ref(f"node {node.id!r} subpipeline alias", node.subpipeline.alias, errors)
        _validate_policy(f"node {node.id!r} policy", node.policy, errors)
        _validate_metadata(f"node {node.id!r} metadata", node.metadata, errors)
    _validate_cycles(manifest.nodes, manifest.edges, manifest.policy, errors)
    _validate_hash("topology_hash", manifest.topology_hash, errors)
    _validate_hash("manifest_hash", manifest.manifest_hash, errors)
    if manifest.topology_hash != compute_topology_hash(manifest):
        errors.append("topology_hash does not match canonical topology")
    if manifest.manifest_hash != compute_manifest_hash(manifest):
        errors.append("manifest_hash does not match canonical manifest")
    try:
        if canonical_json(manifest.to_dict()) != manifest.to_json():
            errors.append("manifest JSON is not canonical")
    except (TypeError, ValueError) as exc:
        errors.append(f"manifest is not JSON serializable: {exc}")
    try:
        json.loads(manifest.to_json())
    except (TypeError, ValueError) as exc:
        errors.append("manifest JSON is not canonical")
        errors.append(f"manifest JSON cannot be decoded: {exc}")
    if errors:
        raise ManifestValidationError("; ".join(errors))


def _validate_id(name: str, value: str, errors: list[str]) -> None:
    _validate_ref(name, value, errors)


def _validate_ref(name: str, value: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{name} must be a non-empty string")
        return
    if not _REF_RE.fullmatch(value):
        errors.append(f"{name} has invalid ref format: {value!r}")


def _validate_optional_ref(name: str, value: str | None, errors: list[str]) -> None:
    if value is not None:
        _validate_ref(name, value, errors)


def _validate_hash(name: str, value: str | None, errors: list[str]) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        errors.append(f"{name} must be 'sha256:' followed by 64 lowercase hex characters")


def _validate_policy(name: str, policy: WorkflowPolicy | None, errors: list[str]) -> None:
    if policy is None:
        return
    if policy.budget is not None:
        _validate_optional_positive_number(f"{name}.budget.max_cost", policy.budget.max_cost, errors)
        _validate_optional_positive_number(f"{name}.budget.max_seconds", policy.budget.max_seconds, errors)
        _validate_optional_positive_int(f"{name}.budget.max_attempts", policy.budget.max_attempts, errors)
        _validate_optional_positive_int(f"{name}.budget.token_budget", policy.budget.token_budget, errors)
    if policy.retry is not None:
        if policy.retry.max_attempts < 1:
            errors.append(f"{name}.retry.max_attempts must be >= 1")
        _validate_ref(f"{name}.retry.backoff", policy.retry.backoff, errors)
        for retry_ref in policy.retry.retry_on:
            _validate_ref(f"{name}.retry.retry_on", retry_ref, errors)
    if policy.loop is not None:
        _validate_optional_positive_int(f"{name}.loop.max_iterations", policy.loop.max_iterations, errors)
        _validate_optional_ref(f"{name}.loop.until_ref", policy.loop.until_ref, errors)
    if policy.fanout is not None:
        _validate_ref(f"{name}.fanout.mode", policy.fanout.mode, errors)
        _validate_optional_positive_int(f"{name}.fanout.width", policy.fanout.width, errors)
        _validate_optional_ref(f"{name}.fanout.reducer_ref", policy.fanout.reducer_ref, errors)
    _validate_timing_policy(f"{name}.timing", policy.timing, errors)
    _validate_idempotency_policy(f"{name}.idempotency", policy.idempotency, errors)
    _validate_effects(f"{name}.effects", policy.effects, errors)
    _validate_reducers(f"{name}.reducers", policy.reducers, errors)
    _validate_compensation_policy(f"{name}.compensation", policy.compensation, errors)
    _validate_escalation_policy(f"{name}.escalation", policy.escalation, errors)
    _validate_control_transitions(
        f"{name}.control_transitions",
        policy.control_transitions,
        errors,
    )
    _validate_topology_overlays(f"{name}.topology_overlays", policy.topology_overlays, errors)
    _validate_authority_requirements(f"{name}.authority", policy.authority, errors)
    route_ids: set[str] = set()
    for route in policy.suspension_routes:
        _validate_suspension_route(f"{name}.suspension_routes", route, route_ids, errors)


def _validate_suspension_route(
    name: str,
    route: SuspensionRoute,
    route_ids: set[str],
    errors: list[str],
) -> None:
    _validate_ref(f"{name}.route_id", route.route_id, errors)
    if route.route_id in route_ids:
        errors.append(f"{name} route_id {route.route_id!r} is duplicated")
    route_ids.add(route.route_id)
    _validate_optional_ref(f"{name}.capability_id", route.capability_id, errors)
    _validate_optional_ref(f"{name}.reentry_id", route.reentry_id, errors)
    _validate_optional_hash(
        f"{name}.payload_schema_hash",
        route.payload_schema_hash,
        errors,
    )
    _validate_optional_hash(f"{name}.resume_schema_hash", route.resume_schema_hash, errors)
    _validate_optional_ref(f"{name}.resume_schema_ref", route.resume_schema_ref, errors)
    _validate_optional_ref(f"{name}.resume_payload_ref", route.resume_payload_ref, errors)


def _validate_timing_policy(name: str, timing: TimingPolicy | None, errors: list[str]) -> None:
    if timing is None:
        return
    _validate_optional_positive_number(f"{name}.timeout_seconds", timing.timeout_seconds, errors)
    _validate_optional_ref(f"{name}.deadline_ref", timing.deadline_ref, errors)
    _validate_optional_positive_number(f"{name}.ttl_seconds", timing.ttl_seconds, errors)


def _validate_idempotency_policy(
    name: str,
    idempotency: IdempotencyPolicy | None,
    errors: list[str],
) -> None:
    if idempotency is None:
        return
    _validate_optional_ref(f"{name}.key_ref", idempotency.key_ref, errors)
    _validate_optional_ref(f"{name}.key_template", idempotency.key_template, errors)
    if not isinstance(idempotency.required, bool):
        errors.append(f"{name}.required must be a boolean")


def _validate_effects(name: str, effects: Iterable[EffectRef], errors: list[str]) -> None:
    effect_ids: set[str] = set()
    for effect in effects:
        _validate_effect_ref(name, effect, effect_ids, errors)


def _validate_effect_ref(
    name: str,
    effect: EffectRef,
    effect_ids: set[str] | None,
    errors: list[str],
) -> None:
    _validate_ref(f"{name}.effect_id", effect.effect_id, errors)
    if effect_ids is not None:
        if effect.effect_id in effect_ids:
            errors.append(f"{name} effect_id {effect.effect_id!r} is duplicated")
        effect_ids.add(effect.effect_id)
    _validate_ref(f"{name}.route", effect.route, errors)
    _validate_optional_ref(f"{name}.payload_ref", effect.payload_ref, errors)
    _validate_optional_hash(f"{name}.payload_schema_hash", effect.payload_schema_hash, errors)
    _validate_idempotency_policy(f"{name}.idempotency", effect.idempotency, errors)


def _validate_reducers(name: str, reducers: Iterable[ReducerRef], errors: list[str]) -> None:
    reducer_ids: set[str] = set()
    for reducer in reducers:
        _validate_ref(f"{name}.reducer_id", reducer.reducer_id, errors)
        if reducer.reducer_id in reducer_ids:
            errors.append(f"{name} reducer_id {reducer.reducer_id!r} is duplicated")
        reducer_ids.add(reducer.reducer_id)
        _validate_optional_ref(f"{name}.input_ref", reducer.input_ref, errors)
        _validate_optional_ref(f"{name}.output_ref", reducer.output_ref, errors)


def _validate_compensation_policy(
    name: str,
    compensation: CompensationPolicy | None,
    errors: list[str],
) -> None:
    if compensation is None:
        return
    _validate_optional_ref(f"{name}.scope_ref", compensation.scope_ref, errors)
    for trigger_ref in compensation.trigger_on:
        _validate_ref(f"{name}.trigger_on", trigger_ref, errors)
    target_ids: set[str] = set()
    for target in compensation.targets:
        _validate_compensation_target(f"{name}.targets", target, target_ids, errors)
    _validate_idempotency_policy(f"{name}.idempotency", compensation.idempotency, errors)


def _validate_compensation_target(
    name: str,
    target: CompensationTarget,
    target_ids: set[str],
    errors: list[str],
) -> None:
    _validate_ref(f"{name}.target_id", target.target_id, errors)
    if target.target_id in target_ids:
        errors.append(f"{name} target_id {target.target_id!r} is duplicated")
    target_ids.add(target.target_id)
    _validate_effect_ref(f"{name}.effect", target.effect, None, errors)
    _validate_optional_ref(f"{name}.condition_ref", target.condition_ref, errors)
    _validate_idempotency_policy(f"{name}.idempotency", target.idempotency, errors)


def _validate_escalation_policy(
    name: str,
    escalation: EscalationPolicy | None,
    errors: list[str],
) -> None:
    if escalation is None:
        return
    if not escalation.targets:
        errors.append(f"{name}.targets must include at least one target")
    for target_ref in escalation.targets:
        _validate_ref(f"{name}.targets", target_ref, errors)
    _validate_optional_positive_int(
        f"{name}.escalate_after_attempts",
        escalation.escalate_after_attempts,
        errors,
    )
    _validate_optional_ref(f"{name}.policy_ref", escalation.policy_ref, errors)
    _validate_ref(f"{name}.backoff", escalation.backoff, errors)


def _validate_control_transitions(
    name: str,
    transitions: Iterable[ControlTransitionSlot],
    errors: list[str],
) -> None:
    transition_ids: set[str] = set()
    for transition in transitions:
        _validate_ref(f"{name}.transition_id", transition.transition_id, errors)
        if transition.transition_id in transition_ids:
            errors.append(f"{name} transition_id {transition.transition_id!r} is duplicated")
        transition_ids.add(transition.transition_id)
        _validate_ref(f"{name}.transition_type", transition.transition_type, errors)
        _validate_optional_ref(f"{name}.trigger_ref", transition.trigger_ref, errors)
        _validate_optional_ref(f"{name}.target_ref", transition.target_ref, errors)
        _validate_optional_hash(f"{name}.payload_schema_hash", transition.payload_schema_hash, errors)
        _validate_optional_ref(f"{name}.policy_ref", transition.policy_ref, errors)
        _validate_idempotency_policy(f"{name}.idempotency", transition.idempotency, errors)


def _validate_topology_overlays(
    name: str,
    overlays: Iterable[TopologyOverlaySlot],
    errors: list[str],
) -> None:
    overlay_ids: set[str] = set()
    for overlay in overlays:
        _validate_ref(f"{name}.overlay_id", overlay.overlay_id, errors)
        if overlay.overlay_id in overlay_ids:
            errors.append(f"{name} overlay_id {overlay.overlay_id!r} is duplicated")
        overlay_ids.add(overlay.overlay_id)
        _validate_ref(f"{name}.overlay_type", overlay.overlay_type, errors)
        _validate_optional_ref(f"{name}.source_ref", overlay.source_ref, errors)
        for target_ref in overlay.target_refs:
            _validate_ref(f"{name}.target_refs", target_ref, errors)
        _validate_optional_ref(f"{name}.condition_ref", overlay.condition_ref, errors)
        _validate_optional_hash(f"{name}.payload_schema_hash", overlay.payload_schema_hash, errors)


def _validate_authority_requirements(
    name: str,
    requirements: Iterable[AuthorityRequirement],
    errors: list[str],
) -> None:
    requirement_ids: set[tuple[str, str]] = set()
    for requirement in requirements:
        _validate_ref(f"{name}.authority_id", requirement.authority_id, errors)
        _validate_ref(f"{name}.action", requirement.action, errors)
        key = (requirement.authority_id, requirement.action)
        if key in requirement_ids:
            errors.append(
                f"{name} authority/action pair {requirement.authority_id!r}/{requirement.action!r} is duplicated"
            )
        requirement_ids.add(key)
        _validate_optional_hash(f"{name}.evidence_schema_hash", requirement.evidence_schema_hash, errors)
        _validate_optional_ref(f"{name}.capability_id", requirement.capability_id, errors)


def _validate_optional_hash(name: str, value: str | None, errors: list[str]) -> None:
    if value is not None:
        _validate_hash(name, value, errors)


def _validate_optional_positive_int(name: str, value: int | None, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        errors.append(f"{name} must be a positive integer")


def _validate_optional_positive_number(name: str, value: float | None, errors: list[str]) -> None:
    if value is None:
        return
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value <= 0
    ):
        errors.append(f"{name} must be a positive finite number")


def _validate_metadata(name: str, metadata: Mapping[str, Any], errors: list[str]) -> None:
    if not isinstance(metadata, Mapping):
        errors.append(f"{name} must be a mapping")
        return
    _validate_json_value(name, metadata, errors)


def _validate_json_value(name: str, value: Any, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, subvalue in value.items():
            if not isinstance(key, str) or not key:
                errors.append(f"{name} metadata keys must be non-empty strings")
                continue
            if key in _RESERVED_METADATA_KEYS:
                errors.append(f"{name} uses reserved metadata key: {key!r}")
            _validate_json_value(f"{name}.{key}", subvalue, errors)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(f"{name}[{index}]", item, errors)
        return
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    errors.append(f"{name} contains non-JSON-serializable value {value!r}")


def _validate_cycles(
    nodes: Iterable[WorkflowNode],
    edges: Iterable[WorkflowEdge],
    manifest_policy: WorkflowPolicy | None,
    errors: list[str],
) -> None:
    nodes_by_id = {node.id: node for node in nodes}
    edge_list = list(edges)
    adjacency: dict[str, list[WorkflowEdge]] = {node_id: [] for node_id in nodes_by_id}
    for edge in edge_list:
        if edge.source in adjacency:
            adjacency[edge.source].append(edge)

    stack: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        visiting.add(node_id)
        stack.append(node_id)
        for edge in adjacency.get(node_id, ()):
            if edge.target not in nodes_by_id:
                continue
            if edge.target in visiting:
                cycle_nodes = stack[stack.index(edge.target) :] + [edge.target]
                if not _cycle_has_bounded_reentry(
                    cycle_nodes, nodes_by_id, manifest_policy, edge_list
                ):
                    errors.append(
                        "arbitrary graph cycles are invalid; edge "
                        f"{edge.id!r} closes cycle {' -> '.join(cycle_nodes)} "
                        "without an explicit bounded reentry route"
                    )
            elif edge.target not in visited:
                visit(edge.target)
        stack.pop()
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes_by_id:
        if node_id not in visited:
            visit(node_id)


def _cycle_has_bounded_reentry(
    cycle_nodes: list[str],
    nodes_by_id: Mapping[str, WorkflowNode],
    manifest_policy: WorkflowPolicy | None,
    edges: Iterable[WorkflowEdge],
) -> bool:
    """Return True if the cycle contains at least one explicit bounded reentry edge."""

    for source_id, target_id in zip(cycle_nodes, cycle_nodes[1:]):
        for edge in _edges_between(source_id, target_id, edges):
            if _is_explicit_bounded_reentry(edge, nodes_by_id, manifest_policy):
                return True
    return False


def _edges_between(
    source_id: str,
    target_id: str,
    edges: Iterable[WorkflowEdge],
) -> Iterable[WorkflowEdge]:
    return (edge for edge in edges if edge.source == source_id and edge.target == target_id)


def _is_explicit_bounded_reentry(
    edge: WorkflowEdge,
    nodes_by_id: Mapping[str, WorkflowNode],
    manifest_policy: WorkflowPolicy | None,
) -> bool:
    if edge.condition_ref is None:
        return False
    candidate_policies = [manifest_policy]
    source = nodes_by_id.get(edge.source)
    target = nodes_by_id.get(edge.target)
    if source is not None:
        candidate_policies.append(source.policy)
    if target is not None:
        candidate_policies.append(target.policy)
    for policy in candidate_policies:
        if policy is None or policy.loop is None or policy.loop.max_iterations is None:
            continue
        if policy.loop.max_iterations < 1:
            continue
        if any(route.reentry_id == edge.condition_ref for route in policy.suspension_routes):
            return True
    return False


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
