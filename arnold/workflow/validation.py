"""Validation helpers for neutral workflow manifests."""

from __future__ import annotations

import ast
import json
import math
import re
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from types import MappingProxyType
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


def _require_ref_segment(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    if not _REF_RE.fullmatch(value):
        raise ValueError(f"{name} has invalid ref format: {value!r}")
    return value


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze_value(subvalue) for key, subvalue in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class RuntimeRef:
    """Inert runtime reference to a workflow value.

    A runtime ref exposes only stable node/output identity, declared dependency
    metadata, fallback-route metadata, and primitive serializable metadata.  It
    deliberately rejects Python truthiness, iteration, arithmetic, mutation,
    attribute probing, and branching because those operations can only represent
    live Python control flow, not manifest-routable topology.
    """

    node_id: str
    output: str
    dependencies: tuple[str, ...] = ()
    fallback_route: str | None = None
    metadata: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "node_id", _require_ref_segment("node_id", self.node_id)
        )
        object.__setattr__(
            self, "output", _require_ref_segment("output", self.output)
        )
        object.__setattr__(
            self, "dependencies", tuple(_require_ref_segment("dependency", dep) for dep in self.dependencies)
        )
        object.__setattr__(
            self, "fallback_route", None if self.fallback_route is None else _require_ref_segment("fallback_route", self.fallback_route)
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def identity(self) -> str:
        """Stable node/output identity for this runtime ref."""

        return f"{self.node_id}.{self.output}"

    def __bool__(self) -> bool:
        raise TypeError("RuntimeRef is an inert reference and has no runtime truthiness")

    def __iter__(self) -> Any:
        raise TypeError("RuntimeRef is not iterable")

    def __len__(self) -> int:
        raise TypeError("RuntimeRef has no length")

    def __int__(self) -> int:
        raise TypeError("RuntimeRef cannot be coerced to a number")

    def __float__(self) -> float:
        raise TypeError("RuntimeRef cannot be coerced to a number")

    def __add__(self, other: object) -> Any:
        raise TypeError("RuntimeRef does not support arithmetic")

    __sub__ = __mul__ = __truediv__ = __floordiv__ = __mod__ = __add__

    def __radd__(self, other: object) -> Any:
        raise TypeError("RuntimeRef does not support arithmetic")

    def __getitem__(self, key: object) -> Any:
        raise TypeError("RuntimeRef does not support indexing")

    def __contains__(self, key: object) -> bool:
        raise TypeError("RuntimeRef does not support membership tests")

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(
            f"RuntimeRef has no attribute {name!r}; "
            "use the declared identity, dependencies, fallback_route, and metadata fields only"
        )


@dataclass(frozen=True, slots=True)
class ManifestValidationIssue:
    """Structured validation issue for neutral workflow manifests."""

    code: str
    message: str
    field: str | None = None
    node_id: str | None = None
    edge_id: str | None = None
    severity: str = "error"
    details: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


class ManifestValidationError(ValueError):
    """Raised when a workflow manifest violates the v1 contract."""

    def __init__(
        self,
        message: str | None = None,
        *,
        issues: Iterable[ManifestValidationIssue] = (),
    ) -> None:
        issue_tuple = tuple(issues)
        if message is None:
            message = "; ".join(issue.message for issue in issue_tuple)
        super().__init__(message)
        self.issues = issue_tuple


def validate_manifest(manifest: WorkflowManifest) -> None:
    """Validate v1 manifest integrity and deterministic coordinates."""

    errors: list[ManifestValidationIssue] = []
    if manifest.schema_version != WorkflowManifest.SCHEMA_VERSION:
        _add_issue(
            errors,
            f"unsupported schema_version {manifest.schema_version!r}",
            code="unsupported_schema_version",
            field="schema_version",
            details={"expected": WorkflowManifest.SCHEMA_VERSION, "actual": manifest.schema_version},
        )
    _validate_id("manifest id", manifest.id, errors)
    node_ids = [node.id for node in manifest.nodes]
    edge_ids = [edge.id for edge in manifest.edges]
    if len(node_ids) != len(set(node_ids)):
        for node_id in _duplicates(node_ids):
            _add_issue(
                errors,
                "node ids must be unique",
                code="duplicate_node_id",
                field="nodes[].id",
                node_id=node_id,
            )
    if len(edge_ids) != len(set(edge_ids)):
        for edge_id in _duplicates(edge_ids):
            _add_issue(
                errors,
                "edge ids must be unique",
                code="duplicate_edge_id",
                field="edges[].id",
                edge_id=edge_id,
            )
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
            _add_issue(
                errors,
                f"edge {edge.id!r} source {edge.source!r} is dangling",
                code="dangling_edge_source",
                field="edges[].source",
                edge_id=edge.id,
                details={"source": edge.source},
            )
        if edge.target not in known_nodes:
            _add_issue(
                errors,
                f"edge {edge.id!r} target {edge.target!r} is dangling",
                code="dangling_edge_target",
                field="edges[].target",
                edge_id=edge.id,
                details={"target": edge.target},
            )
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
        _add_issue(
            errors,
            "topology_hash does not match canonical topology",
            code="topology_hash_mismatch",
            field="topology_hash",
        )
    if manifest.manifest_hash != compute_manifest_hash(manifest):
        _add_issue(
            errors,
            "manifest_hash does not match canonical manifest",
            code="manifest_hash_mismatch",
            field="manifest_hash",
        )
    try:
        if canonical_json(manifest.to_dict()) != manifest.to_json():
            _add_issue(
                errors,
                "manifest JSON is not canonical",
                code="manifest_json_not_canonical",
                field="manifest",
            )
    except (TypeError, ValueError) as exc:
        _add_issue(
            errors,
            f"manifest is not JSON serializable: {exc}",
            code="manifest_json_not_serializable",
            field="manifest",
            details={"error": str(exc)},
        )
    try:
        json.loads(manifest.to_json())
    except (TypeError, ValueError) as exc:
        _add_issue(
            errors,
            "manifest JSON is not canonical",
            code="manifest_json_not_canonical",
            field="manifest",
        )
        _add_issue(
            errors,
            f"manifest JSON cannot be decoded: {exc}",
            code="manifest_json_decode_error",
            field="manifest",
            details={"error": str(exc)},
        )
    if errors:
        raise ManifestValidationError(issues=errors)


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _add_issue(
    errors: list[ManifestValidationIssue],
    message: str,
    *,
    code: str,
    field: str | None = None,
    node_id: str | None = None,
    edge_id: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    errors.append(
        ManifestValidationIssue(
            code=code,
            message=message,
            field=field,
            node_id=node_id,
            edge_id=edge_id,
            details=dict(details or {}),
        )
    )


def _add_generic_issue(
    errors: list[ManifestValidationIssue],
    message: str,
    *,
    name: str,
    code: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    context = _issue_context(name)
    issue_code = code or f"invalid_{str(context.get('field') or name).replace('.', '_').replace('[]', '')}"
    _add_issue(
        errors,
        message,
        code=issue_code,
        field=context.get("field"),
        node_id=context.get("node_id"),
        edge_id=context.get("edge_id"),
        details=details,
    )


def _issue_context(name: str, value: Any | None = None) -> dict[str, Any]:
    match = re.match(r"^node '([^']+)'(?: |\.)(.+)$", name)
    if match:
        node_id, suffix = match.groups()
        return {
            "node_id": node_id,
            "field": _field_for_suffix("nodes[]", suffix),
            "prefix": "node",
        }
    match = re.match(r"^edge '([^']+)'(?: |\.)(.+)$", name)
    if match:
        edge_id, suffix = match.groups()
        return {
            "edge_id": edge_id,
            "field": _field_for_suffix("edges[]", suffix),
            "prefix": "edge",
        }
    if name == "node id":
        return {"node_id": value if isinstance(value, str) else None, "field": "nodes[].id", "prefix": "node"}
    if name == "edge id":
        return {"edge_id": value if isinstance(value, str) else None, "field": "edges[].id", "prefix": "edge"}
    match = re.match(r"^manifest '([^']+)'(?: |\.)(.+)$", name)
    if match:
        _, suffix = match.groups()
        return {"field": _field_for_suffix("manifest", suffix), "prefix": "manifest"}
    if name.startswith("manifest "):
        suffix = name.removeprefix("manifest ")
        if suffix.endswith(" metadata"):
            suffix = "metadata"
        elif suffix.endswith(" policy"):
            suffix = "policy"
        return {"field": _field_for_suffix("manifest", suffix), "prefix": "manifest"}
    if name in {"manifest id", "manifest_hash", "topology_hash"}:
        return {"field": {"manifest id": "id"}.get(name, name), "prefix": "manifest"}
    return {"field": _field_for_suffix(None, name), "prefix": "manifest"}


def _field_for_suffix(base: str | None, suffix: str) -> str:
    suffix = suffix.replace(" ", ".")
    if suffix == "input":
        suffix = "inputs[]"
    if suffix == "output":
        suffix = "outputs[]"
    suffix = suffix.replace(".input", ".inputs[]")
    suffix = suffix.replace(".output", ".outputs[]")
    suffix = suffix.replace(".capability_id", ".capabilities[].capability_id")
    suffix = suffix.replace(".capability.route", ".capabilities[].route")
    suffix = suffix.replace(".subpipeline.", ".subpipeline.")
    if suffix == "kind":
        leaf = "kind"
    else:
        leaf = suffix
    if base is None:
        return leaf
    if base == "manifest":
        return leaf
    return f"{base}.{leaf}"


def _code_for_invalid_ref(name: str, value: Any) -> str:
    context = _issue_context(name, value)
    prefix = context.get("prefix", "manifest")
    field = str(context.get("field") or name)
    leaf = field.rsplit(".", 1)[-1].replace("[]", "")
    leaf = {"inputs": "input", "outputs": "output", "capabilities": "capability"}.get(leaf, leaf)
    if not isinstance(value, str) or not value:
        return f"missing_{prefix}_{leaf}"
    return f"invalid_{prefix}_{leaf}"


def _validate_id(name: str, value: str, errors: list[ManifestValidationIssue]) -> None:
    _validate_ref(name, value, errors)


def _validate_ref(name: str, value: str, errors: list[ManifestValidationIssue]) -> None:
    context = _issue_context(name, value)
    if not isinstance(value, str) or not value:
        _add_issue(
            errors,
            f"{name} must be a non-empty string",
            code=_code_for_invalid_ref(name, value),
            field=context.get("field"),
            node_id=context.get("node_id"),
            edge_id=context.get("edge_id"),
            details={"value": value},
        )
        return
    if not _REF_RE.fullmatch(value):
        _add_issue(
            errors,
            f"{name} has invalid ref format: {value!r}",
            code=_code_for_invalid_ref(name, value),
            field=context.get("field"),
            node_id=context.get("node_id"),
            edge_id=context.get("edge_id"),
            details={"value": value},
        )


def _validate_optional_ref(
    name: str,
    value: str | None,
    errors: list[ManifestValidationIssue],
) -> None:
    if value is not None:
        _validate_ref(name, value, errors)


def _validate_hash(name: str, value: str | None, errors: list[ManifestValidationIssue]) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        context = _issue_context(name, value)
        _add_issue(
            errors,
            f"{name} must be 'sha256:' followed by 64 lowercase hex characters",
            code=f"invalid_{str(context.get('field') or name).replace('.', '_')}",
            field=context.get("field"),
            node_id=context.get("node_id"),
            edge_id=context.get("edge_id"),
            details={"value": value},
        )


def _validate_policy(
    name: str,
    policy: WorkflowPolicy | None,
    errors: list[ManifestValidationIssue],
) -> None:
    if policy is None:
        return
    if policy.budget is not None:
        _validate_optional_positive_number(f"{name}.budget.max_cost", policy.budget.max_cost, errors)
        _validate_optional_positive_number(f"{name}.budget.max_seconds", policy.budget.max_seconds, errors)
        _validate_optional_positive_int(f"{name}.budget.max_attempts", policy.budget.max_attempts, errors)
        _validate_optional_positive_int(f"{name}.budget.token_budget", policy.budget.token_budget, errors)
    if policy.retry is not None:
        if policy.retry.max_attempts < 1:
            _add_generic_issue(errors, f"{name}.retry.max_attempts must be >= 1", name=f"{name}.retry.max_attempts")
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
    errors: list[ManifestValidationIssue],
) -> None:
    _validate_ref(f"{name}.route_id", route.route_id, errors)
    if route.route_id in route_ids:
        _add_generic_issue(
            errors,
            f"{name} route_id {route.route_id!r} is duplicated",
            name=f"{name}.route_id",
            code="duplicate_suspension_route_id",
            details={"route_id": route.route_id},
        )
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


def _validate_timing_policy(
    name: str,
    timing: TimingPolicy | None,
    errors: list[ManifestValidationIssue],
) -> None:
    if timing is None:
        return
    _validate_optional_positive_number(f"{name}.timeout_seconds", timing.timeout_seconds, errors)
    _validate_optional_ref(f"{name}.deadline_ref", timing.deadline_ref, errors)
    _validate_optional_positive_number(f"{name}.ttl_seconds", timing.ttl_seconds, errors)


def _validate_idempotency_policy(
    name: str,
    idempotency: IdempotencyPolicy | None,
    errors: list[ManifestValidationIssue],
) -> None:
    if idempotency is None:
        return
    _validate_optional_ref(f"{name}.key_ref", idempotency.key_ref, errors)
    _validate_optional_ref(f"{name}.key_template", idempotency.key_template, errors)
    if not isinstance(idempotency.required, bool):
        _add_generic_issue(errors, f"{name}.required must be a boolean", name=f"{name}.required")


def _validate_effects(
    name: str,
    effects: Iterable[EffectRef],
    errors: list[ManifestValidationIssue],
) -> None:
    effect_ids: set[str] = set()
    for effect in effects:
        _validate_effect_ref(name, effect, effect_ids, errors)


def _validate_effect_ref(
    name: str,
    effect: EffectRef,
    effect_ids: set[str] | None,
    errors: list[ManifestValidationIssue],
) -> None:
    _validate_ref(f"{name}.effect_id", effect.effect_id, errors)
    if effect_ids is not None:
        if effect.effect_id in effect_ids:
            _add_generic_issue(
                errors,
                f"{name} effect_id {effect.effect_id!r} is duplicated",
                name=f"{name}.effect_id",
                code="duplicate_effect_id",
                details={"effect_id": effect.effect_id},
            )
        effect_ids.add(effect.effect_id)
    _validate_ref(f"{name}.route", effect.route, errors)
    _validate_optional_ref(f"{name}.payload_ref", effect.payload_ref, errors)
    _validate_optional_hash(f"{name}.payload_schema_hash", effect.payload_schema_hash, errors)
    _validate_idempotency_policy(f"{name}.idempotency", effect.idempotency, errors)


def _validate_reducers(
    name: str,
    reducers: Iterable[ReducerRef],
    errors: list[ManifestValidationIssue],
) -> None:
    reducer_ids: set[str] = set()
    for reducer in reducers:
        _validate_ref(f"{name}.reducer_id", reducer.reducer_id, errors)
        if reducer.reducer_id in reducer_ids:
            _add_generic_issue(
                errors,
                f"{name} reducer_id {reducer.reducer_id!r} is duplicated",
                name=f"{name}.reducer_id",
                code="duplicate_reducer_id",
                details={"reducer_id": reducer.reducer_id},
            )
        reducer_ids.add(reducer.reducer_id)
        _validate_optional_ref(f"{name}.input_ref", reducer.input_ref, errors)
        _validate_optional_ref(f"{name}.output_ref", reducer.output_ref, errors)


def _validate_compensation_policy(
    name: str,
    compensation: CompensationPolicy | None,
    errors: list[ManifestValidationIssue],
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
    errors: list[ManifestValidationIssue],
) -> None:
    _validate_ref(f"{name}.target_id", target.target_id, errors)
    if target.target_id in target_ids:
        _add_generic_issue(
            errors,
            f"{name} target_id {target.target_id!r} is duplicated",
            name=f"{name}.target_id",
            code="duplicate_compensation_target_id",
            details={"target_id": target.target_id},
        )
    target_ids.add(target.target_id)
    _validate_effect_ref(f"{name}.effect", target.effect, None, errors)
    _validate_optional_ref(f"{name}.condition_ref", target.condition_ref, errors)
    _validate_idempotency_policy(f"{name}.idempotency", target.idempotency, errors)


def _validate_escalation_policy(
    name: str,
    escalation: EscalationPolicy | None,
    errors: list[ManifestValidationIssue],
) -> None:
    if escalation is None:
        return
    if not escalation.targets:
        _add_generic_issue(errors, f"{name}.targets must include at least one target", name=f"{name}.targets")
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
    errors: list[ManifestValidationIssue],
) -> None:
    transition_ids: set[str] = set()
    for transition in transitions:
        _validate_ref(f"{name}.transition_id", transition.transition_id, errors)
        if transition.transition_id in transition_ids:
            _add_generic_issue(
                errors,
                f"{name} transition_id {transition.transition_id!r} is duplicated",
                name=f"{name}.transition_id",
                code="duplicate_control_transition_id",
                details={"transition_id": transition.transition_id},
            )
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
    errors: list[ManifestValidationIssue],
) -> None:
    overlay_ids: set[str] = set()
    for overlay in overlays:
        _validate_ref(f"{name}.overlay_id", overlay.overlay_id, errors)
        if overlay.overlay_id in overlay_ids:
            _add_generic_issue(
                errors,
                f"{name} overlay_id {overlay.overlay_id!r} is duplicated",
                name=f"{name}.overlay_id",
                code="duplicate_topology_overlay_id",
                details={"overlay_id": overlay.overlay_id},
            )
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
    errors: list[ManifestValidationIssue],
) -> None:
    requirement_ids: set[tuple[str, str]] = set()
    for requirement in requirements:
        _validate_ref(f"{name}.authority_id", requirement.authority_id, errors)
        _validate_ref(f"{name}.action", requirement.action, errors)
        key = (requirement.authority_id, requirement.action)
        if key in requirement_ids:
            _add_generic_issue(
                errors,
                f"{name} authority/action pair {requirement.authority_id!r}/{requirement.action!r} is duplicated",
                name=f"{name}.authority_id",
                code="duplicate_authority_requirement",
                details={"authority_id": requirement.authority_id, "action": requirement.action},
            )
        requirement_ids.add(key)
        _validate_optional_hash(f"{name}.evidence_schema_hash", requirement.evidence_schema_hash, errors)
        _validate_optional_ref(f"{name}.capability_id", requirement.capability_id, errors)


