"""Derived, user-facing Megaplan lifecycle presentation.

The persisted plan lifecycle, independent review verdict, and currently running
phase answer different questions.  In particular, ``finalized`` is the correct
durable state while an ``execute`` step consumes the finalized task document.
Consumers should retain those raw facts and use this projection for labels
shown to people.

Every projection carries source-cursor metadata, freshness evaluation, a
content-addressed digest, and an explicit ``_non_authoritative`` marker.
Projections may deny, block, diagnose, emit drift, or surface uncertainty,
but they are **never** bearer authority for dispatch, repair, retry,
completion, cancellation, publication, or delivery.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping, Optional

from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorDimension,
    SourceCursorVector,
)

# ── Precedence constants ────────────────────────────────────────────────────

_FAILED_STATES = {"failed", "aborted", "cancelled"}
_PAUSED_STATES = {"paused", "awaiting_human", "awaiting_human_verify"}
_COMPLETED_STATES = {"done", "complete", "completed"}
_BLOCKED_STATES = {"blocked", "clarifying"}

# ── Digest helpers ──────────────────────────────────────────────────────────


def _canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, no whitespace variance."""
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _projection_digest(*parts: str) -> str:
    """Content-addressed digest over null-joined canonical parts."""
    raw = "\x00".join(parts)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Projection: plan lifecycle display state ────────────────────────────────


def plan_status_presentation(
    plan_state: Any,
    *,
    active_step: Mapping[str, Any] | None = None,
    active_phase: Any = None,
    review_verdict: Any = None,
    completed: bool = False,
    # ── M9: source-cursor metadata ──
    source_cursor: SourceCursorVector | None = None,
    lifecycle_cursor: DimensionCursor | None = None,
    observed_at_epoch_ms: Optional[float] = None,
) -> dict[str, Any]:
    """Project lifecycle, review truth, and live phase into a display contract.

    Args:
        plan_state: Canonical plan lifecycle state (e.g. ``finalized``, ``done``).
        active_step: Currently executing step dict, if any.
        active_phase: Override phase (derived from active_step if None).
        review_verdict: Independent review verdict (``needs_rework``, ``approved``).
        completed: Manual override for terminal completed state.
        source_cursor: Full source-cursor vector (optional — added to output).
        lifecycle_cursor: Per-dimension cursor for the lifecycle dimension.
        observed_at_epoch_ms: Observation timestamp for freshness evaluation.

    Returns:
        Dict with display-state keys plus M9 metadata:
        ``active_phase``, ``execution_state``, ``display_state``,
        ``source_cursor`` (if provided), ``freshness``, ``projection_digest``,
        ``_non_authoritative`` (always True).
    """

    raw_state = str(plan_state or "").strip().lower()
    phase_value = active_phase
    if phase_value is None and isinstance(active_step, Mapping):
        phase_value = active_step.get("phase") or active_step.get("step")
    phase = str(phase_value or "").strip().lower() or None
    if phase == "loop_execute":
        phase = "execute"
    verdict = str(review_verdict or "").strip().lower()

    # ── Preserved precedence: completed/failed/paused/blocked > review/rework/finalized
    if completed or raw_state in _COMPLETED_STATES:
        execution_state = "completed"
        display_state = "completed" if completed else raw_state
    elif raw_state in _FAILED_STATES:
        execution_state = "failed"
        display_state = raw_state
    elif raw_state in _PAUSED_STATES:
        execution_state = "paused"
        display_state = raw_state
    elif raw_state in _BLOCKED_STATES:
        execution_state = "blocked"
        display_state = raw_state
    elif phase == "review":
        execution_state = "reviewing"
        display_state = "reviewing"
    elif phase == "execute":
        execution_state = "reworking" if verdict == "needs_rework" else "executing"
        display_state = execution_state
    elif verdict == "needs_rework":
        execution_state = "rework_required"
        display_state = "needs_rework"
    elif raw_state == "finalized":
        execution_state = "ready"
        display_state = raw_state
    else:
        execution_state = "inactive"
        display_state = raw_state or None

    # ── Core projection (backward-compatible baseline) ──
    result: dict[str, Any] = {
        "active_phase": phase,
        "execution_state": execution_state,
        "display_state": display_state,
    }

    # ── M9 metadata: only attach when caller opts in ──
    _has_m9_context = (
        source_cursor is not None
        or lifecycle_cursor is not None
        or observed_at_epoch_ms is not None
    )

    if _has_m9_context:
        result["_non_authoritative"] = True

        # ── Source-cursor metadata ──
        if source_cursor is not None:
            result["source_cursor"] = source_cursor.to_dict()

        # ── Freshness evaluation ──
        freshness: dict[str, Any] = {
            "status": "unknown",
            "observed_at_epoch_ms": observed_at_epoch_ms,
        }
        if lifecycle_cursor is not None:
            freshness["lifecycle_cursor"] = lifecycle_cursor.to_dict()
            freshness["lifecycle_state"] = lifecycle_cursor.state
        if observed_at_epoch_ms is not None:
            now_ms = time.time() * 1000
            age_ms = now_ms - observed_at_epoch_ms
            freshness["age_ms"] = age_ms
            # Default freshness window: 60s fresh, 300s stale
            if age_ms <= 60_000:
                freshness["status"] = "fresh"
            elif age_ms <= 300_000:
                freshness["status"] = "stale"
            else:
                freshness["status"] = "stale"
        result["freshness"] = freshness

        # ── Content-addressed digest ──
        digest_parts = [
            _canonical_json(
                {
                    "active_phase": phase,
                    "execution_state": execution_state,
                    "display_state": display_state,
                }
            ).decode("utf-8"),
        ]
        if source_cursor is not None:
            digest_parts.append(_canonical_json(source_cursor.to_dict()).decode("utf-8"))
        result["projection_digest"] = _projection_digest(*digest_parts)

    return result


