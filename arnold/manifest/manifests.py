"""Workflow manifest v1 contract.

The manifest contract is a neutral, serializable description of workflow
topology and execution policy slots.  It deliberately does not execute nodes,
compile a DSL, or import product pipeline modules.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, ClassVar, Mapping, TypeVar, get_args, get_origin, get_type_hints

from arnold.manifest.refs import SourceSpan, canonical_alias

_HASH_PREFIX = "sha256:"
_T = TypeVar("_T")

# Repository root for the installed Arnold package.  Used to normalize
# absolute paths (e.g. prompt_bundle directories) so manifest hashes are
# independent of where the repo is checked out.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256_json(value: Mapping[str, Any]) -> str:
    encoded = canonical_json(value).encode("utf-8")
    return _HASH_PREFIX + hashlib.sha256(encoded).hexdigest()


def canonical_json(value: Mapping[str, Any]) -> str:
    """Return the canonical JSON representation used for manifest hashing."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(subvalue)
            for key, subvalue in sorted(value.items(), key=lambda item: str(item[0]))
            if subvalue is not None
        }
    if isinstance(value, (tuple, list)):
        return [_normalize(item) for item in value]
    return value


def _strip_hashes(payload: dict[str, Any]) -> dict[str, Any]:
    stripped = dict(payload)
    stripped.pop("manifest_hash", None)
    stripped.pop("topology_hash", None)
    return stripped


@dataclass(frozen=True)
class CapabilityRequirement:
    """A neutral capability requirement named by product-owned policy later."""

    capability_id: str
    route: str = "default"
    required: bool = True


@dataclass(frozen=True)
class BudgetPolicy:
    """Budget carrier for later governors."""

    max_cost: float | None = None
    max_seconds: float | None = None
    max_attempts: int | None = None
    token_budget: int | None = None


@dataclass(frozen=True)
class RetryPolicy:
    """Retry slot; algorithms are intentionally runner-owned."""

    max_attempts: int = 1
    backoff: str = "none"
    retry_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoopPolicy:
    """Loop slot for bounded iterative topology."""

    max_iterations: int | None = None
    until_ref: str | None = None


@dataclass(frozen=True)
class FanoutPolicy:
    """Fanout/reducer slot for parallel topology."""

    mode: str = "static"
    width: int | None = None
    reducer_ref: str | None = None


@dataclass(frozen=True)
class IdempotencyPolicy:
    """Neutral idempotency key contract for replay-safe effects."""

    key_ref: str | None = None
    key_template: str | None = None
    required: bool = True


@dataclass(frozen=True)
class EffectRef:
    """String-keyed external effect reference resolved by runtime registries."""

    effect_id: str
    route: str = "default"
    payload_ref: str | None = None
    payload_schema_hash: str | None = None
    idempotency: IdempotencyPolicy | None = None


@dataclass(frozen=True)
class CompensationTarget:
    """Declared compensation target, ordered by manifest position."""

    target_id: str
    effect: EffectRef
    condition_ref: str | None = None
    idempotency: IdempotencyPolicy | None = None


@dataclass(frozen=True)
class CompensationPolicy:
    """Compensation slots; execution order is runner-owned."""

    targets: tuple[CompensationTarget, ...] = ()
    scope_ref: str | None = None
    trigger_on: tuple[str, ...] = ()
    idempotency: IdempotencyPolicy | None = None


@dataclass(frozen=True)
class EscalationPolicy:
    """Escalation routing data without product-specific meanings."""

    targets: tuple[str, ...] = ()
    escalate_after_attempts: int | None = None
    policy_ref: str | None = None
    backoff: str = "none"


@dataclass(frozen=True)
class TimingPolicy:
    """Runtime timing limits for timeout, deadline, and TTL handling."""

    timeout_seconds: float | None = None
    deadline_ref: str | None = None
    ttl_seconds: float | None = None


@dataclass(frozen=True)
class ReducerRef:
    """String-keyed reducer reference resolved by runtime registries."""

    reducer_id: str
    input_ref: str | None = None
    output_ref: str | None = None


@dataclass(frozen=True)
class ControlTransitionSlot:
    """Generic control transition record slot."""

    transition_id: str
    transition_type: str
    trigger_ref: str | None = None
    target_ref: str | None = None
    payload_schema_hash: str | None = None
    policy_ref: str | None = None
    idempotency: IdempotencyPolicy | None = None


@dataclass(frozen=True)
class TopologyOverlaySlot:
    """Runtime topology overlay slot recorded as control data, not mutation."""

    overlay_id: str
    overlay_type: str
    source_ref: str | None = None
    target_refs: tuple[str, ...] = ()
    condition_ref: str | None = None
    payload_schema_hash: str | None = None


@dataclass(frozen=True)
class AuthorityRequirement:
    """Authority contract required before a runtime mutation is accepted."""

    authority_id: str
    action: str
    evidence_schema_hash: str | None = None
    capability_id: str | None = None


@dataclass(frozen=True)
class SubpipelineRef:
    """Reference to a nested manifest, not an embedded runner."""

    manifest_hash: str
    alias: str | None = None


@dataclass(frozen=True)
class SuspensionRoute:
    """Generic suspension route, distinct from any human-specific policy."""

    route_id: str
    capability_id: str | None = None
    reentry_id: str | None = None
    payload_schema_hash: str | None = None
    resume_schema_hash: str | None = None
    resume_schema_ref: str | None = None
    resume_payload_ref: str | None = None


