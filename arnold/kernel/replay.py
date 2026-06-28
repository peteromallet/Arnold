"""Replay resolution, cursor validation, and quarantine contracts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from arnold.kernel.events import EventEnvelope


_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class ReplayDecision(StrEnum):
    """Possible replay resolver outcomes."""

    REUSE = "reuse"
    RECOMPUTE = "recompute"
    ALIAS = "alias"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class ReplayResolution:
    """Decision returned by a replay resolver."""

    decision: ReplayDecision
    reason: str
    alias_manifest_hash: str | None = None


@dataclass(frozen=True)
class QuarantineRecord:
    """Operator-visible replay quarantine record."""

    run_id: str
    original_manifest_hash: str
    observed_manifest_hash: str
    reason: str


@dataclass(frozen=True)
class ReplayCursor:
    """Durable cursor describing where a resumed run must continue.

    A cursor is fully determined by manifest coordinate and journal position.
    The runtime resolves native manifest-hash cursors first; explicit legacy
    aliases are accepted only when they are present, unambiguous, and safe.
    """

    manifest_hash: str
    reentry_id: str | None = None
    scope_stack: tuple[str, ...] = ()
    artifact_root: str | None = None
    event_sequence: int | None = None

    def __post_init__(self) -> None:
        if not _HASH_RE.fullmatch(self.manifest_hash):
            raise ValueError("manifest_hash must be 'sha256:' followed by 64 lowercase hex characters")
        if self.reentry_id is not None and not _REF_SEGMENT_RE.fullmatch(self.reentry_id):
            raise ValueError("reentry_id contains characters outside the ref alphabet")
        if self.event_sequence is not None and self.event_sequence < 0:
            raise ValueError("event_sequence must be non-negative")


@dataclass(frozen=True)
class LegacyAliasRecord:
    """Compatibility alias from a legacy pipeline identity to a manifest hash.

    Unsafe aliases (empty source, wildcard, or import-path shaped) are detected
    by :func:`resolve_cursor` and quarantined rather than resolved.
    """

    alias: str
    source_manifest_hash: str
    target_manifest_hash: str
    authority_id: str | None = None

    def __post_init__(self) -> None:
        if not self.alias:
            raise ValueError("legacy alias must be non-empty")
        if not _HASH_RE.fullmatch(self.source_manifest_hash):
            raise ValueError("source_manifest_hash must be a sha256 hash")
        if not _HASH_RE.fullmatch(self.target_manifest_hash):
            raise ValueError("target_manifest_hash must be a sha256 hash")


@dataclass(frozen=True)
class CursorResolution:
    """Outcome of resolving a resume cursor against available aliases."""

    cursor: ReplayCursor | None
    resolution: ReplayResolution
    quarantine: QuarantineRecord | None = None


def _is_unsafe_alias(alias: str) -> bool:
    """Reject import-path-shaped or wildcard aliases."""

    if not alias:
        return True
    if ":" in alias or "/" in alias or "*" in alias or "\\" in alias:
        return True
    if alias.startswith("arnold.") or alias.startswith("python:") or alias.startswith("import:"):
        return True
    return False


def resolve_cursor(
    requested: ReplayCursor,
    native_manifest_hash: str,
    legacy_aliases: Mapping[str, LegacyAliasRecord] | None = None,
    run_id: str | None = None,
) -> CursorResolution:
    """Resolve a resume cursor with native-first semantics.

    1. If the cursor manifest_hash matches the native manifest_hash, accept it.
    2. Otherwise look up a safe legacy alias by source hash. Missing or unsafe
       aliases are quarantined.
    3. If an alias exists, rewrite the cursor to the target manifest hash.
    """

    if requested.manifest_hash == native_manifest_hash:
        return CursorResolution(
            cursor=requested,
            resolution=ReplayResolution(
                decision=ReplayDecision.REUSE,
                reason="native manifest hash matches",
            ),
        )

    aliases = legacy_aliases or {}
    alias = aliases.get(requested.manifest_hash)
    if alias is None:
        return CursorResolution(
            cursor=None,
            resolution=ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason="cursor manifest_hash does not match native manifest and no legacy alias exists",
            ),
            quarantine=QuarantineRecord(
                run_id=run_id or "",
                original_manifest_hash=native_manifest_hash,
                observed_manifest_hash=requested.manifest_hash,
                reason="missing legacy alias for cursor manifest_hash",
            ),
        )

    if _is_unsafe_alias(alias.alias):
        return CursorResolution(
            cursor=None,
            resolution=ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason=f"legacy alias {alias.alias!r} is unsafe",
            ),
            quarantine=QuarantineRecord(
                run_id=run_id or "",
                original_manifest_hash=native_manifest_hash,
                observed_manifest_hash=requested.manifest_hash,
                reason=f"unsafe legacy alias: {alias.alias!r}",
            ),
        )

    if alias.target_manifest_hash != native_manifest_hash:
        return CursorResolution(
            cursor=None,
            resolution=ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason=(
                    "legacy alias target manifest hash does not match native manifest hash"
                ),
            ),
            quarantine=QuarantineRecord(
                run_id=run_id or "",
                original_manifest_hash=native_manifest_hash,
                observed_manifest_hash=requested.manifest_hash,
                reason="ambiguous legacy alias target for cursor manifest_hash",
            ),
        )

    rewritten = ReplayCursor(
        manifest_hash=alias.target_manifest_hash,
        reentry_id=requested.reentry_id,
        scope_stack=requested.scope_stack,
        artifact_root=requested.artifact_root,
        event_sequence=requested.event_sequence,
    )
    return CursorResolution(
        cursor=rewritten,
        resolution=ReplayResolution(
            decision=ReplayDecision.ALIAS,
            reason=f"legacy alias {alias.alias!r} resolved to target manifest hash",
            alias_manifest_hash=alias.target_manifest_hash,
        ),
    )


def validate_replay_cursor(
    cursor: ReplayCursor,
    *,
    expected_manifest_hash: str,
    expected_artifact_root: str | None = None,
    max_event_sequence: int | None = None,
) -> ReplayResolution:
    """Validate a resolved cursor against the current run context."""

    if cursor.manifest_hash != expected_manifest_hash:
        return ReplayResolution(
            decision=ReplayDecision.QUARANTINE,
            reason="cursor manifest_hash does not match expected manifest hash",
        )

    if expected_artifact_root is not None and cursor.artifact_root != expected_artifact_root:
        return ReplayResolution(
            decision=ReplayDecision.QUARANTINE,
            reason="cursor artifact_root does not match expected artifact root",
        )

    if max_event_sequence is not None:
        if cursor.event_sequence is None:
            return ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason="cursor event_sequence is required when a journal exists",
            )
        if cursor.event_sequence > max_event_sequence:
            return ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason="cursor event_sequence exceeds the maximum journal sequence",
            )

    if cursor.scope_stack and any(not _REF_SEGMENT_RE.fullmatch(s) for s in cursor.scope_stack):
        return ReplayResolution(
            decision=ReplayDecision.QUARANTINE,
            reason="cursor scope_stack contains invalid ref segments",
        )

    return ReplayResolution(
        decision=ReplayDecision.REUSE,
        reason="cursor is valid for the current run context",
    )


def validate_event_sequence_against_cursor(
    events: tuple[EventEnvelope, ...],
    cursor: ReplayCursor,
) -> ReplayResolution:
    """Validate that replayed events are consistent with a resume cursor.

    The cursor's event_sequence is the last consumed sequence; events must be
    monotonic and begin after it.
    """

    last_sequence = cursor.event_sequence
    for event in events:
        if event.sequence is None:
            return ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason="event is missing sequence",
            )
        if last_sequence is not None and event.sequence <= last_sequence:
            return ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason=f"event sequence {event.sequence} is not after cursor sequence {last_sequence}",
            )
        last_sequence = event.sequence
    return ReplayResolution(
        decision=ReplayDecision.REUSE,
        reason="event sequence is consistent with cursor",
    )


def validate_artifact_content_hashes(
    artifacts: Mapping[str, Path],
    expected_hashes: Mapping[str, str],
) -> ReplayResolution:
    """Validate that artifact files match expected content hashes.

    ``artifacts`` maps artifact_id to a filesystem path. ``expected_hashes``
    maps artifact_id to "sha256:..." content hashes. Missing files or hash
    mismatches are quarantined.
    """

    for artifact_id, expected_hash in expected_hashes.items():
        path = artifacts.get(artifact_id)
        if path is None:
            return ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason=f"artifact {artifact_id!r} is missing for content-hash validation",
            )
        if not path.exists():
            return ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason=f"artifact path for {artifact_id!r} does not exist",
            )
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected_hash:
            return ReplayResolution(
                decision=ReplayDecision.QUARANTINE,
                reason=f"artifact {artifact_id!r} content hash mismatch",
            )
    return ReplayResolution(
        decision=ReplayDecision.REUSE,
        reason="all artifact content hashes match",
    )


def compute_expected_hash(content: bytes) -> str:
    """Return the canonical sha256 content hash for bytes."""

    return "sha256:" + hashlib.sha256(content).hexdigest()


__all__ = [
    "CursorResolution",
    "LegacyAliasRecord",
    "QuarantineRecord",
    "ReplayCursor",
    "ReplayDecision",
    "ReplayResolution",
    "compute_expected_hash",
    "resolve_cursor",
    "validate_artifact_content_hashes",
    "validate_event_sequence_against_cursor",
    "validate_replay_cursor",
]
