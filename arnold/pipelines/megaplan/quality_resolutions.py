"""Resolution model for ``quality_gate_resolutions``.

Durable, append-only events stored in ``state.json`` under
``meta.quality_gate_resolutions`` let operators explicitly accept a quality
gate finding as debt, mark it fixed for rerun verification, or keep it
terminal.

Quality-specific domain constants and ``accepted_with_debt`` validation
remain local. Non-domain-specific plumbing (event sorting, latest-event
aggregation, base event building, optional-field validation, behavior
classification, shared string constants) delegates to
``megaplan.resolution_contract``.
"""

from __future__ import annotations

from typing import Any

from arnold.pipelines.megaplan.resolution_contract import (
    ADVANCE_WITH_DEBT,
    HARD_BLOCK,
    RERUN_REQUIRED,
    RESOLVED,
    build_base_resolution_event,
    classify_quality_resolution_behavior,
    latest_events_by_key,
    validate_optional_string_field,
    validate_optional_string_list,
)

# -- quality-specific state constants (distinct from user-action domain) -----

ACCEPTED_WITH_DEBT = "accepted_with_debt"
FIXED = "fixed"
MANUAL_REQUIRED = "manual_required"
REJECTED = "rejected"

_VALID_RESOLUTIONS: frozenset[str] = frozenset(
    [ACCEPTED_WITH_DEBT, FIXED, MANUAL_REQUIRED, REJECTED]
)
VALID_RESOLUTIONS: tuple[str, ...] = tuple(sorted(_VALID_RESOLUTIONS))

# -- re-export shared symbols so existing callers keep working --------------

__all__ = [
    "ACCEPTED_WITH_DEBT",
    "ADVANCE_WITH_DEBT",
    "FIXED",
    "HARD_BLOCK",
    "MANUAL_REQUIRED",
    "REJECTED",
    "RERUN_REQUIRED",
    "RESOLVED",
    "VALID_RESOLUTIONS",
    "build_quality_resolution_event",
    "classify_quality_resolution_behavior",
    "is_non_terminal_quality_resolution",
    "latest_quality_resolutions",
    "validate_quality_resolution_event",
]


# -- validation -------------------------------------------------------------


def validate_quality_resolution_event(event: dict[str, Any]) -> None:
    """Validate one quality-gate resolution event.

    ``accepted_with_debt`` requires enough context to record durable debt:
    phase, at least one evidence item, and a debt note.
    """
    from arnold.pipelines.megaplan.types import CliError

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

    # -- shared optional-field helpers for simple type/emptiness checks -----
    validate_optional_string_field(
        event, "phase",
        error_message="quality resolution phase must be non-empty",
    )
    validate_optional_string_list(
        event, "evidence",
        error_message="quality resolution evidence must be a list of non-empty strings",
    )
    validate_optional_string_field(
        event, "debt_note",
        error_message="quality resolution debt_note must be non-empty",
    )
    validate_optional_string_field(
        event, "fallback_mode",
        error_message="quality resolution fallback_mode must be non-empty",
    )

    # -- quality-specific debt-acceptance requirements (keep here) ----------
    if resolution == ACCEPTED_WITH_DEBT:
        phase = event.get("phase")
        if not isinstance(phase, str) or not phase.strip():
            raise CliError(
                "invalid_args",
                "accepted_with_debt quality resolution requires phase",
            )
        evidence = event.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise CliError(
                "invalid_args",
                "accepted_with_debt quality resolution requires evidence",
            )
        debt_note = event.get("debt_note")
        if not isinstance(debt_note, str) or not debt_note.strip():
            raise CliError(
                "invalid_args",
                "accepted_with_debt quality resolution requires debt_note",
            )


# -- builders ---------------------------------------------------------------


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
    event = build_base_resolution_event(
        id_field="blocker_id",
        id_value=blocker_id,
        resolution=resolution,
        created_by=created_by,
        timestamp=timestamp,
        fallback_mode=fallback_mode,
        phase=phase,
        evidence=evidence,
        debt_note=debt_note,
    )

    validate_quality_resolution_event(event)
    return event


# -- latest-event aggregation -----------------------------------------------


def latest_quality_resolutions(
    resolution_events: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Return the latest well-formed-looking event for each blocker ID."""
    return latest_events_by_key(
        resolution_events,
        key_field="blocker_id",
    )


# -- behavior classification ------------------------------------------------


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
