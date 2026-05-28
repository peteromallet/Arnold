"""Shared helpers for user-action and quality resolution contracts.

This module centralizes resolution semantics that were previously duplicated
across the disk-backed user-action pipeline, the in-memory user-action event
pipeline, and the quality-resolution pipeline. User-action and quality domains
remain distinct: they have different valid state sets, validation rules, and
behavior outputs.
"""

from __future__ import annotations

from typing import Any, Literal

ResolutionSource = Literal["disk", "memory"]

DISK_SOURCE: ResolutionSource = "disk"
MEMORY_SOURCE: ResolutionSource = "memory"
VALID_RESOLUTION_SOURCES: frozenset[ResolutionSource] = frozenset(
    {DISK_SOURCE, MEMORY_SOURCE}
)

SUPPORTED_USER_ACTION_RESOLUTION_STATES: frozenset[str] = frozenset(
    {"satisfied", "accepted_blocked", "waived", "manual_required", "rejected"}
)
SUPPORTED_QUALITY_RESOLUTION_STATES: frozenset[str] = frozenset(
    {"accepted_with_debt", "fixed", "manual_required", "rejected"}
)

FALLBACK_STATES: frozenset[str] = frozenset({"accepted_blocked", "waived"})
HARD_BLOCK_STATES: frozenset[str] = frozenset({"manual_required", "rejected"})

OMIT = "omit"
FALLBACK = "fallback"
HARD_BLOCK = "hard_block"
UNRESOLVED = "unresolved"

ADVANCE_WITH_DEBT = "advance_with_debt"
RERUN_REQUIRED = "rerun_required"
RESOLVED = "resolved"

_MISSING = object()


def _validate_source(source: str) -> ResolutionSource:
    if source not in VALID_RESOLUTION_SOURCES:
        expected = ", ".join(sorted(VALID_RESOLUTION_SOURCES))
        raise ValueError(
            f"Unsupported resolution source {source!r}. Expected one of: {expected}."
        )
    return source


def _source_fields(
    source: str,
    *,
    disk_field: str,
    memory_field: str,
) -> tuple[str, str]:
    resolved_source = _validate_source(source)
    if resolved_source == DISK_SOURCE:
        return disk_field, memory_field
    return memory_field, disk_field


def _aliased_record_value(
    record: dict[str, Any],
    *,
    source: str,
    disk_field: str,
    memory_field: str,
) -> Any:
    primary_field, alias_field = _source_fields(
        source,
        disk_field=disk_field,
        memory_field=memory_field,
    )
    primary_value = record.get(primary_field, _MISSING)
    if primary_value is not _MISSING:
        return primary_value
    return record.get(alias_field, _MISSING)


def resolution_state(
    record: dict[str, Any] | None,
    *,
    source: str,
) -> str | None:
    """Return the source-specific resolution state string from *record*."""
    if not isinstance(record, dict):
        return None
    value = _aliased_record_value(
        record,
        source=source,
        disk_field="state",
        memory_field="resolution",
    )
    if isinstance(value, str):
        return value
    return None


def resolution_applies_to_task(
    record: dict[str, Any] | None,
    task_id: str | None,
    *,
    source: str,
) -> bool:
    """Return whether a resolution record applies to ``task_id``.

    The disk and memory pipelines intentionally preserve different empty-list
    semantics. Disk records treat an empty task list as "applies to all";
    memory records treat an explicit empty list as "applies to no concrete
    task", while ``task_id is None`` remains an aggregate applicability check.
    """
    resolved_source = _validate_source(source)
    if not isinstance(record, dict):
        return False

    task_scope = _aliased_record_value(
        record,
        source=resolved_source,
        disk_field="applies_to_task_ids",
        memory_field="applies_to_tasks",
    )

    if resolved_source == DISK_SOURCE and task_id is None:
        return False

    if task_scope is _MISSING:
        return True

    if resolved_source == MEMORY_SOURCE and task_scope is None:
        return True

    if not isinstance(task_scope, list):
        return False

    if resolved_source == MEMORY_SOURCE and task_id is None:
        return True

    filtered_task_ids = {
        item for item in task_scope if isinstance(item, str) and item
    }

    if not filtered_task_ids:
        return resolved_source == DISK_SOURCE

    return task_id in filtered_task_ids