@dataclass(frozen=True)
class WorkflowPolicy:
    """Per-node or manifest-level policy slots."""

    budget: BudgetPolicy | None = None
    retry: RetryPolicy | None = None
    loop: LoopPolicy | None = None
    fanout: FanoutPolicy | None = None
    timing: TimingPolicy | None = None
    idempotency: IdempotencyPolicy | None = None
    effects: tuple[EffectRef, ...] = ()
    reducers: tuple[ReducerRef, ...] = ()
    compensation: CompensationPolicy | None = None
    escalation: EscalationPolicy | None = None
    control_transitions: tuple[ControlTransitionSlot, ...] = ()
    topology_overlays: tuple[TopologyOverlaySlot, ...] = ()
    authority: tuple[AuthorityRequirement, ...] = ()
    suspension_routes: tuple[SuspensionRoute, ...] = ()


@dataclass(frozen=True)
class WorkflowNode:
    """A manifest node with neutral execution coordinates."""

    id: str
    kind: str
    label: str | None = None
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    capabilities: tuple[CapabilityRequirement, ...] = ()
    policy: WorkflowPolicy | None = None
    source_span: SourceSpan | None = None
    subpipeline: SubpipelineRef | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEdge:
    """Directed manifest edge."""

    id: str
    source: str
    target: str
    label: str = "default"
    condition_ref: str | None = None
    source_span: SourceSpan | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowManifest:
    """Versioned workflow manifest.

    ``id`` is the human-chosen alias. ``manifest_hash`` is computed from the
    canonical manifest body and is the runtime discriminator used by events,
    replay, registries, and deletion gates.
    """

    SCHEMA_VERSION: ClassVar[str] = "arnold.workflow.manifest.v1"

    id: str
    nodes: tuple[WorkflowNode, ...]
    edges: tuple[WorkflowEdge, ...] = ()
    schema_version: str = SCHEMA_VERSION
    version: str | None = None
    capabilities: tuple[CapabilityRequirement, ...] = ()
    policy: WorkflowPolicy | None = None
    source_span: SourceSpan | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    topology_hash: str | None = None
    manifest_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", canonical_alias(self.id))
        object.__setattr__(self, "nodes", tuple(sorted(self.nodes, key=lambda node: node.id)))
        object.__setattr__(self, "edges", tuple(sorted(self.edges, key=lambda edge: edge.id)))
        computed_topology = compute_topology_hash(self)
        computed_manifest = compute_manifest_hash(self)
        if self.topology_hash is None:
            object.__setattr__(self, "topology_hash", computed_topology)
        if self.manifest_hash is None:
            object.__setattr__(self, "manifest_hash", computed_manifest)

    def to_dict(self, *, include_hashes: bool = True) -> dict[str, Any]:
        payload = _normalize(self)
        if not include_hashes:
            return _strip_hashes(payload)
        return payload

    def to_json(self) -> str:
        """Serialize using canonical JSON."""

        return canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> "WorkflowManifest":
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("workflow manifest JSON must decode to an object")
        return _decode_dataclass(cls, payload)


def _normalize_for_hash(value: Any) -> Any:
    """Normalize values for stable hashing across checkouts.

    - Removes source-span fields (they contain absolute paths).
    - Rewrites absolute paths under the repo root to relative paths.
    - Drops None values.
    """
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_for_hash(subvalue)
            for key, subvalue in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) != "source_span" and subvalue is not None
        }
    if isinstance(value, (tuple, list)):
        return [_normalize_for_hash(item) for item in value]
    if isinstance(value, str):
        try:
            p = Path(value)
            if p.is_absolute() and _REPO_ROOT in p.parents:
                return str(p.relative_to(_REPO_ROOT).as_posix())
        except (ValueError, OSError):
            pass
    return value


def compute_manifest_hash(manifest: WorkflowManifest) -> str:
    """Compute a stable hash over the manifest body, excluding hash fields."""

    return _sha256_json(_normalize_for_hash(manifest.to_dict(include_hashes=False)))


def compute_topology_hash(manifest: WorkflowManifest) -> str:
    """Compute a stable hash over topology-defining fields only."""

    topology = {
        "schema_version": manifest.schema_version,
        "id": manifest.id,
        "nodes": [
            {
                "id": node.id,
                "kind": node.kind,
                "inputs": tuple(node.inputs),
                "outputs": tuple(node.outputs),
                "subpipeline": node.subpipeline,
            }
            for node in sorted(manifest.nodes, key=lambda item: item.id)
        ],
        "edges": [
            {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "label": edge.label,
                "condition_ref": edge.condition_ref,
            }
            for edge in sorted(manifest.edges, key=lambda item: item.id)
        ],
    }
    return _sha256_json(_normalize(topology))


def _decode_dataclass(cls: type[_T], payload: Mapping[str, Any]) -> _T:
    kwargs: dict[str, Any] = {}
    type_hints = get_type_hints(cls)
    for item in fields(cls):
        if item.name not in payload:
            continue
        kwargs[item.name] = _decode_value(type_hints[item.name], payload[item.name])
    return cls(**kwargs)


def _decode_value(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is tuple and args:
        inner = args[0]
        return tuple(_decode_value(inner, item) for item in value)
    if origin is dict or origin is Mapping:
        return dict(value)
    if origin is type(None):
        return None
    if origin is not None and type(None) in args:
        non_none = [arg for arg in args if arg is not type(None)][0]
        if value is None:
            return None
        return _decode_value(non_none, value)
    if isinstance(annotation, type) and is_dataclass(annotation):
        if not isinstance(value, Mapping):
            raise ValueError(f"expected object for {annotation.__name__}")
        return _decode_dataclass(annotation, value)
    return value
