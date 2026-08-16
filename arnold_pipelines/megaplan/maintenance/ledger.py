"""Maintenance ledger facade: strict append, dead-letter, at-most-once replay.

This module is the sole Maintenance-owned persistence facade (T12).  It sits
on top of the existing incident ``NdjsonEventJournal`` (through
:class:`~arnold_pipelines.megaplan.incident.ledger.IncidentLedger`) and adds
three failure-boundary guarantees that the plain journal does not provide:

1. **Strict-only persistence.**  Only a :class:`MaintenanceEvent` that
   strict-decodes through the single canonical codec is ever persisted.  Every
   owner reference inside an event is already an immutable, locator-only
   :class:`OwnerRef` (frozen, never embeds owner payloads), so a strict event
   inherently persists immutable owner references.  Legacy permissive
   validation is never reached from this facade.

2. **Bounded redacted dead letter.**  When the primary append fails with an
   I/O error (``OSError``), the facade attempts **one** dead letter in the
   existing ledger directory (``maintenance-dead-letters.jsonl``).  The dead
   letter records the original canonical bytes + digest (so it is replayable),
   a closed *failure type*, the replay identity, and a redacted failure
   detail.  A dead letter that would exceed the size bound is refused
   (``DeadLetterSinkFailure``) rather than written unbounded.

3. **At-most-once replay.**  Replaying dead letters validates the original
   schema and digest, reuses the occurrence idempotency key, appends the
   original logical event at most once (the journal's atomic
   lookup→append deduplicates exact duplicates and rejects divergent ones),
   and records each disposition append-only in a separate dispositions file.
   A dead-letter sink failure is reported as an exception — never as success.

Fail-closed contract (SC12)
---------------------------
* Policy rejections (strict-decode ``ValueError``) and divergent duplicates
  (:class:`MaintenanceEventConflict`) are **not** write failures: they
  propagate without dead-lettering and without writing anything.
* A primary I/O failure that cannot be dead-lettered raises
  :class:`DeadLetterSinkFailure` (carrying both errors); it never returns a
  success-shaped result.
* A primary I/O failure whose dead letter was written raises
  :class:`MaintenanceAppendFailure` (carrying the dead letter) — the event is
  recoverable but is NOT claimed as committed.
* Replay outcomes are explicit: ``replayed``, ``already_present``,
  ``conflict``, ``invalid``, or ``replay_failed``.  Only the first two mean
  the original logical event is now committed exactly once; the others never
  rewrite history and never claim success.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.cloud.redact import redact_text
from arnold_pipelines.megaplan.incident.ledger import (
    IncidentLedger,
    MaintenanceEventConflict,
)
from arnold_pipelines.megaplan.maintenance.events import MaintenanceEvent
from arnold_pipelines.megaplan.maintenance.identity import (
    MaintenanceCodecError,
    canonical_digest,
    canonical_dumps,
    canonical_json,
    strict_loads,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Dead-letter filename inside the existing incident-ledger directory.
DEAD_LETTER_FILE: str = "maintenance-dead-letters.jsonl"

#: Append-only disposition filename inside the incident-ledger directory.
DISPOSITION_FILE: str = "maintenance-dead-letter-dispositions.jsonl"

#: Schema version for both dead-letter and disposition records.
DEAD_LETTER_SCHEMA_VERSION: int = 1

#: Bounded size for a single dead-letter record (UTF-8 bytes, including the
#: trailing newline).  Larger dead letters are refused instead of written.
MAX_DEAD_LETTER_BYTES: int = 256 * 1024


# ---------------------------------------------------------------------------
# Typed failure / replay outcome vocabularies
# ---------------------------------------------------------------------------


class FailureType(str, Enum):
    """Closed failure-type vocabulary recorded on a dead letter."""

    WRITE_FAILURE = "write_failure"


class ReplayOutcome(str, Enum):
    """Closed disposition vocabulary for one replayed dead letter."""

    #: The original logical event was appended now (first time).
    REPLAYED = "replayed"
    #: The original logical event was already committed with the same digest.
    ALREADY_PRESENT = "already_present"
    #: A divergent duplicate for the occurrence is already committed.
    CONFLICT = "conflict"
    #: The dead letter failed schema/digest validation; nothing appended.
    INVALID = "invalid"
    #: The primary append failed again during replay; nothing appended.
    REPLAY_FAILED = "replay_failed"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MaintenanceLedgerError(Exception):
    """Base error for the Maintenance ledger facade."""


class MaintenanceAppendFailure(MaintenanceLedgerError):
    """Primary append failed and a replayable dead letter was written.

    The original logical event is NOT committed to the primary ledger, but a
    redacted dead letter carrying its canonical bytes/digest is now durable
    and can be replayed.  ``dead_letter`` holds the record that was written.
    """

    def __init__(
        self,
        message: str,
        *,
        dead_letter: dict[str, Any] | None = None,
        primary_error: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.dead_letter = dead_letter
        self.primary_error = primary_error


class DeadLetterSinkFailure(MaintenanceLedgerError):
    """Both the primary append AND the dead-letter sink failed.

    Nothing is committed and nothing is recoverable through the dead-letter
    path.  ``primary_error`` and ``sink_error`` preserve both causes so a
    caller can distinguish the two independent failures.
    """

    def __init__(
        self,
        message: str,
        *,
        primary_error: BaseException | None = None,
        sink_error: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.primary_error = primary_error
        self.sink_error = sink_error


# ---------------------------------------------------------------------------
# Replay report types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayDisposition:
    """The append-only disposition recorded for one replayed dead letter."""

    replay_id: str
    idempotency_key: str
    outcome: ReplayOutcome
    seq: int | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DEAD_LETTER_SCHEMA_VERSION,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "disposition": self.outcome.value,
            "replay_id": self.replay_id,
            "idempotency_key": self.idempotency_key,
            "seq": self.seq,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ReplayReport:
    """Result of one :meth:`MaintenanceLedger.replay_dead_letters` call."""

    dispositions: tuple[ReplayDisposition, ...]

    @property
    def replayed_count(self) -> int:
        """Number of dead letters whose event is now committed exactly once."""
        return sum(
            1
            for disposition in self.dispositions
            if disposition.outcome
            in (ReplayOutcome.REPLAYED, ReplayOutcome.ALREADY_PRESENT)
        )

    @property
    def pending_or_failed_count(self) -> int:
        """Number of dead letters that did NOT become committed this run."""
        return len(self.dispositions) - self.replayed_count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _replay_id(idempotency_key: str, digest: str) -> str:
    """Deterministic replay identity for one (occurrence, content) pair.

    The replay identity is derived from the idempotency key plus the canonical
    digest, so two dead letters for the same occurrence but different content
    (a divergent duplicate) receive distinct identities while identical dead
    letters share one identity and are replayed at most once.
    """
    return hashlib.sha256(
        canonical_json([idempotency_key, digest]).encode("utf-8")
    ).hexdigest()


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    """Parse every JSON line from *path* (blank/undecodable lines skipped)."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# ---------------------------------------------------------------------------
# The Maintenance ledger facade
# ---------------------------------------------------------------------------


