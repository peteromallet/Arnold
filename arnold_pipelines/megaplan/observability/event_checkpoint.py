"""Cursor-bounded compatibility projection for large plan event journals.

``events.ndjson`` remains the append-only source evidence.  This module keeps a
content-addressed, atomically-published acceleration checkpoint beside it so
ordinary status and supervision reads fold only records appended after the
last durable cursor.  A checkpoint never grants workflow authority.

The checkpoint is deliberately tied to the journal inode, store incarnation,
restore generation, fold version, byte cursor, hash-chain prefix, and a byte
anchor immediately before the cursor.  Invalid acceleration state is rejected;
callers may explicitly permit a one-time streaming rebuild.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import resource
import tempfile
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Mapping

CHECKPOINT_SCHEMA_VERSION = 1
SUPERVISION_FOLD_VERSION = "megaplan-supervision-v1"
DEFAULT_MAX_TAIL_EVENTS = 5_000
ANCHOR_BYTES = 64 * 1024

_EVENTS_FILE = "events.ndjson"
_SEQ_FILE = ".events.seq"
_CHECKPOINT_FILE = ".events.supervision-checkpoint.json"
_CHECKPOINT_LOCK_FILE = ".events.supervision-checkpoint.lock"
_INCARNATION_FILE = ".events.store-incarnation"
_RESTORE_GENERATION_FILE = ".events.restore-generation"


class EventCheckpointError(RuntimeError):
    """Acceleration state could not be trusted."""


@dataclass(frozen=True)
class BoundedEventProjection:
    """Bounded event window plus durable cursor and performance receipt."""

    events: tuple[dict[str, Any], ...]
    record_count: int
    last_seq: int | None
    latest_by_kind: Mapping[str, dict[str, Any]]
    cursor: Mapping[str, Any]
    receipt: Mapping[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _checkpoint_digest(payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    body.pop("checkpoint_digest", None)
    return "sha256:" + hashlib.sha256(_canonical_json(body)).hexdigest()


def _chain_hash(previous: str, raw_line: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(previous.encode("ascii"))
    hasher.update(b"\0")
    hasher.update(raw_line.rstrip(b"\r\n"))
    hasher.update(b"\n")
    return "sha256:" + hasher.hexdigest()


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical_json(payload) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _read_or_create_incarnation(plan_dir: Path) -> str:
    path = plan_dir / _INCARNATION_FILE
    try:
        value = path.read_text(encoding="ascii").strip()
    except OSError:
        value = ""
    if value:
        return value
    candidate = str(uuid.uuid4())
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return path.read_text(encoding="ascii").strip()
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(candidate + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return candidate


def _restore_generation(plan_dir: Path) -> str:
    try:
        value = (plan_dir / _RESTORE_GENERATION_FILE).read_text(
            encoding="ascii"
        ).strip()
    except OSError:
        value = ""
    return value or "0"


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Linux reports KiB; macOS reports bytes.
    return value * 1024 if value < 10_000_000 else value


def _event_seq(event: Mapping[str, Any]) -> int | None:
    value = event.get("seq")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _fold_lines(
    handle: BinaryIO,
    *,
    tail: deque[dict[str, Any]],
    latest_by_kind: dict[str, dict[str, Any]],
    prefix_hash: str,
    record_count: int,
    last_seq: int | None,
    tolerate_sequence_anomalies: bool = False,
    sequence_anomalies: list[dict[str, Any]] | None = None,
) -> tuple[str, int, int | None, int, int, int]:
    """Fold valid JSON records from *handle* into the bounded projection.

    A checkpointed (warm) fold remains fail-closed: seeing a sequence that is
    not strictly after the checkpoint is evidence that the append boundary is
    not trustworthy.  A cold rebuild is different.  It is explicitly a
    recovery read over retained evidence, and old workspaces can contain a
    duplicated/reset prefix from a store restore.  In that mode we retain all
    records, surface the anomaly in the receipt, and advance the cursor using
    the greatest observed sequence rather than regressing it.
    """
    bytes_read = 0
    fold_count = 0
    sequence_anomaly_count = 0
    for raw_line in handle:
        bytes_read += len(raw_line)
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(event, dict):
            continue
        seq = _event_seq(event)
        if seq is not None and last_seq is not None and seq <= last_seq:
            sequence_anomaly_count += 1
            if sequence_anomalies is not None and len(sequence_anomalies) < 20:
                sequence_anomalies.append(
                    {
                        "seq": seq,
                        "previous_seq": last_seq,
                        "record_number": record_count + 1,
                        "byte_offset": bytes_read - len(raw_line),
                        "kind": event.get("kind"),
                    }
                )
            if not tolerate_sequence_anomalies:
                raise EventCheckpointError(
                    f"non-monotonic event seq beyond checkpoint: {seq} <= {last_seq}"
                )
        prefix_hash = _chain_hash(prefix_hash, raw_line)
        record_count += 1
        fold_count += 1
        if seq is not None:
            # Recovery folds may encounter a reset prefix.  Never let the
            # durable cursor move backwards after observing a later sequence.
            last_seq = seq if last_seq is None else max(last_seq, seq)
        tail.append(event)
        kind = event.get("kind")
        if isinstance(kind, str) and kind:
            latest_by_kind[kind] = event
            payload = event.get("payload")
            if kind == "plan_finished" and isinstance(payload, dict):
                state = payload.get("state")
                if isinstance(state, str) and state:
                    latest_by_kind[f"{kind}:state={state.casefold()}"] = event
    return (
        prefix_hash,
        record_count,
        last_seq,
        bytes_read,
        fold_count,
        sequence_anomaly_count,
    )


def _anchor(path: Path, offset: int) -> tuple[int, str, int]:
    start = max(0, offset - ANCHOR_BYTES)
    length = offset - start
    with path.open("rb") as handle:
        handle.seek(start)
        raw = handle.read(length)
    if len(raw) != length:
        raise EventCheckpointError("journal anchor is shorter than checkpoint cursor")
    return start, "sha256:" + hashlib.sha256(raw).hexdigest(), len(raw)


def _load_checkpoint(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EventCheckpointError("checkpoint_missing") from exc
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EventCheckpointError("checkpoint_corrupt") from exc
    if not isinstance(payload, dict):
        raise EventCheckpointError("checkpoint_not_object")
    if payload.get("checkpoint_digest") != _checkpoint_digest(payload):
        raise EventCheckpointError("checkpoint_digest_mismatch")
    return payload


def _validate_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    journal_path: Path,
    incarnation: str,
    restore_generation: str,
    max_tail_events: int,
) -> os.stat_result:
    if checkpoint.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise EventCheckpointError("checkpoint_schema_mismatch")
    if checkpoint.get("fold_version") != SUPERVISION_FOLD_VERSION:
        raise EventCheckpointError("checkpoint_fold_version_mismatch")
    if checkpoint.get("store_incarnation") != incarnation:
        raise EventCheckpointError("checkpoint_store_incarnation_mismatch")
    if checkpoint.get("restore_generation") != restore_generation:
        raise EventCheckpointError("checkpoint_restore_generation_mismatch")
    if checkpoint.get("journal_path") != str(journal_path.resolve()):
        raise EventCheckpointError("checkpoint_journal_path_mismatch")
    if int(checkpoint.get("max_tail_events") or -1) != max_tail_events:
        raise EventCheckpointError("checkpoint_tail_policy_mismatch")
    try:
        stat = journal_path.stat()
        offset = int(checkpoint["source_offset"])
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise EventCheckpointError("checkpoint_cursor_invalid") from exc
    if offset < 0 or stat.st_size < offset:
        raise EventCheckpointError("checkpoint_cursor_beyond_journal")
    if (
        int(checkpoint.get("source_device") or -1) != stat.st_dev
        or int(checkpoint.get("source_inode") or -1) != stat.st_ino
    ):
        raise EventCheckpointError("checkpoint_source_incarnation_mismatch")
    anchor_start, anchor_digest, anchor_length = _anchor(journal_path, offset)
    checkpoint_anchor_start = checkpoint.get("anchor_start")
    checkpoint_anchor_length = checkpoint.get("anchor_length")
    if (
        not isinstance(checkpoint_anchor_start, int)
        or checkpoint_anchor_start != anchor_start
        or not isinstance(checkpoint_anchor_length, int)
        or checkpoint_anchor_length != anchor_length
        or checkpoint.get("anchor_digest") != anchor_digest
    ):
        raise EventCheckpointError("checkpoint_prefix_anchor_mismatch")
    if not isinstance(checkpoint.get("tail_events"), list):
        raise EventCheckpointError("checkpoint_tail_invalid")
    if not isinstance(checkpoint.get("latest_by_kind"), dict):
        raise EventCheckpointError("checkpoint_latest_index_invalid")
    return stat


def _publish_checkpoint(
    *,
    plan_dir: Path,
    journal_path: Path,
    stat: os.stat_result,
    incarnation: str,
    restore_generation: str,
    max_tail_events: int,
    source_offset: int,
    record_count: int,
    last_seq: int | None,
    prefix_hash: str,
    tail: deque[dict[str, Any]],
    latest_by_kind: Mapping[str, dict[str, Any]],
    fold_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    anchor_start, anchor_digest, anchor_length = _anchor(
        journal_path, source_offset
    )
    payload: dict[str, Any] = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "fold_version": SUPERVISION_FOLD_VERSION,
        "store_incarnation": incarnation,
        "restore_generation": restore_generation,
        "journal_path": str(journal_path.resolve()),
        "source_device": stat.st_dev,
        "source_inode": stat.st_ino,
        "source_offset": source_offset,
        "source_record_count": record_count,
        "source_last_seq": last_seq,
        "source_prefix_hash": prefix_hash,
        "anchor_start": anchor_start,
        "anchor_length": anchor_length,
        "anchor_digest": anchor_digest,
        "max_tail_events": max_tail_events,
        "tail_events": list(tail),
        "latest_by_kind": dict(latest_by_kind),
        "last_fold_receipt": dict(fold_receipt),
        "published_at": _utc_now(),
        "_non_authoritative": True,
    }
    payload["checkpoint_digest"] = _checkpoint_digest(payload)
    _atomic_write(plan_dir / _CHECKPOINT_FILE, payload)
    return payload


def read_bounded_event_projection(
    plan_dir: str | Path,
    *,
    max_tail_events: int = DEFAULT_MAX_TAIL_EVENTS,
    allow_rebuild: bool = True,
    publish_checkpoint: bool = True,
) -> BoundedEventProjection:
    """Read a supervision projection by folding only events after its cursor.

    A missing or invalid checkpoint is rebuilt exactly once by streaming the
    journal when ``allow_rebuild`` is true.  ``allow_rebuild=False`` is the
    strict fail-closed probe used by canaries and recovery admission.
    """

    if max_tail_events < 1:
        raise ValueError("max_tail_events must be positive")
    root = Path(plan_dir)
    journal_path = root / _EVENTS_FILE
    started = time.monotonic()
    rss_before = _rss_bytes()
    if not journal_path.exists():
        return BoundedEventProjection(
            events=(),
            record_count=0,
            last_seq=None,
            latest_by_kind={},
            cursor={"source_offset": 0, "source_prefix_hash": "sha256:0"},
            receipt={
                "mode": "empty",
                "bytes_read": 0,
                "fold_count": 0,
                "sequence_anomaly_count": 0,
                "sequence_anomalies": [],
                "degraded": False,
                "wall_time_seconds": time.monotonic() - started,
                "peak_rss_bytes": _rss_bytes(),
            },
        )

    checkpoint_lock_path = root / _CHECKPOINT_LOCK_FILE
    seq_lock_path = root / _SEQ_FILE
    if publish_checkpoint:
        checkpoint_lock_fd = os.open(
            str(checkpoint_lock_path), os.O_RDWR | os.O_CREAT, 0o644
        )
        seq_lock_fd = os.open(
            str(seq_lock_path), os.O_RDWR | os.O_CREAT, 0o644
        )
        checkpoint_lock_mode = fcntl.LOCK_EX
    else:
        required = (
            checkpoint_lock_path,
            seq_lock_path,
            root / _CHECKPOINT_FILE,
            root / _INCARNATION_FILE,
        )
        if not all(path.exists() for path in required):
            raise EventCheckpointError("checkpoint_missing")
        checkpoint_lock_fd = os.open(str(checkpoint_lock_path), os.O_RDONLY)
        seq_lock_fd = os.open(str(seq_lock_path), os.O_RDONLY)
        checkpoint_lock_mode = fcntl.LOCK_SH
    rebuild_reason = ""
    sequence_anomalies: list[dict[str, Any]] = []
    prior_sequence_anomaly_count = 0
    try:
        fcntl.flock(checkpoint_lock_fd, checkpoint_lock_mode)
        fcntl.flock(seq_lock_fd, fcntl.LOCK_SH)
        if publish_checkpoint:
            incarnation = _read_or_create_incarnation(root)
        else:
            try:
                incarnation = (root / _INCARNATION_FILE).read_text(
                    encoding="ascii"
                ).strip()
            except OSError as exc:
                raise EventCheckpointError(
                    "checkpoint_store_incarnation_missing"
                ) from exc
            if not incarnation:
                raise EventCheckpointError("checkpoint_store_incarnation_missing")
        restore_generation = _restore_generation(root)
        try:
            checkpoint = _load_checkpoint(root / _CHECKPOINT_FILE)
            stat = _validate_checkpoint(
                checkpoint,
                journal_path=journal_path,
                incarnation=incarnation,
                restore_generation=restore_generation,
                max_tail_events=max_tail_events,
            )
            mode = "warm"
            tail = deque(checkpoint["tail_events"], maxlen=max_tail_events)
            latest_by_kind = {
                str(kind): dict(event)
                for kind, event in checkpoint["latest_by_kind"].items()
                if isinstance(event, dict)
            }
            offset = int(checkpoint["source_offset"])
            prefix_hash = str(checkpoint["source_prefix_hash"])
            record_count = int(checkpoint["source_record_count"])
            raw_last_seq = checkpoint.get("source_last_seq")
            last_seq = int(raw_last_seq) if isinstance(raw_last_seq, int) else None
            prior_receipt = checkpoint.get("last_fold_receipt")
            if isinstance(prior_receipt, Mapping):
                raw_prior_count = prior_receipt.get("sequence_anomaly_count")
                if isinstance(raw_prior_count, int) and raw_prior_count > 0:
                    prior_sequence_anomaly_count = raw_prior_count
                prior_samples = prior_receipt.get("sequence_anomalies")
                if isinstance(prior_samples, list):
                    sequence_anomalies.extend(
                        item for item in prior_samples[:20] if isinstance(item, dict)
                    )
        except EventCheckpointError as exc:
            if not allow_rebuild:
                raise
            rebuild_reason = str(exc)
            mode = "cold_rebuild"
            stat = journal_path.stat()
            tail = deque(maxlen=max_tail_events)
            latest_by_kind = {}
            offset = 0
            prefix_hash = "sha256:genesis"
            record_count = 0
            last_seq = None

        bytes_read = 0
        fold_count = 0

        def fold_current_view() -> tuple[int, int]:
            """Fold the selected view and return ``(offset, anomaly_count)``."""

            nonlocal prefix_hash, record_count, last_seq
            nonlocal bytes_read, fold_count
            with journal_path.open("rb") as handle:
                handle.seek(offset)
                (
                    prefix_hash,
                    record_count,
                    last_seq,
                    bytes_read,
                    fold_count,
                    anomaly_count,
                ) = _fold_lines(
                    handle,
                    tail=tail,
                    latest_by_kind=latest_by_kind,
                    prefix_hash=prefix_hash,
                    record_count=record_count,
                    last_seq=last_seq,
                    tolerate_sequence_anomalies=(mode == "cold_rebuild"),
                    sequence_anomalies=sequence_anomalies,
                )
                return handle.tell(), anomaly_count

        try:
            source_offset, fold_anomaly_count = fold_current_view()
            sequence_anomaly_count = (
                prior_sequence_anomaly_count + fold_anomaly_count
                if mode == "warm"
                else fold_anomaly_count
            )
        except EventCheckpointError as exc:
            # A warm checkpoint is an acceleration hint, never authority.  If
            # the appended segment is inconsistent, discard that hint and do
            # one bounded cold rebuild.  The cold path keeps the source rows,
            # records the anomaly, and publishes a degraded-but-useful receipt.
            if not allow_rebuild or mode != "warm":
                raise
            rebuild_reason = f"warm_fold:{exc}"
            mode = "cold_rebuild"
            stat = journal_path.stat()
            tail = deque(maxlen=max_tail_events)
            latest_by_kind = {}
            offset = 0
            prefix_hash = "sha256:genesis"
            record_count = 0
            last_seq = None
            sequence_anomalies.clear()
            prior_sequence_anomaly_count = 0
            source_offset, sequence_anomaly_count = fold_current_view()
        final_stat = journal_path.stat()
        if (
            final_stat.st_dev != stat.st_dev
            or final_stat.st_ino != stat.st_ino
            or final_stat.st_size != source_offset
        ):
            raise EventCheckpointError("journal_changed_during_checkpoint_fold")
        if publish_checkpoint:
            if mode != "warm" or fold_count:
                durable_fold_receipt = {
                    "recorded_at": _utc_now(),
                    "mode": mode,
                    "rebuild_reason": rebuild_reason,
                    "bytes_read": bytes_read,
                    "fold_count": fold_count,
                    "sequence_anomaly_count": sequence_anomaly_count,
                    "sequence_anomalies": list(sequence_anomalies),
                    "wall_time_seconds": time.monotonic() - started,
                    "peak_rss_bytes": max(rss_before, _rss_bytes()),
                    "rss_delta_bytes": max(0, _rss_bytes() - rss_before),
                    "source_offset": source_offset,
                    "_non_authoritative": True,
                }
                checkpoint = _publish_checkpoint(
                    plan_dir=root,
                    journal_path=journal_path,
                    stat=final_stat,
                    incarnation=incarnation,
                    restore_generation=restore_generation,
                    max_tail_events=max_tail_events,
                    source_offset=source_offset,
                    record_count=record_count,
                    last_seq=last_seq,
                    prefix_hash=prefix_hash,
                    tail=tail,
                    latest_by_kind=latest_by_kind,
                    fold_receipt=durable_fold_receipt,
                )
        elif fold_count:
            # Read-only callers may consume a transient incremental view, but
            # never publish acceleration state into the audited workspace.
            checkpoint = {
                **checkpoint,
                "source_offset": source_offset,
                "source_record_count": record_count,
                "source_last_seq": last_seq,
                "source_prefix_hash": prefix_hash,
                "checkpoint_digest": None,
            }
    finally:
        try:
            fcntl.flock(seq_lock_fd, fcntl.LOCK_UN)
            os.close(seq_lock_fd)
        finally:
            fcntl.flock(checkpoint_lock_fd, fcntl.LOCK_UN)
            os.close(checkpoint_lock_fd)

    receipt = {
        "schema_version": 1,
        "mode": mode,
        "rebuild_reason": rebuild_reason,
        "bytes_read": bytes_read,
        "fold_count": fold_count,
        "sequence_anomaly_count": sequence_anomaly_count,
        "sequence_anomalies": list(sequence_anomalies),
        "degraded": bool(sequence_anomaly_count),
        "wall_time_seconds": time.monotonic() - started,
        "peak_rss_bytes": max(rss_before, _rss_bytes()),
        "rss_delta_bytes": max(0, _rss_bytes() - rss_before),
        "cursor": {
            "source_offset": checkpoint["source_offset"],
            "record_count": checkpoint["source_record_count"],
            "last_seq": checkpoint["source_last_seq"],
            "prefix_hash": checkpoint["source_prefix_hash"],
            "store_incarnation": checkpoint["store_incarnation"],
            "restore_generation": checkpoint["restore_generation"],
            "fold_version": checkpoint["fold_version"],
            "checkpoint_digest": checkpoint["checkpoint_digest"],
        },
        "_non_authoritative": True,
    }
    return BoundedEventProjection(
        events=tuple(tail),
        record_count=record_count,
        last_seq=last_seq,
        latest_by_kind=latest_by_kind,
        cursor=receipt["cursor"],
        receipt=receipt,
    )


def latest_event_of_kind(
    plan_dir: str | Path,
    kind: str,
    *,
    allow_rebuild: bool = True,
) -> dict[str, Any]:
    """Return the latest folded event for *kind* without rescanning history."""

    projection = read_bounded_event_projection(
        plan_dir, allow_rebuild=allow_rebuild
    )
    event = projection.latest_by_kind.get(kind)
    return dict(event) if isinstance(event, Mapping) else {}


__all__ = [
    "ANCHOR_BYTES",
    "BoundedEventProjection",
    "CHECKPOINT_SCHEMA_VERSION",
    "DEFAULT_MAX_TAIL_EVENTS",
    "EventCheckpointError",
    "SUPERVISION_FOLD_VERSION",
    "latest_event_of_kind",
    "read_bounded_event_projection",
]
