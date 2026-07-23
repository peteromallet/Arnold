"""Atomic I/O, journaling helpers, path resolution, and config management."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import time
from base64 import b64decode, b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

try:  # Python 3.11+
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    try:
        import tomli as tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore[assignment]

from arnold_pipelines.megaplan.schemas import SCHEMAS, strict_schema
from arnold_pipelines.megaplan.profiles.policy import KNOWN_AGENTS


# ---------------------------------------------------------------------------
# Pure utilities
# ---------------------------------------------------------------------------

def now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(text: str, max_length: int = 30) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(slug) <= max_length:
        return slug or "plan"
    truncated = slug[:max_length]
    last_hyphen = truncated.rfind("-")
    if last_hyphen > 10:
        truncated = truncated[:last_hyphen]
    return truncated or "plan"


def json_dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=False) + "\n"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def sha256_text(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def compute_task_batches(
    tasks: list[dict[str, Any]],
    completed_ids: set[str] | None = None,
) -> list[list[str]]:
    """Compute topological batches from task records plus already-satisfied IDs.

    ``completed_ids`` is intentionally a pure input contract: it is a set of
    task IDs whose dependencies should be treated as already satisfied. In
    production, callers must derive that set from corroborated authority
    evidence, not raw legacy ``status="done"`` / ``"skipped"`` assertions.
    """

    completed = set(completed_ids or set())
    if not tasks:
        return []

    task_ids = [task["id"] for task in tasks]
    task_id_set = set(task_ids)
    remaining: dict[str, set[str]] = {}
    order_index = {task_id: index for index, task_id in enumerate(task_ids)}

    for task in tasks:
        task_id = task["id"]
        deps = task.get("depends_on", [])
        if not isinstance(deps, list):
            deps = []
        normalized_deps: set[str] = set()
        for dep in deps:
            if dep in task_id_set:
                normalized_deps.add(dep)
                continue
            if dep in completed:
                continue
            raise ValueError(f"Unknown dependency ID '{dep}' for task '{task_id}'")
        remaining[task_id] = normalized_deps

    batches: list[list[str]] = []
    satisfied = set(completed)
    unscheduled = set(task_ids)

    while unscheduled:
        ready = [
            task_id
            for task_id in unscheduled
            if remaining[task_id].issubset(satisfied)
        ]
        ready.sort(key=order_index.__getitem__)
        if not ready:
            cycle_ids = sorted(unscheduled, key=order_index.__getitem__)
            raise ValueError("Cyclic dependency graph detected among tasks: " + ", ".join(cycle_ids))
        batches.append(ready)
        satisfied.update(ready)
        unscheduled.difference_update(ready)

    return batches


def split_oversized_batches(
    batches: list[list[str]],
    max_size: int,
    *,
    default_max_size: int = 5,
) -> list[list[str]]:
    if max_size <= 0:
        max_size = default_max_size
    if max_size <= 0:
        max_size = 5

    split_batches: list[list[str]] = []
    for batch in batches:
        if len(batch) <= max_size:
            split_batches.append(batch)
            continue
        for index in range(0, len(batch), max_size):
            split_batches.append(batch[index:index + max_size])
    return split_batches


_CHECKPOINT_RECORDS = {
    "completed_subobjectives",
    "remaining_subobjectives",
    "output_hashes",
    "test_state",
}


def _has_valid_checkpoint_contract(task: dict[str, Any]) -> bool:
    """Return True if *task* carries a valid complexity >=7 checkpoint contract.

    A valid contract requires ``checkpoint.required`` is ``True``, a
    ``max_interval_seconds`` integer in (0, 300], and a ``records`` list
    whose entries are a superset of the four required record kinds.
    """
    checkpoint = task.get("checkpoint")
    if not isinstance(checkpoint, dict) or checkpoint.get("required") is not True:
        return False
    interval = checkpoint.get("max_interval_seconds")
    if not isinstance(interval, int) or interval <= 0 or interval > 300:
        return False
    records = checkpoint.get("records")
    if not isinstance(records, list):
        return False
    return _CHECKPOINT_RECORDS.issubset(set(records))


def split_high_complexity_batches(
    batches: list[list[str]],
    finalize_data: dict[str, Any],
    *,
    max_tasks_per_batch: int = 5,
) -> list[list[str]]:
    """Isolate complexity >=7 tasks in their own batches before worker dispatch.

    High-complexity tasks require either a checkpoint contract plus explicit
    larger budget, or splitting implementation from proof/validation. This
    helper ensures that every complexity >=7 task gets its own batch so the
    worker has the full turn budget for both implementation and
    proof/validation.  Tasks without a valid checkpoint contract are kept in
    their original batch positions (a post-admission defense-in-depth guard
    — the admission check in ``compile_task_feasibility`` should have already
    rejected them).

    Task identities and checkpoint records are never mutated; only the
    batch grouping changes.
    """
    if not batches or not finalize_data:
        return batches

    tasks = finalize_data.get("tasks", [])
    if not isinstance(tasks, list):
        return batches

    task_map: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if isinstance(task, dict) and isinstance(task.get("id"), str):
            task_map[task["id"]] = task

    split: list[list[str]] = []
    for batch in batches:
        high_complexity_ids: list[str] = []
        other_ids: list[str] = []
        for tid in batch:
            task = task_map.get(tid)
            if not isinstance(task, dict):
                other_ids.append(tid)
                continue
            complexity = task.get("complexity")
            if isinstance(complexity, int) and complexity >= 7:
                high_complexity_ids.append(tid)
            else:
                other_ids.append(tid)

        if not high_complexity_ids:
            split.append(batch)
            continue

        # Isolate each high-complexity task in its own batch so the
        # worker receives the full turn budget for both implementation
        # and proof/validation.
        for tid in high_complexity_ids:
            split.append([tid])

        # Remaining non-high-complexity tasks stay grouped together
        # (subject to the normal max_tasks_per_batch ceiling).
        if other_ids:
            for chunk_start in range(0, len(other_ids), max_tasks_per_batch):
                split.append(other_ids[chunk_start:chunk_start + max_tasks_per_batch])

    return split


def compute_global_batches(finalize_data: dict[str, Any]) -> list[list[str]]:
    tasks = finalize_data.get("tasks", [])
    return compute_task_batches(tasks)


def compute_batch_complexity(
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
) -> int:
    """Return the maximum valid task complexity for a batch of tasks.

    Indexes finalize tasks by ID and returns ``max(effective_complexity)``
    for the batch.  Each task's effective complexity is
    ``max(task.complexity, task.tier_override)`` when ``tier_override`` is an
    integer in 1..10; out-of-range or non-integer ``tier_override`` values are
    silently ignored and the base ``complexity`` is used.  Treats missing task
    IDs, missing ``complexity``, non-integer complexity, and out-of-range
    values as **10** (fail-safe: expensive model).  Returns 10 for empty or
    malformed batch input.
    """
    if not batch_task_ids:
        return 10
    tasks = finalize_data.get("tasks", [])
    if not isinstance(tasks, list):
        return 10
    task_map: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if isinstance(task, dict) and isinstance(task.get("id"), str):
            task_map[task["id"]] = task
    max_complexity = 0
    for tid in batch_task_ids:
        task = task_map.get(tid)
        if not isinstance(task, dict):
            return 10
        complexity = task.get("complexity")
        if not isinstance(complexity, int):
            return 10
        if complexity < 1 or complexity > 10:
            return 10
        tier_override = task.get("tier_override")
        if isinstance(tier_override, int) and 1 <= tier_override <= 10:
            effective = max(complexity, tier_override)
        else:
            effective = complexity
        if effective > max_complexity:
            max_complexity = effective
    return max_complexity if max_complexity > 0 else 10


# ---------------------------------------------------------------------------
# Atomic I/O
# ---------------------------------------------------------------------------

MAX_FRAMED_JSON_RECORD_BYTES = 1024 * 1024


def _fsync_file_descriptor(fd: int) -> None:
    os.fsync(fd)


def fsync_dir(path: Path) -> None:
    directory = path if path.is_dir() else path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(directory, os.O_RDONLY)
    try:
        _fsync_file_descriptor(fd)
    finally:
        os.close(fd)


def fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        _fsync_file_descriptor(handle.fileno())


def _write_bytes_direct(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(content)
        handle.flush()
        _fsync_file_descriptor(handle.fileno())
    fsync_dir(path.parent)


def _restore_staged_payload(entry: Mapping[str, Any]) -> bytes:
    payload = entry.get("content")
    storage = entry.get("content_storage")
    if not isinstance(payload, str):
        raise ValueError("Prepared journal entry is missing inline content")
    if storage == "text":
        return payload.encode("utf-8")
    if storage == "base64":
        return b64decode(payload.encode("ascii"))
    raise ValueError(f"Unsupported prepared content storage: {storage!r}")


def _serialize_inline_payload(content: bytes | str) -> tuple[str, str]:
    if isinstance(content, str):
        return ("text", content)
    return ("base64", b64encode(content).decode("ascii"))


def _content_sha256(content: bytes | str) -> str:
    if isinstance(content, str):
        return sha256_text(content)
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _path_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return "sha256:" + hashlib.sha256(handle.read()).hexdigest()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        handle.flush()
        _fsync_file_descriptor(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)
    fsync_dir(path.parent)


def atomic_write_text(path: Path, content: str, *, _plan_dir: Path | None = None) -> None:
    from arnold.runtime.state_persistence import atomic_write_bytes as _rt_atomic_write_bytes

    _rt_atomic_write_bytes(path, content.encode("utf-8"))
    if _plan_dir is not None:
        try:
            from arnold_pipelines.megaplan.observability.events import emit, EventKind
            emit(
                EventKind.ARTIFACT_WRITTEN,
                plan_dir=_plan_dir,
                payload={"path": str(path), "size_bytes": len(content)},
            )
        except Exception:
            try:
                from arnold_pipelines.megaplan.handlers.shared import _warn_best_effort_emit_failure

                _warn_best_effort_emit_failure(
                    "M3A_WARN_EMIT_ARTIFACT_WRITTEN",
                    action="atomic-write-text",
                    plan_dir=_plan_dir,
                    event_kind="artifact_written",
                    context={"path": str(path), "size_bytes": len(content)},
                )
            except Exception:
                pass


def atomic_write_json(path: Path, data: Any, *, _plan_dir: Path | None = None) -> None:
    atomic_write_text(path, json_dump(data), _plan_dir=_plan_dir)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# R1 authority: cached state read shim
# ---------------------------------------------------------------------------

# Mode literal carried by the 8 authority readers and 11 cache-tolerant
# readers under the R1 flip. The third mode value ``"forward_only"`` is
# reserved for the dormant-path readers that never route through this shim.
PlanStateReadMode = Literal["authority", "cache_tolerant", "forward_only"]


def read_plan_state_cached(plan_dir: Path, *, mode: "PlanStateReadMode") -> Any:
    """Read ``plan_dir/state.json`` under the R1 cache/authority discipline.

    Modes
    -----
    ``"authority"``
        When ``r1_authority_on()`` is true, rebuild the canonical state by
        folding ``events.ndjson`` (the shadow-WAL), compare it against the
        on-disk ``state.json`` cache, and on divergence rewrite the cache
        with the WAL truth and emit a ``STATE_CACHE_DRIFT`` event. Returns
        the WAL truth. When the master flag is OFF, behaves identically to
        ``"cache_tolerant"`` (reads ``state.json`` directly with no fold).

    ``"cache_tolerant"``
        Always reads ``state.json`` directly. Used by reporters/observers
        that tolerate a slightly stale view between writes.

    ``"forward_only"``
        Explicit no-op classification — also reads ``state.json`` directly.
        Used by dormant-path callers retired at M6.
    """
    state_path = Path(plan_dir) / "state.json"

    if mode == "authority":
        # Lazy import to avoid module-load-time cycles
        # (flags → _pipeline → _core.io).
        from arnold_pipelines.megaplan.feature_flags import r1_authority_on
        if r1_authority_on():
            from arnold_pipelines.megaplan.observability.fold import rebuild_state_from_wal
            wal_state = rebuild_state_from_wal(Path(plan_dir))
            disk_state: Any = None
            if state_path.exists():
                try:
                    disk_state = json.loads(state_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    disk_state = None
            # Normalize both sides for a stable compare.
            try:
                disk_norm = json.loads(json.dumps(disk_state, sort_keys=True))
                wal_norm = json.loads(json.dumps(wal_state, sort_keys=True))
            except (TypeError, ValueError):
                disk_norm = disk_state
                wal_norm = wal_state
            if disk_norm != wal_norm:
                # Rewrite cache to match WAL truth, then announce the drift.
                atomic_write_json(state_path, wal_state)
                try:
                    from arnold_pipelines.megaplan.observability.events import emit, EventKind
                    emit(
                        EventKind.STATE_CACHE_DRIFT,
                        plan_dir=Path(plan_dir),
                        payload={
                            "disk_keys": sorted(disk_norm.keys()) if isinstance(disk_norm, dict) else None,
                            "wal_keys": sorted(wal_norm.keys()) if isinstance(wal_norm, dict) else None,
                        },
                    )
                except Exception:
                    pass
            return wal_state
        # Flag OFF: read disk directly.
        return read_json(state_path)

    if mode in ("cache_tolerant", "forward_only"):
        return read_json(state_path)

    raise ValueError(f"unknown PlanStateReadMode: {mode!r}")


def journal_root(root: Path) -> Path:
    return root / "_journal"


def journal_prepare_path(root: Path, tx_id: str) -> Path:
    return journal_root(root) / f"tx-{tx_id}.prepare.json"


def journal_commit_path(root: Path, tx_id: str) -> Path:
    return journal_root(root) / f"tx-{tx_id}.commit"


def _validate_cas_guards(
    expected_prior_sha256: str | None,
    target_absent: bool,
) -> None:
    """Reject contradictory CAS guard combinations.

    ``expected_prior_sha256`` (target must exist with this prior hash) and
    ``target_absent`` (target must not exist) are mutually exclusive.  Both
    unset is the default non-CAS path.
    """
    if expected_prior_sha256 is not None and target_absent:
        raise ValueError(
            "journal CAS guards are mutually exclusive: "
            "expected_prior_sha256 and target_absent cannot both be set"
        )


def journal_text_write(
    path: Path,
    content: str,
    *,
    tx_id: str | None = None,
    expected_prior_sha256: str | None = None,
    target_absent: bool = False,
) -> dict[str, Any]:
    _validate_cas_guards(expected_prior_sha256, target_absent)
    storage, inline = _serialize_inline_payload(content)
    temp_name = f".{path.name}.tx-{tx_id or 'pending'}.tmp"
    entry: dict[str, Any] = {
        "target_path": str(path),
        "temp_path": str(path.parent / temp_name),
        "content_storage": storage,
        "content": inline,
        "content_sha256": _content_sha256(content),
        "prior_content_sha256": _path_sha256(path) if path.exists() else None,
    }
    # CAS guard keys are only emitted when set so non-CAS entries remain
    # byte-identical to the pre-CAS journal format.
    if expected_prior_sha256 is not None:
        entry["expected_prior_sha256"] = expected_prior_sha256
    if target_absent:
        entry["target_absent"] = True
    return entry


def journal_bytes_write(
    path: Path,
    content: bytes,
    *,
    tx_id: str | None = None,
    expected_prior_sha256: str | None = None,
    target_absent: bool = False,
) -> dict[str, Any]:
    _validate_cas_guards(expected_prior_sha256, target_absent)
    storage, inline = _serialize_inline_payload(content)
    temp_name = f".{path.name}.tx-{tx_id or 'pending'}.tmp"
    entry: dict[str, Any] = {
        "target_path": str(path),
        "temp_path": str(path.parent / temp_name),
        "content_storage": storage,
        "content": inline,
        "content_sha256": _content_sha256(content),
        "prior_content_sha256": _path_sha256(path) if path.exists() else None,
    }
    if expected_prior_sha256 is not None:
        entry["expected_prior_sha256"] = expected_prior_sha256
    if target_absent:
        entry["target_absent"] = True
    return entry


def journal_event_log(path: Path, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "path": str(path),
        "records": [dict(record) for record in records],
    }


def journal_blob_promotion(
    blob_dir: Path,
    content: bytes,
    *,
    extension: str,
    metadata: Mapping[str, Any],
    expected_prior_sha256: str | None = None,
    target_absent: bool = False,
) -> dict[str, Any]:
    _validate_cas_guards(expected_prior_sha256, target_absent)
    storage, inline = _serialize_inline_payload(content)
    normalized_ext = extension.lstrip(".")
    entry: dict[str, Any] = {
        "blob_dir": str(blob_dir),
        "staging_path": str(blob_dir / "data.staging"),
        "final_path": str(blob_dir / f"data.{normalized_ext}"),
        "meta_path": str(blob_dir / "meta.json"),
        "content_storage": storage,
        "content": inline,
        "content_sha256": _content_sha256(content),
        "metadata": dict(metadata),
    }
    if expected_prior_sha256 is not None:
        entry["expected_prior_sha256"] = expected_prior_sha256
    if target_absent:
        entry["target_absent"] = True
    return entry


def framed_json_record_bytes(record: Mapping[str, Any]) -> bytes:
    normalized = dict(record)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_FRAMED_JSON_RECORD_BYTES:
        normalized = _compact_oversized_framed_record(normalized)
        payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_FRAMED_JSON_RECORD_BYTES:
        raise ValueError(
            f"Framed JSON record exceeds {MAX_FRAMED_JSON_RECORD_BYTES} bytes: {len(payload)}",
        )
    return struct.pack(">I", len(payload)) + payload + b"\n"


def _compact_oversized_framed_record(record: dict[str, Any]) -> dict[str, Any]:
    """Drop redundant large state snapshots from framed event-log records.

    File-store event logs have a hard per-record frame limit. State-change
    events can embed an entire emitted state snapshot in ``post_state``; keep a
    deterministic hash/size stub so journal recovery can complete without
    making the framed log unbounded.
    """

    if record.get("event_type") != "state_change":
        return record
    compacted = dict(record)
    for field in ("prior_state", "pre_state", "post_state"):
        value = compacted.get(field)
        if value is None:
            continue
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(payload) <= MAX_FRAMED_JSON_RECORD_BYTES // 4:
            continue
        compacted[field] = {
            "_omitted_for_framed_log": True,
            "reason": "state snapshot exceeds framed event-log record budget",
            "original_size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    compacted["pre_state_canonical_json"] = None
    compacted["post_state_canonical_json"] = None
    return compacted


def append_framed_json_records(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    should_fsync = any(record.get("event_type") == "_tx_commit" for record in records)
    with path.open("ab", buffering=0) as handle:
        for record in records:
            handle.write(framed_json_record_bytes(record))
        if should_fsync:
            _fsync_file_descriptor(handle.fileno())
    if should_fsync:
        fsync_dir(path.parent)


def append_framed_json_transaction(
    path: Path,
    tx_id: str,
    records: Sequence[Mapping[str, Any]],
) -> None:
    framed_records: list[dict[str, Any]] = [{"tx_id": tx_id, "event_type": "_tx_begin"}]
    for record in records:
        normalized = dict(record)
        record_tx_id = normalized.get("tx_id")
        if record_tx_id is not None and record_tx_id != tx_id:
            raise ValueError(f"Framed record tx_id mismatch: expected {tx_id!r}, got {record_tx_id!r}")
        normalized["tx_id"] = tx_id
        framed_records.append(normalized)
    framed_records.append({"tx_id": tx_id, "event_type": "_tx_commit"})
    append_framed_json_records(path, framed_records)


def iter_framed_json_records(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []

    def _iterator() -> Iterable[dict[str, Any]]:
        with path.open("rb") as handle:
            while True:
                length_bytes = handle.read(4)
                if not length_bytes:
                    return
                if len(length_bytes) < 4:
                    return
                (payload_len,) = struct.unpack(">I", length_bytes)
                if payload_len > MAX_FRAMED_JSON_RECORD_BYTES:
                    return
                payload = handle.read(payload_len)
                if len(payload) < payload_len:
                    return
                newline = handle.read(1)
                if newline != b"\n":
                    return
                try:
                    record = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return
                if isinstance(record, dict):
                    yield record

    return _iterator()


def committed_framed_json_transactions(path: Path) -> dict[str, list[dict[str, Any]]]:
    committed: dict[str, list[dict[str, Any]]] = {}
    pending: dict[str, list[dict[str, Any]]] = {}
    for record in iter_framed_json_records(path):
        tx_id = record.get("tx_id")
        if not isinstance(tx_id, str) or not tx_id:
            continue
        event_type = record.get("event_type")
        if event_type == "_tx_begin":
            pending[tx_id] = [record]
            continue
        bucket = pending.get(tx_id)
        if bucket is None:
            continue
        bucket.append(record)
        if event_type == "_tx_commit":
            committed[tx_id] = bucket
            pending.pop(tx_id, None)
    return committed


def read_committed_framed_json_records(
    path: Path,
    *,
    include_markers: bool = False,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for transaction in committed_framed_json_transactions(path).values():
        if include_markers:
            records.extend(transaction)
            continue
        records.extend(
            record
            for record in transaction
            if record.get("event_type") not in {"_tx_begin", "_tx_commit"}
        )
    return records


def _stage_write_entry(entry: Mapping[str, Any]) -> None:
    temp_path = Path(entry["temp_path"])
    _write_bytes_direct(temp_path, _restore_staged_payload(entry))


def _stage_blob_entry(entry: Mapping[str, Any]) -> None:
    staging_path = Path(entry["staging_path"])
    meta_path = Path(entry["meta_path"])
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_direct(staging_path, _restore_staged_payload(entry))
    atomic_write_json(meta_path, entry.get("metadata", {}))


def prepare_journal_transaction(
    root: Path,
    tx_id: str,
    *,
    writes: Sequence[Mapping[str, Any]] = (),
    event_logs: Sequence[Mapping[str, Any]] = (),
    blobs: Sequence[Mapping[str, Any]] = (),
) -> Path:
    normalized_writes = [dict(entry) for entry in writes]
    normalized_event_logs = [dict(entry) for entry in event_logs]
    normalized_blobs = [dict(entry) for entry in blobs]
    for entry in normalized_writes:
        target_path = Path(entry["target_path"])
        temp_path = entry.get("temp_path")
        if not isinstance(temp_path, str) or ".tx-pending." in temp_path:
            entry["temp_path"] = str(target_path.parent / f".{target_path.name}.tx-{tx_id}.tmp")
    prepare_path = journal_prepare_path(root, tx_id)
    payload = {
        "tx_id": tx_id,
        "prepared_at": now_utc(),
        "writes": normalized_writes,
        "event_logs": normalized_event_logs,
        "blob_promotions": normalized_blobs,
    }
    atomic_write_json(prepare_path, payload)
    for entry in normalized_writes:
        _stage_write_entry(entry)
    for entry in normalized_blobs:
        _stage_blob_entry(entry)
    return prepare_path


def write_journal_commit_marker(root: Path, tx_id: str) -> Path:
    marker_path = journal_commit_path(root, tx_id)
    _write_bytes_direct(marker_path, b"")
    return marker_path


def _rename_with_fsync(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dest)
    fsync_dir(dest.parent)


def _apply_prepared_writes(payload: Mapping[str, Any]) -> None:
    for entry in payload.get("writes", []):
        target_path = Path(entry["target_path"])
        desired_sha = entry.get("content_sha256")
        if target_path.exists() and desired_sha == _path_sha256(target_path):
            temp_path = Path(entry["temp_path"])
            if temp_path.exists():
                temp_path.unlink()
            continue
        temp_path = Path(entry["temp_path"])
        if not temp_path.exists():
            _stage_write_entry(entry)
        _rename_with_fsync(temp_path, target_path)


def _apply_prepared_blob_promotions(payload: Mapping[str, Any]) -> None:
    for entry in payload.get("blob_promotions", []):
        final_path = Path(entry["final_path"])
        desired_sha = entry.get("content_sha256")
        atomic_write_json(Path(entry["meta_path"]), entry.get("metadata", {}))
        if final_path.exists() and desired_sha == _path_sha256(final_path):
            staging_path = Path(entry["staging_path"])
            if staging_path.exists():
                staging_path.unlink()
            continue
        staging_path = Path(entry["staging_path"])
        if not staging_path.exists():
            _stage_blob_entry(entry)
        _rename_with_fsync(staging_path, final_path)


def _apply_prepared_event_logs(payload: Mapping[str, Any]) -> None:
    tx_id = payload["tx_id"]
    for entry in payload.get("event_logs", []):
        log_path = Path(entry["path"])
        committed_ids = set(committed_framed_json_transactions(log_path))
        if tx_id in committed_ids:
            continue
        append_framed_json_transaction(log_path, tx_id, entry.get("records", []))


def _cleanup_prepared_transaction(payload: Mapping[str, Any]) -> None:
    for entry in payload.get("writes", []):
        temp_path = Path(entry["temp_path"])
        if temp_path.exists():
            temp_path.unlink()
    for entry in payload.get("blob_promotions", []):
        staging_path = Path(entry["staging_path"])
        if staging_path.exists():
            staging_path.unlink()
    prepare_path = journal_prepare_path(Path(payload["journal_root"]), payload["tx_id"])
    commit_path = journal_commit_path(Path(payload["journal_root"]), payload["tx_id"])
    if prepare_path.exists():
        prepare_path.unlink()
    if commit_path.exists():
        commit_path.unlink()
    fsync_dir(prepare_path.parent)


def commit_journal_transaction(root: Path, tx_id: str) -> None:
    prepare_path = journal_prepare_path(root, tx_id)
    payload = read_json(prepare_path)
    if not isinstance(payload, dict):
        raise ValueError(f"Malformed prepare payload at {prepare_path}")
    payload["journal_root"] = str(root)
    write_journal_commit_marker(root, tx_id)
    _apply_prepared_writes(payload)
    _apply_prepared_blob_promotions(payload)
    _apply_prepared_event_logs(payload)
    _cleanup_prepared_transaction(payload)


def discard_uncommitted_journal_transaction(root: Path, tx_id: str) -> None:
    prepare_path = journal_prepare_path(root, tx_id)
    if not prepare_path.exists():
        return
    payload = read_json(prepare_path)
    if not isinstance(payload, dict):
        prepare_path.unlink()
        fsync_dir(prepare_path.parent)
        return
    payload["journal_root"] = str(root)
    _cleanup_prepared_transaction(payload)


# ---------------------------------------------------------------------------
# Compare-And-Swap (CAS) journal guards
# ---------------------------------------------------------------------------
#
# CAS guards are an *extension layer* over the existing journal machinery
# (SD1).  A write/blob entry may carry two optional guards that are evaluated
# at commit time, **before** the commit marker is written:
#
# * ``expected_prior_sha256`` — the target file must currently exist and its
#   on-disk SHA-256 must equal this value.  Detects concurrent modification
#   between prepare and commit (lost update).
# * ``target_absent`` — the target file must NOT currently exist.  Enforces
#   create-only semantics.
#
# When both guards are unset (the default), journal behaviour is byte-identical
# to the pre-CAS code paths.  The guards are evaluated before the commit marker
# so that a CAS violation never produces a durable commit record: the prepared
# transaction is discarded (temp files + prepare.json removed, no marker), and
# recovery therefore treats it as never-committed.


@dataclass(frozen=True)
class JournalCASViolation:
    """A single failed CAS guard for one journal entry.

    ``guard`` is either ``"expected_prior_sha256"`` or ``"target_absent"``.
    ``expected``/``actual`` carry the compared values (SHA-256 strings or
    ``None`` when the target is absent).
    """

    section: str
    entry_index: int
    target_path: str
    guard: str
    expected: str | None
    actual: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "entry_index": self.entry_index,
            "target_path": self.target_path,
            "guard": self.guard,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class JournalCASResult:
    """Outcome of a CAS-aware journal commit.

    ``committed`` is True when the transaction was durably committed (CAS guards
    satisfied, or no guards present).  When False, ``violations`` lists every
    entry whose guard failed and the prepared transaction has been discarded.
    """

    tx_id: str
    committed: bool
    violations: tuple[JournalCASViolation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "committed": self.committed,
            "violations": [violation.to_dict() for violation in self.violations],
        }


def evaluate_cas_guards(payload: Mapping[str, Any]) -> tuple[JournalCASViolation, ...]:
    """Evaluate CAS guards for every write/blob entry in *payload*.

    Returns a tuple of :class:`JournalCASViolation` (empty when all guards
    pass or no guards are present).  This is a pure read of current filesystem
    state — it performs no writes.
    """
    violations: list[JournalCASViolation] = []
    # section -> the key that names the target path within each entry.
    for section, path_key in (("writes", "target_path"), ("blob_promotions", "final_path")):
        entries = payload.get(section)
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                continue
            path_value = entry.get(path_key)
            if not isinstance(path_value, str):
                continue
            target_path = Path(path_value)
            expected_sha = entry.get("expected_prior_sha256")
            target_absent = bool(entry.get("target_absent"))
            exists = target_path.exists()
            actual_sha = _path_sha256(target_path) if exists else None
            if expected_sha is not None:
                # File must exist AND hash must match the expected prior hash.
                if actual_sha != expected_sha:
                    violations.append(
                        JournalCASViolation(
                            section=section,
                            entry_index=index,
                            target_path=str(target_path),
                            guard="expected_prior_sha256",
                            expected=str(expected_sha),
                            actual=actual_sha,
                        )
                    )
            elif target_absent:
                # File must NOT exist.
                if exists:
                    violations.append(
                        JournalCASViolation(
                            section=section,
                            entry_index=index,
                            target_path=str(target_path),
                            guard="target_absent",
                            expected=None,
                            actual=actual_sha,
                        )
                    )
    return tuple(violations)


def commit_journal_transaction_cas(root: Path, tx_id: str) -> JournalCASResult:
    """Commit a journal transaction under CAS guards.

    CAS guards on each write/blob entry are evaluated **before** the commit
    marker is written.  If any guard fails, the prepared transaction is
    discarded (temp files + prepare.json removed, no commit marker created) and
    a failure :class:`JournalCASResult` is returned — the transaction is
    indistinguishable from never-committed to recovery.

    When no guards are present (or all pass), this delegates to the existing
    :func:`commit_journal_transaction` so non-CAS commit, apply, and cleanup
    behaviour is unchanged.
    """
    prepare_path = journal_prepare_path(root, tx_id)
    payload = read_json(prepare_path)
    if not isinstance(payload, dict):
        raise ValueError(f"Malformed prepare payload at {prepare_path}")
    violations = evaluate_cas_guards(payload)
    if violations:
        discard_uncommitted_journal_transaction(root, tx_id)
        return JournalCASResult(tx_id=tx_id, committed=False, violations=violations)
    commit_journal_transaction(root, tx_id)
    return JournalCASResult(tx_id=tx_id, committed=True, violations=())


def scrub_stale_staging_files(root: Path, *, older_than_seconds: int = 3600) -> list[Path]:
    cutoff = time.time() - older_than_seconds
    removed: list[Path] = []
    changed_dirs: set[Path] = set()
    if not root.exists():
        return removed
    try:
        staging_paths = list(root.rglob("*.staging"))
    except FileNotFoundError:
        return removed
    for staging_path in staging_paths:
        try:
            if staging_path.stat().st_mtime > cutoff:
                continue
        except FileNotFoundError:
            continue
        staging_path.unlink(missing_ok=True)
        removed.append(staging_path)
        changed_dirs.add(staging_path.parent)
    for directory in sorted(changed_dirs):
        fsync_dir(directory)
    return removed


def recover_journal(root: Path) -> dict[str, list[str]]:
    journal_dir = journal_root(root)
    result = {"replayed": [], "discarded": [], "scrubbed_staging": []}
    result["scrubbed_staging"] = [str(path) for path in scrub_stale_staging_files(root)]
    if not journal_dir.exists():
        return result

    for prepare_path in sorted(journal_dir.glob("tx-*.prepare.json")):
        match = re.fullmatch(r"tx-(.+)\.prepare\.json", prepare_path.name)
        if match is None:
            continue
        tx_id = match.group(1)
        if journal_commit_path(root, tx_id).exists():
            commit_journal_transaction(root, tx_id)
            result["replayed"].append(tx_id)
        else:
            discard_uncommitted_journal_transaction(root, tx_id)
            result["discarded"].append(tx_id)

    for commit_path in sorted(journal_dir.glob("tx-*.commit")):
        tx_id = commit_path.name[len("tx-") : -len(".commit")]
        if not journal_prepare_path(root, tx_id).exists():
            commit_path.unlink()
            fsync_dir(journal_dir)

    return result


def load_finalize_snapshot(plan_dir: Path) -> dict[str, Any]:
    return read_json(plan_dir / "finalize_snapshot.json")


def render_final_md(finalize_data: dict[str, Any], *, phase: str = "finalize") -> str:
    from arnold_pipelines.megaplan.orchestration.plan_contracts import render_contract_markdown

    show_execution_gaps = phase in ("execute", "review")
    show_review_gaps = phase == "review"
    tasks = finalize_data.get("tasks", [])
    sense_checks = finalize_data.get("sense_checks", [])

    lines = ["# Execution Checklist", ""]
    gap_counts: dict[str, int] = {}
    for task in tasks:
        status = task.get("status")
        checkbox = "[x]" if status == "done" else "[ ]"
        status_suffix = " (skipped)" if status == "skipped" else ""
        lines.append(f"- {checkbox} **{task['id']}:** {task['description']}{status_suffix}")
        depends_on = task.get("depends_on", [])
        if depends_on:
            lines.append(f"  Depends on: {', '.join(depends_on)}")
        executor_notes = task.get("executor_notes", "")
        if executor_notes.strip():
            lines.append(f"  Executor notes: {executor_notes}")
        elif show_execution_gaps and status != "pending":
            lines.append("  Executor notes: [MISSING]")
            gap_counts["Executor notes missing"] = gap_counts.get("Executor notes missing", 0) + 1
        files_changed = task.get("files_changed", [])
        if files_changed:
            lines.append("  Files changed:")
            for path in files_changed:
                lines.append(f"    - {path}")
        if show_execution_gaps and status == "pending":
            gap_counts["Tasks without executor updates"] = gap_counts.get("Tasks without executor updates", 0) + 1
        reviewer_verdict = task.get("reviewer_verdict", "")
        if reviewer_verdict.strip():
            lines.append(f"  Reviewer verdict: {reviewer_verdict}")
            evidence_files = task.get("evidence_files", [])
            if evidence_files:
                lines.append("  Evidence files:")
                for path in evidence_files:
                    lines.append(f"    - {path}")
        elif show_review_gaps:
            lines.append("  Reviewer verdict: [PENDING]")
            gap_counts["Reviewer verdicts pending"] = gap_counts.get("Reviewer verdicts pending", 0) + 1
        lines.append("")

    contract_markdown = render_contract_markdown(finalize_data)
    if contract_markdown:
        lines.extend([contract_markdown, ""])

    lines.extend(["## Watch Items", ""])
    watch_items = finalize_data.get("watch_items", [])
    if watch_items:
        for item in watch_items:
            lines.append(f"- {item}")
    else:
        lines.append("- None.")
    lines.append("")

    lines.extend(["## Sense Checks", ""])
    if sense_checks:
        for sense_check in sense_checks:
            lines.append(f"- **{sense_check['id']}** ({sense_check['task_id']}): {sense_check['question']}")
            executor_note = sense_check.get("executor_note", "")
            if executor_note.strip():
                lines.append(f"  Executor note: {executor_note}")
            elif show_execution_gaps:
                lines.append("  Executor note: [MISSING]")
                gap_counts["Sense-check acknowledgments missing"] = gap_counts.get("Sense-check acknowledgments missing", 0) + 1
            verdict = sense_check.get("verdict", "")
            if verdict.strip():
                lines.append(f"  Verdict: {verdict}")
            elif show_review_gaps:
                lines.append("  Verdict: [PENDING]")
                gap_counts["Sense-check verdicts pending"] = gap_counts.get("Sense-check verdicts pending", 0) + 1
            lines.append("")
    else:
        lines.extend(["- None.", ""])

    lines.extend(["## Meta", ""])
    meta_commentary = (finalize_data.get("meta_commentary") or "").strip()
    lines.append(meta_commentary or "None.")
    lines.append("")

    if gap_counts:
        lines.extend(["## Coverage Gaps", ""])
        for label, count in gap_counts.items():
            lines.append(f"- {label}: {count}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def project_config_path(project_dir: Path) -> Path:
    """Return the expected path to the project-scoped TOML config file."""
    return project_dir / ".megaplan" / "config.toml"


def load_project_config(project_dir: Path) -> dict[str, Any]:
    """Load the project-scoped ``.megaplan/config.toml`` file.

    Returns an empty dict when the file does not exist, ``tomllib`` is
    unavailable, or the file is malformed (warn-and-ignore semantics).
    Does not cache — every call reads the file afresh so the function is
    concurrency-safe and does not carry process-global project state.
    """
    path = project_config_path(project_dir)
    if not path.is_file():
        return {}
    if tomllib is None:
        print(
            f"megaplan: warning: cannot read project config at {path}: "
            f"tomllib/tomli not available (Python 3.11+ required for built-in tomllib)",
            file=sys.stderr,
        )
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, ValueError, OSError) as exc:
        print(
            f"megaplan: warning: ignoring malformed project config at {path}: {exc}",
            file=sys.stderr,
        )
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def config_dir(home: Path | None = None) -> Path:
    if home is None:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg) / "megaplan"
        home = Path.home()
    return home / ".config" / "megaplan"


def load_config(home: Path | None = None) -> dict[str, Any]:
    path = config_dir(home) / "config.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        import sys
        print(f"megaplan: warning: ignoring malformed config at {path}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_config(config: dict[str, Any], home: Path | None = None) -> Path:
    path = config_dir(home) / "config.json"
    atomic_write_json(path, config)
    return path


def get_effective(
    section: str,
    key: str,
    *,
    home: Path | None = None,
    project_dir: Path | None = None,
) -> Any:
    from arnold_pipelines.megaplan.types import DEFAULTS

    default_key = f"{section}.{key}"
    if default_key not in DEFAULTS:
        raise KeyError(default_key)
    # M4 T13: flag-gated delegation to N-layer ConfigResolver. Flag-OFF path
    # below is byte-identical to the pre-T13 behaviour for the 30+ callers.
    from arnold_pipelines.megaplan.feature_flags import unified_config_on

    if unified_config_on():
        from arnold_pipelines.megaplan._core.config_resolver import ConfigResolver

        return ConfigResolver().effective(section, key)
    config = load_config(home)
    section_config = config.get(section)
    if isinstance(section_config, dict) and key in section_config:
        value = section_config[key]
    else:
        value = DEFAULTS[default_key]

    if project_dir is not None:
        project_config = load_project_config(project_dir)
        project_section = project_config.get(section)
        if isinstance(project_section, dict) and key in project_section:
            return project_section[key]

    return value


def setting_is_explicit(
    section: str,
    key: str,
    *,
    home: Path | None = None,
    project_dir: Path | None = None,
) -> bool:
    """Return True iff ``section.key`` is explicitly set in user or project config.

    Distinguishes a user-set or project-set value (even if it equals the
    default) from the fallback to ``DEFAULTS``. Used so a profile-level
    default (e.g.  ``adaptive_critique``) can win over the global default
    *only* when the user has not pinned the value themselves.

    When *project_dir* is passed, a key that is present ONLY in the project
    TOML (and absent from the global JSON config) is still counted as
    explicit — a project config entry is a deliberate operator pin.
    """
    # M4 T13: flag-gated delegation. Flag-OFF retains existing behaviour.
    from arnold_pipelines.megaplan.feature_flags import unified_config_on

    if unified_config_on():
        from arnold_pipelines.megaplan._core.config_resolver import ConfigResolver

        return ConfigResolver().explicit_at(section, key) is not None
    config = load_config(home)
    section_config = config.get(section)
    if isinstance(section_config, dict) and key in section_config:
        return True
    if project_dir is not None:
        project_config = load_project_config(project_dir)
        project_section = project_config.get(section)
        if isinstance(project_section, dict) and key in project_section:
            return True
    return False


# Absolute path to the megaplan-vendored Shannon fork. Kept in sync with
# ``megaplan.workers.shannon.VENDORED_SHANNON_PATH`` so this module does not
# import the workers package at module load (workers depends on _core).
# parents[0]=_core, parents[1]=megaplan.
_VENDORED_SHANNON_PATH = (
    Path(__file__).resolve().parents[1] / "vendor" / "shannon" / "index.ts"
).resolve()


_TRUTHY_SHANNON_STREAM_VALUES = {"1", "true", "on", "yes"}
_FALSY_SHANNON_STREAM_VALUES = {"0", "false", "off", "no"}


def _channel_shadow_gate_green(root: Path, plan_id: str) -> bool:
    path = root / ".megaplan" / "bakeoffs" / plan_id / "channel_shadow.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    gate = state.get("gate")
    if not isinstance(gate, dict):
        return False
    channel_pair = gate.get("channel_pair")
    if not isinstance(channel_pair, dict):
        return False
    channels = {
        channel_pair.get("primary_worker_channel"),
        channel_pair.get("shadow_worker_channel"),
    }
    return (
        gate.get("greenlight") is True
        and int(gate.get("real_parity_success_count") or 0) >= int(gate.get("threshold") or 5)
        and int(gate.get("real_parity_failure_count") or 0) == 0
        and channels == {"shannon_tmux", "shannon_stream"}
        and channel_pair.get("primary_auth_channel") == "subscription"
        and channel_pair.get("shadow_auth_channel") == "subscription"
    )


def _shannon_stream_worker_enabled(
    *,
    root: Path | None = None,
    plan_id: str | None = None,
) -> bool:
    """Return True when Shannon stream is explicitly enabled or rollout-gated."""
    raw = os.getenv("MEGAPLAN_SHANNON_STREAM_WORKER")
    if raw is not None:
        normalized = raw.strip().lower()
        if normalized in _FALSY_SHANNON_STREAM_VALUES:
            return False
        return normalized in _TRUTHY_SHANNON_STREAM_VALUES
    if root is None or not plan_id:
        return False
    return _channel_shadow_gate_green(root, plan_id)


def is_claude_stream_available(*, shutil_ref: Any = None) -> bool:
    """Return True iff the Claude CLI is on PATH for the headless stream worker."""
    if shutil_ref is None:
        shutil_ref = shutil
    return bool(shutil_ref.which("claude"))


def is_shannon_available(*, shutil_ref: Any = None) -> bool:
    """Return True iff bun + claude + tmux are on PATH and the vendored
    Shannon fork is present at ``megaplan/vendor/shannon/index.ts``.

    Replaces the legacy ``shutil.which`` probe for ``shannon``: the runtime now
    invokes ``bun <vendored-index.ts>`` directly, so the binary is bun and the
    fork must physically exist in-repo.
    """
    if shutil_ref is None:
        shutil_ref = shutil
    if not all(shutil_ref.which(bin) for bin in ("bun", "tmux", "claude")):
        return False
    return _VENDORED_SHANNON_PATH.is_file()


def shannon_missing_deps(*, shutil_ref: Any = None) -> list[str]:
    """Return list of missing Shannon dependencies (bun, tmux, claude, and/or
    the vendored fork)."""
    if shutil_ref is None:
        shutil_ref = shutil
    missing = [bin for bin in ("bun", "tmux", "claude") if not shutil_ref.which(bin)]
    if not _VENDORED_SHANNON_PATH.is_file():
        missing.append("megaplan/vendor/shannon/index.ts")
    return missing


def detect_available_agents() -> list[str]:
    # Access shutil via the _core package so monkeypatches on megaplan._core.shutil work.
    import arnold_pipelines.megaplan._core as _core_pkg
    _shutil_ref = _core_pkg.shutil
    available = [a for a in KNOWN_AGENTS if a not in ("hermes", "shannon") and _shutil_ref.which(a)]
    if (Path(__file__).resolve().parents[1] / "agent" / "run_agent.py").is_file():
        available.append("hermes")
    if is_shannon_available(shutil_ref=_shutil_ref):
        available.append("shannon")
    return available


# ---------------------------------------------------------------------------
# Runtime layout / path helpers
# ---------------------------------------------------------------------------

def _enforce_openai_strict_mode(node: Any, _path: tuple[str, ...] = ()) -> Any:
    # OpenAI structured outputs reject any object schema where `required` doesn't
    # cover every key in `properties`. Some megaplan schemas use an explicit-required
    # carve-out that violates this rule. Make non-required properties nullable and
    # promote them to required so the submission is strict-mode-safe.
    if isinstance(node, dict):
        node = {key: _enforce_openai_strict_mode(value, _path + (key,)) for key, value in node.items()}
        if "oneOf" in node and "anyOf" not in node:
            # Codex/OpenAI structured output accepts nested anyOf, but rejects
            # oneOf in output schemas. Megaplan's stored-artifact schemas can
            # still use oneOf for validation; runtime schemas get the looser
            # dialect before being handed to `codex exec --output-schema`.
            node["anyOf"] = node.pop("oneOf")
        if "const" in node and "enum" not in node:
            node["enum"] = [node.pop("const")]
        if node.get("type") == "object" and isinstance(node.get("properties"), dict):
            properties: dict[str, Any] = node["properties"]
            required = set(node.get("required", []))
            missing = [key for key in properties if key not in required]
            if missing:
                for key in missing:
                    prop = properties[key]
                    if isinstance(prop, dict):
                        existing = prop.get("type")
                        if isinstance(existing, str) and existing != "null":
                            prop = {**prop, "type": [existing, "null"]}
                        elif isinstance(existing, list) and "null" not in existing:
                            prop = {**prop, "type": list(existing) + ["null"]}
                        properties[key] = prop
                node["properties"] = properties
                node["required"] = list(properties.keys())
        return node
    if isinstance(node, list):
        return [_enforce_openai_strict_mode(item, _path) for item in node]
    return node


def ensure_runtime_layout(root: Path) -> None:
    megaplan_rt = root / ".megaplan"
    (megaplan_rt / "plans").mkdir(parents=True, exist_ok=True)
    (megaplan_rt / "initiatives").mkdir(parents=True, exist_ok=True)
    schemas_dir = megaplan_rt / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    for filename, schema in SCHEMAS.items():
        atomic_write_json(schemas_dir / filename, _enforce_openai_strict_mode(strict_schema(schema)))


def megaplan_root(root: Path) -> Path:
    return root / ".megaplan"


def plans_root(root: Path) -> Path:
    return megaplan_root(root) / "plans"


def _git_common_dir(root: Path) -> Path | None:
    git_path = root / ".git"
    if git_path.is_dir():
        return git_path.resolve()
    if not git_path.is_file():
        return None
    try:
        content = git_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "gitdir:"
    if not content.startswith(prefix):
        return None
    gitdir = Path(content[len(prefix):].strip())
    if not gitdir.is_absolute():
        gitdir = (root / gitdir).resolve()
    if gitdir.parent.name == "worktrees":
        return gitdir.parent.parent.resolve()
    return gitdir.resolve()


def repo_storage_id(root: Path) -> str:
    resolved = root.resolve()
    common_dir = _git_common_dir(resolved)
    identity_source = str(common_dir or resolved)
    label_source = common_dir.parent.name if common_dir is not None else resolved.name
    digest = hashlib.sha256(identity_source.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(label_source or 'repo')}-{digest}"


def canonical_megaplan_root(root: Path, *, home: Path | None = None) -> Path:
    base_home = (home or Path.home()).expanduser().resolve()
    return base_home / ".megaplan" / repo_storage_id(root)


def orphan_plans_root(root: Path, *, home: Path | None = None) -> Path:
    return canonical_megaplan_root(root, home=home) / "orphan_plans"


def plan_search_roots(root: Path, *, home: Path | None = None) -> list[Path]:
    """Return canonical and legacy plan roots for *root*.

    Canonical orphan plans live under ``~/.megaplan/<repo-id>/orphan_plans``.
    Legacy plans remain in-place under ``<root>/.megaplan/plans`` until a later
    migration step intentionally moves runtime writes across.
    """

    roots = [orphan_plans_root(root, home=home), plans_root(root)]
    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in roots:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(candidate)
    return deduped


def has_any_plan_root(root: Path, *, home: Path | None = None) -> bool:
    return any(candidate.is_dir() for candidate in plan_search_roots(root, home=home))


def find_plan_dir(start: Path, requested_name: str, *, home: Path | None = None) -> Path | None:
    """Find ``requested_name`` across canonical and legacy plan roots near *start*."""

    resolved_start = start.resolve()
    seen_project_roots: set[Path] = set()

    def _check(project_root: Path) -> Path | None:
        resolved_project = project_root.resolve()
        if resolved_project in seen_project_roots:
            return None
        seen_project_roots.add(resolved_project)
        for candidate_root in plan_search_roots(resolved_project, home=home):
            plan_dir = candidate_root / requested_name
            if (plan_dir / "state.json").exists():
                return plan_dir
        return None

    for project_root in (resolved_start, *resolved_start.parents):
        plan_dir = _check(project_root)
        if plan_dir is not None:
            return plan_dir

    for megaplan_dir in sorted(resolved_start.rglob(".megaplan")):
        if not megaplan_dir.is_dir():
            continue
        plan_dir = _check(megaplan_dir.parent)
        if plan_dir is not None:
            return plan_dir

    return None


def schemas_root(root: Path) -> Path:
    return megaplan_root(root) / "schemas"


def artifact_path(plan_dir: Path, filename: str) -> Path:
    return plan_dir / filename


# ---------------------------------------------------------------------------
# Execute batch artifacts (S4 directory layout)
#
# New writes use a deterministic directory-based layout:
#   execute_batches/batch_{index}/tasks_{stable_task_id_digest}.json
# Reads keep migration-only compatibility with the legacy flat layout:
#   execution_batch_{N}.json
# ---------------------------------------------------------------------------

EXECUTE_BATCHES_DIRNAME = "execute_batches"
_STABLE_DIGEST_LEN = 12
_EXECUTE_BATCH_DIR_RE = re.compile(r"batch_(\d+)$")
_LEGACY_BATCH_ARTIFACT_RE = re.compile(r"execution_batch_(\d+)\.json$")
_EXECUTE_BATCH_TASKS_RE = re.compile(r"tasks_[0-9a-f]+\.json$")


def stable_task_id_digest(task_ids: Iterable[str]) -> str:
    """Short stable hex digest over the canonical (sorted, deduped) task-ID set.

    The digest is order- and duplicate-insensitive so the same batch membership
    always maps to the same filename, regardless of how the caller ordered the
    task IDs.
    """
    canonical = sorted({str(tid) for tid in task_ids})
    joined = "\n".join(canonical).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()[:_STABLE_DIGEST_LEN]


def execute_batch_dir(plan_dir: Path, batch_index: int) -> Path:
    """Directory that holds the S4 batch artifact for ``batch_index``."""
    return plan_dir / EXECUTE_BATCHES_DIRNAME / f"batch_{batch_index}"


def execute_batch_artifact_path(
    plan_dir: Path, batch_index: int, task_ids: Iterable[str]
) -> Path:
    """Deterministic S4 write path for a batch artifact.

    Form: ``execute_batches/batch_{index}/tasks_{stable_task_id_digest}.json``
    """
    return (
        execute_batch_dir(plan_dir, batch_index)
        / f"tasks_{stable_task_id_digest(task_ids)}.json"
    )


def legacy_batch_artifact_path(plan_dir: Path, batch_number: int) -> Path:
    """Legacy flat batch artifact path (migration read-only)."""
    return plan_dir / f"execution_batch_{batch_number}.json"


def batch_artifact_path(plan_dir: Path, batch_number: int) -> Path:
    """Legacy flat batch artifact path.

    Retained for migration-only read compatibility. New writes must use
    :func:`execute_batch_artifact_path`; readers should use
    :func:`resolve_batch_artifact` or :func:`list_batch_artifacts`.
    """
    return legacy_batch_artifact_path(plan_dir, batch_number)


def batch_artifact_index(path: Path) -> int | None:
    """Extract the 1-indexed batch number from a batch artifact path.

    Handles both the S4 directory layout
    (``execute_batches/batch_{index}/tasks_*.json``) and the legacy flat layout
    (``execution_batch_{N}.json``). Returns ``None`` when the path does not look
    like a batch artifact.
    """
    # S4 layout: the index lives in the parent directory name.
    parent_match = _EXECUTE_BATCH_DIR_RE.fullmatch(path.parent.name)
    if (
        parent_match is not None
        and _EXECUTE_BATCH_TASKS_RE.fullmatch(path.name) is not None
    ):
        return int(parent_match.group(1))
    # Legacy flat layout.
    legacy_match = _LEGACY_BATCH_ARTIFACT_RE.search(path.name)
    if legacy_match is not None:
        return int(legacy_match.group(1))
    return None


def resolve_batch_artifact(
    plan_dir: Path, batch_index: int, task_ids: Iterable[str] | None = None
) -> Path | None:
    """Resolve the on-disk batch artifact for ``batch_index``.

    Prefers the new S4 directory layout and falls back to the legacy flat
    ``execution_batch_{N}.json`` artifact for migration-only compatibility.
    Returns ``None`` when no artifact exists for the index.
    """
    if task_ids is not None:
        new_path = execute_batch_artifact_path(plan_dir, batch_index, task_ids)
        if new_path.exists():
            return new_path
    # Fall back to any S4 artifact already on disk for this index even when the
    # supplied task-id digest does not match (e.g. a resumed subset of a batch).
    batch_dir = execute_batch_dir(plan_dir, batch_index)
    if batch_dir.is_dir():
        candidates = sorted(
            p
            for p in batch_dir.iterdir()
            if p.is_file()
            and p.name.startswith("tasks_")
            and p.suffix == ".json"
        )
        if candidates:
            return _preferred_batch_attempt(candidates)
    legacy = legacy_batch_artifact_path(plan_dir, batch_index)
    if legacy.exists():
        return legacy
    return None


def _preferred_batch_attempt(candidates: Iterable[Path]) -> Path:
    """Select the newest fenced attempt, with legacy artifacts as fallback.

    Execute retries may reuse a numeric batch directory while changing its
    task digest.  Lexicographic filename order is unrelated to attempt order
    and can therefore hide a later accepted receipt behind an older,
    pre-dispatch artifact.  Modern dispatch fence tokens are monotonic within
    a run, so prefer them; mtime is the compatibility ordering for legacy
    receipts that predate dispatch identity.
    """

    def _attempt_key(path: Path) -> tuple[int, int, int, str]:
        fence_token = -1
        has_dispatch_identity = 0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            payload = {}
        if isinstance(payload, Mapping):
            dispatch_identity = payload.get("dispatch_identity")
            if isinstance(dispatch_identity, Mapping):
                has_dispatch_identity = 1
                fence = dispatch_identity.get("fence")
                raw_token = fence.get("token") if isinstance(fence, Mapping) else None
                if isinstance(raw_token, int) and not isinstance(raw_token, bool):
                    fence_token = raw_token
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            mtime_ns = -1
        return (has_dispatch_identity, fence_token, mtime_ns, path.name)

    return max(candidates, key=_attempt_key)


def list_batch_artifacts(plan_dir: Path) -> list[Path]:
    """List batch artifacts sorted by batch index.

    New writes live under ``execute_batches/batch_{index}/tasks_*.json``; the
    legacy flat ``execution_batch_{N}.json`` artifacts are included only when no
    S4 artifact exists for the same index (migration-only read compatibility).
    """
    by_index: dict[int, Path] = {}
    batches_root = plan_dir / EXECUTE_BATCHES_DIRNAME
    if batches_root.is_dir():
        for entry in sorted(batches_root.iterdir()):
            if not entry.is_dir():
                continue
            m = _EXECUTE_BATCH_DIR_RE.fullmatch(entry.name)
            if m is None:
                continue
            index = int(m.group(1))
            candidates = [
                child
                for child in entry.iterdir()
                if child.is_file()
                and child.name.startswith("tasks_")
                and child.suffix == ".json"
            ]
            if candidates:
                by_index[index] = _preferred_batch_attempt(candidates)
    for path in plan_dir.glob("execution_batch_*.json"):
        if not path.is_file():
            continue
        m = _LEGACY_BATCH_ARTIFACT_RE.search(path.name)
        if m is None:
            continue
        index = int(m.group(1))
        by_index.setdefault(index, path)
    return [by_index[i] for i in sorted(by_index)]


def current_iteration_artifact(plan_dir: Path, prefix: str, iteration: int) -> Path:
    return plan_dir / f"{prefix}_v{iteration}.json"


def current_iteration_raw_artifact(plan_dir: Path, prefix: str, iteration: int) -> Path:
    return plan_dir / f"{prefix}_v{iteration}_raw.txt"


# ---------------------------------------------------------------------------
# Git diff summary (used by prompts)
# ---------------------------------------------------------------------------

import subprocess


def collect_git_diff_summary(project_dir: Path, base_ref: str | None = None) -> str:
    if not (project_dir / ".git").exists():
        return "Project directory is not a git repository."
    try:
        process = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(project_dir),
            text=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "git not found on PATH."
    except subprocess.TimeoutExpired:
        return "git status timed out."
    if process.returncode != 0:
        return f"Unable to read git status: {process.stderr.strip() or process.stdout.strip()}"
    status = process.stdout.strip()
    if status:
        return status
    branch_summary = _collect_branch_diff_summary(project_dir, base_ref=base_ref)
    return branch_summary or "No git changes detected."


def _branch_diff_base(project_dir: Path) -> str | None:
    def _git(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=str(project_dir),
                text=True,
                capture_output=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        return proc if proc.returncode == 0 else None

    branch_proc = _git(["branch", "--show-current"])
    branch = (branch_proc.stdout.strip() if branch_proc else "")
    if branch in {"", "main", "master"}:
        return None
    for candidate in ("origin/main", "main", "origin/master", "master"):
        base_proc = _git(["merge-base", candidate, "HEAD"])
        if base_proc and base_proc.stdout.strip():
            return base_proc.stdout.strip()
    return None


def _collect_branch_diff_summary(project_dir: Path, *, base_ref: str | None = None) -> str:
    base = base_ref or _branch_diff_base(project_dir)
    if not base:
        return ""
    try:
        proc = subprocess.run(
            ["git", "diff", "--stat", f"{base}...HEAD"],
            cwd=str(project_dir),
            text=True,
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    summary = proc.stdout.strip()
    return f"Branch diff against base {base[:12]}:\n{summary}" if summary else ""


def collect_git_diff_patch(project_dir: Path, base_ref: str | None = None) -> str:
    if not (project_dir / ".git").exists():
        return "Project directory is not a git repository."

    def _is_untracked_diff_noise(rel_path: str) -> bool:
        from arnold_pipelines.megaplan.review.mechanical import _is_diff_noise

        return _is_diff_noise(rel_path)

    def _run_git(
        args: list[str],
        *,
        allow_returncodes: tuple[int, ...] = (0,),
    ) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
        try:
            process = subprocess.run(
                ["git", *args],
                cwd=str(project_dir),
                text=True,
                capture_output=True,
                timeout=30,
            )
        except FileNotFoundError:
            return None, "git not found on PATH."
        except subprocess.TimeoutExpired:
            return None, "git diff timed out."
        if process.returncode not in allow_returncodes:
            detail = process.stderr.strip() or process.stdout.strip()
            return None, f"Unable to read git diff: {detail}"
        return process, None

    base = base_ref or _branch_diff_base(project_dir)

    patches: list[str] = []
    seen_patches: set[str] = set()

    def _append_patch(raw_patch: str) -> None:
        patch = raw_patch.rstrip()
        if patch and patch not in seen_patches:
            patches.append(patch)
            seen_patches.add(patch)

    if base:
        branch_process, error = _run_git(["diff", "--binary", "--no-ext-diff", f"{base}...HEAD"])
        if error:
            return error
        _append_patch(branch_process.stdout if branch_process is not None else "")

    tracked_process, error = _run_git(["diff", "--binary", "--no-ext-diff", "HEAD"])
    if error:
        return error

    untracked_process, error = _run_git(["ls-files", "--others", "--exclude-standard"])
    if error:
        return error

    _append_patch(tracked_process.stdout if tracked_process is not None else "")

    untracked_paths = [
        line.strip()
        for line in (untracked_process.stdout if untracked_process is not None else "").splitlines()
        if line.strip() and not _is_untracked_diff_noise(line.strip())
    ]
    for rel_path in untracked_paths:
        if not (project_dir / rel_path).exists():
            continue
        patch_process, error = _run_git(
            ["diff", "--no-index", "--binary", "--no-ext-diff", "/dev/null", rel_path],
            allow_returncodes=(0, 1),
        )
        if error:
            return error
        _append_patch(patch_process.stdout if patch_process is not None else "")

    patch = "\n".join(patches).strip()
    if patch:
        return patch

    base = _branch_diff_base(project_dir)
    if base:
        branch_process, error = _run_git(["diff", "--binary", "--no-ext-diff", f"{base}...HEAD"])
        if not error:
            branch_patch = (branch_process.stdout if branch_process is not None else "").strip()
            if branch_patch:
                return branch_patch

    return "No git changes detected."


def find_command(name: str) -> str | None:
    import arnold_pipelines.megaplan._core as _core_pkg
    return _core_pkg.shutil.which(name)


# ---------------------------------------------------------------------------
# Projection persistence primitives (M7 custody — cursor-checked appends,
# atomic rebuild, deterministic replay, accepted-source-record ordering,
# cursor-mismatch recovery with preservation of prior projection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionCursor:
    """Cursor position in a source event stream for projection tracking.

    A projection cursor is recorded alongside every projection append so that
    consumers can validate that the source records have not been rewritten
    or truncated before accepting the projection as current.

    Required fields:
      - ``source_path``: absolute or well-known path to the source ledger.
      - ``source_record_count``: number of accepted source records at append time.
      - ``source_digest``: SHA-256 of the canonicalised source ledger at append time.
      - ``last_appended_at``: ISO-8601 timestamp of the last append.
    """

    source_path: str
    source_record_count: int
    source_digest: str
    last_appended_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, str) or not self.source_path.strip():
            raise ValueError("source_path must be a non-empty string")
        if not isinstance(self.source_record_count, int) or self.source_record_count < 0:
            raise ValueError("source_record_count must be a non-negative integer")
        if not isinstance(self.source_digest, str) or not self.source_digest.strip():
            raise ValueError("source_digest must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_record_count": self.source_record_count,
            "source_digest": self.source_digest,
            "last_appended_at": self.last_appended_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProjectionCursor":
        return cls(
            source_path=str(data.get("source_path", "")),
            source_record_count=int(data.get("source_record_count", 0)),
            source_digest=str(data.get("source_digest", "")),
            last_appended_at=str(data.get("last_appended_at", "")),
        )


@dataclass(frozen=True)
class ProjectionRecord:
    """A single projection event record with its cursor context.

    Each projection record carries the cursor that was observed when the
    event was appended, enabling cursor-checked validation during replay.
    """

    event_type: str
    event_id: str
    payload: Mapping[str, Any]
    occurred_at: str
    cursor: ProjectionCursor | None = None
    idempotency_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "payload": dict(self.payload),
            "occurred_at": self.occurred_at,
        }
        if self.cursor is not None:
            result["cursor"] = self.cursor.to_dict()
        if self.idempotency_key:
            result["idempotency_key"] = self.idempotency_key
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProjectionRecord":
        cursor_data = data.get("cursor")
        cursor = ProjectionCursor.from_dict(cursor_data) if isinstance(cursor_data, Mapping) else None
        return cls(
            event_type=str(data.get("event_type", "")),
            event_id=str(data.get("event_id", "")),
            payload=dict(data.get("payload", {})),
            occurred_at=str(data.get("occurred_at", "")),
            cursor=cursor,
            idempotency_key=str(data.get("idempotency_key", "")),
        )


def _projection_cursor_from_path(source_path: Path) -> ProjectionCursor:
    """Build a ProjectionCursor by hashing the current state of *source_path*."""
    source_path_resolved = source_path.resolve()
    record_count = 0
    if source_path_resolved.exists():
        try:
            text = source_path_resolved.read_text(encoding="utf-8")
            lines = [line for line in text.splitlines() if line.strip()]
            record_count = len(lines)
        except (FileNotFoundError, OSError):
            pass
    source_digest = (
        sha256_file(source_path_resolved)
        if source_path_resolved.exists()
        else "sha256:" + hashlib.sha256(b"").hexdigest()
    )
    return ProjectionCursor(
        source_path=str(source_path_resolved),
        source_record_count=record_count,
        source_digest=source_digest,
        last_appended_at=now_utc(),
    )


def _validate_projection_cursor(
    expected: ProjectionCursor,
    observed: ProjectionCursor,
    *,
    strict_digest: bool = True,
) -> bool:
    """Return True when *observed* cursor is compatible with *expected*.

    Cursor compatibility means:
    - ``source_path`` must match exactly.
    - ``source_record_count`` in *observed* must be >= *expected* (append-only).
    - If ``strict_digest`` is True, ``source_digest`` must match exactly.
      If False, digest mismatch alone is a soft warning (cursor drift).
    """
    if observed.source_path != expected.source_path:
        return False
    if observed.source_record_count < expected.source_record_count:
        return False
    if strict_digest and observed.source_digest != expected.source_digest:
        return False
    return True


def projection_history_path(base_dir: Path, projection_id: str) -> Path:
    """Return the path to the append-only projection history JSON-lines file."""
    return base_dir / f"{projection_id}.projection.jsonl"


def projection_state_path(base_dir: Path, projection_id: str) -> Path:
    """Return the path to the cached projection state file."""
    return base_dir / f"{projection_id}.state.json"


def projection_snapshot_path(base_dir: Path, projection_id: str) -> Path:
    """Return the path where the complete projection snapshot is atomically written."""
    return base_dir / f"{projection_id}.snapshot.json"


def projection_lock_path(base_dir: Path, projection_id: str) -> Path:
    """Return the path to the serialization lock file."""
    return base_dir / f"{projection_id}.lock"


def append_projection_event(
    base_dir: Path,
    projection_id: str,
    record: ProjectionRecord,
    *,
    source_path: Path | None = None,
    flock: bool = True,
    snapshot_dir: Path | None = None,
) -> ProjectionRecord:
    """Append a projection event with cursor-checked validation.

    If *source_path* is provided, the current source cursor is computed
    and embedded in the record before appending.  If the record already
    carries a cursor and the observed source cursor is *behind* the
    record's cursor (source record count has decreased), the append is
    rejected with a :class:`ProjectionCursorMismatchError`.

    *snapshot_dir* is the directory where projection snapshots are stored.
    It is used for cursor mismatch recovery to preserve the prior complete
    projection.  When ``None``, defaults to *base_dir*.

    Returns the record as appended (with cursor embedded).
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    history_path = projection_history_path(base_dir, projection_id)
    snap_dir = snapshot_dir if snapshot_dir is not None else base_dir

    # Compute and validate cursor
    if source_path is not None:
        observed_cursor = _projection_cursor_from_path(source_path)

        # Determine the last recorded cursor from history for validation
        last_cursor = latest_projection_cursor(base_dir, projection_id)
        validation_cursor = record.cursor if record.cursor is not None else last_cursor

        if validation_cursor is not None:
            if not _validate_projection_cursor(
                validation_cursor, observed_cursor, strict_digest=False
            ):
                # Cursor mismatch: preserve prior projection, raise error
                _preserve_prior_projection_on_mismatch(
                    snap_dir, projection_id, validation_cursor, observed_cursor
                )
                raise ProjectionCursorMismatchError(
                    f"source record count regressed for projection "
                    f"{projection_id!r}: expected >= {validation_cursor.source_record_count}, "
                    f"observed {observed_cursor.source_record_count}"
                )
        enriched_record = ProjectionRecord(
            event_type=record.event_type,
            event_id=record.event_id,
            payload=record.payload,
            occurred_at=record.occurred_at or now_utc(),
            cursor=observed_cursor,
            idempotency_key=record.idempotency_key,
        )
    else:
        enriched_record = record

    # Idempotency check against the last line in the history
    if history_path.exists():
        try:
            existing_text = history_path.read_text(encoding="utf-8")
            existing_lines = [line for line in existing_text.splitlines() if line.strip()]
            if existing_lines:
                last_line = existing_lines[-1]
                last_record = json.loads(last_line)
                if (
                    last_record.get("idempotency_key")
                    and last_record["idempotency_key"] == enriched_record.idempotency_key
                    and last_record.get("event_type") == enriched_record.event_type
                ):
                    # Idempotent repeat — no-op
                    return ProjectionRecord.from_dict(last_record)
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass

    # Append atomically
    line = json.dumps(enriched_record.to_dict(), sort_keys=True) + "\n"
    if flock:
        _projection_append_flock(base_dir, projection_id, history_path, line)
    else:
        _projection_append_inproc(history_path, line)

    return enriched_record


