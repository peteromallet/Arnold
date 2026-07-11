"""Durable proof of the subjects dispatched in one Megaplan execute batch.

The resolver in this module is deliberately pure.  It accepts already-read
artifact data and plan subject identifiers, and proves the embedded scope from
the versioned record plus the S4 path identity.  In particular, it never reads
``finalize.json`` and never widens an unprovable scope to all plan subjects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from arnold_pipelines.megaplan._core.io import stable_task_id_digest
from arnold_pipelines.megaplan.authority.binding import DispatchIdentity, ResultEnvelope
from arnold_pipelines.run_authority import ContractError

BATCH_SCOPE_KEY = "batch_scope"
BATCH_SCOPE_SCHEMA_VERSION = 1
DISPATCH_IDENTITY_KEY = "dispatch_identity"
RESULT_ENVELOPES_KEY = "result_envelopes"

_S4_BATCH_DIR_RE = re.compile(r"batch_([1-9][0-9]*)")
_S4_TASK_FILE_RE = re.compile(r"tasks_([0-9a-f]{12})\.json")
_SCOPE_FIELDS = frozenset(
    {
        "schema_version",
        "batch_number",
        "task_ids",
        "sense_check_ids",
        "task_set_digest",
    }
)


def _valid_subject_id(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _canonical_subject_ids(values: Iterable[str], *, field: str) -> tuple[str, ...]:
    materialized = tuple(values)
    invalid = [value for value in materialized if not _valid_subject_id(value)]
    if invalid:
        raise ValueError(f"{field} must contain non-empty, whitespace-trimmed strings")
    return tuple(sorted(set(materialized)))


@dataclass(frozen=True, slots=True)
class BatchScope:
    """Immutable, canonical durable scope for one dispatched batch."""

    schema_version: int
    batch_number: int
    task_ids: tuple[str, ...]
    sense_check_ids: tuple[str, ...]
    task_set_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != BATCH_SCOPE_SCHEMA_VERSION:
            raise ValueError(f"unsupported batch scope schema version: {self.schema_version!r}")
        if (
            isinstance(self.batch_number, bool)
            or not isinstance(self.batch_number, int)
            or self.batch_number < 1
        ):
            raise ValueError("batch_number must be a positive integer")
        if not self.task_ids:
            raise ValueError("task_ids must contain at least one task ID")
        if self.task_ids != _canonical_subject_ids(self.task_ids, field="task_ids"):
            raise ValueError("task_ids must be sorted and duplicate-free")
        if self.sense_check_ids != _canonical_subject_ids(
            self.sense_check_ids, field="sense_check_ids"
        ):
            raise ValueError("sense_check_ids must be sorted and duplicate-free")
        expected_digest = stable_task_id_digest(self.task_ids)
        if self.task_set_digest != expected_digest:
            raise ValueError("task_set_digest does not match task_ids")

    @classmethod
    def create(
        cls,
        *,
        batch_number: int,
        task_ids: Iterable[str],
        sense_check_ids: Iterable[str] = (),
    ) -> "BatchScope":
        """Create a canonical record from trusted dispatch inputs.

        Ordering and duplicates in trusted in-memory dispatch inputs do not
        affect durable identity.  The resolver is stricter with persisted
        records and rejects metadata that needed such normalization.
        """

        canonical_tasks = _canonical_subject_ids(task_ids, field="task_ids")
        canonical_checks = _canonical_subject_ids(
            sense_check_ids, field="sense_check_ids"
        )
        return cls(
            schema_version=BATCH_SCOPE_SCHEMA_VERSION,
            batch_number=batch_number,
            task_ids=canonical_tasks,
            sense_check_ids=canonical_checks,
            task_set_digest=stable_task_id_digest(canonical_tasks),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "batch_number": self.batch_number,
            "task_ids": list(self.task_ids),
            "sense_check_ids": list(self.sense_check_ids),
            "task_set_digest": self.task_set_digest,
        }


@dataclass(frozen=True, slots=True)
class BatchScopeQuarantine:
    """Structured explanation for refusing mutation from an artifact."""

    reason: str
    message: str
    source_path: str
    task_ids: tuple[str, ...] = ()
    sense_check_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "reason": self.reason,
            "message": self.message,
            "source_path": self.source_path,
            "task_ids": list(self.task_ids),
            "sense_check_ids": list(self.sense_check_ids),
        }


@dataclass(frozen=True, slots=True)
class BatchScopeResolution:
    """Exactly one of a proven scope or quarantine record."""

    scope: BatchScope | None = None
    quarantine: BatchScopeQuarantine | None = None

    def __post_init__(self) -> None:
        if (self.scope is None) == (self.quarantine is None):
            raise ValueError("resolution must contain exactly one of scope or quarantine")

    @property
    def is_proven(self) -> bool:
        return self.scope is not None


@dataclass(frozen=True, slots=True)
class BatchAuthorityMetadata:
    """Persisted dispatch authority read beside compatibility batch scope."""

    dispatch_identity: DispatchIdentity
    result_envelopes: tuple[ResultEnvelope, ...]


@dataclass(frozen=True, slots=True)
class BatchAuthorityMetadataResolution:
    """Exactly one of decoded authority metadata or a quarantine record."""

    metadata: BatchAuthorityMetadata | None = None
    quarantine: BatchScopeQuarantine | None = None

    def __post_init__(self) -> None:
        if (self.metadata is None) == (self.quarantine is None):
            raise ValueError("resolution must contain exactly one of metadata or quarantine")

    @property
    def is_proven(self) -> bool:
        return self.metadata is not None


def _readable_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if _valid_subject_id(item))


def _quarantine(
    source_path: str,
    reason: str,
    message: str,
    metadata: Mapping[str, Any] | None = None,
) -> BatchScopeResolution:
    return BatchScopeResolution(
        quarantine=BatchScopeQuarantine(
            reason=reason,
            message=message,
            source_path=source_path,
            task_ids=_readable_ids(metadata.get("task_ids")) if metadata else (),
            sense_check_ids=(
                _readable_ids(metadata.get("sense_check_ids")) if metadata else ()
            ),
        )
    )


def _authority_quarantine(
    source_path: str,
    reason: str,
    message: str,
) -> BatchAuthorityMetadataResolution:
    return BatchAuthorityMetadataResolution(
        quarantine=BatchScopeQuarantine(
            reason=reason,
            message=message,
            source_path=source_path,
        )
    )


def resolve_batch_authority_metadata(
    artifact_payload: Mapping[str, Any],
    source_path: str | Path,
) -> BatchAuthorityMetadataResolution:
    """Decode persisted dispatch/result envelopes without using ``batch_scope``.

    ``batch_scope`` remains a compatibility proof for legacy artifact filtering.
    Authority metadata is accepted only from the dispatch identity and result
    envelopes that were persisted beside that proof.
    """

    source = str(source_path)
    raw_identity = artifact_payload.get(DISPATCH_IDENTITY_KEY)
    if raw_identity is None:
        return _authority_quarantine(
            source,
            "missing_dispatch_identity",
            "artifact has no persisted dispatch identity",
        )
    if not isinstance(raw_identity, Mapping):
        return _authority_quarantine(
            source,
            "malformed_dispatch_identity",
            "persisted dispatch identity must be an object",
        )
    try:
        identity = DispatchIdentity.from_dict(raw_identity)
    except ContractError as exc:
        return _authority_quarantine(
            source,
            "malformed_dispatch_identity",
            f"persisted dispatch identity is invalid: {exc}",
        )

    raw_envelopes = artifact_payload.get(RESULT_ENVELOPES_KEY)
    if raw_envelopes is None:
        raw_envelopes = ()
    if not isinstance(raw_envelopes, (list, tuple)):
        return _authority_quarantine(
            source,
            "malformed_result_envelopes",
            "persisted result envelopes must be an array",
        )
    envelopes: list[ResultEnvelope] = []
    for index, raw_envelope in enumerate(raw_envelopes):
        if not isinstance(raw_envelope, Mapping):
            return _authority_quarantine(
                source,
                "malformed_result_envelopes",
                f"persisted result_envelopes[{index}] must be an object",
            )
        try:
            envelope = ResultEnvelope.from_dict(raw_envelope)
        except ContractError as exc:
            return _authority_quarantine(
                source,
                "malformed_result_envelopes",
                f"persisted result_envelopes[{index}] is invalid: {exc}",
            )
        if envelope.dispatch.digest() != identity.digest():
            return _authority_quarantine(
                source,
                "result_envelope_dispatch_mismatch",
                f"persisted result_envelopes[{index}] does not reference the dispatch identity",
            )
        envelopes.append(envelope)

    return BatchAuthorityMetadataResolution(
        metadata=BatchAuthorityMetadata(
            dispatch_identity=identity,
            result_envelopes=tuple(envelopes),
        )
    )


def resolve_batch_scope(
    artifact_payload: Mapping[str, Any],
    source_path: str | Path,
    *,
    known_task_ids: Iterable[str],
    known_sense_check_ids: Iterable[str],
    expected_batch_number: int | None = None,
) -> BatchScopeResolution:
    """Prove embedded batch scope without performing I/O or mutating inputs.

    ``known_*_ids`` are the caller's immutable plan-subject registry, not a
    source from which scope may be reconstructed.  Only subjects explicitly
    present in valid embedded metadata can be returned as proven.
    """

    source = str(source_path)
    raw_metadata = artifact_payload.get(BATCH_SCOPE_KEY)
    if raw_metadata is None:
        return _quarantine(
            source,
            "missing_batch_scope",
            "artifact has no versioned embedded batch scope",
        )
    if not isinstance(raw_metadata, Mapping):
        return _quarantine(
            source,
            "malformed_batch_scope",
            "embedded batch scope must be an object",
        )
    metadata = raw_metadata
    if set(metadata) != _SCOPE_FIELDS:
        return _quarantine(
            source,
            "malformed_batch_scope",
            "embedded batch scope fields do not match schema version 1",
            metadata,
        )

    version = metadata.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        return _quarantine(
            source, "malformed_batch_scope", "schema_version must be an integer", metadata
        )
    if version != BATCH_SCOPE_SCHEMA_VERSION:
        return _quarantine(
            source,
            "unsupported_schema_version",
            f"unsupported embedded batch scope schema version: {version}",
            metadata,
        )

    batch_number = metadata.get("batch_number")
    if (
        isinstance(batch_number, bool)
        or not isinstance(batch_number, int)
        or batch_number < 1
    ):
        return _quarantine(
            source,
            "malformed_batch_scope",
            "batch_number must be a positive integer",
            metadata,
        )

    raw_tasks = metadata.get("task_ids")
    raw_checks = metadata.get("sense_check_ids")
    if not isinstance(raw_tasks, list) or not isinstance(raw_checks, list):
        return _quarantine(
            source,
            "malformed_batch_scope",
            "task_ids and sense_check_ids must be arrays",
            metadata,
        )
    if not raw_tasks:
        return _quarantine(
            source,
            "malformed_batch_scope",
            "task_ids must contain at least one task ID",
            metadata,
        )
    if any(not _valid_subject_id(value) for value in (*raw_tasks, *raw_checks)):
        return _quarantine(
            source,
            "malformed_subject_id",
            "subject IDs must be non-empty, whitespace-trimmed strings",
            metadata,
        )

    task_ids = tuple(raw_tasks)
    sense_check_ids = tuple(raw_checks)
    if task_ids != tuple(sorted(set(task_ids))) or sense_check_ids != tuple(
        sorted(set(sense_check_ids))
    ):
        return _quarantine(
            source,
            "noncanonical_subject_ids",
            "persisted subject IDs must be sorted and duplicate-free",
            metadata,
        )

    known_tasks = frozenset(known_task_ids)
    known_checks = frozenset(known_sense_check_ids)
    unknown_tasks = tuple(task_id for task_id in task_ids if task_id not in known_tasks)
    if unknown_tasks:
        return _quarantine(
            source,
            "unknown_task_ids",
            f"embedded scope contains unknown task IDs: {', '.join(unknown_tasks)}",
            metadata,
        )
    unknown_checks = tuple(
        check_id for check_id in sense_check_ids if check_id not in known_checks
    )
    if unknown_checks:
        return _quarantine(
            source,
            "unknown_sense_check_ids",
            f"embedded scope contains unknown sense-check IDs: {', '.join(unknown_checks)}",
            metadata,
        )

    digest = metadata.get("task_set_digest")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{12}", digest) is None:
        return _quarantine(
            source,
            "malformed_batch_scope",
            "task_set_digest must be a 12-character lowercase hex digest",
            metadata,
        )
    computed_digest = stable_task_id_digest(task_ids)
    if digest != computed_digest:
        return _quarantine(
            source,
            "scope_digest_mismatch",
            "embedded task_set_digest does not match embedded task_ids",
            metadata,
        )

    path = Path(source)
    directory_match = _S4_BATCH_DIR_RE.fullmatch(path.parent.name)
    file_match = _S4_TASK_FILE_RE.fullmatch(path.name)
    if directory_match is None or file_match is None:
        return _quarantine(
            source,
            "invalid_artifact_path",
            "artifact source path is not a canonical S4 batch path",
            metadata,
        )
    path_batch_number = int(directory_match.group(1))
    if batch_number != path_batch_number or (
        expected_batch_number is not None and batch_number != expected_batch_number
    ):
        return _quarantine(
            source,
            "batch_identity_mismatch",
            "embedded, path, and expected batch numbers do not agree",
            metadata,
        )
    if file_match.group(1) != digest:
        return _quarantine(
            source,
            "artifact_digest_mismatch",
            "S4 artifact filename digest does not match embedded batch scope",
            metadata,
        )

    return BatchScopeResolution(
        scope=BatchScope(
            schema_version=version,
            batch_number=batch_number,
            task_ids=task_ids,
            sense_check_ids=sense_check_ids,
            task_set_digest=digest,
        )
    )


__all__ = [
    "BATCH_SCOPE_KEY",
    "BATCH_SCOPE_SCHEMA_VERSION",
    "DISPATCH_IDENTITY_KEY",
    "RESULT_ENVELOPES_KEY",
    "BatchAuthorityMetadata",
    "BatchAuthorityMetadataResolution",
    "BatchScope",
    "BatchScopeQuarantine",
    "BatchScopeResolution",
    "resolve_batch_authority_metadata",
    "resolve_batch_scope",
]
