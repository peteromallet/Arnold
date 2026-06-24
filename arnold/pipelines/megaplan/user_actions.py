"""Resolution model for finalized user-action prerequisites.

.. note::

   This module is a **memory-source compatibility wrapper** around the
   canonical shared contract in :mod:`megaplan.resolution_contract`.  All
   resolution semantics (applicability checks, event aggregation, classifier
   decisions, event builders, and validations) are delegated to the shared
   module with ``source="memory"``, while public constants are re-exported
   for backward-compatible imports.

   Fields ``phase``, ``evidence``, and ``debt_note`` are accepted as
   operator / recovery metadata on user-action events alongside the
   standard resolution fields.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Re-export shared constants from the canonical contract module.
# ---------------------------------------------------------------------------

from arnold.pipelines.megaplan.resolution_contract import (  # noqa: E402
    FALLBACK,
    HARD_BLOCK,
    OMIT,
    SUPPORTED_USER_ACTION_RESOLUTION_STATES,
    UNRESOLVED,
    build_base_resolution_event,
    classify_resolution_behavior,
    latest_events_by_key,
    resolution_applies_to_task as _shared_resolution_applies_to_task,
    resolution_state,
    validate_optional_string_list,
)

# ---------------------------------------------------------------------------
# Local aliases for string constants (preserve the original names for
# callers that import them directly from this module).
# ---------------------------------------------------------------------------

SATISFIED = "satisfied"
ACCEPTED_BLOCKED = "accepted_blocked"
WAIVED = "waived"
MANUAL_REQUIRED = "manual_required"
REJECTED = "rejected"

_VALID_RESOLUTIONS: frozenset[str] = SUPPORTED_USER_ACTION_RESOLUTION_STATES
VALID_RESOLUTIONS: tuple[str, ...] = tuple(sorted(_VALID_RESOLUTIONS))


# ---------------------------------------------------------------------------
# Shared helpers re-exported under their original names.
# ---------------------------------------------------------------------------

def effective_resolutions(
    resolution_events: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, dict[str, Any]]:
    """Return the latest resolution event for each action ID.

    Delegates to :func:`megaplan.resolution_contract.latest_events_by_key`
    with ``key_field="action_id"`` and ``valid_states`` set to
    ``SUPPORTED_USER_ACTION_RESOLUTION_STATES``, preserving the original
    behaviour.
    """
    return latest_events_by_key(
        resolution_events,
        key_field="action_id",
        state_field="resolution",
        valid_states=SUPPORTED_USER_ACTION_RESOLUTION_STATES,
    )


# ---------------------------------------------------------------------------
# Memory-source wrapper — hardcodes ``source="memory"`` for backward
# compatibility with callers that import from this module.
# ---------------------------------------------------------------------------


def resolution_applies_to_task(
    resolution_event: dict[str, Any] | None,
    task_id: str | None,
) -> bool:
    """Return whether a resolution event applies to ``task_id``.

    Missing ``applies_to_tasks`` means the operator resolved the action for
    all tasks. An explicit empty list means none. Malformed scopes are
    ignored defensively.

    Delegates to :func:`megaplan.resolution_contract.resolution_applies_to_task`
    with ``source="memory"``.
    """
    return _shared_resolution_applies_to_task(
        resolution_event, task_id, source="memory"
    )


# ---------------------------------------------------------------------------
# Action resolution status payload
# ---------------------------------------------------------------------------


def action_resolution_status(
    action: dict[str, Any],
    effective: dict[str, dict[str, Any]],
    task_id: str | None = None,
) -> dict[str, Any]:
    """Return the resolution status payload for one finalized user action.

    Uses the shared :func:`~megaplan.resolution_contract.resolution_state`
    helper for state lookup, :func:`resolution_applies_to_task` for scoping,
    and :func:`classify_resolution_behavior` for the execute-time behaviour
    label.
    """
    action_id = action.get("id") if isinstance(action, dict) else None
    if not isinstance(action_id, str) or not action_id.strip():
        return {
            "resolution": UNRESOLVED,
            "behavior": HARD_BLOCK,
            "event": None,
            "is_resolved": False,
        }
    event = effective.get(action_id)
    if event is not None and not _shared_resolution_applies_to_task(
        event, task_id, source="memory"
    ):
        event = None
    resolution = resolution_state(event, source="memory")
    if not isinstance(resolution, str) or resolution not in _VALID_RESOLUTIONS:
        resolution = UNRESOLVED
    behavior = classify_resolution_behavior(resolution)
    return {
        "resolution": resolution,
        "behavior": behavior,
        "event": event,
        "is_resolved": resolution != UNRESOLVED,
    }


# ---------------------------------------------------------------------------
# Validation — delegates shared list checks to the contract module.
# ---------------------------------------------------------------------------


def validate_resolution_event(event: dict[str, Any]) -> None:
    """Validate one user-action resolution event.

    Uses shared validators from :mod:`megaplan.resolution_contract` for
    optional string-list and string fields (``applies_to_tasks``,
    ``evidence``).
    """
    from arnold.pipelines.megaplan.types import CliError

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
    validate_optional_string_list(
        event,
        "applies_to_tasks",
        error_message="user action applies_to_tasks must be a list of non-empty strings",
    )
    validate_optional_string_list(
        event,
        "evidence",
        error_message="user action evidence must be a list of non-empty strings",
    )


# ---------------------------------------------------------------------------
# Event builder — delegates base construction to the contract module.
# ---------------------------------------------------------------------------


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
    """Build a validated append-only resolution event for ``state.meta``.

    Delegates base event construction to
    :func:`megaplan.resolution_contract.build_base_resolution_event`, then
    validates the result.  ``phase``, ``evidence``, and ``debt_note`` are
    accepted as operator / recovery metadata on the user-action event.
    """
    event = build_base_resolution_event(
        id_field="action_id",
        id_value=action_id,
        resolution=resolution,
        created_by=created_by,
        timestamp=timestamp,
        fallback_mode=fallback_mode,
        tasks_field="applies_to_tasks",
        tasks=tasks,
        instructions=instructions,
        reason=reason,
        phase=phase,
        evidence=evidence,
        debt_note=debt_note,
    )
    validate_resolution_event(event)
    return event
