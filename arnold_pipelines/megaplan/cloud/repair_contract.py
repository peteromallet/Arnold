"""Shared repair-data JSON contract helpers for cloud repair artifacts."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.runtime.state_persistence import atomic_write_json as _atomic_write_json
from arnold_pipelines.megaplan.cloud.redact import redact_payload as canonical_redact_payload

CURRENT_SCHEMA_VERSION = 1

ADDITIVE_FIELD_DEFAULTS: dict[str, Any] = {
    "schema_version": CURRENT_SCHEMA_VERSION,
    "target": {},
    "incident_id": "",
    "attempt_ids": [],
    "verification": {},
    "discord_escalation": {},
    "known_prior_issue_refs": [],
}

_LIST_FIELDS = {
    "attempt_ids",
    "attempts",
    "iterations",
    "known_prior_issue_refs",
}
_DICT_FIELDS = {
    "current_advancement_snapshot",
    "current_recurrence",
    "current_signature",
    "discord_escalation",
    "initial_facts",
    "target",
    "verification",
}
_INDEX_TOP_LEVEL_KEYS = ("sessions", "incidents")
_INDEX_REF_KEYS = ("latest-attempt", "latest-outcome", "unresolved-escalation")
_ACTIVE_SESSION_STATUSES = frozenset(
    {"active", "running", "repairing", "in_progress", "pending"}
)
_RESOLVED_RECORD_STATES = frozenset(
    {
        "accepted_blocked",
        "closed",
        "complete",
        "completed",
        "delivered",
        "resolved",
        "satisfied",
        "waived",
    }
)
_UNRESOLVED_RECORD_STATES = frozenset(
    {"active", "awaiting_human", "needs_human", "open", "pending", "unresolved"}
)
_RETENTION_WINDOWS_DAYS = {
    "attempts": 14,
    "incidents": 30,
    "escalations": 90,
    "meta": 90,
    "audit_reports": 30,
}
_SNAPSHOT_RETENTION_DAYS = 30
_MIN_ATTEMPTS_PER_SESSION = 20


def load_json(path: str | Path, *, default: Any | None = None) -> Any:
    """Load JSON from *path*, returning *default* for missing or invalid files."""

    target = Path(path)
    fallback = {} if default is None else deepcopy(default)
    try:
        return validate_repair_data(target)
    except ValueError:
        return fallback


def atomic_write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Atomically write JSON using the shared fsync/replace runtime primitive."""

    _atomic_write_json(Path(path), dict(payload))


def read_repair_index(path: str | Path) -> dict[str, Any]:
    """Strictly read and validate a repair index JSON file."""

    return validate_repair_index(path)


def load_repair_index(path: str | Path, *, default: Any | None = None) -> dict[str, Any]:
    """Load a repair index JSON file, returning *default* when unreadable."""

    fallback = _normalize_repair_index(default or {})
    try:
        return validate_repair_index(path)
    except ValueError:
        return fallback


