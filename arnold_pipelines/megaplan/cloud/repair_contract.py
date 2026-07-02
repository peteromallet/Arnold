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
) -> dict[str, Any]:
    """Validate, optionally redact, and atomically persist repair-data JSON."""

    prepared = redact_repair_data(payload, redactor=redactor)
    atomic_write_json(path, prepared)
    return prepared


def _coerce_payload(payload_or_path: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"repair-data file missing: {path}") from exc
    except OSError as exc:
        raise ValueError(f"repair-data file unreadable: {path}") from exc
    except Exception as exc:
        raise ValueError(f"repair-data file is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("repair-data payload must be a JSON object")
    return payload


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

_SIDECAR_KINDS = ("events", "incidents", "attempts")
_SIDECAR_FILENAME = {kind: f"{kind}.jsonl" for kind in _SIDECAR_KINDS}


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
    "append_incident_record",
    "append_jsonl_record",
    "append_repair_event",
    "atomic_write_json",
    "build_verification_record",
    "classify_verification_outcome",
    "compute_deadline",
    "ensure_additive_fields",
    "is_budget_exhausted",
    "is_success_outcome",
    "is_terminal_outcome",
    "load_json",
    "merge_additive_fields",
    "read_jsonl_records",
    "redact_repair_data",
    "remaining_budget_secs",
    "save_repair_data",
    "validate_jsonl_summary",
    "validate_repair_data",
]
