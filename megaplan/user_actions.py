"""Resolution model for finalized user-action prerequisites."""

from __future__ import annotations

from typing import Any

SATISFIED = "satisfied"
ACCEPTED_BLOCKED = "accepted_blocked"
WAIVED = "waived"
MANUAL_REQUIRED = "manual_required"
REJECTED = "rejected"

_VALID_RESOLUTIONS: frozenset[str] = frozenset(
    [SATISFIED, ACCEPTED_BLOCKED, WAIVED, MANUAL_REQUIRED, REJECTED]
)
VALID_RESOLUTIONS: tuple[str, ...] = tuple(sorted(_VALID_RESOLUTIONS))

OMIT = "omit"
FALLBACK = "fallback"
HARD_BLOCK = "hard_block"
UNRESOLVED = "unresolved"


def _event_sort_key(event: dict[str, Any]) -> str:
    timestamp = event.get("timestamp") or event.get("created_at") or ""
    if isinstance(timestamp, str):
        return timestamp
    return str(timestamp)


def classify_resolution_behavior(resolution: str | None) -> str:
    """Map a prerequisite resolution state to execute-time behavior."""
    if resolution == SATISFIED:
        return OMIT
    if resolution in {ACCEPTED_BLOCKED, WAIVED}:
        return FALLBACK
    return HARD_BLOCK


def effective_resolutions(
    resolution_events: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, dict[str, Any]]:
    """Return the latest resolution event for each action ID."""
    if not resolution_events:
        return {}
    latest: dict[str, dict[str, Any]] = {}
    sorted_events = sorted(
        (event for event in resolution_events if isinstance(event, dict)),
        key=_event_sort_key,
    )
    for event in sorted_events:
        action_id = event.get("action_id")
        resolution = event.get("resolution")
        if (
            isinstance(action_id, str)
            and action_id.strip()
            and isinstance(resolution, str)
            and resolution in _VALID_RESOLUTIONS
        ):
            latest[action_id] = event
    return latest


def resolution_applies_to_task(
    resolution_event: dict[str, Any] | None,
    task_id: str | None,
) -> bool:
    """Return whether a resolution event applies to ``task_id``.

    Missing ``applies_to_tasks`` means the operator resolved the action for all
    tasks. An explicit empty list means none. Malformed scopes are ignored
    defensively.
    """
    if not isinstance(resolution_event, dict):
        return False
    applies_to_tasks = resolution_event.get("applies_to_tasks")
    if applies_to_tasks is None:
        return True
    if not isinstance(applies_to_tasks, list):
        return False
    if task_id is None:
        return True
    return task_id in {
        item for item in applies_to_tasks if isinstance(item, str) and item
    }


def action_resolution_status(
    action: dict[str, Any],
    effective: dict[str, dict[str, Any]],
    task_id: str | None = None,
) -> dict[str, Any]:
    """Return the resolution status payload for one finalized user action."""
    action_id = action.get("id") if isinstance(action, dict) else None
    if not isinstance(action_id, str) or not action_id.strip():
        return {
            "resolution": UNRESOLVED,
            "behavior": HARD_BLOCK,
            "event": None,
            "is_resolved": False,
        }
    event = effective.get(action_id)
    if event is not None and not resolution_applies_to_task(event, task_id):
        event = None
    resolution = event.get("resolution") if isinstance(event, dict) else None
    if not isinstance(resolution, str) or resolution not in _VALID_RESOLUTIONS:
        resolution = UNRESOLVED
    behavior = classify_resolution_behavior(resolution)
    return {
        "resolution": resolution,
        "behavior": behavior,
        "event": event,
        "is_resolved": resolution != UNRESOLVED,
    }


def validate_resolution_event(event: dict[str, Any]) -> None:
    """Validate one user-action resolution event."""
    from megaplan.types import CliError

    if not isinstance(event, dict):
        raise CliError("invalid_args", "user action resolution event must be an object")
    action_id = event.get("action_id")
    if not isinstance(action_id, str) or not action_id.strip():
        raise CliError("invalid_args", "user action resolution requires action_id")
    resolution = event.get("resolution")
    if not isinstance(resolution, str) or resolution not in _VALID_RESOLUTIONS:
        raise CliError(
            "invalid_args",
            f"user action resolution must be one of: {', '.join(VALID_RESOLUTIONS)}",
        )
    applies_to_tasks = event.get("applies_to_tasks")
    if applies_to_tasks is not None and (
        not isinstance(applies_to_tasks, list)
        or not all(isinstance(item, str) and item.strip() for item in applies_to_tasks)
    ):
        raise CliError(
            "invalid_args",
            "user action applies_to_tasks must be a list of non-empty strings",
        )
    evidence = event.get("evidence", [])
    if evidence is not None and (
        not isinstance(evidence, list)
        or not all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        raise CliError(
            "invalid_args",
            "user action evidence must be a list of non-empty strings",
        )


def build_resolution_event(
    *,
    action_id: str,
    resolution: str,
    fallback_mode: str | None = None,
    tasks: list[str] | tuple[str, ...] | None = None,
    instructions: str | None = None,
    reason: str | None = None,
    phase: str | None = None,
    evidence: list[str] | tuple[str, ...] | None = None,
    debt_note: str | None = None,
    created_by: str = "operator",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a validated append-only resolution event for ``state.meta``."""
    from megaplan._core.io import now_utc

    ts = timestamp or now_utc()
    event: dict[str, Any] = {
        "action_id": action_id,
        "resolution": resolution,
        "timestamp": ts,
        "created_at": ts,
        "created_by": created_by,
    }
    if fallback_mode is not None:
        event["fallback_mode"] = fallback_mode
    if tasks is not None:
        event["applies_to_tasks"] = list(tasks)
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

    validate_resolution_event(event)
    return event
