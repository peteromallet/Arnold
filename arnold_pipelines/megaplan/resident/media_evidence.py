"""Typed-media evidence emission for resident domains.

The resident evidence contract (B12) requires every produced artifact to be
recorded as typed evidence in the resident store together with the
``MediaUsage`` cost entries that account for it.  This module is the single
write surface: ``emit_media_evidence`` appends one evidence system-log record
per artifact plus one cost record per media unit into the store.  The
manifest, ledger, notifications, heartbeat, watchdog, and restart-recovery
paths all consume the same store records, so emitting into the store covers
every downstream surface.

Typed media content types recognized by the contract:

- ``video/mp4`` — video outputs;
- ``audio/wav`` — audio outputs;
- ``x-astrid-timeline`` — the Astrid project timeline document.

``MediaUsage`` units follow ``arnold.runtime.costing.media_cost.MediaUsage``:
``video_second``, ``audio_second``, ``image``, ``token``, and the Astrid
``timeline_document`` unit for timeline artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.types import CliError

MEDIA_EVIDENCE_CATEGORY = "system"
MEDIA_EVIDENCE_EVENT_TYPE = "typed_media_evidence"
MEDIA_COST_CATEGORY = "system"
MEDIA_COST_EVENT_TYPE = "media_usage_cost"

TIMELINE_DOCUMENT_UNIT = "timeline_document"

# Content type -> default MediaUsage unit (override per artifact if needed).
CONTENT_TYPE_UNIT: Mapping[str, str] = {
    "video/mp4": "video_second",
    "audio/wav": "audio_second",
    "x-astrid-timeline": TIMELINE_DOCUMENT_UNIT,
    "application/json": "document",
}


@dataclass(frozen=True)
class MediaEvidence:
    """One typed-media artifact evidence record."""

    artifact_path: str
    content_type: str
    size_bytes: int
    digest: str
    producer_tool: str
    run_id: str | None = None
    stage_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_path": self.artifact_path,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "digest": self.digest,
            "producer_tool": self.producer_tool,
            "run_id": self.run_id,
            "stage_id": self.stage_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MediaUsageRecord:
    """One ``MediaUsage`` cost entry for a typed-media artifact."""

    unit: str
    count: float
    content_type: str
    artifact_path: str
    run_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit": self.unit,
            "count": float(self.count),
            "content_type": self.content_type,
            "artifact_path": self.artifact_path,
            "run_id": self.run_id,
        }


def default_media_usage(
    evidence: MediaEvidence,
    *,
    count: float | None = None,
) -> MediaUsageRecord:
    """Derive the canonical MediaUsage record for an evidence artifact."""
    unit = CONTENT_TYPE_UNIT.get(evidence.content_type, "document")
    if count is None:
        count = 1.0
    return MediaUsageRecord(
        unit=unit,
        count=count,
        content_type=evidence.content_type,
        artifact_path=evidence.artifact_path,
        run_id=evidence.run_id,
    )


def compute_file_digest(path: Path, *, algorithm: str = "sha256") -> str:
    """Digest a produced artifact file (used as the evidence record digest)."""
    import hashlib

    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_content_type(content_type: str) -> None:
    if content_type not in CONTENT_TYPE_UNIT:
        raise CliError(
            "invalid_args",
            f"unsupported media content type {content_type!r}; "
            f"supported: {sorted(CONTENT_TYPE_UNIT)}",
        )


def emit_media_evidence(
    store: Any,
    *,
    evidence: MediaEvidence,
    usage: MediaUsageRecord | None = None,
    turn_id: str | None = None,
    epic_id: str | None = None,
) -> dict[str, Any]:
    """Emit one typed-media evidence record + MediaUsage cost into the store.

    ``store`` is any megaplan ``Store`` implementation (FileStore/DBStore).
    Two store records are appended:

    - a system log with category ``media_evidence`` carrying the artifact
      metadata, digest, producer tool, and stage;
    - a system log with category ``media_usage_cost`` carrying the
      ``MediaUsage`` unit/count and content type.

    Returns the serialized evidence record (also usable as a manifest entry).
    """
    _validate_content_type(evidence.content_type)
    usage_record = usage or default_media_usage(evidence)

    details = {
        **evidence.as_dict(),
        "media_usage": usage_record.as_dict(),
    }
    evidence_log = store.log_system_event(
        level="info",
        category=MEDIA_EVIDENCE_CATEGORY,
        event_type=MEDIA_EVIDENCE_EVENT_TYPE,
        message=(
            f"typed media evidence {evidence.content_type} "
            f"{Path(evidence.artifact_path).name}"
        ),
        details=details,
        turn_id=turn_id,
        epic_id=epic_id,
        idempotency_key=f"media-evidence:{evidence.digest}",
    )
    cost_log = store.log_system_event(
        level="info",
        category=MEDIA_COST_CATEGORY,
        event_type=MEDIA_COST_EVENT_TYPE,
        message=f"MediaUsage {usage_record.unit}={usage_record.count}",
        details=usage_record.as_dict(),
        turn_id=turn_id,
        epic_id=epic_id,
        idempotency_key=f"media-usage:{evidence.digest}:{usage_record.unit}",
    )
    return {
        "evidence_log_id": getattr(evidence_log, "id", None),
        "cost_log_id": getattr(cost_log, "id", None),
        "evidence": details,
    }


def list_media_evidence(
    store: Any,
    *,
    limit: int = 50,
) -> Sequence[dict[str, Any]]:
    """Return recent typed-media evidence records from the resident store."""
    records: list[dict[str, Any]] = []
    reader = getattr(store, "_system_logs", None)
    if reader is None:
        return records
    for entry in reader():
        if getattr(entry, "event_type", None) != MEDIA_EVIDENCE_EVENT_TYPE:
            continue
        payload = getattr(entry, "details", None) or {}
        if isinstance(payload, dict):
            records.append(payload)
    return records[-limit:]
