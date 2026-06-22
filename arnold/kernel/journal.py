"""Append-only deterministic NDJSON event journal.

The journal is the durable state authority for the manifest runtime.  It is
file-backed, product-neutral, and serializes :class:`EventEnvelope` instances
as canonical NDJSON lines.  Malformed or mismatched lines are quarantined
rather than silently dropped so operators can inspect them.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypeVar

from arnold.kernel.events import (
    EventEnvelope,
    ReplayReference,
    canonical_event_json,
    event_from_json,
    validate_event_envelope,
)


_JOURNAL_FILE = "events.ndjson"
_SEQ_FILE = ".events.seq"
_INIT_TS_FILE = ".events.init_ts"
_QUARANTINE_DIR = ".quarantine"
_QUARANTINE_FILE = "journal.ndjson"


class EventJournal(Protocol):
    """Minimal append/read journal protocol for later runners."""

    def append(self, event: EventEnvelope) -> EventEnvelope: ...

    def read(self) -> tuple[EventEnvelope, ...]: ...


@dataclass(frozen=True)
class JournalPosition:
    """Stable journal position."""

    journal_uri: str
    sequence: int


@dataclass(frozen=True)
class JournalQuarantineRecord:
    """A journal line that could not be parsed or validated."""

    line_number: int
    raw_line: str
    reason: str


class NDJsonEventJournal:
    """Append-only NDJSON journal with monotonic sequence assignment.

    Writes ``<artifact_root>/events.ndjson`` and uses ``.events.seq`` as a
    process-safe sequence counter guarded by ``fcntl.flock``.  Every appended
    event receives the next sequence number and an ``occurred_at`` timestamp
    when one is not already present.

    Reads return only valid, consistent events.  Malformed JSON, missing
    required fields, or events whose manifest hash / artifact root diverge
    from the first valid event are quarantined.
    """

    def __init__(self, artifact_root: str | Path) -> None:
        self._root = Path(artifact_root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._journal_path = self._root / _JOURNAL_FILE
        self._seq_path = self._root / _SEQ_FILE
        self._init_ts_path = self._root / _INIT_TS_FILE
        self._quarantine_dir = self._root / _QUARANTINE_DIR

    @property
    def journal_uri(self) -> str:
        return str(self._journal_path)

    def append(self, event: EventEnvelope) -> EventEnvelope:
        """Append one event, assigning ``sequence`` and ``occurred_at``."""

        init_ts = self._load_init_ts()

        seq_fd = os.open(str(self._seq_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(seq_fd, fcntl.LOCK_EX)

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

            occurred_at = event.occurred_at or datetime.now(timezone.utc).isoformat()
            artifact_root = event.artifact_root or str(self._root)
            replay = event.replay
            if replay is None:
                replay = ReplayReference(
                    journal_uri=str(self._journal_path), sequence=new_seq
                )
            elif replay.sequence is None:
                replay = ReplayReference(
                    journal_uri=replay.journal_uri or str(self._journal_path),
                    sequence=new_seq,
                    cursor=replay.cursor,
                )

            to_write = EventEnvelope(
                event_id=event.event_id,
                family=event.family,
                kind=event.kind,
                manifest=event.manifest,
                run_id=event.run_id,
                payload_schema_hash=event.payload_schema_hash,
                payload=dict(event.payload),
                idempotency_key=event.idempotency_key,
                occurred_at=occurred_at,
                replay=replay,
                sequence=new_seq,
                reentry_id=event.reentry_id,
                scope_stack=event.scope_stack,
                artifact_root=artifact_root,
            )
            validate_event_envelope(to_write)

            line = canonical_event_json(to_write)
            with open(self._journal_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())

            fcntl.flock(seq_fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(seq_fd)
            except OSError:
                pass

        if init_ts is None:
            self._write_init_ts(datetime.now(timezone.utc))

        return to_write

    def read(self) -> tuple[EventEnvelope, ...]:
        """Return all valid events, quarantining any malformed lines."""

        events, _ = self.read_with_quarantine()
        return events

    def read_with_quarantine(
        self,
    ) -> tuple[tuple[EventEnvelope, ...], tuple[JournalQuarantineRecord, ...]]:
        """Return valid events plus quarantined malformed/mismatched lines."""

        events: list[EventEnvelope] = []
        quarantine: list[JournalQuarantineRecord] = []
        expected_manifest_hash: str | None = None
        expected_artifact_root: str | None = None
        last_sequence: int | None = None

        if not self._journal_path.exists():
            return (tuple(events), tuple(quarantine))

        with open(self._journal_path, "r", encoding="utf-8") as fh:
            for line_number, raw_line in enumerate(fh, start=1):
                stripped = raw_line.rstrip("\n").rstrip("\r")
                if not stripped:
                    continue
                try:
                    event = event_from_json(stripped)
                    validate_event_envelope(event)
                except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
                    quarantine.append(
                        JournalQuarantineRecord(
                            line_number=line_number,
                            raw_line=stripped,
                            reason=f"parse/validation error: {exc}",
                        )
                    )
                    continue

                if expected_manifest_hash is None:
                    expected_manifest_hash = event.manifest.manifest_hash
                    expected_artifact_root = event.artifact_root
                elif (
                    event.manifest.manifest_hash != expected_manifest_hash
                    or event.artifact_root != expected_artifact_root
                ):
                    quarantine.append(
                        JournalQuarantineRecord(
                            line_number=line_number,
                            raw_line=stripped,
                            reason=(
                                f"lineage mismatch: manifest_hash or artifact_root "
                                f"does not match the journal's first event"
                            ),
                        )
                    )
                    continue

                if event.sequence is None or (
                    last_sequence is not None and event.sequence <= last_sequence
                ):
                    quarantine.append(
                        JournalQuarantineRecord(
                            line_number=line_number,
                            raw_line=stripped,
                            reason=(
                                f"sequence violation: {event.sequence} after {last_sequence}"
                            ),
                        )
                    )
                    continue

                last_sequence = event.sequence
                events.append(event)

        return (tuple(events), tuple(quarantine))

    def fold(self, initial: _T, reducer: Callable[[_T, EventEnvelope], _T]) -> _T:
        """Fold valid events from left to right."""

        state = initial
        for event in self.read():
            state = reducer(state, event)
        return state

    def _load_init_ts(self) -> datetime | None:
        if not self._init_ts_path.exists():
            return None
        try:
            raw = self._init_ts_path.read_text(encoding="utf-8").strip()
            return datetime.fromisoformat(raw)
        except (ValueError, OSError):
            return None

    def _write_init_ts(self, ts: datetime) -> None:
        self._init_ts_path.write_text(ts.isoformat(), encoding="utf-8")

    def _quarantine_path(self) -> Path:
        self._quarantine_dir.mkdir(parents=True, exist_ok=True)
        return self._quarantine_dir / _QUARANTINE_FILE

    def quarantine(self, record: JournalQuarantineRecord) -> Path:
        """Persist a quarantine record to ``.quarantine/journal.ndjson``."""

        path = self._quarantine_path()
        line = json.dumps(
            {
                "line_number": record.line_number,
                "raw_line": record.raw_line,
                "reason": record.reason,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return path


_T = TypeVar("_T")


def read_event_journal(artifact_root: str | Path) -> tuple[EventEnvelope, ...]:
    """Read all valid events from ``artifact_root/events.ndjson``."""

    return NDJsonEventJournal(artifact_root).read()


def fold_event_journal(
    artifact_root: str | Path,
    initial: _T,
    reducer: Callable[[_T, EventEnvelope], _T],
) -> _T:
    """Fold valid events from ``artifact_root/events.ndjson``."""

    return NDJsonEventJournal(artifact_root).fold(initial, reducer)


__all__ = [
    "EventJournal",
    "JournalPosition",
    "JournalQuarantineRecord",
    "NDJsonEventJournal",
    "fold_event_journal",
    "read_event_journal",
]