def _event_sort_key(event: dict[str, Any]) -> str:
    timestamp = event.get("timestamp") or event.get("created_at") or ""
    if isinstance(timestamp, str):
        return timestamp
    return str(timestamp)


def latest_events_by_key(
    events: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    key_field: str,
    state_field: str = "resolution",
    valid_states: frozenset[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the latest well-formed event for each ``key_field`` value."""
    if not events:
        return {}

    latest: dict[str, dict[str, Any]] = {}
    sorted_events = sorted(
        (event for event in events if isinstance(event, dict)),
        key=_event_sort_key,
    )
    for event in sorted_events:
        key = event.get(key_field)
        if not isinstance(key, str) or not key.strip():
            continue
        if valid_states is not None:
            state = event.get(state_field)
            if not isinstance(state, str) or state not in valid_states:
                continue
        latest[key] = event
    return latest


def build_base_resolution_event(
    *,
    id_field: str,
    id_value: str,
    resolution: str,
    created_by: str = "operator",
    timestamp: str | None = None,
    fallback_mode: str | None = None,
    tasks_field: str | None = None,
    tasks: list[str] | tuple[str, ...] | None = None,
    instructions: str | None = None,
    reason: str | None = None,
    phase: str | None = None,
    evidence: list[str] | tuple[str, ...] | None = None,
    debt_note: str | None = None,
) -> dict[str, Any]:
    """Build a base append-only resolution event with shared metadata fields."""
    from megaplan._core.io import now_utc

    ts = timestamp or now_utc()
    event: dict[str, Any] = {
        id_field: id_value,
        "resolution": resolution,
        "timestamp": ts,
        "created_at": ts,
        "created_by": created_by,
    }
    if fallback_mode is not None:
        event["fallback_mode"] = fallback_mode
    if tasks_field is not None and tasks is not None:
        event[tasks_field] = list(tasks)
    if instructions is not None:
        event["instructions"] = instructions
    if reason is not None:
        event["reason"] = reason
    if phase is not None:
        event["phase"] = phase
    if evidence is not None:
        event["evidence"] = list(evidence)
    if debt_note is not None:
        event["debt_note"] = debt_note
    return event


def validate_optional_string_list(
    event: dict[str, Any],
    field_name: str,
    *,
    error_message: str,
) -> None:
    """Validate that an optional field is a list of non-empty strings."""
    value = event.get(field_name)
    if value is not None and (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        from megaplan.types import CliError

        raise CliError("invalid_args", error_message)


def validate_optional_string_field(
    event: dict[str, Any],
    field_name: str,
    *,
    error_message: str,
) -> None:
    """Validate that an optional field is a non-empty string."""
    value = event.get(field_name)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        from megaplan.types import CliError

        raise CliError("invalid_args", error_message)


def classify_resolution_behavior(resolution: str | None) -> str:
    """Map a user-action resolution state to execute-time behavior."""
    if resolution == "satisfied":
        return OMIT
    if resolution in FALLBACK_STATES:
        return FALLBACK
    return HARD_BLOCK


def resolution_recommended_action(
    record: dict[str, Any] | None,
    *,
    source: str,
) -> str:
    """Return the recommended action string for a user-action resolution."""
    state = resolution_state(record, source=source)
    if state in FALLBACK_STATES:
        return "continue_with_fallback"
    if state == "satisfied":
        return "retry_execute"
    if state == "rejected":
        return "cannot_continue"
    if state == "manual_required":
        return "awaiting_human"
    return "awaiting_human"


def classify_quality_resolution_behavior(
    resolution: str | None,
    *,
    deviation_active: bool = True,
) -> str:
    """Map a quality resolution state to control-flow behavior."""
    if resolution == "accepted_with_debt":
        return ADVANCE_WITH_DEBT
    if resolution == "fixed":
        return RERUN_REQUIRED if deviation_active else RESOLVED
    return HARD_BLOCK
