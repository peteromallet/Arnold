"""Capsule Definition identity projection helpers.

Rehomed from ``arnold_pipelines.megaplan._pipeline.behavioral_manifest``
during M3 burn-down (T15).  Only the projection functions consumed by
``store/capsule.py`` are carried forward; the full static-behavioral-manifest
builder remains in the legacy module for internal ``_pipeline`` consumers
until M4.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

SCHEMA_VERSION = 1


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    """Return stable JSON bytes for identity projections."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def capsule_definition_identity_projection(
    *,
    static_behavioral_hash: str,
    runtime_topology_hash: str | None = None,
) -> dict[str, object]:
    """Return the canonical Capsule Definition identity inputs.

    Runtime topology is intentionally additive.  Static-only definitions keep
    the static source identity but are marked non-replay-ready until a trusted
    runtime topology hash is available.
    """
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "projection": "megaplan.capsule-definition-identity",
        "static_behavioral_hash": static_behavioral_hash,
        "runtime_topology_hash": runtime_topology_hash,
        "identity_mode": "static+runtime-topology"
        if runtime_topology_hash
        else "static-only",
        "replay_ready": bool(runtime_topology_hash),
    }
    canonical = canonical_json_bytes(payload)
    return {
        **payload,
        "canonical_bytes": canonical,
        "definition_identity_hash": "sha256:" + hashlib.sha256(canonical).hexdigest(),
    }
