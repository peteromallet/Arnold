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
import hashlib
import json
import os
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
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
                current = (
                    int(raw.strip())
                    if raw.strip()
                    else self._recover_durable_sequence()
                )
            except (ValueError, FileNotFoundError):
                current = self._recover_durable_sequence()
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

    def _recover_durable_sequence(self) -> int:
        """Recover the counter when its advisory sidecar is absent/corrupt.

        ``events.ndjson`` is durable source evidence while ``.events.seq`` is
        only an optimization.  A plan journal can therefore survive a clone,
        import, or artifact restore without its ignored sidecar.  Starting at
        ``-1`` in that case would reuse sequence zero and permanently poison
        every strict projection.  Recovery is only paid on the exceptional
        missing/corrupt-sidecar path and runs while the writer lock is held.
        """
        highest = -1
        try:
            with open(self._ndjson_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        seq = json.loads(line).get("seq")
                    except (json.JSONDecodeError, AttributeError):
                        continue
                    if isinstance(seq, int) and not isinstance(seq, bool):
                        highest = max(highest, seq)
        except FileNotFoundError:
            pass
        return highest

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
# Step 18 — Bounded tail reads and durable journal cursor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JournalCursor:
    """Monotonic cursor over a durable NDJSON event journal.

    Derived **entirely** from the durable ``events.ndjson`` content — never
    from the ``.events.seq`` sidecar, which is advisory metadata whose
    disagreement with the durable records is a *drift signal* (handled by
    :func:`detect_journal_drift`), not a source of authority.

    A cursor captures how many records the journal contains, the highest
    ``seq`` observed in those records, and a SHA-256 digest of the canonical
    record stream so that restarts can detect append-order regressions
    (record-count decrease, content rewrite) from durable evidence alone.

    This is **rebuildable projection evidence**: the same cursor is
    reproducible by re-reading the durable file.  It is not itself authority
    over source state.
    """

    artifact_root: str
    """Absolute path to the journal root."""

    record_count: int
    """Number of valid JSON records observed in ``events.ndjson``."""

    last_seq: Optional[int]
    """Highest ``seq`` value observed, or ``None`` when no records have a seq."""

    digest: str
    """``sha256:...`` digest of the canonical (sorted-key) record stream."""

    computed_at: str
    """ISO-8601 UTC timestamp when this cursor was computed."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_root": self.artifact_root,
            "record_count": self.record_count,
            "last_seq": self.last_seq,
            "digest": self.digest,
            "computed_at": self.computed_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "JournalCursor":
        last_seq = data.get("last_seq")
        return cls(
            artifact_root=str(data["artifact_root"]),
            record_count=int(data["record_count"]),
            last_seq=int(last_seq) if last_seq is not None else None,
            digest=str(data["digest"]),
            computed_at=str(data["computed_at"]),
        )


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_event_journal_tail(artifact_root: Path, limit: int) -> list[dict]:
    """Return the last *limit* events from the journal in file (append) order.

    Uses a fixed-size sliding window (``collections.deque(maxlen=limit)``) so
    memory is bounded by *limit* regardless of journal size.  This makes
    restart work bounded by new events and append order: a caller that only
    needs the most recent events pays O(limit) memory, not O(journal-size).

    The returned list preserves file order, which matches monotonic ``seq``
    order from the flock-guarded writer.  Lines that fail to parse as JSON
    are silently skipped (same semantics as :func:`read_event_journal`).

    Parameters
    ----------
    artifact_root:
        Directory containing ``events.ndjson``.
    limit:
        Maximum number of trailing events to return.  Must be non-negative.
        A limit of ``0`` returns an empty list without reading the file.

    Raises
    ------
    ValueError
        If *limit* is negative.
    """
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if limit == 0:
        return []
    ndjson_path = Path(artifact_root) / _NDJSON_FILE
    if not ndjson_path.exists():
        return []
    window: deque[dict] = deque(maxlen=limit)
    with open(ndjson_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            window.append(event)
    return list(window)


def journal_cursor(artifact_root: Path) -> JournalCursor:
    """Compute a :class:`JournalCursor` from the durable journal content.

    The cursor is read-only and derived purely from ``events.ndjson``.  The
    ``.events.seq`` sidecar is **not** consulted — it is advisory metadata
    and its disagreement with the durable records is a drift signal handled
    by :func:`detect_journal_drift`, not by this function.

    The digest is computed over the concatenation of each record's canonical
    JSON (sorted keys, no extra whitespace), making it stable across
    re-reads of the same content.
    """
    root = str(Path(artifact_root).resolve())
    ndjson_path = Path(artifact_root) / _NDJSON_FILE
    record_count = 0
    last_seq: Optional[int] = None
    hasher = hashlib.sha256()
    if ndjson_path.exists():
        with open(ndjson_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                record_count += 1
                seq = event.get("seq")
                if isinstance(seq, int | float) and seq == int(seq):
                    seq_int = int(seq)
                    if last_seq is None or seq_int > last_seq:
                        last_seq = seq_int
                canonical = json.dumps(
                    event, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                )
                hasher.update(canonical.encode("utf-8"))
                hasher.update(b"\n")
    digest = "sha256:" + hasher.hexdigest()
    return JournalCursor(
        artifact_root=root,
        record_count=record_count,
        last_seq=last_seq,
        digest=digest,
        computed_at=_now_utc_iso(),
    )


# ---------------------------------------------------------------------------
# Step 19 — Sidecar / sequence drift detection from durable evidence
# ---------------------------------------------------------------------------


def read_sidecar_seq(artifact_root: Path) -> Optional[int]:
    """Read the advisory ``.events.seq`` sidecar counter.

    Returns ``None`` when the sidecar is absent or unparseable.  This value
    is **advisory metadata** — it is never treated as authority over the
    durable journal records.  Disagreement between this value and the actual
    highest ``seq`` in ``events.ndjson`` is reported by
    :func:`detect_journal_drift`.
    """
    seq_path = Path(artifact_root) / _SEQ_FILE
    if not seq_path.exists():
        return None
    try:
        raw = seq_path.read_text(encoding="ascii").strip()
        return int(raw) if raw else None
    except (ValueError, OSError):
        return None


@dataclass(frozen=True)
class JournalDrift:
    """A single drift finding derived from durable journal evidence.

    Every field is derived from durable append-only records
    (``events.ndjson``) or the advisory ``.events.seq`` sidecar.  The
    ``evidence`` mapping cites the durable records that prove the drift —
    never labels, liveness signals, WBC receipts, or rebuildable
    projections.

    The ``kind`` is always ``"DRIFT_DETECTED"`` so consumers can filter on a
    single sentinel regardless of drift type.
    """

    kind: str
    """Always ``"DRIFT_DETECTED"``."""

    drift_type: str
    """One of: ``stale_sidecar``, ``future_sidecar``, ``sequence_reset``, ``crash_gap``."""

    detail: str
    """Human-readable description of the drift."""

    evidence: Mapping[str, Any]
    """Durable evidence proving the drift (seq values, record citations, digests)."""

    computed_at: str
    """ISO-8601 UTC timestamp when this finding was computed."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "drift_type": self.drift_type,
            "detail": self.detail,
            "evidence": dict(self.evidence),
            "computed_at": self.computed_at,
        }


