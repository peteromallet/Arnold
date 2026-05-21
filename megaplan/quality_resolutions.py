"""Resolution model for ``quality_gate_resolutions``.

Durable, append-only events stored in ``state.json`` under
``meta.quality_gate_resolutions`` let operators explicitly accept a quality
gate finding as debt, mark it fixed for rerun verification, or keep it
terminal.
"""

from __future__ import annotations

from typing import Any

ACCEPTED_WITH_DEBT = "accepted_with_debt"
FIXED = "fixed"
MANUAL_REQUIRED = "manual_required"
REJECTED = "rejected"

_VALID_RESOLUTIONS: frozenset[str] = frozenset(
    [ACCEPTED_WITH_DEBT, FIXED, MANUAL_REQUIRED, REJECTED]
)
VALID_RESOLUTIONS: tuple[str, ...] = tuple(sorted(_VALID_RESOLUTIONS))

ADVANCE_WITH_DEBT = "advance_with_debt"
RERUN_REQUIRED = "rerun_required"
RESOLVED = "resolved"
HARD_BLOCK = "hard_block"


def _event_sort_key(event: dict[str, Any]) -> str:
    timestamp = event.get("timestamp") or event.get("created_at") or ""
    if isinstance(timestamp, str):
        return timestamp
    return str(timestamp)


def validate_quality_resolution_event(event: dict[str, Any]) -> None:
    """Validate one quality-gate resolution event.

    ``accepted_with_debt`` requires enough context to record durable debt:
    phase, at least one evidence item, and a debt note.
    """
    from megaplan.types import CliError

    if not isinstance(event, dict):
        raise CliError("invalid_args", "quality resolution event must be an object")

    blocker_id = event.get("blocker_id")
    if not isinstance(blocker_id, str) or not blocker_id.strip():
        raise CliError("invalid_args", "quality resolution requires blocker_id")

    resolution = event.get("resolution")
    if not isinstance(resolution, str) or resolution not in _VALID_RESOLUTIONS:
        raise CliError(
            "invalid_args",
            f"quality resolution must be one of: {', '.join(VALID_RESOLUTIONS)}",
        )

    phase = event.get("phase")
    if phase is not None and (not isinstance(phase, str) or not phase.strip()):
        raise CliError("invalid_args", "quality resolution phase must be non-empty")

    evidence = event.get("evidence", [])
    if evidence is not None and (
        not isinstance(evidence, list)
        or not all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        raise CliError(
            "invalid_args",
            "quality resolution evidence must be a list of non-empty strings",
        )

    debt_note = event.get("debt_note")
    if debt_note is not None and (
        not isinstance(debt_note, str) or not debt_note.strip()
    ):
        raise CliError("invalid_args", "quality resolution debt_note must be non-empty")
    fallback_mode = event.get("fallback_mode")
    if fallback_mode is not None and (
        not isinstance(fallback_mode, str) or not fallback_mode.strip()
    ):
        raise CliError(
            "invalid_args", "quality resolution fallback_mode must be non-empty"
        )

    if resolution == ACCEPTED_WITH_DEBT:
        if not isinstance(phase, str) or not phase.strip():
            raise CliError(
                "invalid_args",
                "accepted_with_debt quality resolution requires phase",
            )
        if not isinstance(evidence, list) or not evidence:
            raise CliError(
                "invalid_args",
                "accepted_with_debt quality resolution requires evidence",
            )
        if not isinstance(debt_note, str) or not debt_note.strip():
            raise CliError(
                "invalid_args",
                "accepted_with_debt quality resolution requires debt_note",
            )


def build_quality_resolution_event(
    *,
    blocker_id: str,
    resolution: str,
    phase: str | None = None,
    evidence: list[str] | tuple[str, ...] | None = None,
    debt_note: str | None = None,
    fallback_mode: str | None = None,
    created_by: str = "operator",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a validated quality-gate resolution event."""
    from megaplan._core.io import now_utc

    ts = timestamp or now_utc()
    event: dict[str, Any] = {
        "blocker_id": blocker_id,
        "resolution": resolution,
        "timestamp": ts,
        "created_at": ts,
        "created_by": created_by,
    }
    if phase is not None:
        event["phase"] = phase
    if evidence is not None:
        event["evidence"] = list(evidence)
    if debt_note is not None:
        event["debt_note"] = debt_note
    if fallback_mode is not None:
        event["fallback_mode"] = fallback_mode

    validate_quality_resolution_event(event)
    return event


def latest_quality_resolutions(
    resolution_events: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Return the latest well-formed-looking event for each blocker ID."""
    if not resolution_events:
        return {}
    latest: dict[str, dict[str, Any]] = {}
    sorted_events = sorted(
        (event for event in resolution_events if isinstance(event, dict)),
        key=_event_sort_key,
    )
    for event in sorted_events:
        blocker_id = event.get("blocker_id")
        if not isinstance(blocker_id, str) or not blocker_id.strip():
            continue
        latest[blocker_id] = event
    return latest


def classify_quality_resolution_behavior(
    resolution: str | None,
    *,
    deviation_active: bool = True,
) -> str:
    """Map a quality resolution to control-flow behavior.

    ``fixed`` is not advancing while the deviation is still active; the
    operator has asserted a fix, but execute/review must rerun until the
    finding disappears.
    """
    if resolution == ACCEPTED_WITH_DEBT:
        return ADVANCE_WITH_DEBT
    if resolution == FIXED:
        return RERUN_REQUIRED if deviation_active else RESOLVED
    return HARD_BLOCK


def is_non_terminal_quality_resolution(
    resolution: str | None,
    *,
    deviation_active: bool = True,
) -> bool:
    """Return whether this resolution can move the phase past a blocker."""
    return classify_quality_resolution_behavior(
        resolution,
        deviation_active=deviation_active,
    ) in {ADVANCE_WITH_DEBT, RESOLVED}
