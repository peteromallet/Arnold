"""Project Store events into the legacy per-plan ``events.ndjson`` view."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from arnold_pipelines.megaplan.store import StoredEvent, Store
from arnold_pipelines.megaplan.workflows.events import workflow_cursor


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_PROJECTION_SEQ_FILE = ".events.projection.seq"


def _canonical_dumps(value: Any) -> str:
    """Canonical JSON used by projection and schema-equivalence tests."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _transaction_id(plan_id: str, phase: str | None, seq: int) -> str:
    raw = f"{plan_id}::{phase or 'cli'}::{seq}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _iso_timestamp(value: datetime | str | None, seq: int) -> str:
    if isinstance(value, datetime):
        dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(value, str) and value:
        return value
    return (_EPOCH + timedelta(microseconds=seq)).isoformat()


def _event_from_stored(plan_id: str, seq: int, event: StoredEvent) -> dict[str, Any]:
    projected = {
        "seq": seq,
        "schema_version": 1,
        "ts_utc": _iso_timestamp(event.occurred_at, seq),
        "ts_rel_init_s": None,
        "kind": event.kind,
        "phase": event.phase,
        "payload": dict(event.payload),
        "transaction_id": _transaction_id(plan_id, event.phase, seq),
        "store_method": event.source,
    }
    if event.run_id is not None:
        projected["run_id"] = event.run_id
    cursor = workflow_cursor(event.phase)
    if cursor is not None:
        projected["workflow_cursor"] = cursor.to_dict()
    return projected


def schema_equivalence_triples(events: Iterable[Mapping[str, Any]]) -> tuple[tuple[Any, Any, Any], ...]:
    """Return the T16 equivalence shape: ordered ``(kind, phase, payload)``."""

    return tuple(
        (
            event.get("kind"),
            event.get("phase"),
            json.loads(_canonical_dumps(event.get("payload") or {})),
        )
        for event in events
    )


def project_events(store: Store, plan_id: str) -> tuple[dict[str, Any], ...]:
    return tuple(
        _event_from_stored(plan_id, event.seq if event.seq is not None else seq, event)
        for seq, event in enumerate(store.events_for_plan(plan_id))
    )


def project_events_ndjson(store: Store, plan_id: str) -> str:
    events = project_events(store, plan_id)
    if not events:
        return ""
    return "\n".join(_canonical_dumps(event) for event in events) + "\n"


def _atomic_write_text(path: Path, content: str) -> None:
    """Replace *path* without exposing readers to a truncated projection."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _projection_seq_path(plan_dir: Path) -> Path:
    return plan_dir / _PROJECTION_SEQ_FILE


def _read_projection_seq(plan_dir: Path) -> int | None:
    try:
        return int(_projection_seq_path(plan_dir).read_text(encoding="ascii").strip())
    except (FileNotFoundError, OSError, ValueError):
        return None


def _write_projection_seq(plan_dir: Path, seq: int) -> None:
    _atomic_write_text(_projection_seq_path(plan_dir), str(seq))


def _project_emitted_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical compatibility projection for one emitted event."""

    projected = dict(event)
    phase = projected.get("phase")
    cursor = workflow_cursor(phase if isinstance(phase, str) else None)
    if cursor is not None:
        projected["workflow_cursor"] = cursor.to_dict()
    else:
        projected.pop("workflow_cursor", None)
    return projected


def append_projection_event(
    plan_dir: Path,
    store: Store,
    event: Mapping[str, Any],
    *,
    plan_id: str | None = None,
) -> bool:
    """Append one already-stored event to the compatibility projection.

    The caller holds the plan's sequence lock.  The projection cursor proves
    the existing file ends immediately before ``event``; a missing or
    mismatched cursor falls back to one atomic rebuild from Store.  Normal
    telemetry therefore writes O(event-size), rather than rewriting the whole
    journal for every heartbeat.
    """

    plan_dir = Path(plan_dir)
    ndjson_path = plan_dir / "events.ndjson"
    raw_seq = event.get("seq")
    if not isinstance(raw_seq, int):
        return write_projection(plan_dir, store, plan_id=plan_id, force=True)

    projected_seq = _read_projection_seq(plan_dir)
    if not ndjson_path.exists() or projected_seq != raw_seq - 1:
        return write_projection(plan_dir, store, plan_id=plan_id, force=True)

    line = (_canonical_dumps(_project_emitted_event(event)) + "\n").encode("utf-8")
    fd = os.open(str(ndjson_path), os.O_WRONLY | os.O_APPEND)
    try:
        view = memoryview(line)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    _write_projection_seq(plan_dir, raw_seq)
    return True


def write_projection(
    plan_dir: Path,
    store: Store,
    *,
    plan_id: str | None = None,
    force: bool = False,
) -> bool:
    """Materialize ``events.ndjson`` from Store events.

    Returns ``True`` when a projection was written. Existing journals are
    preserved unless ``force=True``.
    """

    plan_dir = Path(plan_dir)
    ndjson_path = plan_dir / "events.ndjson"
    if ndjson_path.exists() and not force:
        return False
    events = project_events(store, plan_id or plan_dir.name)
    if not events:
        return False
    content = "\n".join(_canonical_dumps(event) for event in events) + "\n"
    _atomic_write_text(ndjson_path, content)
    seqs = [event.get("seq") for event in events if isinstance(event.get("seq"), int)]
    if seqs:
        _write_projection_seq(plan_dir, max(seqs))
    return True


def ensure_events_projection(
    plan_dir: Path,
    *,
    store: Store | None = None,
    plan_id: str | None = None,
) -> bool:
    """Lazily create ``events.ndjson`` when a Store-backed stream exists."""

    plan_dir = Path(plan_dir)
    if (plan_dir / "events.ndjson").exists():
        return False
    if store is None:
        return False
    return write_projection(plan_dir, store, plan_id=plan_id or plan_dir.name)


__all__ = [
    "_canonical_dumps",
    "append_projection_event",
    "ensure_events_projection",
    "project_events",
    "project_events_ndjson",
    "schema_equivalence_triples",
    "write_projection",
]
