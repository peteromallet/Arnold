"""Megaplan content-type registration and artifact adapter helpers.

All Megaplan product schemas are declared here and registered through the
neutral ``arnold.kernel.content_types.ContentTypeRegistry``.  The neutral
kernel has no knowledge of these content types; it only carries opaque
``content_type_id`` strings and schema hashes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.kernel import GeneratedArtifactProvenance
from arnold.kernel.artifacts import ArtifactBinding
from arnold.kernel.content_types import (
    ContentTypeRegistration,
    ContentTypeRegistry,
    RetentionPolicy,
    schema_hash,
)

# ---------------------------------------------------------------------------
# Canonical Megaplan content-type identifiers
# ---------------------------------------------------------------------------

PLAN_CONTENT_TYPE = "application/x-megaplan-plan+json"
RECEIPT_CONTENT_TYPE = "application/x-megaplan-receipt+json"
CAPSULE_CONTENT_TYPE = "application/x-megaplan-capsule+json"
DELTA_CONTENT_TYPE = "application/x-megaplan-delta+json"
GATE_SIGNAL_CONTENT_TYPE = "application/x-megaplan-gate-signal+json"
REVIEW_OUTPUT_CONTENT_TYPE = "application/x-megaplan-review-output+json"
EXECUTION_EVIDENCE_CONTENT_TYPE = "application/x-megaplan-execution-evidence+json"
STATE_ARTIFACT_CONTENT_TYPE = "application/x-megaplan-state-artifact+json"


# ---------------------------------------------------------------------------
# Schema documents (stable, versioned)
# ---------------------------------------------------------------------------

_PLAN_SCHEMA = {
    "type": "object",
    "required": ["plan_text", "version"],
    "properties": {
        "plan_text": {"type": "string"},
        "version": {"type": "integer"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "success_criteria": {"type": "array"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
}

_RECEIPT_SCHEMA = {
    "type": "object",
    "required": ["step", "success"],
    "properties": {
        "step": {"type": "string"},
        "success": {"type": "boolean"},
        "summary": {"type": "string"},
        "artifacts": {"type": "array", "items": {"type": "string"}},
    },
}

_CAPSULE_SCHEMA = {
    "type": "object",
    "required": ["capsule_hash"],
    "properties": {
        "capsule_hash": {"type": "string"},
        "completeness": {"type": "string"},
        "replay_ready": {"type": "boolean"},
        "record_count": {"type": "integer"},
    },
}

_DELTA_SCHEMA = {
    "type": "object",
    "required": ["from_version", "to_version"],
    "properties": {
        "from_version": {"type": "integer"},
        "to_version": {"type": "integer"},
        "diff": {"type": "string"},
        "flags_addressed": {"type": "array"},
    },
}

_GATE_SIGNAL_SCHEMA = {
    "type": "object",
    "required": ["signals"],
    "properties": {
        "signals": {"type": "object"},
        "robustness": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "criteria_check": {"type": "object"},
        "preflight_results": {"type": "object"},
        "unresolved_flags": {"type": "array"},
    },
}

_REVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["verdict"],
    "properties": {
        "verdict": {"type": "string"},
        "rework_items": {"type": "array"},
        "summary": {"type": "string"},
    },
}

_EXECUTION_EVIDENCE_SCHEMA = {
    "type": "object",
    "required": ["tasks"],
    "properties": {
        "tasks": {"type": "array"},
        "status": {"type": "string"},
        "artifacts": {"type": "array", "items": {"type": "string"}},
    },
}

_STATE_ARTIFACT_SCHEMA = {
    "type": "object",
    "required": ["name", "current_state", "iteration"],
    "properties": {
        "name": {"type": "string"},
        "current_state": {"type": "string"},
        "iteration": {"type": "integer"},
        "config": {"type": "object"},
        "meta": {"type": "object"},
    },
}


# ---------------------------------------------------------------------------
# Schema versions
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------------------

def build_megaplan_content_type_registry() -> ContentTypeRegistry:
    """Return a registry with all canonical Megaplan content types."""

    registry = ContentTypeRegistry()
    for type_id, schema, retention in (
        (PLAN_CONTENT_TYPE, _PLAN_SCHEMA, RetentionPolicy.RUN),
        (RECEIPT_CONTENT_TYPE, _RECEIPT_SCHEMA, RetentionPolicy.AUDIT),
        (CAPSULE_CONTENT_TYPE, _CAPSULE_SCHEMA, RetentionPolicy.LEGAL_HOLD),
        (DELTA_CONTENT_TYPE, _DELTA_SCHEMA, RetentionPolicy.RUN),
        (GATE_SIGNAL_CONTENT_TYPE, _GATE_SIGNAL_SCHEMA, RetentionPolicy.RUN),
        (REVIEW_OUTPUT_CONTENT_TYPE, _REVIEW_OUTPUT_SCHEMA, RetentionPolicy.RUN),
        (EXECUTION_EVIDENCE_CONTENT_TYPE, _EXECUTION_EVIDENCE_SCHEMA, RetentionPolicy.AUDIT),
        (STATE_ARTIFACT_CONTENT_TYPE, _STATE_ARTIFACT_SCHEMA, RetentionPolicy.AUDIT),
    ):
        registry.register(
            ContentTypeRegistration(
                type_id=type_id,
                schema_version=_SCHEMA_VERSION,
                schema_hash=schema_hash(schema),
                retention_policy=retention,
            )
        )
    return registry


#: Product-wide content-type registry.  Neutral runtime code never imports this.
MEGAPLAN_CONTENT_TYPES = build_megaplan_content_type_registry()


# ---------------------------------------------------------------------------
# Artifact adapter helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ArtifactAdapterContext:
    """Inputs needed to write a versioned Megaplan artifact.

    The artifact root is either ``plan_dir`` (legacy M1 layout) or a manifest
    artifact root supplied by the runtime.
    """

    plan_dir: Path
    artifact_root: Path | None = None

    @property
    def root(self) -> Path:
        return self.artifact_root or self.plan_dir


def _artifact_provenance(
    *,
    artifact_id: str,
    content_type_id: str,
    generator_module: str,
    source_hash: str | None = None,
    parent_artifact_id: str | None = None,
    parent_content_hash: str | None = None,
) -> GeneratedArtifactProvenance:
    from arnold.kernel.artifacts import ProvenanceParent
    from datetime import datetime, timezone

    parents: tuple[ProvenanceParent, ...] = ()
    if parent_artifact_id:
        parents = (
            ProvenanceParent(
                parent_artifact_id=parent_artifact_id,
                content_hash=parent_content_hash or "sha256:" + "0" * 64,
            ),
        )
    return GeneratedArtifactProvenance(
        generator_module=generator_module,
        generator_source_hash=source_hash or "sha256:" + "0" * 64,
        manifest_contract_version="arnold.workflow.manifest.v1",
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        parents=parents,
    )


def _write_json_artifact(
    ctx: ArtifactAdapterContext,
    *,
    artifact_id: str,
    content_type_id: str,
    payload: Mapping[str, Any],
    extension: str = "json",
    generator_module: str = "arnold_pipelines.megaplan.content_types",
    provenance: GeneratedArtifactProvenance | None = None,
) -> ArtifactBinding:
    """Write a JSON artifact using the M1 versioned convention.

    M1 convention: ``<plan_dir>/<artifact_id>_<version>.<extension>`` for
    versioned artifacts, or ``<plan_dir>/<artifact_id>.<extension>`` for
    unversioned singletons.  For manifest-backed runs the artifact root is used
    directly.
    """

    from arnold.kernel.artifacts import FileBackedArtifactStore

    store = FileBackedArtifactStore(ctx.root, content_type_registry=MEGAPLAN_CONTENT_TYPES)
    content = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if provenance is None:
        provenance = _artifact_provenance(
            artifact_id=artifact_id,
            content_type_id=content_type_id,
            generator_module=generator_module,
            source_hash="sha256:" + hashlib_sha256(content),
        )
    return store.write_artifact(
        artifact_id=artifact_id,
        content=content,
        content_type_id=content_type_id,
        provenance=provenance,
        extension=extension,
    )


def hashlib_sha256(data: bytes) -> str:
    """Return the hex digest for bytes."""

    import hashlib

    return hashlib.sha256(data).hexdigest()


def write_plan_artifact(
    ctx: ArtifactAdapterContext,
    *,
    artifact_id: str,
    plan_text: str,
    version: int,
    questions: list[str] | None = None,
    success_criteria: list[Any] | None = None,
    assumptions: list[str] | None = None,
) -> ArtifactBinding:
    """Write a versioned Megaplan plan artifact."""

    versioned_id = f"{artifact_id}_v{version}"
    payload = {
        "plan_text": plan_text.rstrip() + "\n",
        "version": version,
        "questions": list(questions or []),
        "success_criteria": list(success_criteria or []),
        "assumptions": list(assumptions or []),
    }
    return _write_json_artifact(
        ctx,
        artifact_id=versioned_id,
        content_type_id=PLAN_CONTENT_TYPE,
        payload=payload,
    )


def write_receipt_artifact(
    ctx: ArtifactAdapterContext,
    *,
    step: str,
    success: bool,
    summary: str,
    artifacts: list[str] | None = None,
    artifact_id: str | None = None,
) -> ArtifactBinding:
    """Write a step receipt artifact."""

    payload = {
        "step": step,
        "success": success,
        "summary": summary,
        "artifacts": list(artifacts or []),
    }
    return _write_json_artifact(
        ctx,
        artifact_id=artifact_id or f"receipt_{step}",
        content_type_id=RECEIPT_CONTENT_TYPE,
        payload=payload,
    )


def write_gate_signal_artifact(
    ctx: ArtifactAdapterContext,
    *,
    version: int,
    signals: Mapping[str, Any],
    robustness: str,
    preflight_results: Mapping[str, Any] | None = None,
    unresolved_flags: list[Any] | None = None,
    warnings: list[str] | None = None,
) -> ArtifactBinding:
    """Write a gate-signals artifact following the M1 ``gate_signals_vN.json`` name."""

    payload = {
        "signals": dict(signals),
        "robustness": robustness,
        "warnings": list(warnings or []),
        "criteria_check": {},
        "preflight_results": dict(preflight_results or {}),
        "unresolved_flags": list(unresolved_flags or []),
    }
    return _write_json_artifact(
        ctx,
        artifact_id=f"gate_signals_v{version}",
        content_type_id=GATE_SIGNAL_CONTENT_TYPE,
        payload=payload,
    )


def write_state_artifact(
    ctx: ArtifactAdapterContext,
    *,
    state: Mapping[str, Any],
    artifact_id: str = "state",
) -> ArtifactBinding:
    """Write a migration-surviving state artifact as a read-only projection."""

    payload = {
        "name": state.get("name", ""),
        "current_state": state.get("current_state", ""),
        "iteration": state.get("iteration", 0),
        "config": dict(state.get("config", {})),
        "meta": dict(state.get("meta", {})),
    }
    return _write_json_artifact(
        ctx,
        artifact_id=artifact_id,
        content_type_id=STATE_ARTIFACT_CONTENT_TYPE,
        payload=payload,
    )


__all__ = [
    "CAPSULE_CONTENT_TYPE",
    "DELTA_CONTENT_TYPE",
    "EXECUTION_EVIDENCE_CONTENT_TYPE",
    "GATE_SIGNAL_CONTENT_TYPE",
    "MEGAPLAN_CONTENT_TYPES",
    "PLAN_CONTENT_TYPE",
    "RECEIPT_CONTENT_TYPE",
    "REVIEW_OUTPUT_CONTENT_TYPE",
    "STATE_ARTIFACT_CONTENT_TYPE",
    "ArtifactAdapterContext",
    "build_megaplan_content_type_registry",
    "write_gate_signal_artifact",
    "write_plan_artifact",
    "write_receipt_artifact",
    "write_state_artifact",
]
