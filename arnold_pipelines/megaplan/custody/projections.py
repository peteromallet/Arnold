"""Custody projection store — cursor-checked appends, atomic rebuild, and recovery.

Provides a Custody-specific projection persistence layer on top of the
shared :mod:`arnold_pipelines.megaplan._core.io` projection primitives.
Every append is cursor-checked against an accepted-source-record ledger;
rebuilds are atomic; replay is deterministic; and cursor mismatches
preserve the prior complete projection for recovery.

Storage layout under ``<base_dir>/``::

    <projection_id>.projection.jsonl   — append-only event stream
    <projection_id>.state.json         — cached projection state
    <projection_id>.lock               — fcntl.flock serialization gate
    projections/
      <projection_id>.snapshot.json    — atomic rebuild snapshot
      recovery/
        <projection_id>.pre-mismatch-*.snapshot.json — preserved prior projections

Principles
----------
* **Cursor-checked appends** — Every append validates that the accepted-source
  record cursor has not regressed (record count decreased) or been rewritten
  (digest mismatch when strict).  Appends that fail cursor validation raise
  :class:`ProjectionCursorMismatchError` after preserving the prior projection.
* **Atomic rebuild** — ``rebuild_projection()`` writes a complete snapshot
  atomically via temp-file + rename so consumers never see a partial write.
* **Deterministic replay** — ``replay_projection()`` replays the append-only
  history through a pure fold function, producing identical output for the
  same input sequence.
* **Accepted-source-record ordering** — Projection events are ordered by
  their source cursor record count and can be validated during replay.
* **Preservation on mismatch** — When a cursor mismatch is detected, the
  prior complete projection is copied to ``recovery/`` before the error is
  raised, so the state is never lost.

All production gates and mutating effects remain disabled in M7;
this module runs in shadow/report-only mode.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    ProjectionCursorMismatchError,
    ProjectionRecord,
    append_projection_event,
    deterministic_projection_replay,
    latest_projection_cursor,
    load_projection_history,
    now_utc,
    projection_snapshot_path,
    rebuild_projection_atomically,
    recover_projection_from_cursor_mismatch,
)


# ── Schema version constant ────────────────────────────────────────────────

PROJECTION_SCHEMA_VERSION = 1


# ── Projection event types ─────────────────────────────────────────────────


class ProjectionEventType(StrEnum):
    """Semantic event types for Custody projection records."""

    SNAPSHOT_BUILT = "snapshot_built"
    """A complete projection snapshot was rebuilt from accepted source records."""

    APPEND_CURSOR_CHECKED = "append_cursor_checked"
    """A projection event was appended after passing cursor validation."""

    APPEND_BLOCKED = "append_blocked"
    """An append was blocked by cursor mismatch (preserved prior projection)."""

    RECOVERY_ATTEMPTED = "recovery_attempted"
    """A projection recovery was attempted from a preserved prior snapshot."""

    RECOVERY_SUCCESS = "recovery_success"
    """A projection was successfully recovered from a preserved prior snapshot."""

    RECONCILE = "reconcile"
    """Manual reconciliation event after cursor mismatch resolution."""


# ── Error types ────────────────────────────────────────────────────────────


class ProjectionStoreError(RuntimeError):
    """Base exception for custody projection-store operations."""


class ProjectionNotFoundError(ProjectionStoreError):
    """Raised when a referenced projection does not exist."""


# ── Projection store ───────────────────────────────────────────────────────


def _default_base_dir() -> Path:
    return Path(os.path.expanduser("~/.megaplan/custody/projections"))



@dataclass
class CustodyProjectionStore:
    """Cursor-checked Custody projection store.

    Construct via :func:`open_projection_store`.  Each instance manages
    projections under a single ``base_dir``.

    Every append is validated against the accepted-source-record cursor
    before being written to the append-only history.  Rebuilds are atomic
    and snapshot-based.  Cursor mismatches preserve the prior projection.
    """

    base_dir: Path
    flock: bool = True

    # -- append ----------------------------------------------------------------

    def append(
        self,
        projection_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        source_path: Path | None = None,
        idempotency_key: str = "",
    ) -> ProjectionRecord:
        """Append a cursor-checked projection event.

        If *source_path* is provided, the current accepted-source cursor is
        computed and embedded.  The append is atomically written to the
        projection history.

        Parameters
        ----------
        projection_id:
            Unique identifier for this projection.
        event_type:
            Semantic event type (see :class:`ProjectionEventType`).
        payload:
            The projection event payload.
        source_path:
            Path to the accepted-source-record ledger used for cursor validation.
        idempotency_key:
            Optional key for idempotent repeat detection.

        Returns
        -------
        ProjectionRecord
            The record as appended (with cursor embedded).

        Raises
        ------
        ProjectionCursorMismatchError
            If cursor validation fails.  The prior projection is preserved
            before this error is raised.
        """
        event_id = _generate_event_id(projection_id, event_type)
        record = ProjectionRecord(
            event_type=event_type,
            event_id=event_id,
            payload=payload,
            occurred_at=now_utc(),
            cursor=None,  # Cursor will be computed from source_path
            idempotency_key=idempotency_key,
        )
        return append_projection_event(
            self.base_dir,
            projection_id,
            record,
            source_path=source_path,
            flock=self.flock,
            snapshot_dir=self.base_dir / "projections",
        )

    # -- rebuild ---------------------------------------------------------------

    def rebuild(
        self,
        projection_id: str,
        projection_data: Mapping[str, Any],
        *,
        source_path: Path | None = None,
        event_type: str = ProjectionEventType.SNAPSHOT_BUILT,
    ) -> Path:
        """Atomically rebuild the complete projection snapshot.

        The snapshot is written atomically so that consumers see either the
        complete previous version or the complete new version — never a
        partial write.

        Also appends a ``SNAPSHOT_BUILT`` event to the projection history
        for auditability.

        Parameters
        ----------
        projection_id:
            Unique identifier for this projection.
        projection_data:
            The complete projection data to write.
        source_path:
            Optional path to the accepted-source-record ledger for cursor tracking.
        event_type:
            Event type recorded in the history (default: ``SNAPSHOT_BUILT``).

        Returns
        -------
        Path
            The path to the written snapshot file.
        """
        # Compute cursor from source if available
        cursor: ProjectionCursor | None = None
        if source_path is not None:
            cursor = self._cursor_from_source(source_path)

        # Atomic snapshot write
        snapshot_path = rebuild_projection_atomically(
            self.base_dir / "projections",
            projection_id,
            projection_data,
            cursor=cursor,
        )

        # Append history record
        self.append(
            projection_id,
            event_type,
            {
                "snapshot_path": str(snapshot_path),
                "schema_version": PROJECTION_SCHEMA_VERSION,
            },
            source_path=source_path,
            idempotency_key=f"rebuild-{projection_id}-{now_utc()}",
        )

        return snapshot_path

    # -- load / replay ---------------------------------------------------------

    def load_snapshot(self, projection_id: str) -> dict[str, Any] | None:
        """Load the most recent projection snapshot."""
        snapshot_dir = self.base_dir / "projections"
        snapshot_path = projection_snapshot_path(snapshot_dir, projection_id)
        if not snapshot_path.exists():
            return None
        try:
            return json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

    def load_history(
        self, projection_id: str
    ) -> tuple[ProjectionRecord, ...]:
        """Load the full projection event history."""
        return load_projection_history(self.base_dir, projection_id)

    def replay(
        self,
        projection_id: str,
        *,
        fold_fn: Callable[[dict[str, Any], ProjectionRecord], dict[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        """Deterministically replay the projection history.

        If *fold_fn* is provided, it is called with ``(accumulator, record)``
        for each record in accepted-source-record order.  The accumulator
        starts as an empty dict.

        Returns the final accumulated state.
        """
        return deterministic_projection_replay(
            self.base_dir, projection_id, fold_fn=fold_fn
        )

    def latest_cursor(self, projection_id: str) -> ProjectionCursor | None:
        """Return the cursor from the most recent projection record."""
        return latest_projection_cursor(self.base_dir, projection_id)

    # -- recovery --------------------------------------------------------------

    def recover_from_cursor_mismatch(
        self,
        projection_id: str,
        source_path: Path,
    ) -> dict[str, Any]:
        """Recover from a cursor mismatch using preserved prior projection.

        Returns a dict with the recovered projection, cursor, and diagnostics.
        Also appends a ``RECOVERY_ATTEMPTED`` or ``RECOVERY_SUCCESS`` event
        to the projection history.
        """
        result = recover_projection_from_cursor_mismatch(
            self.base_dir / "projections", projection_id, source_path=source_path,
        )

        # Record recovery attempt in history. We intentionally do NOT pass
        # source_path here because the source may still be in a regressed
        # state — the recovery event documents what happened, it does not
        # require a valid source cursor.
        if result["status"] == "recovered":
            self.append(
                projection_id,
                ProjectionEventType.RECOVERY_SUCCESS,
                {
                    "recovered_from": result.get("snapshot_path"),
                    "cursor": result.get("cursor"),
                    "diagnostics": result.get("diagnostics", []),
                },
                idempotency_key=f"recovery-{projection_id}-{now_utc()}",
            )
        else:
            self.append(
                projection_id,
                ProjectionEventType.RECOVERY_ATTEMPTED,
                {
                    "status": result["status"],
                    "diagnostics": result.get("diagnostics", []),
                },
                idempotency_key=f"recovery-attempt-{projection_id}-{now_utc()}",
            )

        return result

    # -- reconcile -------------------------------------------------------------

    def reconcile(
        self,
        projection_id: str,
        reconciled_data: Mapping[str, Any],
        *,
        source_path: Path,
        diagnostics: Sequence[Mapping[str, Any]] = (),
    ) -> Path:
        """Manually reconcile after cursor mismatch resolution.

        Writes a reconciled snapshot and appends a ``RECONCILE`` history event.
        """
        cursor = self._cursor_from_source(source_path)
        snapshot_path = rebuild_projection_atomically(
            self.base_dir / "projections",
            projection_id,
            reconciled_data,
            cursor=cursor,
        )
        self.append(
            projection_id,
            ProjectionEventType.RECONCILE,
            {
                "snapshot_path": str(snapshot_path),
                "cursor": cursor.to_dict(),
                "diagnostics": [dict(d) for d in diagnostics],
            },
            source_path=source_path,
            idempotency_key=f"reconcile-{projection_id}-{now_utc()}",
        )
        return snapshot_path

    # -- validation ------------------------------------------------------------

    def validate_source_cursor(
        self,
        projection_id: str,
        source_path: Path,
        *,
        strict_digest: bool = False,
    ) -> dict[str, Any]:
        """Validate the current source cursor against the last recorded cursor.

        Returns a dict with keys:
          - ``valid``: bool
          - ``record_count_ok``: bool
          - ``digest_ok``: bool (None if not strict)
          - ``last_cursor``: the last recorded cursor (or None)
          - ``current_cursor``: the current source cursor
          - ``diagnostics``: list of diagnostic messages
        """
        from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path, _validate_projection_cursor

        last_cursor = self.latest_cursor(projection_id)
        current_cursor = _projection_cursor_from_path(source_path)
        diagnostics: list[str] = []

        if last_cursor is None:
            diagnostics.append("No prior cursor recorded — first append or fresh projection")
            return {
                "valid": True,
                "record_count_ok": True,
                "digest_ok": None,
                "last_cursor": None,
                "current_cursor": current_cursor.to_dict(),
                "diagnostics": diagnostics,
            }

        valid = _validate_projection_cursor(last_cursor, current_cursor, strict_digest=strict_digest)
        record_count_ok = current_cursor.source_record_count >= last_cursor.source_record_count
        digest_ok = (
            current_cursor.source_digest == last_cursor.source_digest
            if strict_digest
            else None
        )

        if not record_count_ok:
            diagnostics.append(
                f"Source record count regressed: "
                f"expected >= {last_cursor.source_record_count}, "
                f"observed {current_cursor.source_record_count}"
            )
        if strict_digest and digest_ok is False:
            diagnostics.append(
                f"Source digest mismatch: "
                f"expected {last_cursor.source_digest[:16]}..., "
                f"observed {current_cursor.source_digest[:16]}..."
            )

        return {
            "valid": valid,
            "record_count_ok": record_count_ok,
            "digest_ok": digest_ok,
            "last_cursor": last_cursor.to_dict(),
            "current_cursor": current_cursor.to_dict(),
            "diagnostics": diagnostics,
        }

    # -- internal helpers ------------------------------------------------------

    def _cursor_from_source(self, source_path: Path) -> ProjectionCursor:
        """Compute a cursor from the current state of *source_path*."""
        from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path
        return _projection_cursor_from_path(source_path)


# ── Event ID generation ────────────────────────────────────────────────────


def _generate_event_id(projection_id: str, event_type: str) -> str:
    """Generate a unique event ID from projection_id + event_type + high-precision timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")
    seed = f"{projection_id}:{event_type}:{ts}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"proj-{digest}"


