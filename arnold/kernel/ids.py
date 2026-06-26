"""Neutral kernel identity contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum


_HASH_PREFIX = "sha256:"


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_hash(field_name: str, value: str) -> None:
    if not value.startswith(_HASH_PREFIX) or len(value) != len(_HASH_PREFIX) + 64:
        raise ValueError(f"{field_name} must be a sha256 content hash")
    try:
        int(value[len(_HASH_PREFIX) :], 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a sha256 content hash") from exc


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


def derive_pipeline_identity(alias: str, manifest_hash: str) -> str:
    """Derive the canonical runtime pipeline identity."""

    return _sha256_text(f"workflow:{alias}@{manifest_hash}")


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
