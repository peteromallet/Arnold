"""Execution-level resume primitives.

This module bridges the kernel's replay/suspension cursors with the
execution runner. It stays product-neutral: it only imports
``arnold.kernel``, ``arnold.manifest``, and the ``arnold.agent`` wire
contracts used by the adapter bridge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.kernel import (
    EventFamily,
    LegacyAliasRecord,
    ManifestReference,
    NDJsonEventJournal,
    ReplayCursor,
    ReplayDecision,
    ReplayResolution,
    SuspensionCursor,
    SuspensionRecord,
    SuspensionState,
    resolve_cursor,
    validate_artifact_content_hashes,
    validate_event_sequence_against_cursor,
    validate_replay_cursor,
    validate_resume_payload,
    validate_suspension_record,
)
from arnold.kernel.events import EventEnvelope
from arnold.manifest import ManifestCursor, NodeRef, WorkflowManifest, manifest_coordinate


@dataclass(frozen=True)
class ResumeRequest:
    """Caller request to resume a workflow run from a durable cursor."""

    run_id: str
    cursor: ReplayCursor
    resume_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResumeOutcome:
    """Result of validating and preparing a resume request."""

    ok: bool
    manifest_cursor: ManifestCursor | None = None
    suspension: SuspensionCursor | None = None
    replay_resolution: ReplayResolution | None = None
    quarantine_reason: str | None = None


def build_resume_manifest_cursor(
    manifest: WorkflowManifest,
    cursor: ReplayCursor,
    *,
    node_ref: str | None = None,
) -> ManifestCursor:
    """Build a runner-facing ManifestCursor from a validated ReplayCursor."""

    coordinate = manifest_coordinate(manifest.id, cursor.manifest_hash)
    return coordinate.cursor(
        node=NodeRef(node_ref) if node_ref is not None else None,
        reentry_id=cursor.reentry_id,
    )


def prepare_resume(
    manifest: WorkflowManifest,
    request: ResumeRequest,
    *,
    artifact_root: str | Path,
    legacy_aliases: Mapping[str, LegacyAliasRecord] | None = None,
    suspension_record: SuspensionRecord | None = None,
    resume_schema_hash: str | None = None,
    resume_validator: Any | None = None,
    expected_artifact_hashes: Mapping[str, str] | None = None,
    artifact_paths: Mapping[str, Path] | None = None,
) -> ResumeOutcome:
    """Validate a resume request and produce a runner-ready manifest cursor.

    Steps:

    1. Resolve the requested cursor with native-first semantics.
    2. Validate the resolved cursor against the manifest and journal state.
    3. Validate event sequence and artifact content hashes if a journal exists.
    4. Validate the suspension record and resume payload if provided.
    """

    native_hash = manifest.manifest_hash or ""
    resolution = resolve_cursor(
        request.cursor,
        native_manifest_hash=native_hash,
        legacy_aliases=legacy_aliases,
        run_id=request.run_id,
    )

    if resolution.resolution.decision is ReplayDecision.QUARANTINE:
        return ResumeOutcome(
            ok=False,
            replay_resolution=resolution.resolution,
            quarantine_reason=resolution.resolution.reason,
        )

    resolved_cursor = resolution.cursor
    assert resolved_cursor is not None

    journal = NDJsonEventJournal(artifact_root)
    events = journal.read()
    max_sequence = events[-1].sequence if events else None

    validation = validate_replay_cursor(
        resolved_cursor,
        expected_manifest_hash=native_hash,
        expected_artifact_root=str(artifact_root),
        max_event_sequence=max_sequence,
    )
    if validation.decision is ReplayDecision.QUARANTINE:
        return ResumeOutcome(
            ok=False,
            replay_resolution=validation,
            quarantine_reason=validation.reason,
        )

    if events:
        sequence_validation = validate_event_sequence_against_cursor(events, resolved_cursor)
        if sequence_validation.decision is ReplayDecision.QUARANTINE:
            return ResumeOutcome(
                ok=False,
                replay_resolution=sequence_validation,
                quarantine_reason=sequence_validation.reason,
            )

    if expected_artifact_hashes and artifact_paths:
        artifact_validation = validate_artifact_content_hashes(
            artifact_paths,
            expected_artifact_hashes,
        )
        if artifact_validation.decision is ReplayDecision.QUARANTINE:
            return ResumeOutcome(
                ok=False,
                replay_resolution=artifact_validation,
                quarantine_reason=artifact_validation.reason,
            )

    node_ref: str | None = None
    route_id: str | None = None
    suspension: SuspensionCursor | None = None
    if suspension_record is not None:
        record_validation = validate_suspension_record(
            suspension_record,
            expected_manifest_hash=native_hash,
            allowed_states={SuspensionState.PENDING},
        )
        if record_validation.decision is ReplayDecision.QUARANTINE:
            return ResumeOutcome(
                ok=False,
                replay_resolution=record_validation,
                quarantine_reason=record_validation.reason,
            )

        payload_validation = validate_resume_payload(
            request.resume_payload,
            resume_schema_hash=resume_schema_hash,
            validator=resume_validator,
        )
        if not payload_validation.ok:
            return ResumeOutcome(
                ok=False,
                quarantine_reason=payload_validation.reason,
            )

        node_ref = suspension_record.node_ref
        route_id = suspension_record.route.route_id
        suspension = SuspensionCursor(
            cursor=resolved_cursor,
            node_ref=node_ref,
            route_id=route_id,
            payload_schema_hash=suspension_record.route.payload_schema_hash,
        )

    manifest_cursor = build_resume_manifest_cursor(manifest, resolved_cursor, node_ref=node_ref)
    return ResumeOutcome(
        ok=True,
        manifest_cursor=manifest_cursor,
        suspension=suspension,
        replay_resolution=validation,
    )


def resume_event(
    run_id: str,
    manifest: WorkflowManifest,
    suspension: SuspensionCursor,
    payload: Mapping[str, Any],
) -> EventEnvelope:
    """Build a ``node_resumed`` event envelope for the journal."""

    return EventEnvelope(
        event_id=f"{run_id}:resumed:{suspension.route_id}",
        family=EventFamily.SUSPENSION,
        kind="node_resumed",
        manifest=ManifestReference(
            alias=manifest.id,
            manifest_hash=manifest.manifest_hash or "",
        ),
        run_id=run_id,
        payload_schema_hash=suspension.payload_schema_hash or "",
        payload={
            "node_ref": suspension.node_ref,
            "route_id": suspension.route_id,
            "resume_payload": dict(payload),
        },
        scope_stack=suspension.cursor.scope_stack,
        reentry_id=suspension.cursor.reentry_id,
    )


__all__ = [
    "ResumeOutcome",
    "ResumeRequest",
    "build_resume_manifest_cursor",
    "prepare_resume",
    "resume_event",
]
