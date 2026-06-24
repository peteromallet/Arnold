"""Canonical topology hashing for Arnold pipeline graphs.

``compute_topology_hash(pipeline)`` projects a stable subset of the
pipeline graph into a sorted-JSON canonical form and returns a
content-addressed ``sha256:<hex>`` digest.  The projection is
deliberately narrow so that irrelevant runtime fields (e.g. callable
references, opaque resources) do not perturb the hash.

Projected fields (per the M2 parity contract):
* stage names (sorted)
* entry stage
* edges (per stage: label, target, kind)
* decision vocabularies (per stage)
* override vocabularies (per stage)
* decision routes and suspension schemas (per stage)
* declared ports (per-stage produces / consumes)
* binding map (if present)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    Stage,
)


def _edge_repr(edge: Edge) -> dict[str, str]:
    """Project an Edge to a stable dict for JSON serialization."""
    return {
        "label": edge.label,
        "target": edge.target,
        "kind": edge.kind,
    }


def _port_repr(port: Port) -> dict[str, str]:
    """Project a Port to a stable dict."""
    return {
        "name": port.name,
        "content_type": port.content_type,
    }


def _portref_repr(ref: PortRef) -> dict[str, str]:
    """Project a PortRef to a stable dict."""
    return {
        "port_name": ref.port_name,
        "content_type": ref.content_type,
    }


def _stable_json_value(value: Any) -> Any:
    """Normalize JSON-like structural metadata into deterministic values."""
    if isinstance(value, dict):
        return {
            str(k): _stable_json_value(value[k])
            for k in sorted(value.keys(), key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_stable_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_stable_json_value(item) for item in value),
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ),
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _stage_topology(stage: Stage | ParallelStage) -> dict[str, Any]:
    """Extract the topology-relevant fields from a single stage.

    Callable references (``step``, ``loop_condition``, etc.) are
    deliberately excluded — their identity is not structural.
    """
    base: dict[str, Any] = {
        "name": stage.name,
        "edges": sorted(
            [_edge_repr(e) for e in stage.edges],
            key=lambda e: (e["kind"], e["label"], e["target"]),
        ),
        "decision_vocabulary": sorted(stage.decision_vocabulary),
        "override_vocabulary": sorted(stage.override_vocabulary),
    }

    decision_routes = getattr(stage, "decision_routes", {}) or {}
    if decision_routes:
        base["decision_routes"] = {
            str(label): (None if target is None else str(target))
            for label, target in sorted(decision_routes.items())
        }

    suspension_schema = getattr(stage, "suspension_schema", None)
    if suspension_schema is not None:
        base["suspension_schema"] = _stable_json_value(suspension_schema)

    # Declared ports.
    produces: list[dict[str, str]] = sorted(
        [_port_repr(p) for p in stage.produces],
        key=lambda p: (p["name"], p["content_type"]),
    )
    consumes: list[dict[str, str]] = sorted(
        [_portref_repr(c) for c in stage.consumes],
        key=lambda c: (c["port_name"], c["content_type"]),
    )

    if produces:
        base["produces"] = produces
    if consumes:
        base["consumes"] = consumes

    return base


def compute_topology_hash(pipeline: Pipeline) -> str:
    """Return a ``sha256:<hex>`` topology hash for *pipeline*.

    The hash is constructed from a canonical sorted-JSON projection of:

    * stage names (sorted)
    * entry stage
    * per-stage edges (label, target, kind; sorted)
    * per-stage decision / override vocabularies
    * per-stage decision routes and suspension schemas
    * per-stage declared ports (produces / consumes; sorted, empty omitted)
    * binding map (if present; keys sorted)

    Callable references (``step``, ``loop_condition``, ``join``, etc.)
    are deliberately excluded — they are not structural graph fields.

    Returns:
        A string of the form ``sha256:<64-hex-chars>``.
    """
    stages_projection: dict[str, dict[str, Any]] = {}
    for name in sorted(pipeline.stages.keys()):
        stages_projection[name] = _stage_topology(pipeline.stages[name])

    projection: dict[str, Any] = {
        "entry": pipeline.entry,
        "stages": stages_projection,
    }

    if pipeline.binding_map is not None:
        # Normalize binding_map to a sorted stable form.
        normalized_bindings: dict[str, Any] = {}
        for key in sorted(pipeline.binding_map.keys()):
            value = pipeline.binding_map[key]
            if isinstance(value, dict):
                normalized_bindings[key] = dict(sorted(value.items()))
            else:
                normalized_bindings[key] = value
        projection["binding_map"] = normalized_bindings

    canonical = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = ["compute_topology_hash"]
