"""Mechanism-only NDJSON event journal and backend-backed adapters.

This module provides a pure-mechanism append-only event journal with
monotonic sequence numbers, thread/process-safe fcntl locking, and
canonical JSON serialization.  It has zero knowledge of Megaplan event
kinds, phase names, store backends, or policy semantics.

Exports
-------
* ``EventEnvelope`` — frozen dataclass carrying kind + payload + metadata.
* ``EventSink`` — single-method Protocol that every backend implements.
* ``NdjsonEventJournal`` — fcntl-locked NDJSON append journal with
  ``.events.seq`` / ``.events.init_ts`` / ``events.ndjson`` sidecars.
* ``read_event_journal`` — parse and return all events sorted by seq.
* ``NdjsonEventSink`` — thin adapter wrapping ``NdjsonEventJournal`` to
  satisfy the ``EventSink`` Protocol.
* ``BackendEventJournal`` / ``BackendEventSink`` — adapters routing event
  writes and reads through a persistence backend that owns monotonic ordering.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol


# ---------------------------------------------------------------------------
# Sidecar file names
# ---------------------------------------------------------------------------

_SEQ_FILE = ".events.seq"
_INIT_TS_FILE = ".events.init_ts"
_NDJSON_FILE = "events.ndjson"


# ---------------------------------------------------------------------------
# EventEnvelope — lifted from megaplan observability/event_sink.py:31-56
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EventEnvelope:
    """The envelope an EventSink emits.

    Pinned JSON Schema (for documentation; backends serialize differently):

        {
          "type": "object",
          "properties": {
            "kind":            {"type": "string"},
            "payload":         {"type": "object"},
            "scope":           {"type": ["string", "null"]},
            "phase":           {"type": ["string", "null"]},
            "idempotency_key": {"type": ["string", "null"]},
            "schema_version":  {"const": 1}
          },
          "required": ["kind", "payload", "schema_version"]
        }
    """

    kind: str
    payload: dict = field(default_factory=dict)
    scope: Optional[str] = None
    phase: Optional[str] = None
    idempotency_key: Optional[str] = None
    schema_version: int = 1


# ---------------------------------------------------------------------------
# EventSink Protocol — lifted from megaplan observability/event_sink.py:59-71
# ---------------------------------------------------------------------------


class EventSink(Protocol):
    """Single-method emit surface every observability backend implements."""

    def emit(
        self,
        kind: str,
        *,
        payload: Optional[dict] = None,
        scope: Optional[str] = None,
        phase: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:  # pragma: no cover — Protocol
        ...


# ---------------------------------------------------------------------------
# NdjsonEventJournal — fcntl-locked monotonic-seq NDJSON append
# ---------------------------------------------------------------------------


class NdjsonEventJournal:
    """Append-only NDJSON event journal with fcntl-locked monotonic seq.

    Writes one JSON line per event to ``<artifact_root>/events.ndjson``.
    Uses sidecar files ``.events.seq`` (monotonic counter) and
    ``.events.init_ts`` (first-write timestamp) under the same root.

    The full critical section (read seq → increment → write counter →
    append event → release lock) is guarded by ``fcntl.flock`` on the
    ``.events.seq`` sidecar, guaranteeing monotonic seq and strict file
    order across concurrent OS processes.

    **Zero Store dependency.**  This journal writes directly to the
    filesystem with no store backend, no projection, and no event-kind
    classification.  ``kind`` is an opaque string.
    """

    def __init__(self, artifact_root: Path) -> None:
        self._root = Path(artifact_root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._seq_path = self._root / _SEQ_FILE
        self._init_ts_path = self._root / _INIT_TS_FILE
        self._ndjson_path = self._root / _NDJSON_FILE

    # ── public API ─────────────────────────────────────────────────────

    def emit(
        self,
        kind: str,
        *,
        payload: Optional[dict] = None,
        scope: Optional[str] = None,
        phase: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """Write one event to the journal and return it as a dict.

        Returns the full event dict including the assigned ``seq``.
        """
        init_ts = self._load_init_ts()

        # Build the event dict.
        event: dict[str, Any] = {
            "seq": -1,  # placeholder — assigned under flock
            "schema_version": 1,
            "ts_utc": "",
            "ts_rel_init_s": None,
            "kind": kind,
            "payload": payload if payload is not None else {},
        }
        if scope is not None:
            event["scope"] = scope
        if phase is not None:
            event["phase"] = phase
        if idempotency_key is not None:
            event["idempotency_key"] = idempotency_key

        # ── FULL critical section under flock ─────────────────────────
        seq_fd = os.open(str(self._seq_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(seq_fd, fcntl.LOCK_EX)

            # (1) Read → increment → write seq counter.
            try:
                raw = os.read(seq_fd, 128)
                current = int(raw.strip()) if raw.strip() else -1
            except (ValueError, FileNotFoundError):
                current = -1
            new_seq = current + 1
            os.lseek(seq_fd, 0, os.SEEK_SET)
            os.write(seq_fd, str(new_seq).encode("ascii"))
            os.ftruncate(seq_fd, os.lseek(seq_fd, 0, os.SEEK_CUR))
            os.fsync(seq_fd)

            # (2) Patch the real seq/timestamp and append to NDJSON.
            ts_utc = datetime.now(timezone.utc)
            event["seq"] = new_seq
            event["ts_utc"] = ts_utc.isoformat()
            if init_ts is not None:
                event["ts_rel_init_s"] = (ts_utc - init_ts).total_seconds()
            elif kind == "init" and init_ts is None:
                event["ts_rel_init_s"] = 0.0

            line = json.dumps(
                event,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            with open(self._ndjson_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())

            # (3) Release flock.
            fcntl.flock(seq_fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(seq_fd)
            except OSError:
                pass

        # Persist init timestamp outside the critical section.
        if init_ts is None:
            self._write_init_ts(ts_utc)

        return event

    # ── internal helpers ───────────────────────────────────────────────

    def _load_init_ts(self) -> Optional[datetime]:
        if not self._init_ts_path.exists():
            return None
        try:
            raw = self._init_ts_path.read_text(encoding="utf-8").strip()
            return datetime.fromisoformat(raw)
        except (ValueError, OSError):
            return None

    def _write_init_ts(self, ts: datetime) -> None:
        self._init_ts_path.write_text(ts.isoformat(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def read_event_journal(artifact_root: Path) -> list[dict]:
    """Parse every line from ``<artifact_root>/events.ndjson``.

    Returns events sorted by ``seq`` (ascending).  Lines that fail to
    parse as JSON are silently skipped.  Does **not** invoke any
    projection or store backend — this is a pure file reader.
    """
    ndjson_path = Path(artifact_root) / _NDJSON_FILE
    if not ndjson_path.exists():
        return []

    events: list[dict] = []
    with open(ndjson_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(event)

    events.sort(key=lambda e: e.get("seq", 0))
    return events


def read_event_journal_paged(
    artifact_root: Path,
    *,
    since_seq: int | None = None,
    from_seq: int | None = None,
    to_seq: int | None = None,
    limit: int | None = None,
    sort_page: bool = False,
) -> list[dict]:
    """Return a bounded page of events from ``<artifact_root>/events.ndjson``.

    Implemented over :func:`stream_event_journal` (lazy, no projection/store
    coupling).  Returned events preserve file-order by default (which matches
    monotonic ``seq`` order from the ``fcntl.flock``-guarded append).

    Cursor semantics
    ----------------
    * ``since_seq`` — keep only events whose ``seq`` is **strictly greater
      than** *since_seq* (``seq > since_seq``).
    * ``from_seq`` — keep only events whose ``seq`` is **greater than or
      equal to** *from_seq* (``seq >= from_seq``).
    * ``to_seq`` — keep only events whose ``seq`` is **strictly less than**
      *to_seq* (``seq < to_seq``).  Together with *from_seq* this forms an
      ``[from_seq, to_seq)`` half-open interval.
    * ``since_seq`` and ``from_seq`` are **mutually exclusive**; passing
      both raises :class:`ValueError`.
    * ``limit`` — if not *None*, truncate the page to at most *limit*
      events (applied after filtering).
    * ``sort_page`` — if *False* (default) events are returned in file
      order.  If *True* they are sorted by ``seq`` ascending.

    Returns
    -------
    list[dict]
        Ordered page of events matching the requested window.
        May be empty.
    """
    if since_seq is not None and from_seq is not None:
        raise ValueError(
            "since_seq and from_seq are mutually exclusive; pass only one"
        )

    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")

    page: list[dict] = []
    for event in stream_event_journal(artifact_root):
        seq = event.get("seq", 0)

        # Apply lower-bound filter.
        if since_seq is not None and seq <= since_seq:
            continue
        if from_seq is not None and seq < from_seq:
            continue

        # Apply upper-bound filter.
        if to_seq is not None and seq >= to_seq:
            continue

        page.append(event)

        # Apply limit (after filtering).
        if limit is not None and len(page) >= limit:
            break

    if sort_page:
        page.sort(key=lambda e: e.get("seq", 0))

    return page


def stream_event_journal(artifact_root: Path) -> Iterator[dict]:
    """Yield every event from ``<artifact_root>/events.ndjson`` lazily.

    Reuses the same parse semantics as :func:`read_event_journal`:
    missing files yield nothing, blank lines are skipped, and lines
    that fail to decode as JSON are silently skipped.  Events are
    yielded in file order (which matches monotonic ``seq`` order
    because the journal is append-only under ``fcntl.flock``).

    Does **not** invoke any projection or store backend — this is a
    pure file reader.
    """
    ndjson_path = Path(artifact_root) / _NDJSON_FILE
    if not ndjson_path.exists():
        return
    with open(ndjson_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield event


# ---------------------------------------------------------------------------
# NdjsonEventSink — thin Protocol adapter
# ---------------------------------------------------------------------------


class NdjsonEventSink:
    """Thin adapter wrapping ``NdjsonEventJournal`` to satisfy ``EventSink``.

    Delegates ``emit(kind, *, payload, scope, phase, idempotency_key)``
    directly to the underlying journal.
    """

    def __init__(self, artifact_root: Path) -> None:
        self._journal = NdjsonEventJournal(artifact_root)

    def emit(
        self,
        kind: str,
        *,
        payload: Optional[dict] = None,
        scope: Optional[str] = None,
        phase: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        return self._journal.emit(
            kind,
            payload=payload,
            scope=scope,
            phase=phase,
            idempotency_key=idempotency_key,
        )


class BackendEventJournal:
    """Event journal adapter backed by a persistence backend.

    The backend is responsible for assigning monotonic unique ordering via its
    ``emit_event`` implementation. This adapter preserves the
    ``NdjsonEventJournal`` emit surface so existing call sites can swap storage
    backends without changing event production code.
    """

    def __init__(
        self,
        backend: Any,
        scope: Any,
        *,
        default_scope: Optional[str] = None,
    ) -> None:
        self._backend = backend
        self._scope = scope
        self._default_scope = default_scope

    def emit(
        self,
        kind: str,
        *,
        payload: Optional[dict] = None,
        scope: Optional[str] = None,
        phase: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        row = self._backend.emit_event(
            self._scope,
            kind=kind,
            payload=payload,
            phase=phase,
            idempotency_key=idempotency_key,
            event_scope=scope if scope is not None else self._default_scope,
        )
        return dict(row.payload)

    def read(
        self,
        *,
        since_seq: int | None = None,
        to_seq: int | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return [
            dict(row.payload)
            for row in self._backend.read_events(
                self._scope,
                since_sequence=since_seq,
                to_sequence=to_seq,
                limit=limit,
            )
        ]


class BackendEventSink:
    """Thin ``EventSink`` adapter over :class:`BackendEventJournal`."""

    def __init__(
        self,
        backend: Any,
        scope: Any,
        *,
        default_scope: Optional[str] = None,
    ) -> None:
        self._journal = BackendEventJournal(
            backend,
            scope,
            default_scope=default_scope,
        )

    def emit(
        self,
        kind: str,
        *,
        payload: Optional[dict] = None,
        scope: Optional[str] = None,
        phase: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        return self._journal.emit(
            kind,
            payload=payload,
            scope=scope,
            phase=phase,
            idempotency_key=idempotency_key,
        )


__all__ = [
    "EventEnvelope",
    "EventSink",
    "BackendEventJournal",
    "BackendEventSink",
    "NdjsonEventJournal",
    "NdjsonEventSink",
    "read_event_journal",
    "read_event_journal_paged",
    "stream_event_journal",
]