def _validate_optional_hash(
    name: str,
    value: str | None,
    errors: list[ManifestValidationIssue],
) -> None:
    if value is not None:
        _validate_hash(name, value, errors)


def _validate_optional_positive_int(
    name: str,
    value: int | None,
    errors: list[ManifestValidationIssue],
) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        _add_generic_issue(errors, f"{name} must be a positive integer", name=name, details={"value": value})


def _validate_optional_positive_number(
    name: str,
    value: float | None,
    errors: list[ManifestValidationIssue],
) -> None:
    if value is None:
        return
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value <= 0
    ):
        _add_generic_issue(errors, f"{name} must be a positive finite number", name=name, details={"value": value})


def _validate_metadata(
    name: str,
    metadata: Mapping[str, Any],
    errors: list[ManifestValidationIssue],
) -> None:
    if not isinstance(metadata, Mapping):
        _add_generic_issue(errors, f"{name} must be a mapping", name=name, code="invalid_metadata")
        return
    _validate_json_value(name, metadata, errors)


def _validate_json_value(name: str, value: Any, errors: list[ManifestValidationIssue]) -> None:
    if isinstance(value, Mapping):
        for key, subvalue in value.items():
            if not isinstance(key, str) or not key:
                _add_generic_issue(
                    errors,
                    f"{name} metadata keys must be non-empty strings",
                    name=name,
                    code="invalid_metadata_key",
                    details={"key": key},
                )
                continue
            if key in _RESERVED_METADATA_KEYS:
                _add_generic_issue(
                    errors,
                    f"{name} uses reserved metadata key: {key!r}",
                    name=f"{name}.{key}",
                    code="reserved_metadata_key",
                    details={"key": key},
                )
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
    _add_generic_issue(
        errors,
        f"{name} contains non-JSON-serializable value {value!r}",
        name=name,
        code="metadata_not_json_serializable",
        details={"value_repr": repr(value)},
    )


def _validate_cycles(
    nodes: Iterable[WorkflowNode],
    edges: Iterable[WorkflowEdge],
    manifest_policy: WorkflowPolicy | None,
    errors: list[ManifestValidationIssue],
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
                    _add_issue(
                        errors,
                        "arbitrary graph cycles are invalid; edge "
                        f"{edge.id!r} closes cycle {' -> '.join(cycle_nodes)} "
                        "without an explicit bounded reentry route",
                        code="arbitrary_cycle",
                        field="edges[]",
                        edge_id=edge.id,
                        details={"cycle": cycle_nodes},
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