def validate_repair_data(payload_or_path: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Validate repair-data payloads while preserving legacy keys and shapes."""

    payload = _coerce_payload(payload_or_path)
    validated = deepcopy(payload)
    schema_version = validated.get("schema_version", 0)
    if not isinstance(schema_version, int) or schema_version < 0:
        raise ValueError("repair-data schema_version must be a non-negative integer")
    for field in _LIST_FIELDS:
        if field in validated and not isinstance(validated[field], list):
            raise ValueError(f"repair-data field {field!r} must be a list")
    for field in _DICT_FIELDS:
        if field in validated and not isinstance(validated[field], dict):
            raise ValueError(f"repair-data field {field!r} must be an object")
    if "outcome" in validated and not isinstance(validated["outcome"], str):
        raise ValueError("repair-data field 'outcome' must be a string")
    return validated


def ensure_additive_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a validated copy with the additive M1 contract fields present."""

    updated = validate_repair_data(payload)
    for field, default in ADDITIVE_FIELD_DEFAULTS.items():
        if field not in updated:
            updated[field] = deepcopy(default)
    return updated


def merge_additive_fields(payload: Mapping[str, Any], **updates: Any) -> dict[str, Any]:
    """Merge supported additive fields without disturbing legacy contract keys."""

    unsupported = sorted(set(updates) - set(ADDITIVE_FIELD_DEFAULTS))
    if unsupported:
        raise ValueError(f"unsupported additive repair-data fields: {', '.join(unsupported)}")
    merged = ensure_additive_fields(payload)
    for field, value in updates.items():
        merged[field] = deepcopy(value)
    return validate_repair_data(merged)


def redact_repair_data(
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Recursively redact string values using the supplied hook."""

    validated = validate_repair_data(payload)
    if redactor is None:
        return canonical_redact_payload(validated)
    return _redact_value(validated, redactor)


def save_repair_data(
    path: str | Path,
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Validate, optionally redact, and atomically persist repair-data JSON.

    When the repair-data outcome has changed meaningfully (or this is the
    first write), an incident-ledger event is appended via
    :mod:`arnold_pipelines.megaplan.cloud.incident_bridge`.  No-op saves
    (same outcome as the previous payload) do **not** produce duplicate
    events.
    """

    prepared = redact_repair_data(payload, redactor=redactor)
    target = Path(path)

    # ------------------------------------------------------------------
    # Snapshot the previous payload *before* overwriting so we can
    # decide whether this is a meaningful transition.
    # ------------------------------------------------------------------
    previous_outcome = _read_previous_outcome(target)

    atomic_write_json(target, prepared)
    _update_session_index_from_repair_data(target, prepared, redactor=redactor)

    # Only emit an incident event when the outcome actually changed.
    current_outcome = str(prepared.get("outcome") or REPAIRING).strip() or REPAIRING
    if previous_outcome is None or previous_outcome != current_outcome:
        _emit_incident_bridge_event(prepared, root=root)

    return prepared


def redact_repair_index(
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Recursively redact repair index values using the supplied hook."""

    validated = validate_repair_index(payload)
    if redactor is None:
        return canonical_redact_payload(validated)
    return _redact_value(validated, redactor)


def atomic_write_repair_index(
    path: str | Path,
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Validate, redact, and atomically persist a repair index JSON file."""

    prepared = redact_repair_index(payload, redactor=redactor)
    atomic_write_json(path, prepared)
    return prepared


def update_repair_index(
    path: str | Path,
    updater: Callable[[dict[str, Any]], Mapping[str, Any]],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Atomically read-modify-write a repair index, creating it when missing."""

    current = _read_or_initialize_repair_index(path)
    updated = updater(deepcopy(current))
    if not isinstance(updated, Mapping):
        raise ValueError("repair index updater must return a mapping")
    return atomic_write_repair_index(path, dict(updated), redactor=redactor)


def update_session_index(
    path: str | Path,
    session_id: str,
    entry_updates: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Merge *entry_updates* into the indexed session entry for *session_id*."""

    return update_repair_index(
        path,
        lambda payload: _update_index_entry(payload, "sessions", session_id, entry_updates),
        redactor=redactor,
    )


def update_incident_index(
    path: str | Path,
    incident_id: str,
    entry_updates: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Merge *entry_updates* into the indexed incident entry for *incident_id*."""

    return update_repair_index(
        path,
        lambda payload: _update_index_entry(payload, "incidents", incident_id, entry_updates),
        redactor=redactor,
    )


def _coerce_payload(payload_or_path: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    return _coerce_json_object(payload_or_path, kind="repair-data payload", path_label="repair-data file")


def validate_repair_index(payload_or_path: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Validate the repair index JSON shape used by cleanup/auditor flows."""

    payload = _coerce_json_object(
        payload_or_path,
        kind="repair index payload",
        path_label="repair index file",
    )
    return _normalize_repair_index(payload)


def _coerce_json_object(
    payload_or_path: Mapping[str, Any] | str | Path,
    *,
    kind: str,
    path_label: str,
) -> dict[str, Any]:
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{path_label} missing: {path}") from exc
    except OSError as exc:
        raise ValueError(f"{path_label} unreadable: {path}") from exc
    except Exception as exc:
        raise ValueError(f"{path_label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{kind} must be a JSON object")
    return payload


def _normalize_repair_index(payload: Mapping[str, Any]) -> dict[str, Any]:
    extras = sorted(set(payload) - set(_INDEX_TOP_LEVEL_KEYS))
    if extras:
        raise ValueError(
            "repair index only supports top-level keys: sessions, incidents"
        )

    normalized = {bucket: {} for bucket in _INDEX_TOP_LEVEL_KEYS}
    for bucket in _INDEX_TOP_LEVEL_KEYS:
        source = payload.get(bucket, {})
        if not isinstance(source, dict):
            raise ValueError(f"repair index field {bucket!r} must be an object")
        normalized[bucket] = {}
        for entry_id, entry in source.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"repair index entry {bucket}.{entry_id!s} must be an object"
                )
            entry_copy = deepcopy(entry)
            refs = entry_copy.get("refs", {})
            if refs is None:
                refs = {}
            if not isinstance(refs, dict):
                raise ValueError(
                    f"repair index entry {bucket}.{entry_id!s}.refs must be an object"
                )
            unsupported_refs = sorted(set(refs) - set(_INDEX_REF_KEYS))
            if unsupported_refs:
                raise ValueError(
                    "repair index refs only support: "
                    + ", ".join(_INDEX_REF_KEYS)
                )
            entry_copy["refs"] = {}
            for ref_key in _INDEX_REF_KEYS:
                if ref_key not in refs:
                    continue
                ref_value = refs[ref_key]
                if ref_value is not None and not isinstance(ref_value, dict):
                    raise ValueError(
                        f"repair index ref {bucket}.{entry_id!s}.refs.{ref_key} "
                        "must be an object or null"
                    )
                entry_copy["refs"][ref_key] = deepcopy(ref_value)
            normalized[bucket][str(entry_id)] = entry_copy
    return normalized


def _read_or_initialize_repair_index(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return _normalize_repair_index({})
    return read_repair_index(target)


def _update_index_entry(
    payload: dict[str, Any],
    bucket: str,
    entry_id: str,
    entry_updates: Mapping[str, Any],
) -> dict[str, Any]:
    if bucket not in _INDEX_TOP_LEVEL_KEYS:
        raise ValueError(f"unsupported repair index bucket: {bucket}")
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise ValueError("repair index entry id must be a non-empty string")
    if not isinstance(entry_updates, Mapping):
        raise ValueError("repair index entry updates must be a mapping")

    normalized = _normalize_repair_index(payload)
    current_entry = normalized[bucket].get(entry_id, {"refs": {}})
    merged = deepcopy(current_entry)
    for key, value in entry_updates.items():
        if key == "refs":
            if not isinstance(value, Mapping):
                raise ValueError("repair index entry refs updates must be a mapping")
            merged_refs = dict(merged.get("refs", {}))
            for ref_key, ref_value in value.items():
                if ref_key not in _INDEX_REF_KEYS:
                    raise ValueError(
                        "repair index refs only support: "
                        + ", ".join(_INDEX_REF_KEYS)
                    )
                if ref_value is not None and not isinstance(ref_value, Mapping):
                    raise ValueError(
                        f"repair index ref {bucket}.{entry_id}.refs.{ref_key} "
                        "must be a mapping or null"
                    )
                merged_refs[ref_key] = deepcopy(ref_value)
            merged["refs"] = merged_refs
            continue
        merged[key] = deepcopy(value)
    normalized[bucket][entry_id] = merged
    return normalized


def _redact_value(value: Any, redactor: Callable[[str], str]) -> Any:
    if isinstance(value, str):
        return redactor(value)
    if isinstance(value, dict):
        return {key: _redact_value(item, redactor) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, redactor) for item in value]
    return deepcopy(value)


# ---------------------------------------------------------------------------
# Repair verification outcome lattice and budget helpers
# ---------------------------------------------------------------------------

# -- outcome constants -------------------------------------------------------
COMPLETE = "complete"
PROGRESSED = "progressed"
LIVE_WITH_FRESH_ACTIVITY = "live_with_fresh_activity"
TRUE_HUMAN_BLOCKER = "true_human_blocker"
PARTIAL_LIVENESS = "partial_liveness"
REPAIRING = "repairing"
REPAIR_TIMEOUT = "repair_timeout"
REPAIR_EXHAUSTED = "repair_exhausted"
NEEDS_HUMAN = "needs_human"
DISCORD_ESCALATED = "discord_escalated"  # legacy non-success — preserved for compatibility

SUCCESS_OUTCOMES: frozenset[str] = frozenset(
    {COMPLETE, PROGRESSED, LIVE_WITH_FRESH_ACTIVITY, TRUE_HUMAN_BLOCKER}
)

NON_SUCCESS_OUTCOMES: frozenset[str] = frozenset(
    {PARTIAL_LIVENESS, REPAIRING, REPAIR_TIMEOUT, REPAIR_EXHAUSTED, NEEDS_HUMAN, DISCORD_ESCALATED}
)

ALL_OUTCOMES: frozenset[str] = SUCCESS_OUTCOMES | NON_SUCCESS_OUTCOMES


def is_success_outcome(outcome: str) -> bool:
    """Return True when *outcome* is a terminal repair success.

    Only ``complete``, ``progressed``, ``live_with_fresh_activity``, and
    ``true_human_blocker`` are considered success.  Liveness-only outcomes
    (``partial_liveness``) are explicitly excluded.
    """
    return outcome in SUCCESS_OUTCOMES


def is_terminal_outcome(outcome: str) -> bool:
    """Return True when *outcome* is terminal (success or non-success).

    ``repairing`` is the only non-terminal outcome; everything else is terminal.
    """
    return outcome != REPAIRING


# -- one-hour budget helpers ------------------------------------------------

DEFAULT_REPAIR_BUDGET_SECS: int = 3600


def compute_deadline(
    start_time: datetime,
    budget_secs: int = DEFAULT_REPAIR_BUDGET_SECS,
) -> datetime:
    """Return the wall-clock deadline computed from *start_time* + *budget_secs*."""
    from datetime import timedelta

    return start_time + timedelta(seconds=budget_secs)


def remaining_budget_secs(
    deadline: datetime,
    now: datetime | None = None,
) -> float:
    """Return the number of seconds remaining before *deadline* (never negative)."""
    if now is None:
        now = datetime.now(timezone.utc)
    delta = (deadline - now).total_seconds()
    return max(0.0, delta)


def is_budget_exhausted(
    deadline: datetime,
    now: datetime | None = None,
) -> bool:
    """Return True when no budget remains before *deadline*."""
    return remaining_budget_secs(deadline, now) <= 0.0


# -- verification outcome classification ------------------------------------


def classify_verification_outcome(
    *,
    is_complete: bool = False,
    has_progressed: bool = False,
    has_fresh_activity: bool = False,
    has_true_human_blocker: bool = False,
    is_live: bool = False,
    pre_snapshot: Mapping[str, Any] | None = None,
    post_snapshot: Mapping[str, Any] | None = None,
) -> str:
    """Classify a repair verification outcome from explicit evidence flags.

    The outcome lattice (first match wins):

    1. *is_complete* → :data:`COMPLETE` (terminal success)
    2. *has_progressed* → :data:`PROGRESSED` (terminal success)
    3. *has_fresh_activity* → :data:`LIVE_WITH_FRESH_ACTIVITY` (terminal success)
    4. *has_true_human_blocker* → :data:`TRUE_HUMAN_BLOCKER` (terminal success)
    5. *is_live* with no progress/fresh-activity/blocker → :data:`PARTIAL_LIVENESS` (terminal non-success)
    6. Otherwise → :data:`REPAIRING` (non-terminal)

    *pre_snapshot* and *post_snapshot* are accepted for forward compatibility
    with snapshot-driven delta detection but are not compared here; callers
    should compute the explicit flags before calling this function.
    """
    if is_complete:
        return COMPLETE
    if has_progressed:
        return PROGRESSED
    if has_fresh_activity:
        return LIVE_WITH_FRESH_ACTIVITY
    if has_true_human_blocker:
        return TRUE_HUMAN_BLOCKER
    if is_live:
        return PARTIAL_LIVENESS
    return REPAIRING


def build_verification_record(
    outcome: str,
    *,
    pre_snapshot: Mapping[str, Any] | None = None,
    post_snapshot: Mapping[str, Any] | None = None,
    delta_summary: str = "",
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    """Return a structured verification record suitable for repair-data persistence.

    Args:
        outcome: One of the outcome lattice constants (e.g. :data:`COMPLETE`).
        pre_snapshot: Optional pre-relaunch resolver snapshot.
        post_snapshot: Optional post-relaunch resolver snapshot.
        delta_summary: Human-readable description of what changed (or didn't).
        recorded_at: Timestamp for the record (defaults to now).
    """
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc)
    return {
        "outcome": outcome,
        "is_success": is_success_outcome(outcome),
        "is_terminal": is_terminal_outcome(outcome),
        "recorded_at": recorded_at.isoformat(),
        "pre_snapshot": dict(pre_snapshot) if pre_snapshot is not None else None,
        "post_snapshot": dict(post_snapshot) if post_snapshot is not None else None,
        "delta_summary": delta_summary,
    }


# ---------------------------------------------------------------------------
# JSONL / NDJSON sidecar helpers (append-only, atomic)
# ---------------------------------------------------------------------------

_SIDECAR_KINDS = ("events", "incidents", "attempts", "escalations", "cleanup")
_SIDECAR_FILENAME = {
    "events": "events.jsonl",
    "incidents": "incidents.jsonl",
    "attempts": "attempts.jsonl",
    "escalations": "escalations.jsonl",
    "cleanup": "cleanup.jsonl",
}


def _fsync_dir(path: Path) -> None:
    """fsync the directory containing *path* so renames are durable."""
    directory = path if path.is_dir() else path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    """Atomically append *record* as a JSON line to the JSONL file at *path*.

    Uses read-modify-write with temp-file/fsync/replace so readers never
    see a partial or truncated file.  Parent directories are created as
    needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    new_line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"

    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except Exception:
            existing = ""

    full_content = (existing + new_line).encode("utf-8")

    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(full_content)
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)
    _fsync_dir(path.parent)


def read_jsonl_records(
    path: str | Path,
    *,
    skip_parse_errors: bool = False,
) -> list[dict[str, Any]]:
    """Read all valid records from a JSONL / NDJSON file.

    Args:
        path: Path to the ``.jsonl`` file.
        skip_parse_errors: When *True*, malformed lines are silently
            skipped.  When *False* (default), the first unparseable line
            raises :exc:`ValueError`.

    Returns:
        A list of parsed record dicts, in file order.

    Raises:
        ValueError: If *skip_parse_errors* is *False* and any line cannot
            be parsed as JSON, or if the file does not exist.
    """
    target = Path(path)
    if not target.exists():
        if skip_parse_errors:
            return []
        raise ValueError(f"JSONL file missing: {target}")

    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if skip_parse_errors:
                continue
            raise ValueError(
                f"JSONL parse error at {target}:{lineno}: {exc}"
            ) from exc
        if not isinstance(record, dict):
            if skip_parse_errors:
                continue
            raise ValueError(
                f"JSONL record at {target}:{lineno} is not a JSON object"
            )
        records.append(record)
    return records


def validate_jsonl_summary(path: str | Path) -> dict[str, Any]:
    """Return a validation summary for a JSONL sidecar file.

    The returned dict contains:

    * ``file`` — absolute path to the inspected file.
    * ``total_lines`` — number of non-empty lines.
    * ``valid_records`` — number of successfully parsed object records.
    * ``parse_errors`` — list of ``{line, error}`` dicts for malformed lines.
    * ``non_object_lines`` — count of lines that parsed as non-object JSON.
    * ``first_record`` — the first valid record (or *None*).
    * ``last_record`` — the last valid record (or *None*).
    * ``ordered`` — *True* if every record carries a ``_sequence`` field that
      is strictly increasing, *False* otherwise (or *None* when there are
      fewer than two records).
    """
    target = Path(path)
    summary: dict[str, Any] = {
        "file": str(target.resolve()),
        "total_lines": 0,
        "valid_records": 0,
        "parse_errors": [],
        "non_object_lines": 0,
        "first_record": None,
        "last_record": None,
        "ordered": None,
    }

    if not target.exists():
        return summary

    sequences: list[int] = []
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        summary["total_lines"] += 1
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            summary["parse_errors"].append({"line": lineno, "error": str(exc)})
            continue
        if not isinstance(record, dict):
            summary["non_object_lines"] += 1
            continue
        summary["valid_records"] += 1
        if summary["first_record"] is None:
            summary["first_record"] = record
        summary["last_record"] = record
        seq = record.get("_sequence")
        if isinstance(seq, int):
            sequences.append(seq)

    if len(sequences) >= 2:
        summary["ordered"] = all(
            sequences[i] < sequences[i + 1] for i in range(len(sequences) - 1)
        )
    return summary


def _sidecar_jsonl_path(sidecar_dir: str | Path, kind: str) -> Path:
    """Return the canonical JSONL path for a sidecar *kind*."""
    if kind not in _SIDECAR_KINDS:
        raise ValueError(
            f"Unknown sidecar kind {kind!r}; expected one of {_SIDECAR_KINDS}"
        )
    base = Path(sidecar_dir)
    return base / kind / _SIDECAR_FILENAME[kind]


def append_jsonl_record(
    sidecar_dir: str | Path,
    kind: str,
    record: Mapping[str, Any],
    *,
    auto_sequence: bool = True,
) -> Path:
    """Append *record* to the typed JSONL sidecar under *sidecar_dir*.

    Args:
        sidecar_dir: Root directory for sidecar files (e.g. ``repair-data.d``).
        kind: One of ``"events"``, ``"incidents"``, ``"attempts"``.
        record: The JSON-serializable record to append.
        auto_sequence: When *True* (default), a ``_sequence`` field is
            injected with the next available integer.

    Returns:
        The :class:`Path` to the JSONL file that was appended to.
    """
    if not isinstance(record, Mapping):
        raise ValueError("JSONL record must be a mapping")

    target = _sidecar_jsonl_path(sidecar_dir, kind)
    enriched: dict[str, Any] = dict(record)

    if auto_sequence:
        existing = read_jsonl_records(target, skip_parse_errors=True)
        enriched["_sequence"] = len(existing) + 1

    if "_timestamp" not in enriched:
        enriched["_timestamp"] = datetime.now(timezone.utc).isoformat()

    _atomic_append_jsonl(target, enriched)
    return target


def append_repair_event(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append a repair event record to the ``events`` sidecar."""
    return append_jsonl_record(sidecar_dir, "events", record, **kwargs)


def append_incident_record(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append an incident record to the ``incidents`` sidecar."""
    return append_jsonl_record(sidecar_dir, "incidents", record, **kwargs)


def append_attempt_record(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append an attempt record to the ``attempts`` sidecar."""
    return append_jsonl_record(sidecar_dir, "attempts", record, **kwargs)


def append_escalation_record(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append an escalation lifecycle record to the ``escalations`` sidecar."""
    return append_jsonl_record(sidecar_dir, "escalations", record, **kwargs)


def append_cleanup_record(
    sidecar_dir: str | Path,
    record: Mapping[str, Any],
    **kwargs: Any,
) -> Path:
    """Append a retention/cleanup lifecycle record to the ``cleanup`` sidecar."""
    return append_jsonl_record(sidecar_dir, "cleanup", record, **kwargs)


def cleanup_repair_data_retention(
    repair_data_dir: str | Path,
    *,
    sidecar_dir: str | Path | None = None,
    audit_report_dir: str | Path | None = None,
    index_path: str | Path | None = None,
    now: datetime | None = None,
    active_session_ids: set[str] | None = None,
    redactor: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Prune stale repair artifacts while preserving protected evidence."""

    if now is None:
        now = datetime.now(timezone.utc)

    repair_root = Path(repair_data_dir)
    cleanup_sidecar_dir = Path(sidecar_dir) if sidecar_dir is not None else repair_root.with_name(f"{repair_root.name}.d")
    audit_root = Path(audit_report_dir) if audit_report_dir is not None else None
    effective_index_path = Path(index_path) if index_path is not None else repair_root / "index.json"

    index_before = load_repair_index(effective_index_path)
    active_sessions = set(active_session_ids or set())
    active_sessions.update(_active_sessions_from_index(index_before))
    referenced_audit_reports = _collect_referenced_audit_reports(
        repair_root,
        index_before,
        audit_root,
    )

    summary: dict[str, Any] = {
        "cleanup_type": "retention",
        "repair_data_dir": str(repair_root),
        "pruned_counts": {},
        "pruned_paths": {},
        "preserved_counts": {},
        "preserved_reasons": {},
        "index_snapshots": {"before": redact_repair_index(index_before, redactor=redactor), "after": {}},
    }

    for path in sorted(repair_root.glob("*.repair-data.json")):
        session_id = path.name[: -len(".repair-data.json")]
        preserve = session_id in active_sessions or _is_within_days(path, now, _SNAPSHOT_RETENTION_DAYS)
        if preserve:
            _record_preserved(summary, "snapshots", "active_session_snapshot" if session_id in active_sessions else "recent_snapshot")
            continue
        _prune_path(path, summary, "snapshots")

    _cleanup_attempt_records(repair_root / "attempts", now, summary)
    _cleanup_json_record_dir(
        repair_root / "incidents",
        now,
        summary,
        category="incidents",
        retention_days=_RETENTION_WINDOWS_DAYS["incidents"],
        preserve_predicate=_is_unresolved_record,
        preserve_reason="unresolved_incident",
    )
    _cleanup_json_record_dir(
        repair_root / "escalations",
        now,
        summary,
        category="escalations",
        retention_days=_RETENTION_WINDOWS_DAYS["escalations"],
        preserve_predicate=_is_unresolved_record,
        preserve_reason="unresolved_escalation",
    )
    _cleanup_json_record_dir(
        repair_root / "meta",
        now,
        summary,
        category="meta",
        retention_days=_RETENTION_WINDOWS_DAYS["meta"],
    )
    if audit_root is not None:
        _cleanup_audit_reports(audit_root, now, referenced_audit_reports, summary)

    index_after = _reconcile_repair_index_after_cleanup(
        index_before,
        repair_root=repair_root,
        active_sessions=active_sessions,
    )
    atomic_write_repair_index(effective_index_path, index_after, redactor=redactor)
    summary["index_snapshots"]["after"] = redact_repair_index(index_after, redactor=redactor)

    cleanup_id = f"cleanup-{now.strftime('%Y%m%dT%H%M%SZ')}"
    record = {
        "cleanup_id": cleanup_id,
        "pruned_counts": summary["pruned_counts"],
        "pruned_paths": summary["pruned_paths"],
        "preserved_counts": summary["preserved_counts"],
        "preserved_reasons": summary["preserved_reasons"],
        "index_snapshots": summary["index_snapshots"],
    }
    cleanup_path = append_cleanup_record(cleanup_sidecar_dir, record)
    summary["cleanup_id"] = cleanup_id
    summary["cleanup_record_path"] = str(cleanup_path)
    return summary


def _cleanup_attempt_records(attempts_dir: Path, now: datetime, summary: dict[str, Any]) -> None:
    if not attempts_dir.exists():
        return

    grouped: dict[str, list[tuple[Path, datetime]]] = {}
    for path in sorted(attempts_dir.glob("*.json")):
        payload = load_json(path, default={})
        session_id = _record_session_id(payload, path)
        grouped.setdefault(session_id, []).append((path, _path_mtime(path)))

    for entries in grouped.values():
        entries.sort(key=lambda item: item[1], reverse=True)
        protected = {path for path, _ in entries[:_MIN_ATTEMPTS_PER_SESSION]}
        for path, _ in entries:
            if path in protected:
                _record_preserved(summary, "attempts", "recent_attempt_floor")
                continue
            if _is_within_days(path, now, _RETENTION_WINDOWS_DAYS["attempts"]):
                _record_preserved(summary, "attempts", "recent_attempt")
                continue
            _prune_path(path, summary, "attempts")


def _cleanup_json_record_dir(
    directory: Path,
    now: datetime,
    summary: dict[str, Any],
    *,
    category: str,
    retention_days: int,
    preserve_predicate: Callable[[Mapping[str, Any]], bool] | None = None,
    preserve_reason: str | None = None,
) -> None:
    if not directory.exists():
        return

    for path in sorted(directory.glob("*.json")):
        payload = load_json(path, default={})
        if preserve_predicate is not None and preserve_predicate(payload):
            _record_preserved(summary, category, preserve_reason or f"{category}_preserved")
            continue
        if _is_within_days(path, now, retention_days):
            _record_preserved(summary, category, f"recent_{category[:-1] if category.endswith('s') else category}")
            continue
        _prune_path(path, summary, category)


def _cleanup_audit_reports(
    audit_dir: Path,
    now: datetime,
    referenced_reports: set[Path],
    summary: dict[str, Any],
) -> None:
    if not audit_dir.exists():
        return

    for path in sorted(audit_dir.glob("*-audit.*")):
        if path.suffix not in {".json", ".md"}:
            continue
        if path.resolve() in referenced_reports:
            _record_preserved(summary, "audit_reports", "referenced_audit_report")
            continue
        if _is_within_days(path, now, _RETENTION_WINDOWS_DAYS["audit_reports"]):
            _record_preserved(summary, "audit_reports", "recent_audit_report")
            continue
        _prune_path(path, summary, "audit_reports")


def _active_sessions_from_index(index_payload: Mapping[str, Any]) -> set[str]:
    active: set[str] = set()
    for session_id, entry in index_payload.get("sessions", {}).items():
        if not isinstance(entry, Mapping):
            continue
        status = str(entry.get("status", "")).strip().lower()
        if status in _ACTIVE_SESSION_STATUSES:
            active.add(str(session_id))
            continue
        refs = entry.get("refs")
        if isinstance(refs, Mapping):
            latest_outcome = refs.get("latest-outcome")
            if isinstance(latest_outcome, Mapping):
                if str(latest_outcome.get("outcome", "")).strip().lower() == REPAIRING:
                    active.add(str(session_id))
    return active


def _read_previous_outcome(target: Path) -> str | None:
    """Return the outcome string from a previous repair-data file, or *None*."""
    try:
        if not target.exists():
            return None
        previous = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(previous, dict):
        return None
    outcome = previous.get("outcome")
    if isinstance(outcome, str) and outcome.strip():
        return outcome.strip()
    return None


def _emit_incident_bridge_event(
    payload: Mapping[str, Any],
    *,
    root: Path | str | None = None,
) -> None:
    """Map the repair-data outcome to an incident-bridge event and append it.

    This is intentionally a best-effort side effect: if the bridge or
    ledger is unavailable the repair-data save still succeeds.
    """
    session_id = str(payload.get("session") or "").strip() or None
    incident_id = str(payload.get("incident_id") or "").strip() or None
    if not incident_id:
        return

    outcome = str(payload.get("outcome") or REPAIRING).strip() or REPAIRING
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        plan_name = str(payload.get("plan_name") or "").strip()
        run_kind = str(payload.get("run_kind") or "").strip()
        workspace = str(payload.get("workspace") or "").strip()
        summary = f"repair-data outcome={outcome}"
        if plan_name:
            summary += f" plan={plan_name}"
        if run_kind:
            summary += f" kind={run_kind}"
        if workspace:
            summary += f" workspace={workspace}"

    evidence: list[Any] = []
    verification = payload.get("verification")
    if isinstance(verification, dict):
        evidence.append({"kind": "verification_record", "data": verification})
    attempt_ids = payload.get("attempt_ids")
    if isinstance(attempt_ids, list) and attempt_ids:
        evidence.append({"kind": "attempt_ids", "ids": list(attempt_ids)})

    try:
        from arnold_pipelines.megaplan.cloud.incident_bridge import (
            append_meta_repair_attempt,
            append_verified_recovered,
        )

        if outcome == REPAIRING:
            append_meta_repair_attempt(
                incident_id=incident_id,
                summary=summary,
                attempt_id=f"{session_id or 'unknown'}-{outcome}",
                outcome="attempted",
                evidence=evidence,
                session_id=session_id,
                root=root,
            )
        elif is_success_outcome(outcome):
            append_verified_recovered(
                incident_id=incident_id,
                summary=summary,
                evidence=evidence,
                session_id=session_id,
                root=root,
            )
        else:
            # Terminal non-success outcomes (repair_timeout, repair_exhausted,
            # needs_human, partial_liveness, discord_escalated, etc.)
            append_meta_repair_attempt(
                incident_id=incident_id,
                summary=summary,
                attempt_id=f"{session_id or 'unknown'}-{outcome}",
                outcome=outcome,
                evidence=evidence,
                session_id=session_id,
                root=root,
            )
    except Exception:
        # Bridge event emission is best-effort; never let it fail the save.
        pass


def _update_session_index_from_repair_data(
    path: Path,
    payload: Mapping[str, Any],
    *,
    redactor: Callable[[str], str] | None = None,
) -> None:
    session_id = str(payload.get("session") or "").strip()
    if not session_id and path.name.endswith(".repair-data.json"):
        session_id = path.name[: -len(".repair-data.json")]
    if not session_id:
        return

    recorded_at = _repair_data_recorded_at(payload)
    outcome = str(payload.get("outcome") or REPAIRING).strip() or REPAIRING
    incident_id = str(payload.get("incident_id") or "").strip()
    latest_outcome_ref: dict[str, Any] = {
        "outcome": outcome,
        "recorded_at": recorded_at,
        "path": str(path),
    }
    if incident_id:
        latest_outcome_ref["incident_id"] = incident_id

    entry_updates: dict[str, Any] = {
        "session": session_id,
        "status": outcome,
        "updated_at": recorded_at,
        "workspace": str(payload.get("workspace") or ""),
        "run_kind": str(payload.get("run_kind") or ""),
        "plan_name": str(payload.get("plan_name") or ""),
        "incident_id": incident_id,
        "refs": {"latest-outcome": latest_outcome_ref},
    }
    if isinstance(payload.get("attempt_ids"), list):
        entry_updates["attempt_ids"] = deepcopy(payload.get("attempt_ids"))

    update_session_index(path.parent / "index.json", session_id, entry_updates, redactor=redactor)


def _repair_data_recorded_at(payload: Mapping[str, Any]) -> str:
    verification = payload.get("verification")
    if isinstance(verification, Mapping):
        recorded_at = str(verification.get("recorded_at") or "").strip()
        if recorded_at:
            return recorded_at
    for field in ("updated_at", "recorded_at", "created_at"):
        recorded_at = str(payload.get(field) or "").strip()
        if recorded_at:
            return recorded_at
    return datetime.now(timezone.utc).isoformat()


def _reconcile_repair_index_after_cleanup(
    index_payload: Mapping[str, Any],
    *,
    repair_root: Path,
    active_sessions: set[str],
) -> dict[str, Any]:
    normalized = _normalize_repair_index(index_payload)
    reconciled = _normalize_repair_index({})

    for session_id, entry in normalized["sessions"].items():
        snapshot_path = repair_root / f"{session_id}.repair-data.json"
        if not snapshot_path.exists() and session_id not in active_sessions:
            continue
        entry_copy = deepcopy(entry)
        meta_path = str(entry_copy.get("latest_meta_record_path") or "").strip()
        if meta_path and not Path(meta_path).exists():
            entry_copy["latest_meta_record_path"] = ""
            entry_copy["latest_meta_repair_id"] = ""
            entry_copy["latest_meta_outcome"] = ""
            entry_copy["latest_meta_recorded_at"] = ""
        reconciled["sessions"][session_id] = entry_copy

    for incident_id, entry in normalized["incidents"].items():
        incident_path = repair_root / "incidents" / f"{incident_id}.json"
        if incident_path.exists():
            reconciled["incidents"][incident_id] = deepcopy(entry)

    return reconciled


def _collect_referenced_audit_reports(
    repair_root: Path,
    index_payload: Mapping[str, Any],
    audit_root: Path | None,
) -> set[Path]:
    referenced: set[Path] = set()
    for path in sorted((repair_root / "incidents").glob("*.json")):
        payload = load_json(path, default={})
        if _is_unresolved_record(payload):
            referenced.update(_extract_audit_report_paths(payload, audit_root))
    for entry in index_payload.get("incidents", {}).values():
        if isinstance(entry, Mapping) and _is_unresolved_record(entry):
            referenced.update(_extract_audit_report_paths(entry, audit_root))
    return referenced


def _extract_audit_report_paths(value: Any, audit_root: Path | None) -> set[Path]:
    matches: set[Path] = set()
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return matches
        path = Path(candidate)
        if _looks_like_audit_report(path, audit_root):
            matches.add(path.resolve())
        return matches
    if isinstance(value, Mapping):
        for item in value.values():
            matches.update(_extract_audit_report_paths(item, audit_root))
        return matches
    if isinstance(value, list):
        for item in value:
            matches.update(_extract_audit_report_paths(item, audit_root))
    return matches


def _looks_like_audit_report(path: Path, audit_root: Path | None) -> bool:
    name = path.name
    if name.endswith("-audit.json") or name.endswith("-audit.md"):
        return True
    if audit_root is not None:
        try:
            path.resolve().relative_to(audit_root.resolve())
            return path.suffix in {".json", ".md"}
        except ValueError:
            return False
    return False


def _record_session_id(payload: Mapping[str, Any], path: Path) -> str:
    session_id = payload.get("session_id") or payload.get("session")
    if isinstance(session_id, str) and session_id.strip():
        return session_id
    return path.stem


def _is_unresolved_record(payload: Mapping[str, Any]) -> bool:
    for key in ("resolved_at", "closed_at", "completed_at"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return False
    for key in ("resolved", "closed", "completed"):
        if payload.get(key) is True:
            return False

    for key in ("state", "status", "resolution_state", "lifecycle"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        normalized = value.strip().lower()
        if normalized in _RESOLVED_RECORD_STATES:
            return False
        if normalized in _UNRESOLVED_RECORD_STATES:
            return True
    return True


def _is_within_days(path: Path, now: datetime, days: int) -> bool:
    cutoff = now.timestamp() - (days * 86400)
    return path.stat().st_mtime >= cutoff


def _path_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _prune_path(path: Path, summary: dict[str, Any], category: str) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    summary["pruned_counts"][category] = int(summary["pruned_counts"].get(category, 0)) + 1
    summary["pruned_paths"].setdefault(category, []).append(str(path))


def _record_preserved(summary: dict[str, Any], category: str, reason: str) -> None:
    summary["preserved_counts"][category] = int(summary["preserved_counts"].get(category, 0)) + 1
    summary["preserved_reasons"][reason] = int(summary["preserved_reasons"].get(reason, 0)) + 1


__all__ = [
    "ADDITIVE_FIELD_DEFAULTS",
    "ALL_OUTCOMES",
    "COMPLETE",
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_REPAIR_BUDGET_SECS",
    "DISCORD_ESCALATED",
    "LIVE_WITH_FRESH_ACTIVITY",
    "NEEDS_HUMAN",
    "NON_SUCCESS_OUTCOMES",
    "PARTIAL_LIVENESS",
    "PROGRESSED",
    "REPAIR_EXHAUSTED",
    "REPAIR_TIMEOUT",
    "REPAIRING",
    "SUCCESS_OUTCOMES",
    "TRUE_HUMAN_BLOCKER",
    "append_attempt_record",
    "append_cleanup_record",
    "append_escalation_record",
    "append_incident_record",
    "append_jsonl_record",
    "append_repair_event",
    "atomic_write_json",
    "atomic_write_repair_index",
    "build_verification_record",
    "classify_verification_outcome",
    "cleanup_repair_data_retention",
    "compute_deadline",
    "ensure_additive_fields",
    "is_budget_exhausted",
    "is_success_outcome",
    "is_terminal_outcome",
    "load_json",
    "load_repair_index",
    "merge_additive_fields",
    "read_repair_index",
    "read_jsonl_records",
    "redact_repair_index",
    "redact_repair_data",
    "remaining_budget_secs",
    "save_repair_data",
    "update_incident_index",
    "update_repair_index",
    "update_session_index",
    "validate_jsonl_summary",
    "validate_repair_index",
    "validate_repair_data",
]
