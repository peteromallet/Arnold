"""Shared resolution contract helpers for user action resolutions.

A resolution is a machine-readable record that tells the executor how to treat
a user action prerequisite: proceed with fallback instructions, confirm
satisfaction, or hard-block.  Resolutions live in a colocated
``user_action_resolutions.json`` artifact inside the plan directory.

.. note::

   This module is a **disk-source compatibility wrapper** around the canonical
   shared contract in :mod:`megaplan.resolution_contract`.  All resolution
   semantics (applicability checks, classifier decisions, recommended-action
   mapping) are delegated to the shared module with ``source="disk"``, while
   disk I/O helpers remain local to this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._core.io import atomic_write_json, read_json
from arnold.pipelines.megaplan.types import CliError

# ---------------------------------------------------------------------------
# Re-export shared constants from the canonical contract module.
# ---------------------------------------------------------------------------

from arnold.pipelines.megaplan.resolution_contract import (  # noqa: E402
    FALLBACK_STATES,
    HARD_BLOCK_STATES,
    SUPPORTED_USER_ACTION_RESOLUTION_STATES,
    resolution_applies_to_task as _shared_resolution_applies_to_task,
    resolution_recommended_action as _shared_resolution_recommended_action,
)

# ---------------------------------------------------------------------------
# File-local constants (not in shared contract)
# ---------------------------------------------------------------------------

USER_ACTION_RESOLUTIONS_FILE = "user_action_resolutions.json"


# ---------------------------------------------------------------------------
# I/O helpers (disk-specific — kept in this module)
# ---------------------------------------------------------------------------


def load_user_action_resolutions(plan_dir: Path) -> dict[str, dict[str, Any]]:
    """Load the resolutions artifact, returning {} when the file is absent.

    Raises ``CliError('invalid_user_action_resolutions', ...)`` when the file
    exists but is malformed (not a JSON object keyed by strings).
    """
    path = plan_dir / USER_ACTION_RESOLUTIONS_FILE
    if not path.exists():
        return {}

    try:
        data = read_json(path)
    except Exception as exc:
        raise CliError(
            "invalid_user_action_resolutions",
            f"Failed to parse {USER_ACTION_RESOLUTIONS_FILE}: {exc}",
        ) from exc

    if not isinstance(data, dict):
        raise CliError(
            "invalid_user_action_resolutions",
            f"{USER_ACTION_RESOLUTIONS_FILE} must be a JSON object keyed by action_id, "
            f"got {type(data).__name__}.",
        )

    for key, value in data.items():
        if not isinstance(key, str) or not key.strip():
            raise CliError(
                "invalid_user_action_resolutions",
                f"{USER_ACTION_RESOLUTIONS_FILE} keys must be non-empty strings "
                f"(action IDs).",
            )
        if not isinstance(value, dict):
            raise CliError(
                "invalid_user_action_resolutions",
                f"Resolution for action '{key}' must be a JSON object.",
            )
        state = value.get("state")
        if (
            not isinstance(state, str)
            or state not in SUPPORTED_USER_ACTION_RESOLUTION_STATES
        ):
            raise CliError(
                "invalid_user_action_resolutions",
                f"Resolution for action '{key}' has invalid or missing state "
                f"'{state!r}'. Must be one of: "
                f"{', '.join(sorted(SUPPORTED_USER_ACTION_RESOLUTION_STATES))}.",
            )

    return data


def save_user_action_resolutions(
    plan_dir: Path,
    resolutions: dict[str, dict[str, Any]],
) -> None:
    """Atomically write the full resolutions dict to the plan directory."""
    path = plan_dir / USER_ACTION_RESOLUTIONS_FILE
    atomic_write_json(path, resolutions)


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def upsert_user_action_resolution(
    plan_dir: Path,
    action_id: str,
    state: str,
    reason: str = "",
    *,
    fallback_mode: str = "",
    applies_to_task_ids: list[str] | None = None,
    instructions: str = "",
    created_by: str = "",
) -> dict[str, dict[str, Any]]:
    """Create or update the resolution for *action_id* and persist.

    Parameters
    ----------
    plan_dir:
        Plan directory containing (or that will receive) the resolutions file.
    action_id:
        Must match an existing user_action id in ``finalize.json`` (caller
        responsibility — this helper only validates the resolution shape).
    state:
        One of ``SUPPORTED_USER_ACTION_RESOLUTION_STATES``.
    reason:
        Human-readable explanation for the resolution choice.
    fallback_mode:
        Describes *how* the executor should proceed when the state is
        ``accepted_blocked`` or ``waived`` (e.g. "skip", "mock", "use_dummy").
    applies_to_task_ids:
        Task IDs that this resolution covers.  An empty or ``None`` list means
        the resolution applies to *all* tasks blocked by this action.
    instructions:
        Concrete fallback instructions the executor should follow.
    created_by:
        Actor identifier (defaults to ``"cli"`` at the CLI layer; passed
        through directly here).

    Returns the full updated resolutions dict after writing to disk.
    """
    if state not in SUPPORTED_USER_ACTION_RESOLUTION_STATES:
        raise CliError(
            "invalid_user_action_resolutions",
            f"Unsupported resolution state {state!r}. "
            f"Must be one of: {', '.join(sorted(SUPPORTED_USER_ACTION_RESOLUTION_STATES))}.",
        )

    existing = load_user_action_resolutions(plan_dir)

    # Start with the prior entry (if any) so fields not explicitly provided
    # are preserved across upserts.
    existing_entry = existing.get(action_id)
    prior: dict[str, Any] = (
        dict(existing_entry) if isinstance(existing_entry, dict) else {}
    )

    # Preserve the original created_at if this is an update.
    created_at: str
    if isinstance(prior.get("created_at"), str):
        created_at = prior["created_at"]
    else:
        created_at = datetime.now(timezone.utc).isoformat()

    resolution: dict[str, Any] = {
        "action_id": action_id,
        "state": state,
        # Merge: use new values when truthy, otherwise fall back to prior.
        "reason": reason or prior.get("reason", ""),
        "fallback_mode": fallback_mode or prior.get("fallback_mode", ""),
        "applies_to_task_ids": (
            list(applies_to_task_ids)
            if applies_to_task_ids is not None
            else prior.get("applies_to_task_ids", [])
        ),
        "instructions": instructions or prior.get("instructions", ""),
        "created_at": created_at,
        "created_by": created_by or prior.get("created_by", "") or "cli",
    }

    existing[action_id] = resolution
    save_user_action_resolutions(plan_dir, existing)
    return existing


# ---------------------------------------------------------------------------
# Query helpers — thin wrappers around the shared contract
# ---------------------------------------------------------------------------


def resolution_applies_to_task(
    resolution: dict[str, Any] | None,
    task_id: str,
) -> bool:
    """Return ``True`` if *resolution* covers *task_id*.

    A resolution applies when its ``applies_to_task_ids`` list is empty
    (meaning all tasks) or contains *task_id*.

    Delegates to :func:`megaplan.resolution_contract.resolution_applies_to_task`
    with ``source="disk"``.
    """
    return _shared_resolution_applies_to_task(resolution, task_id, source="disk")


def resolution_recommended_action(
    resolution: dict[str, Any] | None,
) -> str:
    """Return the per-resolution recommended action string.

    Returns one of:

    * ``"continue_with_fallback"`` — state is ``accepted_blocked`` or ``waived``
    * ``"retry_execute"`` — state is ``satisfied``
    * ``"awaiting_human"`` — state is ``manual_required`` or no resolution exists
    * ``"cannot_continue"`` — state is ``rejected``

    Delegates to :func:`megaplan.resolution_contract.resolution_recommended_action`
    with ``source="disk"``.
    """
    return _shared_resolution_recommended_action(resolution, source="disk")
