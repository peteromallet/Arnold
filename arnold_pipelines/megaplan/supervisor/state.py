"""Persistence helpers for supervisor orchestration state.

M7: Projection adapters for supervisor state persistence.
---------------------------------------------------------------------
OLD-READER / NEW-WRITER METADATA:
  - Legacy readers (all callers before M7) use load_supervisor_state()
    which reads the state JSON file directly.  These readers accept the
    file as authority without cursor validation.
  - New writers (M7+) supplement each save_supervisor_state() with a
    cursor-checked projection event appended to an append-only history.
  - New readers (M7+) can use rebuild_supervisor_state_projection() or
    supervisor_state_projection_cursor() for cursor-validated reads.
  - UNCERTAINTY: Legacy readers have no cursor validation; divergence
    between the state file and projection history is only detectable by
    the new readers.  Production enforcement remains disabled in M7.
  - The projection history is an append-only ledger; it never erases
    prior records, even on rebuild.
  - The projection is SUPPLEMENTAL evidence, not authority — the state
    JSON file remains the primary source of truth for all callers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arnold_pipelines.megaplan._core import atomic_write_json, slugify
from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    ProjectionCursorMismatchError,
    ProjectionRecord,
    append_projection_event,
    deterministic_projection_replay,
    latest_projection_cursor,
    load_projection_history,
    now_utc,
    projection_history_path,
    projection_snapshot_path,
    rebuild_projection_atomically,
)
from arnold_pipelines.megaplan.supervisor.model import SupervisorState, SupervisorVariantKind
from arnold_pipelines.megaplan.types import CliError


def supervisor_state_root(root: Path) -> Path:
    """Return the persisted supervisor state directory for a project root."""

    return Path(root).resolve() / ".megaplan" / "plans" / ".supervisor"


def supervisor_state_path(root: Path, state_id: str) -> Path:
    """Return the canonical state path for one supervisor run."""

    normalized = _normalize_state_id(state_id)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return supervisor_state_root(root) / f"{slugify(Path(normalized).stem)}-{digest}.json"


def load_supervisor_state(root: Path, state_id: str) -> SupervisorState | None:
    """Load persisted supervisor state, returning ``None`` when absent."""

    state_path = supervisor_state_path(root, state_id)
    if not state_path.exists():
        return None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(
            "invalid_supervisor_state",
            f"supervisor state is invalid JSON: {exc}",
        ) from exc
    if not isinstance(raw, dict):
        raise CliError(
            "invalid_supervisor_state",
            "supervisor state must be a JSON object",
        )
    state = SupervisorState.from_dict(raw)
    validate_supervisor_state(state)
    return state


# ── Supervisor state projection constants ──────────────────────────────────

_SUPERVISOR_PROJECTION_ID = "supervisor-state"
_SUPERVISOR_PROJECTION_SCHEMA_VERSION = 1


def _supervisor_projection_dir(root: Path) -> Path:
    """Return the projection storage directory for supervisor state events."""
    return supervisor_state_root(root) / "projections"


def _cursor_from_state_path(path: Path) -> ProjectionCursor:
    """Build a ProjectionCursor from the current state of *path*."""
    resolved = path.resolve()
    record_count = 0
    if resolved.exists():
        try:
            text = resolved.read_text(encoding="utf-8")
            lines = [line for line in text.splitlines() if line.strip()]
            record_count = len(lines)
        except (FileNotFoundError, OSError):
            pass
    from arnold_pipelines.megaplan._core.io import sha256_file

    source_digest = (
        sha256_file(resolved)
        if resolved.exists()
        else "sha256:" + hashlib.sha256(b"").hexdigest()
    )
    return ProjectionCursor(
        source_path=str(resolved),
        source_record_count=record_count,
        source_digest=source_digest,
        last_appended_at=now_utc(),
    )


def _generate_supervisor_event_id(event_type: str) -> str:
    """Generate a deterministic event ID for supervisor projection events."""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    seed = f"{_SUPERVISOR_PROJECTION_ID}:{event_type}:{ts}"
    return f"sup-proj-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"


def _record_supervisor_state_event(
    root: Path,
    state_id: str,
    state: SupervisorState,
    *,
    event_type: str = "state_saved",
    flock: bool = True,
) -> ProjectionRecord:
    """Append a cursor-checked projection event recording the supervisor state save.

    The event carries the full state payload and a cursor derived from the
    current supervisor state file.  This is a shadow-side-effect — it
    supplements the existing full-file write without replacing it.
    """
    projection_dir = _supervisor_projection_dir(root)
    state_path = supervisor_state_path(root, state_id)

    # Compute a cursor from the current state file (the accepted-source record)
    source_cursor = None
    if state_path.exists():
        try:
            source_cursor = _cursor_from_state_path(state_path)
        except (FileNotFoundError, OSError):
            pass

    event_id = _generate_supervisor_event_id(event_type)
    record = ProjectionRecord(
        event_type=event_type,
        event_id=event_id,
        payload={
            "schema_version": _SUPERVISOR_PROJECTION_SCHEMA_VERSION,
            "state_id": state_id,
            "state": state.to_dict(),
        },
        occurred_at=now_utc(),
        cursor=source_cursor,
        idempotency_key=f"sup-save-{state_id}-{event_id}",
    )
    return append_projection_event(
        projection_dir,
        _SUPERVISOR_PROJECTION_ID,
        record,
        source_path=state_path,
        flock=flock,
        snapshot_dir=projection_dir,
    )


def rebuild_supervisor_state_projection(
    root: Path,
) -> dict[str, Any]:
    """Atomically rebuild the supervisor state projection from the append-only history.

    Returns a dict with keys:
      - ``status``: ``"rebuilt"`` | ``"no_history"`` | ``"error"``
      - ``snapshot_path``: path to the written snapshot (if rebuilt)
      - ``projection``: the complete projected state (if rebuilt)
      - ``cursor``: the latest source cursor (if available)
      - ``record_count``: number of projection records processed
      - ``diagnostics``: list of diagnostic messages

    The rebuild writes a complete snapshot atomically so consumers see
    either the full previous version or the full new version.
    """
    projection_dir = _supervisor_projection_dir(root)
    diagnostics: list[str] = []
    records = load_projection_history(projection_dir, _SUPERVISOR_PROJECTION_ID)
    if not records:
        return {
            "status": "no_history",
            "snapshot_path": None,
            "projection": None,
            "cursor": None,
            "record_count": 0,
            "diagnostics": ["No projection history found — nothing to rebuild"],
        }

    def _fold_supervisor_state(
        acc: dict[str, Any], record: ProjectionRecord
    ) -> dict[str, Any]:
        """Fold: group state entries by state_id, last wins per id."""
        state_payload = record.payload.get("state")
        state_id = record.payload.get("state_id", "")
        if isinstance(state_payload, dict) and state_id:
            per_state = acc.setdefault("states", {})
            per_state[state_id] = dict(state_payload)
        return acc

    try:
        projection_data = deterministic_projection_replay(
            projection_dir, _SUPERVISOR_PROJECTION_ID, fold_fn=_fold_supervisor_state
        )
    except Exception as exc:
        return {
            "status": "error",
            "snapshot_path": None,
            "projection": None,
            "cursor": None,
            "record_count": len(records),
            "diagnostics": [f"Replay failed: {exc}"],
        }

    last_cursor = latest_projection_cursor(projection_dir, _SUPERVISOR_PROJECTION_ID)
    snapshot_path = rebuild_projection_atomically(
        projection_dir,
        _SUPERVISOR_PROJECTION_ID,
        projection_data,
        cursor=last_cursor,
    )
    return {
        "status": "rebuilt",
        "snapshot_path": str(snapshot_path),
        "projection": dict(projection_data),
        "cursor": last_cursor.to_dict() if last_cursor else None,
        "record_count": len(records),
        "diagnostics": diagnostics,
    }


def supervisor_state_projection_cursor(root: Path) -> ProjectionCursor | None:
    """Return the latest cursor from the supervisor state projection history."""
    projection_dir = _supervisor_projection_dir(root)
    return latest_projection_cursor(projection_dir, _SUPERVISOR_PROJECTION_ID)


def supervisor_state_projection_snapshot(root: Path) -> dict[str, Any] | None:
    """Return the most recent supervisor state projection snapshot, or None."""
    projection_dir = _supervisor_projection_dir(root)
    snapshot_path = projection_snapshot_path(projection_dir, _SUPERVISOR_PROJECTION_ID)
    if not snapshot_path.exists():
        return None
    try:
        import json as _json

        return _json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def save_supervisor_state(
    root: Path,
    state_id: str,
    state: SupervisorState,
    *,
    _record_projection: bool = True,
) -> Path:
    """Persist supervisor state with atomic JSON replacement.

    M7 (shadow): In addition to the legacy full-file atomic write, this
    function appends a cursor-checked projection event to an append-only
    history.  The projection event is recorded *after* the state file write
    succeeds so the source-of-truth file always reflects the committed state.

    Set ``_record_projection=False`` to skip the projection side-effect
    (used by internal rebuild/repair callers that should not create
    duplicate records).
    """
    validate_supervisor_state(state)
    state_path = supervisor_state_path(root, state_id)
    atomic_write_json(state_path, state.to_dict())

    # ── M7 projection side-effect ────────────────────────────────────────
    if _record_projection:
        import logging
        _log = logging.getLogger("megaplan")
        try:
            _record_supervisor_state_event(root, state_id, state)
        except ProjectionCursorMismatchError as exc:
            _log.warning(
                "M7 supervisor-state projection append blocked by cursor mismatch: %s. "
                "State file is intact; projection history may need reconciliation.",
                exc,
            )
        except Exception:
            _log.warning(
                "M7 supervisor-state projection append failed (non-fatal). "
                "State file is intact.",
                exc_info=True,
            )

    return state_path


def validate_supervisor_state(state: SupervisorState) -> None:
    """Validate supervisor state invariants before load/save."""

    node_positions: dict[str, int] = {}
    for index, node in enumerate(state.run_nodes):
        if node.node_id in node_positions:
            raise CliError(
                "invalid_supervisor_state",
                f"duplicate supervisor node_id {node.node_id!r}",
            )
        node_positions[node.node_id] = index

    for assertion in state.dependency_assertions:
        node_index = node_positions.get(assertion.node_id)
        if node_index is None:
            raise CliError(
                "invalid_supervisor_state",
                f"dependency assertion references unknown node {assertion.node_id!r}",
            )
        for dependency_id in assertion.depends_on:
            dependency_index = node_positions.get(dependency_id)
            if dependency_index is None:
                raise CliError(
                    "invalid_supervisor_state",
                    f"dependency assertion for {assertion.node_id!r} references unknown node {dependency_id!r}",
                )
            if (
                state.variant == SupervisorVariantKind.CHAIN
                and dependency_index >= node_index
            ):
                raise CliError(
                    "invalid_supervisor_state",
                    f"chain node {assertion.node_id!r} depends on {dependency_id!r}, but chain dependencies must point to earlier nodes",
                )


def _normalize_state_id(state_id: str) -> str:
    normalized = str(state_id).strip()
    if not normalized:
        raise CliError("invalid_supervisor_state", "state_id must be a non-empty string")
    return normalized


__all__ = [
    "load_supervisor_state",
    "rebuild_supervisor_state_projection",
    "save_supervisor_state",
    "supervisor_state_path",
    "supervisor_state_projection_cursor",
    "supervisor_state_projection_snapshot",
    "supervisor_state_root",
    "validate_supervisor_state",
]