class MaintenanceLedger:
    """Append-only Maintenance ledger facade with dead-letter + replay.

    Rooted at ``<root>/.megaplan/incident-ledger`` (the existing incident
    ledger directory).  The primary event stream is the same ``events.jsonl``
    used by :class:`IncidentLedger`; dead letters and dispositions are
    adjunct files inside that directory — never a new authority store.
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        incident_ledger: IncidentLedger | None = None,
    ) -> None:
        self._incident = (
            incident_ledger if incident_ledger is not None else IncidentLedger(root)
        )

    # ── paths ─────────────────────────────────────────────────────────

    @property
    def ledger_dir(self) -> Path:
        return self._incident.ledger_dir

    @property
    def events_path(self) -> Path:
        return self._incident.events_path

    @property
    def dead_letter_path(self) -> Path:
        return self.ledger_dir / DEAD_LETTER_FILE

    @property
    def disposition_path(self) -> Path:
        return self.ledger_dir / DISPOSITION_FILE

    # ── strict append ─────────────────────────────────────────────────

    def append(self, event: MaintenanceEvent | dict[str, Any]) -> dict[str, Any]:
        """Persist one strict Maintenance event, dead-lettering I/O failures.

        *event* may be a :class:`MaintenanceEvent` model or its canonical dict
        form.  It is strict-decoded through the shared codec (unknown/missing
        fields and identity mismatches fail before any write), then appended
        atomically keyed by occurrence idempotency identity plus digest.

        Return / raise semantics
        ------------------------
        * exact duplicate → returns the PRIOR committed record (nothing new);
        * divergent duplicate → raises :class:`MaintenanceEventConflict`;
        * non-strict input → raises ``ValueError`` (nothing written);
        * primary I/O failure with a successful dead letter → raises
          :class:`MaintenanceAppendFailure` (event recoverable, not committed);
        * primary I/O failure with a failed dead-letter sink → raises
          :class:`DeadLetterSinkFailure` (nothing recoverable).

        No path ever reports a failed append as success.
        """
        model = self._coerce_strict(event)
        canonical_bytes = canonical_dumps(model)
        digest = canonical_digest(model)
        try:
            return self._incident.append_maintenance_event(model)
        except MaintenanceEventConflict:
            # Divergent duplicate: a policy conflict, not an I/O failure.
            raise
        except OSError as exc:
            try:
                record = self._build_dead_letter(
                    model,
                    canonical_bytes=canonical_bytes,
                    digest=digest,
                    failure_type=FailureType.WRITE_FAILURE,
                    primary_error=exc,
                )
                self._write_dead_letter(record)
            except DeadLetterSinkFailure:
                raise
            except Exception as sink_exc:  # pragma: no cover - defensive
                raise DeadLetterSinkFailure(
                    f"primary append failed and the dead-letter sink also failed: "
                    f"{sink_exc}",
                    primary_error=exc,
                    sink_error=sink_exc,
                ) from sink_exc
            raise MaintenanceAppendFailure(
                f"maintenance append failed ({type(exc).__name__}: {exc}); "
                f"a redacted dead letter was written for replay",
                dead_letter=record,
                primary_error=exc,
            ) from exc

    def _coerce_strict(
        self, event: MaintenanceEvent | dict[str, Any]
    ) -> MaintenanceEvent:
        """Strict-decode *event* into a :class:`MaintenanceEvent` (no writes)."""
        if isinstance(event, MaintenanceEvent):
            return event
        if isinstance(event, dict):
            try:
                return strict_loads(MaintenanceEvent, event)
            except MaintenanceCodecError as exc:
                raise ValueError(
                    f"maintenance event strict decode failed: {exc}"
                ) from exc
        raise ValueError(
            "maintenance event must be a MaintenanceEvent or a canonical dict"
        )

    # ── dead letter ───────────────────────────────────────────────────

    def _build_dead_letter(
        self,
        model: MaintenanceEvent,
        *,
        canonical_bytes: str,
        digest: str,
        failure_type: FailureType,
        primary_error: BaseException,
    ) -> dict[str, Any]:
        """Build one bounded, redacted dead-letter record.

        The record preserves the ORIGINAL canonical bytes and digest so replay
        can re-validate them; only the diagnostic ``failure_detail`` is
        redacted (secret-scrubbed).  The canonical bytes are not redacted
        because replay must recompute their digest exactly.
        """
        return {
            "schema_version": DEAD_LETTER_SCHEMA_VERSION,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "replay_id": _replay_id(model.idempotency_key, digest),
            "idempotency_key": model.idempotency_key,
            "event_kind": model.event_kind.value,
            "digest": digest,
            "failure_type": failure_type.value,
            "failure_detail": redact_text(
                f"{type(primary_error).__name__}: {primary_error}"
            ),
            "canonical_bytes": canonical_bytes,
        }

    def _write_dead_letter(self, record: dict[str, Any]) -> None:
        """Append one dead-letter record (bounded, one attempt, redacted).

        The record is serialized, size-checked against
        :data:`MAX_DEAD_LETTER_BYTES`, and appended under an ``flock`` so
        concurrent writers cannot interleave.  An oversized record raises
        :class:`DeadLetterSinkFailure` (never written unbounded).
        """
        line = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        data = (line + "\n").encode("utf-8")
        if len(data) > MAX_DEAD_LETTER_BYTES:
            raise DeadLetterSinkFailure(
                f"dead letter is {len(data)} bytes, exceeding the "
                f"{MAX_DEAD_LETTER_BYTES}-byte bound; refused"
            )
        try:
            self._append_line(self.dead_letter_path, data)
        except OSError as exc:
            raise DeadLetterSinkFailure(
                f"dead-letter sink failed: {type(exc).__name__}: {exc}",
                sink_error=exc,
            ) from exc

    # ── replay ────────────────────────────────────────────────────────

    def replay_dead_letters(self) -> ReplayReport:
        """Replay every pending dead letter at most once and record dispositions.

        For each dead letter with no prior disposition:

        * validate the original schema and digest (strict-decode the
          ``canonical_bytes`` and recompute the canonical digest);
        * reuse the occurrence idempotency key;
        * append the original logical event at most once (the journal's atomic
          lookup→append deduplicates exact duplicates and rejects divergent
          duplicates);
        * record the disposition append-only.

        If recording a disposition fails, :class:`DeadLetterSinkFailure` is
        raised and no report is returned — a sink failure is never reported as
        success.
        """
        already_dispositioned = {
            record.get("replay_id")
            for record in _read_ndjson(self.disposition_path)
        }
        dispositions: list[ReplayDisposition] = []
        for record in _read_ndjson(self.dead_letter_path):
            replay_id = record.get("replay_id")
            if replay_id in already_dispositioned:
                continue
            disposition = self._replay_one(record)
            self._record_disposition(disposition)
            dispositions.append(disposition)
        return ReplayReport(dispositions=tuple(dispositions))

    def _replay_one(self, record: dict[str, Any]) -> ReplayDisposition:
        """Validate and replay one dead-letter record; return its disposition."""
        replay_id = str(record.get("replay_id", ""))
        idempotency_key = str(record.get("idempotency_key", ""))
        digest = str(record.get("digest", ""))

        if record.get("schema_version") != DEAD_LETTER_SCHEMA_VERSION:
            return ReplayDisposition(
                replay_id=replay_id,
                idempotency_key=idempotency_key,
                outcome=ReplayOutcome.INVALID,
                seq=None,
                detail="unsupported dead-letter schema version",
            )
        try:
            model = self._validate_dead_letter(record, digest=digest)
        except ValueError as exc:
            return ReplayDisposition(
                replay_id=replay_id,
                idempotency_key=idempotency_key,
                outcome=ReplayOutcome.INVALID,
                seq=None,
                detail=redact_text(str(exc)),
            )
        if model.occurrence_id != idempotency_key:
            return ReplayDisposition(
                replay_id=replay_id,
                idempotency_key=idempotency_key,
                outcome=ReplayOutcome.INVALID,
                seq=None,
                detail=(
                    "dead-letter idempotency key does not match the "
                    "canonical event occurrence_id"
                ),
            )

        existing = self._incident.lookup_maintenance_event(model.occurrence_id)
        if existing is not None:
            stored = existing.get("payload") or {}
            try:
                stored_digest = canonical_digest(
                    strict_loads(MaintenanceEvent, stored)
                )
            except Exception:
                stored_digest = None
            if stored_digest == digest:
                return ReplayDisposition(
                    replay_id=replay_id,
                    idempotency_key=idempotency_key,
                    outcome=ReplayOutcome.ALREADY_PRESENT,
                    seq=existing.get("seq"),
                    detail="original logical event already committed",
                )
            return ReplayDisposition(
                replay_id=replay_id,
                idempotency_key=idempotency_key,
                outcome=ReplayOutcome.CONFLICT,
                seq=None,
                detail=(
                    "divergent duplicate already committed for this occurrence; "
                    "history not rewritten"
                ),
            )

        try:
            appended = self._incident.append_maintenance_event(model)
        except MaintenanceEventConflict as exc:
            return ReplayDisposition(
                replay_id=replay_id,
                idempotency_key=idempotency_key,
                outcome=ReplayOutcome.CONFLICT,
                seq=None,
                detail=redact_text(f"{type(exc).__name__}: {exc}"),
            )
        except OSError as exc:
            return ReplayDisposition(
                replay_id=replay_id,
                idempotency_key=idempotency_key,
                outcome=ReplayOutcome.REPLAY_FAILED,
                seq=None,
                detail=redact_text(f"{type(exc).__name__}: {exc}"),
            )
        return ReplayDisposition(
            replay_id=replay_id,
            idempotency_key=idempotency_key,
            outcome=ReplayOutcome.REPLAYED,
            seq=appended.get("seq"),
            detail="appended by replay",
        )

    def _validate_dead_letter(
        self, record: dict[str, Any], *, digest: str
    ) -> MaintenanceEvent:
        """Strict-decode a dead letter's canonical bytes and verify its digest.

        Raises ``ValueError`` when the record is malformed, the canonical bytes
        do not strict-decode, or the recomputed digest differs from the stored
        digest.  This is the "validate original schema/digest" gate for replay.
        """
        canonical_bytes = record.get("canonical_bytes")
        if not isinstance(canonical_bytes, str) or not canonical_bytes:
            raise ValueError("dead letter is missing canonical_bytes")
        if not digest or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise ValueError("dead letter carries a malformed digest")
        try:
            raw = json.loads(canonical_bytes)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"dead letter canonical bytes are not valid JSON: {exc}"
            ) from exc
        try:
            model = strict_loads(MaintenanceEvent, raw)
        except MaintenanceCodecError as exc:
            raise ValueError(
                f"dead letter canonical bytes do not strict-decode: {exc}"
            ) from exc
        if canonical_digest(model) != digest:
            raise ValueError(
                "dead letter digest does not match its canonical bytes"
            )
        return model

    def _record_disposition(self, disposition: ReplayDisposition) -> None:
        """Append one disposition record (append-only, never rewritten)."""
        line = json.dumps(
            disposition.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        try:
            self._append_line(self.disposition_path, (line + "\n").encode("utf-8"))
        except OSError as exc:
            raise DeadLetterSinkFailure(
                f"disposition sink failed: {type(exc).__name__}: {exc}",
                sink_error=exc,
            ) from exc

    # ── low-level append ──────────────────────────────────────────────

    def _append_line(self, path: Path, data: bytes) -> None:
        """Append *data* to *path* under an exclusive flock (fsync'd)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(fd, data)
            os.fsync(fd)
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass


__all__ = [
    "DEAD_LETTER_FILE",
    "DEAD_LETTER_SCHEMA_VERSION",
    "DISPOSITION_FILE",
    "MAX_DEAD_LETTER_BYTES",
    "DeadLetterSinkFailure",
    "FailureType",
    "MaintenanceAppendFailure",
    "MaintenanceLedger",
    "MaintenanceLedgerError",
    "ReplayDisposition",
    "ReplayOutcome",
    "ReplayReport",
    "MaintenanceEventConflict",
]