def detect_journal_drift(artifact_root: Path) -> list[JournalDrift]:
    """Detect drift between durable journal records and advisory sidecars.

    Returns a list of :class:`JournalDrift` findings, each derived purely
    from durable evidence.  An empty list means no drift was detected.

    Drift types detected
    -------------------
    * ``stale_sidecar`` — ``.events.seq`` lags behind the highest ``seq``
      in ``events.ndjson`` (sidecar not updated after a write).
    * ``future_sidecar`` — ``.events.seq`` is ahead of the highest ``seq``
      in ``events.ndjson`` (crash between seq increment and ndjson append).
    * ``sequence_reset`` — a ``seq`` value in the journal is less than or
      equal to its predecessor in append order (non-monotonic).
    * ``crash_gap`` — a ``seq`` value in the journal skips forward by more
      than 1 from its predecessor in append order (lost intermediate event).

    All evidence is self-healed from durable append-only records: the
    function never writes, never trusts labels or liveness, and never
    rebuilds a projection to decide whether drift occurred.
    """
    root = str(Path(artifact_root).resolve())
    now = _now_utc_iso()
    cursor = journal_cursor(artifact_root)
    sidecar_seq = read_sidecar_seq(artifact_root)
    findings: list[JournalDrift] = []

    # ── Sidecar vs durable journal ──────────────────────────────────
    if sidecar_seq is not None and cursor.last_seq is not None:
        if sidecar_seq < cursor.last_seq:
            findings.append(
                JournalDrift(
                    kind="DRIFT_DETECTED",
                    drift_type="stale_sidecar",
                    detail=(
                        f"Sidecar seq ({sidecar_seq}) is behind durable "
                        f"journal last_seq ({cursor.last_seq}); "
                        f"{cursor.last_seq - sidecar_seq} record(s) not reflected."
                    ),
                    evidence={
                        "artifact_root": root,
                        "sidecar_seq": sidecar_seq,
                        "journal_last_seq": cursor.last_seq,
                        "journal_record_count": cursor.record_count,
                        "journal_digest": cursor.digest,
                    },
                    computed_at=now,
                )
            )
        elif sidecar_seq > cursor.last_seq:
            findings.append(
                JournalDrift(
                    kind="DRIFT_DETECTED",
                    drift_type="future_sidecar",
                    detail=(
                        f"Sidecar seq ({sidecar_seq}) is ahead of durable "
                        f"journal last_seq ({cursor.last_seq}); "
                        f"{sidecar_seq - cursor.last_seq} record(s) lost before fsync."
                    ),
                    evidence={
                        "artifact_root": root,
                        "sidecar_seq": sidecar_seq,
                        "journal_last_seq": cursor.last_seq,
                        "journal_record_count": cursor.record_count,
                        "journal_digest": cursor.digest,
                    },
                    computed_at=now,
                )
            )

    # ── Intra-journal monotonicity (sequence reset / crash gap) ─────
    prev_seq: Optional[int] = None
    prev_record: Optional[dict] = None
    index = 0
    for event in stream_event_journal(artifact_root):
        seq = event.get("seq")
        if not isinstance(seq, int):
            index += 1
            continue
        if prev_seq is not None:
            if seq <= prev_seq:
                findings.append(
                    JournalDrift(
                        kind="DRIFT_DETECTED",
                        drift_type="sequence_reset",
                        detail=(
                            f"seq reset at append index {index}: "
                            f"{prev_seq} -> {seq} (non-monotonic)."
                        ),
                        evidence={
                            "artifact_root": root,
                            "append_index": index,
                            "prev_seq": prev_seq,
                            "this_seq": seq,
                            "prev_record": dict(prev_record) if prev_record else None,
                            "this_record": dict(event),
                            "journal_digest": cursor.digest,
                        },
                        computed_at=now,
                    )
                )
            elif seq > prev_seq + 1:
                findings.append(
                    JournalDrift(
                        kind="DRIFT_DETECTED",
                        drift_type="crash_gap",
                        detail=(
                            f"seq gap at append index {index}: "
                            f"{prev_seq} -> {seq}, expected {prev_seq + 1} "
                            f"({seq - prev_seq - 1} missing)."
                        ),
                        evidence={
                            "artifact_root": root,
                            "append_index": index,
                            "prev_seq": prev_seq,
                            "this_seq": seq,
                            "expected_seq": prev_seq + 1,
                            "missing_count": seq - prev_seq - 1,
                            "prev_record": dict(prev_record) if prev_record else None,
                            "this_record": dict(event),
                            "journal_digest": cursor.digest,
                        },
                        computed_at=now,
                    )
                )
        prev_seq = seq
        prev_record = event
        index += 1

    return findings


