"""Append-only registry helpers for worktree custody records."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from megaplan._core import atomic_write_json, now_utc

from .identity import (
    TASK_ID_TRAILER_ENCODING,
    TaskIdentity,
    decode_original_task_id,
    make_task_identity,
    validate_task_key,
)
from .paths import custody_paths, validate_run_id, validate_task_id

REGISTRY_SCHEMA_VERSION = 2
REGISTRY_SCHEMA_VERSION_LEGACY = 1

MISSING_REGISTRY = "missing_registry"
MISSING_ANCHOR = "missing_anchor"
MALFORMED_JSON = "malformed_json"
BROKEN_CHAIN = "broken_chain"
DIGEST_MISMATCH = "digest_mismatch"
ANCHORED_TAIL_TRUNCATION = "anchored_tail_truncation"
LOCK_FAILURE = "lock_failure"
WRITE_FAILURE = "write_failure"
IDENTITY_MISMATCH = "identity_mismatch"


@dataclass(frozen=True)
class RegistryValidationError:
    code: str
    message: str
    path: str
    line: int | None = None


@dataclass(frozen=True)
class RegistryValidation:
    ok: bool
    run_id: str
    entries: list[dict[str, Any]]
    head: dict[str, Any] | None
    errors: list[RegistryValidationError]


class RegistryError(RuntimeError):
    def __init__(self, code: str, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


def registry_jsonl_path(project_dir: str | Path, run_id: str) -> Path:
    return custody_paths(project_dir).registry_jsonl(run_id)


def registry_head_path(project_dir: str | Path, run_id: str) -> Path:
    return custody_paths(project_dir).registry_head(run_id)


def registry_lock_path(project_dir: str | Path, run_id: str) -> Path:
    return custody_paths(project_dir).registry_lock(run_id)


def append_registry_entry(
    project_dir: str | Path,
    run_id: str,
    entry_type: str,
    payload: dict[str, Any],
    *,
    task_id: str | None = None,
    task_key: str | None = None,
    identity: TaskIdentity | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Append a hash-linked custody registry entry under the per-run lock."""
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    run_id = validate_run_id(run_id)
    if identity is not None:
        task_key = identity.task_key
    if task_id is not None:
        task_id = validate_task_id(task_id)
        if identity is None and task_key is None:
            identity = make_task_identity(task_id)
            task_key = identity.task_key
    if task_key is not None:
        task_key = validate_task_key(task_key)
    paths = custody_paths(project_dir)
    lock_path = paths.registry_lock(run_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with _locked_writer(lock_path):
        if paths.registry_jsonl(run_id).exists() or paths.registry_head(run_id).exists():
            existing = validate_registry(project_dir, run_id)
            if existing.errors:
                error = existing.errors[0]
                raise RegistryError(error.code, error.message, path=Path(error.path))
            entries = existing.entries
        else:
            entries = []

        prev_hash = entries[-1]["entry_hash"] if entries else None
        entry = _build_entry(
            run_id=run_id,
            sequence=len(entries) + 1,
            prev_hash=prev_hash,
            entry_type=entry_type,
            payload=payload,
            task_key=task_key,
            identity=identity,
            timestamp=timestamp or now_utc(),
        )
        _append_entry(paths.registry_jsonl(run_id), entry)
        _write_head(
            paths.registry_head(run_id),
            registry_path=paths.registry_jsonl(run_id),
            run_id=run_id,
            entry_count=entry["sequence"],
            head_hash=entry["entry_hash"],
            timestamp=entry["timestamp"],
        )
        return entry


def read_registry_entries(project_dir: str | Path, run_id: str) -> list[dict[str, Any]]:
    validation = validate_registry(project_dir, run_id)
    if validation.errors:
        error = validation.errors[0]
        raise RegistryError(error.code, error.message, path=Path(error.path))
    return validation.entries


def validate_registry(project_dir: str | Path, run_id: str) -> RegistryValidation:
    run_id = validate_run_id(run_id)
    paths = custody_paths(project_dir)
    registry_path = paths.registry_jsonl(run_id)
    head_path = paths.registry_head(run_id)
    errors: list[RegistryValidationError] = []

    if not registry_path.exists():
        errors.append(
            RegistryValidationError(
                MISSING_REGISTRY,
                "registry JSONL file is missing",
                str(registry_path),
            )
        )
    if not head_path.exists():
        errors.append(
            RegistryValidationError(
                MISSING_ANCHOR,
                "registry head anchor file is missing",
                str(head_path),
            )
        )
    if errors:
        return RegistryValidation(False, run_id, [], None, errors)

    head = _read_head(head_path, errors)
    entries = _read_jsonl_entries(registry_path, errors)
    if errors:
        return RegistryValidation(False, run_id, entries, head, errors)

    _validate_entry_chain(registry_path, entries, errors)
    if not errors:
        _validate_head_anchor(head_path, head, entries, errors)
    return RegistryValidation(not errors, run_id, entries, head, errors)


def _build_entry(
    *,
    run_id: str,
    sequence: int,
    prev_hash: str | None,
    entry_type: str,
    payload: dict[str, Any],
    task_key: str | None,
    identity: TaskIdentity | None,
    timestamp: str,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "run_id": run_id,
        "sequence": sequence,
        "timestamp": timestamp,
        "entry_type": entry_type,
        "task_key": task_key,
        "prev_hash": prev_hash,
        "payload": payload,
    }
    if identity is not None:
        entry["identity"] = identity.registry_identity()
    entry["entry_hash"] = _entry_digest(entry)
    return entry


def _entry_digest(entry: dict[str, Any]) -> str:
    body = {key: value for key, value in entry.items() if key != "entry_hash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_line(entry: dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


class _locked_writer:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self.handle: Any | None = None
        self.locked = False

    def __enter__(self) -> "_locked_writer":
        try:
            self.handle = self.lock_path.open("a+", encoding="utf-8")
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            self.locked = True
            return self
        except OSError as exc:
            if self.handle is not None:
                self.handle.close()
                self.handle = None
            raise RegistryError(
                LOCK_FAILURE,
                f"failed to acquire registry writer lock: {exc}",
                path=self.lock_path,
            ) from exc

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.handle is None:
            return
        try:
            if self.locked:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()


def _append_entry(path: Path, entry: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_line(entry))
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise RegistryError(
            WRITE_FAILURE,
            f"failed to append registry entry: {exc}",
            path=path,
        ) from exc


def _write_head(
    path: Path,
    *,
    registry_path: Path,
    run_id: str,
    entry_count: int,
    head_hash: str,
    timestamp: str,
) -> None:
    head = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "run_id": run_id,
        "entry_count": entry_count,
        "head_hash": head_hash,
        "registry_path": str(registry_path),
        "updated_at": timestamp,
    }
    head["anchor_digest"] = _head_anchor_digest(head)
    try:
        atomic_write_json(path, head)
    except OSError as exc:
        raise RegistryError(
            WRITE_FAILURE,
            f"failed to update registry head anchor: {exc}",
            path=path,
        ) from exc


def _read_head(path: Path, errors: list[RegistryValidationError]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(
            RegistryValidationError(
                MALFORMED_JSON,
                f"registry head anchor is malformed JSON: {exc.msg}",
                str(path),
                exc.lineno,
            )
        )
        return None
    if not isinstance(payload, dict):
        errors.append(
            RegistryValidationError(
                MALFORMED_JSON,
                "registry head anchor must be a JSON object",
                str(path),
            )
        )
        return None
    return payload


def _read_jsonl_entries(
    path: Path,
    errors: list[RegistryValidationError],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                RegistryValidationError(
                    MALFORMED_JSON,
                    f"registry entry is malformed JSON: {exc.msg}",
                    str(path),
                    index,
                )
            )
            break
        if not isinstance(entry, dict):
            errors.append(
                RegistryValidationError(
                    MALFORMED_JSON,
                    "registry entry must be a JSON object",
                    str(path),
                    index,
                )
            )
            break
        entries.append(entry)
    return entries


def _validate_entry_chain(
    path: Path,
    entries: list[dict[str, Any]],
    errors: list[RegistryValidationError],
) -> None:
    previous_hash: str | None = None
    for index, entry in enumerate(entries, start=1):
        if entry.get("entry_hash") != _entry_digest(entry):
            errors.append(
                RegistryValidationError(
                    DIGEST_MISMATCH,
                    "registry entry digest does not match canonical content",
                    str(path),
                    index,
                )
            )
            return
        identity_error = _validate_entry_identity(entry)
        if identity_error is not None:
            errors.append(
                RegistryValidationError(
                    IDENTITY_MISMATCH,
                    identity_error,
                    str(path),
                    index,
                )
            )
            return
        expected_sequence = index
        if entry.get("sequence") != expected_sequence or entry.get("prev_hash") != previous_hash:
            errors.append(
                RegistryValidationError(
                    BROKEN_CHAIN,
                    "registry entry sequence or prev_hash breaks the hash chain",
                    str(path),
                    index,
                )
            )
            return
        previous_hash = entry["entry_hash"]


def _validate_entry_identity(entry: dict[str, Any]) -> str | None:
    schema_version = entry.get("schema_version")
    if schema_version == REGISTRY_SCHEMA_VERSION_LEGACY:
        task_id = entry.get("task_id")
        if task_id is not None:
            try:
                validate_task_id(task_id)
            except (TypeError, ValueError) as exc:
                return f"legacy registry task_id is not custody safe: {exc}"
        return None
    if schema_version != REGISTRY_SCHEMA_VERSION:
        return f"unsupported registry schema_version {schema_version!r}"
    if "task_id" in entry and entry.get("task_id") is not None:
        return "registry schema v2 must use top-level task_key, not raw task_id"
    task_key = entry.get("task_key")
    if task_key is not None:
        try:
            validate_task_key(task_key)
        except (TypeError, ValueError) as exc:
            return f"registry task_key is not custody safe: {exc}"
    identity = entry.get("identity")
    if identity is None:
        return None
    if not isinstance(identity, dict):
        return "registry identity metadata must be an object"
    if identity.get("task_key") != task_key:
        return "registry identity metadata task_key does not match top-level task_key"
    if identity.get("original_task_id_encoding") != TASK_ID_TRAILER_ENCODING:
        return "registry identity metadata has unsupported original task id encoding"
    encoded = identity.get("original_task_id_encoded")
    if not isinstance(encoded, str):
        return "registry identity metadata missing encoded original task id"
    try:
        original = decode_original_task_id(encoded)
        expected = make_task_identity(original)
    except (TypeError, ValueError) as exc:
        return f"registry identity metadata cannot decode original task id: {exc}"
    if expected.task_key != task_key:
        return "registry identity metadata does not round-trip to top-level task_key"
    return None


def _validate_head_anchor(
    path: Path,
    head: dict[str, Any] | None,
    entries: list[dict[str, Any]],
    errors: list[RegistryValidationError],
) -> None:
    if head is None:
        return
    if head.get("anchor_digest") != _head_anchor_digest(head):
        errors.append(
            RegistryValidationError(
                DIGEST_MISMATCH,
                "registry head anchor digest does not match canonical metadata",
                str(path),
            )
        )
        return
    entry_count = head.get("entry_count")
    head_hash = head.get("head_hash")
    if entry_count != len(entries):
        errors.append(
            RegistryValidationError(
                ANCHORED_TAIL_TRUNCATION,
                "registry entry count does not match anchored head",
                str(path),
            )
        )
        return
    actual_tail_hash = entries[-1]["entry_hash"] if entries else None
    if head_hash != actual_tail_hash:
        errors.append(
            RegistryValidationError(
                ANCHORED_TAIL_TRUNCATION,
                "anchored tail hash is not present at the registry tail",
                str(path),
            )
        )


def _head_anchor_digest(head: dict[str, Any]) -> str:
    body = {key: value for key, value in head.items() if key != "anchor_digest"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