def _projection_append_flock(
    base_dir: Path, projection_id: str, history_path: Path, line: str
) -> None:
    """Append a line under flock serialization."""
    import fcntl

    lock_p = projection_lock_path(base_dir, projection_id)
    fd = os.open(lock_p, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _projection_append_inproc(history_path, line)
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _projection_append_inproc(history_path: Path, line: str) -> None:
    """Append a single line to the history atomically (temp-file + rename)."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if history_path.exists():
        try:
            existing = history_path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            existing = ""
    tmp = history_path.with_suffix(history_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(existing + line)
    os.replace(tmp, history_path)


def load_projection_history(
    base_dir: Path, projection_id: str
) -> tuple[ProjectionRecord, ...]:
    """Load all projection event records from the append-only history."""
    path = projection_history_path(base_dir, projection_id)
    if not path.exists():
        return ()
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ()
    if not text.strip():
        return ()
    records: list[ProjectionRecord] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            records.append(ProjectionRecord.from_dict(data))
    return tuple(records)


def latest_projection_cursor(
    base_dir: Path, projection_id: str
) -> ProjectionCursor | None:
    """Return the cursor from the most recent projection record, or None."""
    records = load_projection_history(base_dir, projection_id)
    if not records:
        return None
    # Walk backwards to find the last record with a cursor
    for record in reversed(records):
        if record.cursor is not None:
            return record.cursor
    return None


def rebuild_projection_atomically(
    base_dir: Path,
    projection_id: str,
    projection_data: Mapping[str, Any],
    *,
    cursor: ProjectionCursor | None = None,
) -> Path:
    """Atomically write the complete projection snapshot.

    The snapshot is written to a temp file and atomically renamed into place.
    If *cursor* is provided, it is included in the snapshot metadata.
    Returns the path to the written snapshot.

    *base_dir* is the directory where the snapshot file will be written.
    Callers are expected to pass the appropriate directory (e.g.
    ``base_dir / "projections"``).
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    target_path = projection_snapshot_path(base_dir, projection_id)

    snapshot_doc: dict[str, Any] = {
        "schema_version": 1,
        "projection_id": projection_id,
        "rebuilt_at": now_utc(),
        "projection": dict(projection_data),
    }
    if cursor is not None:
        snapshot_doc["cursor"] = cursor.to_dict()

    # Atomic write via temp file + rename
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(snapshot_doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_path, target_path)
    return target_path


def deterministic_projection_replay(
    base_dir: Path,
    projection_id: str,
    *,
    fold_fn: Any | None = None,
) -> Mapping[str, Any]:
    """Deterministically replay the projection history to compute current state.

    If *fold_fn* is provided, it is called with ``(accumulator, record)`` for
    each record in sequence.  The accumulator starts as an empty dict and the
    final value is returned.

    If *fold_fn* is None, the default fold returns the payload of the last
    non-empty record.
    """
    records = load_projection_history(base_dir, projection_id)
    if fold_fn is not None:
        accumulator: dict[str, Any] = {}
        for record in records:
            accumulator = fold_fn(accumulator, record)
        return accumulator
    # Default fold: last record wins
    last_payload: dict[str, Any] = {}
    for record in records:
        if record.payload:
            last_payload = dict(record.payload)
    return last_payload


def _preserve_prior_projection_on_mismatch(
    base_dir: Path,
    projection_id: str,
    expected_cursor: ProjectionCursor,
    observed_cursor: ProjectionCursor,
) -> None:
    """Preserve the prior complete projection when a cursor mismatch is detected.

    Writes the prior projection snapshot to a recovery file before the
    mismatch error is raised, so that the complete projection state is
    never lost during cursor mismatch recovery.

    *base_dir* is the directory containing the projection snapshot.
    Callers are expected to pass the appropriate directory (e.g.
    ``base_dir / "projections"``).
    """
    snapshot_path = projection_snapshot_path(base_dir, projection_id)
    if not snapshot_path.exists():
        return
    recovery_dir = base_dir / "recovery"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now_utc().replace(":", "-")
    recovery_path = recovery_dir / f"{projection_id}.pre-mismatch-{timestamp}.snapshot.json"
    try:
        content = snapshot_path.read_text(encoding="utf-8")
        recovery_path.write_text(content, encoding="utf-8")
    except (FileNotFoundError, OSError):
        pass


class ProjectionCursorMismatchError(RuntimeError):
    """Raised when a projection append fails cursor validation.

    The prior complete projection is preserved in the recovery directory
    before this error is raised.
    """


def recover_projection_from_cursor_mismatch(
    base_dir: Path,
    projection_id: str,
    *,
    source_path: Path,
) -> dict[str, Any]:
    """Recover from a cursor mismatch by returning the preserved prior projection.

    Returns a dict with keys:
      - ``status``: ``"recovered"`` | ``"no_prior_snapshot"``
      - ``cursor``: the cursor of the recovered projection (if available)
      - ``snapshot_path``: path to the preserved snapshot (if available)
      - ``diagnostics``: list of diagnostic messages
    """
    recovery_dir = base_dir / "recovery"
    diagnostics: list[str] = []

    # Try to find the most recent recovery snapshot
    recovery_snapshots = sorted(
        recovery_dir.glob(f"{projection_id}.pre-mismatch-*.snapshot.json"),
        reverse=True,
    ) if recovery_dir.exists() else []

    if recovery_snapshots:
        snapshot_path = recovery_snapshots[0]
        try:
            snapshot_data = json.loads(snapshot_path.read_text(encoding="utf-8"))
            cursor_data = snapshot_data.get("cursor")
            cursor = (
                ProjectionCursor.from_dict(cursor_data)
                if isinstance(cursor_data, Mapping)
                else None
            )
            return {
                "status": "recovered",
                "cursor": cursor.to_dict() if cursor else None,
                "snapshot_path": str(snapshot_path),
                "projection": snapshot_data.get("projection", {}),
                "diagnostics": [f"Recovered prior projection from {snapshot_path.name}"],
            }
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            diagnostics.append(f"Failed to read recovery snapshot {snapshot_path}: {exc}")

    # Fall back to the current snapshot if it exists
    snapshot_path = projection_snapshot_path(base_dir, projection_id)
    if snapshot_path.exists():
        try:
            snapshot_data = json.loads(snapshot_path.read_text(encoding="utf-8"))
            cursor_data = snapshot_data.get("cursor")
            cursor = (
                ProjectionCursor.from_dict(cursor_data)
                if isinstance(cursor_data, Mapping)
                else None
            )
            return {
                "status": "recovered",
                "cursor": cursor.to_dict() if cursor else None,
                "snapshot_path": str(snapshot_path),
                "projection": snapshot_data.get("projection", {}),
                "diagnostics": ["Recovered current snapshot (no dedicated recovery file found)"],
            }
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            diagnostics.append(f"Failed to read current snapshot: {exc}")

    return {
        "status": "no_prior_snapshot",
        "cursor": None,
        "snapshot_path": None,
        "diagnostics": diagnostics or ["No prior projection snapshot available for recovery"],
    }


# Re-export projection primitives for external consumers
__all__ = [
    # ... existing exports are preserved by the module, we only list projection additions
]