# ---------------------------------------------------------------------------
# Step 20-22 — Compaction manifest, legal-hold retention, bounded IO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegalHoldRange:
    """A closed ``[from_seq, to_seq]`` range of event seqs under legal hold.

    Events whose ``seq`` falls within a legal-hold range must **never** be
    compacted — they are retained verbatim with their exact digest preserved
    so that legal-hold evidence survives any compaction.

    This is a pure value object: it carries no authority of its own.  A
    legal hold is only honoured by :func:`compute_compaction_manifest` when
    it passes validation; invalid holds are rejected with typed drift.
    """

    from_seq: int
    """Inclusive lower bound of the held range."""

    to_seq: int
    """Inclusive upper bound of the held range."""

    def contains(self, seq: int) -> bool:
        return self.from_seq <= seq <= self.to_seq

    def to_dict(self) -> dict[str, Any]:
        return {"from_seq": self.from_seq, "to_seq": self.to_seq}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LegalHoldRange":
        return cls(from_seq=int(data["from_seq"]), to_seq=int(data["to_seq"]))


_COMPACTION_MANIFEST_VERSION = 1
_COMPACTION_MANIFEST_KIND = "COMPACTION_MANIFEST"


@dataclass(frozen=True)
class CompactionManifest:
    """Manifest describing the compaction of an event-journal range.

    A compaction manifest is a **rebuildable projection**: every durable
    field (range, counts, digests) is derived purely from the append-only
    ``events.ndjson`` records.  Re-reading the same durable records with
    :func:`compute_compaction_manifest` reproduces an identical manifest
    (see :func:`manifest_replay_digest_equal`).

    It is **never action authority**.  ``kind`` marks it as a projection
    descriptor (``"COMPACTION_MANIFEST"``), not an action, approval, or
    blessing.  The manifest cannot bless a projection as authority, override
    durable evidence, or authorize any state change.  Parity between a
    manifest and its rebuild (see
    :func:`arnold_pipelines.megaplan.observability.projection_rebuild.verify_compaction_manifest_rebuildable`)
    proves the manifest faithfully projects durable evidence; a mismatch
    means it is stale or tampered and must not be trusted as authority.
    """

    manifest_version: int
    kind: str
    from_seq: int
    """Inclusive lower bound of the compacted range."""

    to_seq: int
    """Inclusive upper bound of the compacted range."""

    compacted_record_count: int
    """Number of records eligible for compaction (not under legal hold)."""

    compacted_digest: str
    """SHA-256 over the canonical records eligible for compaction."""

    preserved_record_count: int
    """Number of records in the range preserved by legal holds."""

    preserved_digest: str
    """SHA-256 over the canonical preserved (legal-hold) records."""

    legal_holds: tuple[LegalHoldRange, ...]
    computed_at: str
    """Non-authoritative timestamp; ignored by replay equality checks."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "kind": self.kind,
            "from_seq": self.from_seq,
            "to_seq": self.to_seq,
            "compacted_record_count": self.compacted_record_count,
            "compacted_digest": self.compacted_digest,
            "preserved_record_count": self.preserved_record_count,
            "preserved_digest": self.preserved_digest,
            "legal_holds": [h.to_dict() for h in self.legal_holds],
            "computed_at": self.computed_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompactionManifest":
        return cls(
            manifest_version=int(data["manifest_version"]),
            kind=str(data["kind"]),
            from_seq=int(data["from_seq"]),
            to_seq=int(data["to_seq"]),
            compacted_record_count=int(data["compacted_record_count"]),
            compacted_digest=str(data["compacted_digest"]),
            preserved_record_count=int(data["preserved_record_count"]),
            preserved_digest=str(data["preserved_digest"]),
            legal_holds=tuple(
                LegalHoldRange.from_dict(h) for h in data.get("legal_holds", [])
            ),
            computed_at=str(data["computed_at"]),
        )


def _canonical_records_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """SHA-256 digest over the canonical (sorted-key) JSON of each record.

    Records are joined by newlines so the digest is order-sensitive and
    stable across re-reads of the same content.  An empty sequence yields a
    well-defined digest of the empty stream.  This mirrors the canonical
    serialization used by :func:`journal_cursor`.
    """
    hasher = hashlib.sha256()
    for record in records:
        canonical = json.dumps(
            dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        hasher.update(canonical.encode("utf-8"))
        hasher.update(b"\n")
    return "sha256:" + hasher.hexdigest()


def read_compaction_window(
    artifact_root: Path, from_seq: int, to_seq: int
) -> list[dict]:
    """Return events with ``from_seq <= seq <= to_seq`` with bounded IO.

    Streams the append-only journal in file order and stops as soon as a
    record's ``seq`` exceeds ``to_seq``.  Because the journal is append-only
    under ``fcntl.flock`` (monotonic ``seq`` in file order), this bounds the
    read to records up to and including ``to_seq`` — a prefix compaction
    reads only the prefix, not the whole journal.

    Memory is bounded by the window size: only records inside the range are
    materialized.  Lines that fail to parse as JSON are skipped (same
    semantics as :func:`read_event_journal`).

    Raises
    ------
    ValueError
        If ``from_seq > to_seq``.
    """
    if from_seq > to_seq:
        raise ValueError(
            f"compaction window from_seq ({from_seq}) must be <= to_seq ({to_seq})"
        )
    window: list[dict] = []
    for event in stream_event_journal(artifact_root):
        seq = event.get("seq")
        if not isinstance(seq, int):
            continue
        if seq < from_seq:
            continue
        if seq > to_seq:
            break
        window.append(event)
    return window


def validate_compaction_legal_holds(
    artifact_root: Path,
    from_seq: int,
    to_seq: int,
    legal_holds: Sequence[LegalHoldRange],
) -> list[JournalDrift]:
    """Validate legal-hold ranges, emitting typed drift for invalid ones.

    A legal hold is rejected (with ``DRIFT_DETECTED``) when it is:

    * ``legal_hold_ambiguous`` — inverted (``from_seq > to_seq``).
    * ``legal_hold_out_of_range`` — a "missing" hold that does not intersect
      the compaction window ``[from_seq, to_seq]`` at all
      (``hold.to_seq < from_seq`` or ``hold.from_seq > to_seq``); it protects
      nothing being compacted and is therefore ambiguous for this compaction.
    * ``legal_hold_overlap`` — touches or overlaps another hold at a boundary
      (closed intervals ``[a, b]`` and ``[c, d]`` with ``b >= c``).

    Every finding cites durable, reconstructable evidence (the offending
    ranges and the compaction window) — never labels, liveness, WBC receipts,
    or rebuilt projections.  Validation is pure range arithmetic and performs
    no journal IO.
    """
    root = str(Path(artifact_root).resolve())
    now = _now_utc_iso()
    window_desc = {"from_seq": from_seq, "to_seq": to_seq}
    findings: list[JournalDrift] = []
    holds = tuple(legal_holds)

    for hold in holds:
        if hold.from_seq > hold.to_seq:
            findings.append(
                JournalDrift(
                    kind="DRIFT_DETECTED",
                    drift_type="legal_hold_ambiguous",
                    detail=(
                        f"legal hold from_seq ({hold.from_seq}) is greater "
                        f"than to_seq ({hold.to_seq}); range is ambiguous."
                    ),
                    evidence={
                        "artifact_root": root,
                        "hold": hold.to_dict(),
                        "compaction_window": dict(window_desc),
                    },
                    computed_at=now,
                )
            )
        elif hold.to_seq < from_seq or hold.from_seq > to_seq:
            findings.append(
                JournalDrift(
                    kind="DRIFT_DETECTED",
                    drift_type="legal_hold_out_of_range",
                    detail=(
                        f"legal hold [{hold.from_seq},{hold.to_seq}] does not "
                        f"intersect the compaction window "
                        f"[{from_seq},{to_seq}]; it protects nothing being "
                        f"compacted (missing from this compaction)."
                    ),
                    evidence={
                        "artifact_root": root,
                        "hold": hold.to_dict(),
                        "compaction_window": dict(window_desc),
                    },
                    computed_at=now,
                )
            )

    # Boundary-overlapping holds (closed intervals touching or overlapping).
    valid_holds = sorted(
        (h for h in holds if h.from_seq <= h.to_seq),
        key=lambda h: (h.from_seq, h.to_seq),
    )
    for left, right in zip(valid_holds, valid_holds[1:]):
        if left.to_seq >= right.from_seq:
            findings.append(
                JournalDrift(
                    kind="DRIFT_DETECTED",
                    drift_type="legal_hold_overlap",
                    detail=(
                        f"legal holds overlap at a boundary: "
                        f"[{left.from_seq},{left.to_seq}] and "
                        f"[{right.from_seq},{right.to_seq}]."
                    ),
                    evidence={
                        "artifact_root": root,
                        "left_hold": left.to_dict(),
                        "right_hold": right.to_dict(),
                        "compaction_window": dict(window_desc),
                    },
                    computed_at=now,
                )
            )

    return findings


def compute_compaction_manifest(
    artifact_root: Path,
    from_seq: int,
    to_seq: int,
    legal_holds: Sequence[LegalHoldRange] = (),
) -> tuple[Optional[CompactionManifest], list[JournalDrift]]:
    """Compute a compaction manifest for ``[from_seq, to_seq]``.

    Returns ``(manifest, drift_findings)``.  When legal-hold validation emits
    any drift (ambiguous, missing, or boundary-overlapping holds), the
    manifest is **not** produced (``None``) and the drift findings are
    returned — compaction is refused rather than blessing an ambiguous range.

    Otherwise:

    * Reads the compaction window with bounded IO
      (:func:`read_compaction_window`).
    * Partitions the window into *compacted* records (eligible for
      compaction) and *preserved* records (covered by a legal hold, retained
      verbatim with their exact digest).
    * Computes exact digests over both partitions so legal-hold evidence and
      compacted evidence are provably preserved.

    The manifest is a rebuildable projection of durable evidence; it is not
    authority over source state.

    Raises
    ------
    ValueError
        If ``from_seq > to_seq``.
    """
    if from_seq > to_seq:
        raise ValueError(
            f"compaction window from_seq ({from_seq}) must be <= to_seq ({to_seq})"
        )

    drift = validate_compaction_legal_holds(
        artifact_root, from_seq, to_seq, legal_holds
    )
    if drift:
        return None, drift

    holds = tuple(legal_holds)
    window = read_compaction_window(artifact_root, from_seq, to_seq)
    compacted: list[dict] = []
    preserved: list[dict] = []
    for record in window:
        seq = record.get("seq")
        if isinstance(seq, int) and any(h.contains(seq) for h in holds):
            preserved.append(record)
        else:
            compacted.append(record)

    return CompactionManifest(
        manifest_version=_COMPACTION_MANIFEST_VERSION,
        kind=_COMPACTION_MANIFEST_KIND,
        from_seq=from_seq,
        to_seq=to_seq,
        compacted_record_count=len(compacted),
        compacted_digest=_canonical_records_digest(compacted),
        preserved_record_count=len(preserved),
        preserved_digest=_canonical_records_digest(preserved),
        legal_holds=holds,
        computed_at=_now_utc_iso(),
    ), []


def rebuild_compaction_manifest(
    manifest: CompactionManifest,
    artifact_root: Path,
) -> tuple[Optional[CompactionManifest], list[JournalDrift]]:
    """Re-derive a compaction manifest from durable evidence.

    Re-runs :func:`compute_compaction_manifest` over the manifest's stored
    range and legal holds against the durable journal.  This is the rebuild
    path that proves a manifest is a faithful projection of durable
    evidence: when the durable records are unchanged, the rebuilt manifest's
    digests and counts equal the original (see
    :func:`manifest_replay_digest_equal`).

    The original manifest is never treated as authority — the rebuild is
    computed solely from durable records.
    """
    return compute_compaction_manifest(
        artifact_root,
        manifest.from_seq,
        manifest.to_seq,
        manifest.legal_holds,
    )


def manifest_replay_digest_equal(
    a: CompactionManifest,
    b: CompactionManifest,
) -> bool:
    """Return ``True`` when two manifests share identical durable fields.

    Compares every durable-derived field (range, counts, digests, legal
    holds) while ignoring the non-authoritative ``computed_at`` timestamp.
    Used to prove replay digest equality and absence of a rebuild loop:
    re-deriving a manifest from unchanged durable evidence yields an equal
    manifest.
    """
    return (
        a.from_seq == b.from_seq
        and a.to_seq == b.to_seq
        and a.compacted_record_count == b.compacted_record_count
        and a.compacted_digest == b.compacted_digest
        and a.preserved_record_count == b.preserved_record_count
        and a.preserved_digest == b.preserved_digest
        and a.legal_holds == b.legal_holds
    )


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
    "CompactionManifest",
    "EventEnvelope",
    "EventSink",
    "BackendEventJournal",
    "BackendEventSink",
    "JournalCursor",
    "JournalDrift",
    "LegalHoldRange",
    "NdjsonEventJournal",
    "NdjsonEventSink",
    "compute_compaction_manifest",
    "detect_journal_drift",
    "journal_cursor",
    "manifest_replay_digest_equal",
    "read_compaction_window",
    "read_event_journal",
    "read_event_journal_paged",
    "read_event_journal_tail",
    "read_sidecar_seq",
    "rebuild_compaction_manifest",
    "stream_event_journal",
    "validate_compaction_legal_holds",
]
