"""Resume cursor migration from legacy Megaplan sentinels to manifest hashes.

Legacy runs identify themselves with a sentinel hash derived from legacy
pipeline state.  This module maps those sentinels to the canonical M3 manifest
hash via ``arnold.kernel.replay.LegacyAliasRecord`` and derives resume cursors
from event-journal sequence plus manifest coordinates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from arnold.kernel.journal import NDJsonEventJournal
from arnold.kernel.replay import LegacyAliasRecord, ReplayCursor, resolve_cursor
from arnold.manifest import ManifestCursor, manifest_coordinate


# ---------------------------------------------------------------------------
# Legacy sentinel -> manifest hash aliases
# ---------------------------------------------------------------------------

# Sentinel hash emitted by legacy runs when no canonical manifest was in use.
# These aliases are deliberately narrow: one sentinel, one target manifest hash.
_LEGACY_SENTINEL_HASH: str = "sha256:" + "0" * 64


def canonical_megaplan_alias(target_manifest_hash: str) -> LegacyAliasRecord:
    """Return the alias mapping the legacy sentinel to a canonical manifest hash."""

    return LegacyAliasRecord(
        alias="megaplan-legacy-sentinel",
        source_manifest_hash=_LEGACY_SENTINEL_HASH,
        target_manifest_hash=target_manifest_hash,
        authority_id="megaplan-resume-migration",
    )


def build_megaplan_legacy_aliases(
    target_manifest_hash: str,
) -> dict[str, LegacyAliasRecord]:
    """Return a lookup map from legacy sentinel hash to canonical alias record."""

    alias = canonical_megaplan_alias(target_manifest_hash)
    return {alias.source_manifest_hash: alias}


# ---------------------------------------------------------------------------
# Cursor resolution
# ---------------------------------------------------------------------------

def resolve_legacy_resume_cursor(
    requested: ReplayCursor,
    target_manifest_hash: str,
    *,
    run_id: str | None = None,
) -> tuple[ReplayCursor | None, str]:
    """Resolve a legacy sentinel cursor against the canonical manifest hash.

    Returns ``(resolved_cursor, reason)``.  When the cursor already matches the
    target manifest hash it is returned unchanged.  When a legacy alias exists
    the cursor is rewritten to the target hash.  Otherwise the resolution is
    quarantined and ``None`` is returned.
    """

    aliases = build_megaplan_legacy_aliases(target_manifest_hash)
    resolution = resolve_cursor(
        requested,
        native_manifest_hash=target_manifest_hash,
        legacy_aliases=aliases,
        run_id=run_id,
    )
    return resolution.cursor, resolution.resolution.reason


# ---------------------------------------------------------------------------
# Journal-derived cursor derivation
# ---------------------------------------------------------------------------

def derive_resume_cursor_from_journal(
    artifact_root: Path,
    target_manifest_hash: str,
    *,
    node_ref: str,
    scope_stack: tuple[str, ...] = (),
    reentry_id: str | None = None,
) -> ReplayCursor:
    """Derive a resume cursor from the event journal sequence and manifest coordinates.

    The cursor is fully determined by the manifest hash, the suspended node,
    and the last consumed event sequence.  It never reads mutable ``state.json``
    as authority.
    """

    journal = NDJsonEventJournal(artifact_root)
    events = journal.read()
    last_sequence = events[-1].sequence if events else None
    return ReplayCursor(
        manifest_hash=target_manifest_hash,
        reentry_id=reentry_id,
        scope_stack=scope_stack,
        artifact_root=str(artifact_root),
        event_sequence=last_sequence,
    )


def derive_manifest_cursor_from_journal(
    artifact_root: Path,
    manifest_id: str,
    manifest_hash: str,
    *,
    node_ref: str,
) -> ManifestCursor:
    """Derive an M3 ``ManifestCursor`` from journal state for direct backend resume."""

    from arnold.manifest import NodeRef

    replay_cursor = derive_resume_cursor_from_journal(
        artifact_root=artifact_root,
        target_manifest_hash=manifest_hash,
        node_ref=node_ref,
    )
    coord = manifest_coordinate(manifest_id, manifest_hash)
    return coord.cursor(
        node=NodeRef(node_ref),
        reentry_id=replay_cursor.reentry_id,
    )


# ---------------------------------------------------------------------------
# Legacy resume cursor extraction from state.json
# ---------------------------------------------------------------------------

def extract_legacy_resume_cursor(
    state: Mapping[str, Any],
    target_manifest_hash: str,
    *,
    artifact_root: Path | None = None,
    run_id: str | None = None,
) -> tuple[ReplayCursor | None, str]:
    """Extract a legacy resume cursor from ``state.json``-shaped data and resolve it.

    The legacy cursor is read *only* as a migration input.  It is immediately
    resolved to the canonical manifest hash; if no alias matches it is
    quarantined.
    """

    manifest_hash = str(state.get("manifest_hash") or _LEGACY_SENTINEL_HASH)
    scope_stack = tuple(state.get("scope_stack") or ())
    reentry_id = state.get("reentry_id")
    event_sequence = state.get("last_event_sequence")
    if isinstance(event_sequence, (int, float)) and event_sequence >= 0:
        event_sequence = int(event_sequence)
    else:
        event_sequence = None

    requested = ReplayCursor(
        manifest_hash=manifest_hash,
        reentry_id=reentry_id,
        scope_stack=scope_stack,
        artifact_root=str(artifact_root) if artifact_root else None,
        event_sequence=event_sequence,
    )
    return resolve_legacy_resume_cursor(
        requested,
        target_manifest_hash=target_manifest_hash,
        run_id=run_id,
    )


__all__ = [
    "build_megaplan_legacy_aliases",
    "canonical_megaplan_alias",
    "derive_manifest_cursor_from_journal",
    "derive_resume_cursor_from_journal",
    "extract_legacy_resume_cursor",
    "resolve_legacy_resume_cursor",
]