# ── Factory ────────────────────────────────────────────────────────────────


def open_projection_store(
    base_dir: Path | None = None,
    *,
    flock: bool = True,
) -> CustodyProjectionStore:
    """Open a custody projection store rooted at *base_dir*.

    If *base_dir* is ``None``, defaults to ``~/.megaplan/custody/projections``.
    """
    base = (base_dir or _default_base_dir()).resolve()
    return CustodyProjectionStore(base_dir=base, flock=flock)


# ── Convenience: batch append ──────────────────────────────────────────────


def append_events(
    store: CustodyProjectionStore,
    projection_id: str,
    events: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    source_path: Path | None = None,
) -> tuple[ProjectionRecord, ...]:
    """Append a batch of projection events in sequence.

    Each element of *events* is a ``(event_type, payload)`` pair.
    Returns the records as appended.
    """
    result: list[ProjectionRecord] = []
    for event_type, payload in events:
        record = store.append(
            projection_id,
            event_type,
            payload,
            source_path=source_path,
        )
        result.append(record)
    return tuple(result)


# ── Public exports ─────────────────────────────────────────────────────────

__all__ = [
    "PROJECTION_SCHEMA_VERSION",
    "CustodyProjectionStore",
    "ProjectionEventType",
    "ProjectionNotFoundError",
    "ProjectionStoreError",
    "append_events",
    "open_projection_store",
]