# ── Projection: accepted-progress display ───────────────────────────────────


def accepted_progress_presentation(
    accepted_progress: Mapping[str, Any] | None,
    *,
    chain_complete: bool = False,
    # ── M9: source-cursor metadata ──
    source_cursor: SourceCursorVector | None = None,
    observed_at_epoch_ms: Optional[float] = None,
) -> dict[str, Any]:
    """Project accepted-progress snapshot data into a stable display contract.

    Consumers (watchdog, resident, human operators) use this to distinguish
    authoritative milestone transitions (backed by acceptance receipts) from
    worker activity, review, repair, custody, and fixer-infrastructure
    liveness signals.

    Args:
        accepted_progress: The accepted-progress snapshot mapping.
        chain_complete: Whether the chain is fully complete.
        source_cursor: Full source-cursor vector (optional).
        observed_at_epoch_ms: Observation timestamp for freshness evaluation.

    Returns:
        Dict with ``acceptance_state``, ``display_label``, plus M9 metadata:
        ``source_cursor``, ``freshness``, ``projection_digest``,
        ``_non_authoritative``.
    """

    if not isinstance(accepted_progress, Mapping) or not accepted_progress:
        result: dict[str, Any] = {
            "acceptance_state": "not_applicable",
            "display_label": None,
        }
        return _attach_m9_metadata(result, source_cursor, observed_at_epoch_ms)

    waiting = bool(accepted_progress.get("waiting_for_acceptance"))
    final_accepted = bool(accepted_progress.get("final_milestone_accepted"))
    acceptance_required = bool(accepted_progress.get("acceptance_required"))
    accepted_labels = accepted_progress.get("accepted_milestones")
    accepted_count = len(accepted_labels) if isinstance(accepted_labels, list) else 0

    # ── Preserved precedence ──
    if waiting:
        result = {
            "acceptance_state": "waiting_for_acceptance",
            "display_label": "chain complete — waiting for acceptance evidence",
        }
    elif chain_complete and final_accepted:
        result = {
            "acceptance_state": "accepted",
            "display_label": "chain complete — accepted",
        }
    elif chain_complete and not acceptance_required:
        result = {
            "acceptance_state": "not_applicable",
            "display_label": "chain complete — acceptance not required (shadow mode)",
        }
    elif accepted_count > 0:
        result = {
            "acceptance_state": "accepted",
            "display_label": f"{accepted_count} milestone(s) accepted",
        }
    elif acceptance_required and not final_accepted:
        result = {
            "acceptance_state": "activity_only",
            "display_label": "activity observed — no accepted milestone transitions yet",
        }
    else:
        result = {
            "acceptance_state": "activity_only",
            "display_label": "activity observed",
        }

    return _attach_m9_metadata(result, source_cursor, observed_at_epoch_ms)


# ── Shared M9 metadata attachment ──────────────────────────────────────────


def _attach_m9_metadata(
    result: dict[str, Any],
    source_cursor: SourceCursorVector | None,
    observed_at_epoch_ms: Optional[float],
) -> dict[str, Any]:
    """Attach source-cursor, freshness, and digest to a projection result.

    Only attaches metadata when at least one M9 parameter is provided.
    When no M9 context is present, returns the bare result unchanged
    (backward-compatible with pre-M9 consumers).
    """
    _has_m9_context = (
        source_cursor is not None
        or observed_at_epoch_ms is not None
    )

    if not _has_m9_context:
        return result

    result["_non_authoritative"] = True

    # Source-cursor metadata
    if source_cursor is not None:
        result["source_cursor"] = source_cursor.to_dict()

    # Freshness evaluation
    freshness: dict[str, Any] = {
        "status": "unknown",
        "observed_at_epoch_ms": observed_at_epoch_ms,
    }
    if observed_at_epoch_ms is not None:
        now_ms = time.time() * 1000
        age_ms = now_ms - observed_at_epoch_ms
        freshness["age_ms"] = age_ms
        if age_ms <= 60_000:
            freshness["status"] = "fresh"
        elif age_ms <= 300_000:
            freshness["status"] = "stale"
        else:
            freshness["status"] = "stale"
    result["freshness"] = freshness

    # Content-addressed digest (over display payload + cursor)
    display_payload = {k: v for k, v in result.items() if k not in (
        "_non_authoritative", "source_cursor", "freshness", "projection_digest",
    )}
    digest_parts = [_canonical_json(display_payload).decode("utf-8")]
    if source_cursor is not None:
        digest_parts.append(_canonical_json(source_cursor.to_dict()).decode("utf-8"))
    result["projection_digest"] = _projection_digest(*digest_parts)

    return result


__all__ = ["plan_status_presentation", "accepted_progress_presentation"]
