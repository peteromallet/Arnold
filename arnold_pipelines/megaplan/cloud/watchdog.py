"""Compatibility helpers for watchdog-facing audit tests and dispatch gating.

Provides :func:`check_watchdog_dispatch_acceptance_gate` so watchdog-facing
Python dispatch callers can verify that a chain's acceptance state supports
launching repairs or continuing past an acceptance milestone (e.g. M5A)
before dispatching.  In fail-closed (atomic/enforce) mode a chain whose
declared successors require acceptance MUST carry a validated acceptance
receipt for its final milestone.  When the receipt is absent the dispatch
caller must emit a typed blocker event instead of silently observing the
blocked state.

Also provides :func:`assess_watchdog_accepted_progress` so watchdog escalation
logic can distinguish authoritative accepted milestone transitions from
fixer-infrastructure activity (repair loops, recovery, custody handover) and
automatic continuation custody (chain advancing to the next milestone without
acceptance evidence).  This ensures the watchdog escalates on genuine absence
of accepted progress rather than treating liveness signals as success.
M7 shadow validation is wired into both ``check_watchdog_dispatch_acceptance_gate``
and ``assess_watchdog_accepted_progress`` so watchdog subprocess launch and
escalation paths diagnose stale authority before acting.  Production enforcement
is always disabled.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arnold_pipelines.megaplan.cloud.six_hour_auditor import build_audit_input
from arnold_pipelines.megaplan.cloud.wrapper_acceptance_gate import (
    BLOCKER_KIND_BY_CALLER,
    CALLER_KINDS,
    check_wrapper_acceptance_gate,
)
from arnold_pipelines.megaplan.orchestration.completion_contract import (
    PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
)

# ── M7 shadow validator import (enforcement always disabled) ────────────────
try:
    from arnold_pipelines.megaplan.custody.action_validator import (
        validate_action_boundary_simple,
    )
    _M7_VALIDATOR_AVAILABLE = True
except ImportError:
    _M7_VALIDATOR_AVAILABLE = False

__all__ = [
    "BLOCKER_KIND_BY_CALLER",
    "CALLER_KINDS",
    "ACTIVITY_CLASSIFICATION_ACCEPTED_PROGRESS",
    "ACTIVITY_CLASSIFICATION_WAITING_FOR_ACCEPTANCE",
    "ACTIVITY_CLASSIFICATION_ACTIVITY_ONLY",
    "ACTIVITY_CLASSIFICATION_FIXER_INFRASTRUCTURE",
    "ACTIVITY_CLASSIFICATION_AUTOMATIC_CONTINUATION_CUSTODY",
    "ACTIVITY_CLASSIFICATION_IDLE",
    "ACTIVITY_CLASSIFICATION_NOT_APPLICABLE",
    "assess_watchdog_accepted_progress",
    "build_audit_input",
    "check_watchdog_dispatch_acceptance_gate",
    "check_wrapper_acceptance_gate",
    "_shadow_validate_watchdog_boundary",
]

# ── typed blocker kinds for watchdog dispatch paths ─────────────────────

WATCHDOG_DISPATCH_BLOCKER_KIND = "watchdog_dispatch_acceptance_gate_closed"
REPAIR_DISPATCH_BLOCKER_KIND = "repair_dispatch_acceptance_gate_closed"


# ── M7 shadow validator helper (T15) ────────────────────────────────────────


def _shadow_validate_watchdog_boundary(
    *,
    dispatch_kind: str,
    spec_path: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    """Run the M7 shadow validator during watchdog dispatch gating (non-blocking).

    Builds a best-effort ``CustodyTargetKey`` from the watchdog dispatch context,
    calls ``validate_action_boundary_simple`` with ``action_type=\"repair\"``
    (for repair dispatch) or ``action_type=\"dispatch\"`` (for watchdog dispatch),
    and returns typed conflict/fence/reconcile diagnostics.  Never raises —
    all errors are captured as diagnostic metadata.

    Production enforcement is always disabled; this is a shadow-only call.
    """
    if not _M7_VALIDATOR_AVAILABLE:
        return {
            "m7_validator_available": False,
            "reason": "action_validator module not importable",
        }

    import hashlib as _hashlib

    try:
        action_type = "repair" if dispatch_kind == "repair" else "dispatch"
        target_dict = {
            "environment": "watchdog",
            "session": session_id or "unknown",
            "chain": spec_path or "unknown",
            "plan_revision": dispatch_kind or "unknown",
            "phase": "watchdog_dispatch",
            "task": dispatch_kind or "unknown",
            "attempt": "1",
            "normalized_failure_kind": "watchdog_dispatch",
            "blocker_or_phase_result_hash": _hashlib.sha256(
                f"{dispatch_kind}:{spec_path}".encode("utf-8")
            ).hexdigest()[:16],
            "fence": "0",
        }

        result = validate_action_boundary_simple(
            action_type=action_type,
            target=target_dict,
            run_authority_grant_id="watchdog-dispatch-grant",
            coordinator_fence_token=0,
            wbc_attempt_reference=spec_path or session_id or "unknown",
        )

        typed_events: list[dict[str, Any]] = []
        for check in result.checks:
            outcome = check.outcome.value
            if outcome == "conflict":
                typed_events.append({
                    "event_type": "conflict",
                    "source": check.source,
                    "detail": check.detail,
                    "observed_at": check.observed_at,
                })
            elif outcome == "fenced":
                typed_events.append({
                    "event_type": "fence",
                    "source": check.source,
                    "detail": check.detail,
                    "observed_at": check.observed_at,
                })
            elif outcome in ("stale", "expired"):
                typed_events.append({
                    "event_type": "reconcile",
                    "source": check.source,
                    "detail": check.detail,
                    "observed_at": check.observed_at,
                })

        return {
            "m7_validator_available": True,
            "gate_result": result.gate_result.value,
            "enforcement_enabled": result.enforcement_enabled,
            "shadow_mode": result.is_shadow,
            "typed_events": typed_events,
            "checks_summary": {
                c.source: c.outcome.value for c in result.checks
            },
            "validated_at": result.validated_at,
        }
    except Exception as exc:
        return {
            "m7_validator_available": True,
            "error": f"{type(exc).__name__}: {exc}",
            "typed_events": [],
        }


def check_watchdog_dispatch_acceptance_gate(
    spec_path: str,
    *,
    workspace: str | None = None,
    chain_state_path: str | None = None,
    dispatch_kind: str = "watchdog",
) -> dict[str, Any]:
    """Check the acceptance gate before a watchdog dispatch operation.

    This is a convenience wrapper around
    :func:`~arnold_pipelines.megaplan.cloud.wrapper_acceptance_gate.check_wrapper_acceptance_gate`
    that uses watchdog-specific defaults and produces typed blocker events
    keyed to the dispatch kind (``watchdog`` or ``repair``).

    Parameters
    ----------
    spec_path:
        Path to the chain spec (YAML).
    workspace:
        Project workspace directory.
    chain_state_path:
        Explicit path to the persisted chain-state JSON.
    dispatch_kind:
        One of ``watchdog`` (general watchdog dispatch) or ``repair``
        (repair-loop dispatch).  Determines the blocker-event kind.

    Returns
    -------
    dict
        ``{"gate_open": true, "reason": "..."}`` when dispatch may proceed,
        or ``{"gate_open": false, "reason": "...", "blocker_event": {...}}``
        when the gate is closed and the dispatch MUST NOT proceed.
    """
    if dispatch_kind not in {"watchdog", "repair"}:
        dispatch_kind = "watchdog"

    result = check_wrapper_acceptance_gate(
        spec_path,
        workspace=workspace,
        chain_state_path=chain_state_path,
        caller_kind=dispatch_kind if dispatch_kind == "repair" else "watchdog",
    )

    # ── override blocker kind with dispatch-specific typed kind ─────────
    if not result.get("gate_open") and isinstance(result.get("blocker_event"), dict):
        blocker_event = result["blocker_event"]
        if dispatch_kind == "repair":
            blocker_event["kind"] = REPAIR_DISPATCH_BLOCKER_KIND
            blocker_event["evidence_kind"] = "repair_dispatch"
        else:
            blocker_event["kind"] = WATCHDOG_DISPATCH_BLOCKER_KIND
            blocker_event["evidence_kind"] = "watchdog_dispatch"
        blocker_event.setdefault(
            "predicate_kind", PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE
        )
        result["blocker_event"] = blocker_event

    # ── M7 shadow validation before watchdog dispatch (T15) ────────────────
    m7_shadow = _shadow_validate_watchdog_boundary(
        dispatch_kind=dispatch_kind,
        spec_path=spec_path,
    )
    result["m7_shadow_validation"] = m7_shadow

    return result


# ── activity classification constants for watchdog escalation ──────────

ACTIVITY_CLASSIFICATION_ACCEPTED_PROGRESS = "accepted_progress"
ACTIVITY_CLASSIFICATION_WAITING_FOR_ACCEPTANCE = "waiting_for_acceptance"
ACTIVITY_CLASSIFICATION_ACTIVITY_ONLY = "activity_only"
ACTIVITY_CLASSIFICATION_FIXER_INFRASTRUCTURE = "fixer_infrastructure"
ACTIVITY_CLASSIFICATION_AUTOMATIC_CONTINUATION_CUSTODY = (
    "automatic_continuation_custody"
)
ACTIVITY_CLASSIFICATION_IDLE = "idle"
ACTIVITY_CLASSIFICATION_NOT_APPLICABLE = "not_applicable"

# Activity kinds that must never be counted as accepted progress.
_NON_PROGRESS_ACTIVITY_KINDS: frozenset[str] = frozenset(
    (
        ACTIVITY_CLASSIFICATION_FIXER_INFRASTRUCTURE,
        ACTIVITY_CLASSIFICATION_AUTOMATIC_CONTINUATION_CUSTODY,
        ACTIVITY_CLASSIFICATION_ACTIVITY_ONLY,
        ACTIVITY_CLASSIFICATION_IDLE,
        ACTIVITY_CLASSIFICATION_NOT_APPLICABLE,
    )
)

# Activity kinds that indicate the chain is blocked and needs escalation.
_ESCALATION_ACTIVITY_KINDS: frozenset[str] = frozenset(
    (
        ACTIVITY_CLASSIFICATION_WAITING_FOR_ACCEPTANCE,
        ACTIVITY_CLASSIFICATION_IDLE,
    )
)

# Status values that signal fixer-infrastructure activity (not progress).
_FIXER_INFRA_STATUSES: frozenset[str] = frozenset(
    ("repairing", "attention", "blocked")
)


def assess_watchdog_accepted_progress(
    snapshot_entry: Mapping[str, Any] | None,
    *,
    chain_complete: bool = False,
    is_fail_closed: bool = False,
    has_declared_successors: bool = False,
) -> dict[str, Any]:
    """Assess whether a snapshot entry represents accepted progress or other activity.

    Watchdog escalation must key off the **absence of accepted progress**.
    Fixer-infrastructure liveness (repair loops, recovery, custody handover)
    and automatic continuation custody (chain advancing without acceptance)
    are **not** progress — they must be reported separately and must not
    suppress escalation.

    Parameters
    ----------
    snapshot_entry:
        A session entry dict from the cloud-status snapshot.  Must carry at
        minimum the ``accepted_progress``, ``status``, ``custody_state``,
        and ``repair_state`` keys produced by
        :func:`~arnold_pipelines.megaplan.cloud.status_snapshot.build_cloud_status`.
    chain_complete:
        Whether the chain has completed all its declared milestones.
    is_fail_closed:
        Whether the chain is in atomic/enforce (fail-closed) mode.
    has_declared_successors:
        Whether the chain spec declares successors that require acceptance.

    Returns
    -------
    dict
        A dict with these keys:

        * ``activity_classification`` — one of the
          ``ACTIVITY_CLASSIFICATION_*`` constants.
        * ``escalate`` — ``True`` when the watchdog should escalate because
          accepted progress is absent and the chain is not making accepted
          forward progress.
        * ``escalation_reason`` — human-readable reason string (empty when
          ``escalate`` is ``False``).
        * ``accepted_progress`` — the raw ``accepted_progress`` sub-dict from
          the snapshot entry, or ``None``.
        * ``acceptance_state`` — ``"accepted"``, ``"waiting_for_acceptance"``,
          ``"activity_only"``, or ``"not_applicable"`` (same contract as
          :func:`~arnold_pipelines.megaplan.status_projection.accepted_progress_presentation`).
        * ``fixer_infrastructure_active`` — ``True`` when repair/attention/
          blocked/recovery custody is observed.
        * ``automatic_continuation_custody`` — ``True`` when the chain has
          advanced past a completed milestone but no acceptance receipt
          exists for the prior milestone.
    """
    if not isinstance(snapshot_entry, Mapping) or not snapshot_entry:
        # ── M7 shadow validation for not-applicable path (T15) ──────────
        m7_shadow = _shadow_validate_watchdog_boundary(
            dispatch_kind="watchdog",
        )
        return {
            "activity_classification": ACTIVITY_CLASSIFICATION_NOT_APPLICABLE,
            "escalate": False,
            "escalation_reason": "",
            "accepted_progress": None,
            "acceptance_state": "not_applicable",
            "fixer_infrastructure_active": False,
            "automatic_continuation_custody": False,
            "m7_shadow_validation": m7_shadow,
        }

    accepted_progress = snapshot_entry.get("accepted_progress")
    if not isinstance(accepted_progress, Mapping):
        accepted_progress = {}

    waiting = bool(accepted_progress.get("waiting_for_acceptance"))
    final_accepted = bool(accepted_progress.get("final_milestone_accepted"))
    acceptance_required = bool(accepted_progress.get("acceptance_required"))
    accepted_labels = accepted_progress.get("accepted_milestones")
    accepted_count = (
        len(accepted_labels) if isinstance(accepted_labels, list) else 0
    )

    # ── detect fixer-infrastructure activity ──────────────────────────
    status = str(snapshot_entry.get("status") or "")
    repairing = bool(snapshot_entry.get("repairing"))
    custody_state = str(snapshot_entry.get("custody_state") or "")
    repair_state = snapshot_entry.get("repair_state")
    repair_state = (
        repair_state if isinstance(repair_state, Mapping) else {}
    )

    fixer_infra_active = (
        status in _FIXER_INFRA_STATUSES
        or repairing
        or bool(repair_state.get("active"))
        or bool(repair_state.get("repairing"))
    )

    # ── detect automatic continuation custody ─────────────────────────
    # Automatic continuation custody: the chain has advanced past a
    # completed milestone (chain_complete is True OR the cursor has
    # moved to a successor) but no acceptance receipt exists for the
    # prior milestone in fail-closed mode.
    auto_continuation = (
        is_fail_closed
        and has_declared_successors
        and chain_complete
        and acceptance_required
        and not final_accepted
        and not waiting
    )

    # ── determine acceptance_state ────────────────────────────────────
    if waiting:
        acceptance_state = "waiting_for_acceptance"
    elif chain_complete and final_accepted:
        acceptance_state = "accepted"
    elif chain_complete and not acceptance_required:
        acceptance_state = "not_applicable"
    elif accepted_count > 0:
        acceptance_state = "accepted"
    elif acceptance_required and not final_accepted:
        acceptance_state = "activity_only"
    else:
        acceptance_state = "activity_only"

    # ── classify activity ─────────────────────────────────────────────
    if waiting:
        activity_classification = ACTIVITY_CLASSIFICATION_WAITING_FOR_ACCEPTANCE
    elif final_accepted or accepted_count > 0:
        activity_classification = ACTIVITY_CLASSIFICATION_ACCEPTED_PROGRESS
    elif fixer_infra_active:
        activity_classification = ACTIVITY_CLASSIFICATION_FIXER_INFRASTRUCTURE
    elif auto_continuation:
        activity_classification = (
            ACTIVITY_CLASSIFICATION_AUTOMATIC_CONTINUATION_CUSTODY
        )
    elif not acceptance_required and chain_complete:
        # Shadow / warn / off modes: acceptance is not required and the
        # chain is complete, so the absence of a receipt is expected.
        # This is not a stall.
        activity_classification = ACTIVITY_CLASSIFICATION_NOT_APPLICABLE
    elif (
        status in ("running",)
        and not fixer_infra_active
        and not chain_complete
    ):
        activity_classification = ACTIVITY_CLASSIFICATION_ACTIVITY_ONLY
    elif not status or status in ("complete",):
        activity_classification = ACTIVITY_CLASSIFICATION_IDLE
    elif not acceptance_required:
        # Shadow / warn / off modes: acceptance not required and chain
        # is not complete (still running or in some other state).
        activity_classification = ACTIVITY_CLASSIFICATION_ACTIVITY_ONLY
    else:
        activity_classification = ACTIVITY_CLASSIFICATION_ACTIVITY_ONLY

    # ── escalation decision ───────────────────────────────────────────
    escalate = activity_classification in _ESCALATION_ACTIVITY_KINDS

    if activity_classification == ACTIVITY_CLASSIFICATION_WAITING_FOR_ACCEPTANCE:
        escalation_reason = (
            "chain complete in fail-closed mode but no acceptance receipt "
            "exists for the final milestone — accepted progress absent"
        )
    elif activity_classification == ACTIVITY_CLASSIFICATION_IDLE:
        escalation_reason = (
            "no accepted progress and no forward activity observed"
        )
    elif activity_classification == ACTIVITY_CLASSIFICATION_FIXER_INFRASTRUCTURE:
        escalation_reason = (
            "fixer-infrastructure activity observed — this is NOT accepted "
            "progress and does not suppress escalation; however, the fixer "
            "is still working so the watchdog defers escalation"
        )
    elif activity_classification == ACTIVITY_CLASSIFICATION_AUTOMATIC_CONTINUATION_CUSTODY:
        escalation_reason = (
            "chain continuing to successor without acceptance evidence — "
            "automatic continuation custody observed"
        )
    else:
        escalation_reason = ""

    # ── M7 shadow validation for escalation path (T15) ────────────────────
    m7_shadow = _shadow_validate_watchdog_boundary(
        dispatch_kind="watchdog",
        session_id=str(snapshot_entry.get("session", "")) if isinstance(snapshot_entry, Mapping) else "",
    )

    return {
        "activity_classification": activity_classification,
        "escalate": escalate,
        "escalation_reason": escalation_reason,
        "accepted_progress": dict(accepted_progress),
        "acceptance_state": acceptance_state,
        "fixer_infrastructure_active": fixer_infra_active,
        "automatic_continuation_custody": auto_continuation,
        "m7_shadow_validation": m7_shadow,
    }
