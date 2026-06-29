"""Neutral kernel identity contracts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


_ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_HASH_PREFIX = "sha256:"


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_hash(field_name: str, value: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a sha256 content hash")
    if not value.startswith(_HASH_PREFIX) or len(value) != len(_HASH_PREFIX) + 64:
        raise ValueError(f"{field_name} must be a sha256 content hash")
    try:
        int(value[len(_HASH_PREFIX) :], 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a sha256 content hash") from exc


def _canonical_hash(field_name: str, value: str) -> str:
    _validate_hash(field_name, value)
    return value.lower()


def _canonical_alias(value: str) -> str:
    if not isinstance(value, str) or not _ALIAS_RE.fullmatch(value):
        raise ValueError(
            "workflow alias must start with a letter and contain only letters, "
            "digits, '_', '.', or '-'"
        )
    return value


def _validate_required(field_name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


@dataclass(frozen=True, order=True)
class RunId:
    """Stable run identifier supplied by execution."""

    value: str


@dataclass(frozen=True, order=True)
class ReentryId:
    """Stable identifier for resuming from a suspension point."""

    value: str


@dataclass(frozen=True, order=True)
class WorkflowIdentity:
    """Canonical runtime identity anchor for a workflow manifest."""

    alias: str
    manifest_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "alias", _canonical_alias(self.alias))
        object.__setattr__(self, "manifest_hash", _canonical_hash("manifest_hash", self.manifest_hash))

    @property
    def pipeline_identity(self) -> str:
        return _derive_pipeline_identity_unchecked(self.alias, self.manifest_hash)

    @property
    def registry_runtime_id(self) -> str:
        return derive_registry_runtime_id(self.alias, self.manifest_hash)

    @property
    def discovery_pipeline_id(self) -> str:
        return derive_discovery_pipeline_id(self.alias, self.manifest_hash)

    @property
    def tenant_id(self) -> str:
        return derive_workflow_tenant_id(self.alias, self.manifest_hash)

    @property
    def generated_artifact_identity_header_fields(self) -> dict[str, str]:
        return generated_artifact_identity_header_fields(self.alias, self.manifest_hash)

    @property
    def judge_sidecar_cross_reference_identity(self) -> str:
        return derive_judge_sidecar_cross_reference_identity(self.alias, self.manifest_hash)

    def to_dict(self) -> dict[str, str]:
        return {
            "alias": self.alias,
            "manifest_hash": self.manifest_hash,
            "pipeline_identity": self.pipeline_identity,
        }


def _derive_pipeline_identity_unchecked(alias: str, manifest_hash: str) -> str:
    return _sha256_text(f"workflow:{alias}@{manifest_hash}")


def derive_pipeline_identity(alias: str, manifest_hash: str) -> str:
    """Derive the canonical runtime pipeline identity."""

    return WorkflowIdentity(alias=alias, manifest_hash=manifest_hash).pipeline_identity


def workflow_identity(alias: str, manifest_hash: str) -> WorkflowIdentity:
    """Build the canonical workflow identity from explicit runtime inputs."""

    return WorkflowIdentity(alias=alias, manifest_hash=manifest_hash)


def workflow_identity_from_manifest(
    manifest: Any | None = None,
    *,
    id: str | None = None,
    workflow_id: str | None = None,
    manifest_hash: str | None = None,
) -> WorkflowIdentity:
    """Adapt a WorkflowManifest-shaped object or explicit id/hash pair."""

    if id is not None:
        if workflow_id is not None:
            raise ValueError("pass only one of id or workflow_id")
        workflow_id = id
    if manifest is not None:
        if workflow_id is not None or manifest_hash is not None:
            raise ValueError("pass either manifest or explicit workflow_id plus manifest_hash")
        workflow_id = getattr(manifest, "id", None)
        manifest_hash = getattr(manifest, "manifest_hash", None)
    if not isinstance(workflow_id, str) or not isinstance(manifest_hash, str):
        raise ValueError("workflow_id and manifest_hash are required")
    return WorkflowIdentity(alias=workflow_id, manifest_hash=manifest_hash)


def derive_registry_runtime_id(alias: str, manifest_hash: str) -> str:
    """Derive the registry runtime id from the workflow alias/hash pair."""

    identity = WorkflowIdentity(alias=alias, manifest_hash=manifest_hash)
    return _sha256_text(f"workflow-registry:{identity.alias}@{identity.manifest_hash}")


def derive_registry_runtime_pipeline_id(alias: str, manifest_hash: str) -> str:
    """Derive the registry runtime id from the workflow alias/hash pair."""

    return derive_registry_runtime_id(alias, manifest_hash)


def derive_discovery_pipeline_id(alias: str, manifest_hash: str) -> str:
    """Derive the discovery runtime pipeline_id from the workflow alias/hash pair."""

    identity = WorkflowIdentity(alias=alias, manifest_hash=manifest_hash)
    return _sha256_text(f"workflow-discovery:{identity.alias}@{identity.manifest_hash}")


def derive_discovery_runtime_pipeline_id(alias: str, manifest_hash: str) -> str:
    """Derive the discovery runtime pipeline_id from the workflow alias/hash pair."""

    return derive_discovery_pipeline_id(alias, manifest_hash)


def derive_workflow_tenant_id(alias: str, manifest_hash: str) -> str:
    """Derive the workflow tenant id from the workflow alias/hash pair."""

    identity = WorkflowIdentity(alias=alias, manifest_hash=manifest_hash)
    return "workflow_" + hashlib.sha256(
        f"workflow-tenant:{identity.alias}@{identity.manifest_hash}".encode("utf-8")
    ).hexdigest()[:24]


def generated_artifact_identity_header_fields(alias: str, manifest_hash: str) -> dict[str, str]:
    """Return generated artifact identity header fields for a workflow run."""

    identity = WorkflowIdentity(alias=alias, manifest_hash=manifest_hash)
    return {
        "workflow_alias": identity.alias,
        "manifest_hash": identity.manifest_hash,
        "pipeline_identity": identity.pipeline_identity,
    }


def generated_artifact_identity_headers(alias: str, manifest_hash: str) -> dict[str, str]:
    """Return generated artifact identity header fields for a workflow run."""

    return generated_artifact_identity_header_fields(alias, manifest_hash)


def derive_generated_artifact_identity_header_fields(alias: str, manifest_hash: str) -> dict[str, str]:
    """Return generated artifact identity header fields for a workflow run."""

    return generated_artifact_identity_header_fields(alias, manifest_hash)


def derive_generated_artifact_identity_headers(alias: str, manifest_hash: str) -> dict[str, str]:
    """Return generated artifact identity header fields for a workflow run."""

    return generated_artifact_identity_header_fields(alias, manifest_hash)


def derive_judge_sidecar_cross_reference_identity(alias: str, manifest_hash: str) -> str:
    """Derive the judge sidecar cross-reference identity for a workflow."""

    identity = WorkflowIdentity(alias=alias, manifest_hash=manifest_hash)
    return _sha256_text(f"workflow-judge-sidecar:{identity.alias}@{identity.manifest_hash}")


def derive_judge_manifest_cross_reference_identity(alias: str, manifest_hash: str) -> str:
    """Derive the judge manifest cross-reference identity for a workflow."""

    return derive_judge_sidecar_cross_reference_identity(alias, manifest_hash)


def derive_idempotency_key(*parts: str) -> str:
    """Derive a deterministic idempotency key from ordered string parts."""

    if not parts or any(part == "" for part in parts):
        raise ValueError("idempotency key parts must be non-empty")
    return _sha256_text("\x1f".join(parts))


class JudgeManifestRelationship(StrEnum):
    """Supported neutral relationships between judges and workflow manifests."""

    JUDGES_WORKFLOW = "judges_workflow"
    REVIEWED_BY_JUDGE = "reviewed_by_judge"


@dataclass(frozen=True, order=True)
class JudgeManifestCrossReference:
    """Immutable link between a judge manifest and a workflow manifest."""

    relationship: JudgeManifestRelationship
    manifest_hash: str
    piece_version: str
    judge_version: str
    rubric_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.relationship, JudgeManifestRelationship):
            try:
                object.__setattr__(
                    self,
                    "relationship",
                    JudgeManifestRelationship(self.relationship),
                )
            except ValueError as exc:
                raise ValueError("relationship must be a known judge manifest relationship") from exc
        _validate_hash("manifest_hash", self.manifest_hash)
        _validate_required("piece_version", self.piece_version)
        _validate_required("judge_version", self.judge_version)
        _validate_hash("rubric_hash", self.rubric_hash)

    def to_dict(self) -> dict[str, str]:
        return {
            "judge_version": self.judge_version,
            "manifest_hash": self.manifest_hash,
            "piece_version": self.piece_version,
            "relationship": self.relationship.value,
            "rubric_hash": self.rubric_hash,
        }
