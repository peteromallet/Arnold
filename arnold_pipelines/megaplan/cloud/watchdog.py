"""Compatibility helpers for watchdog-facing audit tests and dispatch gating.

Provides :func:`check_watchdog_dispatch_acceptance_gate` so watchdog-facing
Python dispatch callers can verify that a chain's acceptance state supports
launching repairs or continuing past an acceptance milestone (e.g. M5A)
before dispatching.  In fail-closed (atomic/enforce) mode a chain whose
declared successors require acceptance MUST carry a validated acceptance
receipt for its final milestone.  When the receipt is absent the dispatch
caller must emit a typed blocker event instead of silently observing the
blocked state.
"""

from __future__ import annotations

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

__all__ = [
    "BLOCKER_KIND_BY_CALLER",
    "CALLER_KINDS",
    "build_audit_input",
    "check_watchdog_dispatch_acceptance_gate",
    "check_wrapper_acceptance_gate",
]

# ── typed blocker kinds for watchdog dispatch paths ─────────────────────

WATCHDOG_DISPATCH_BLOCKER_KIND = "watchdog_dispatch_acceptance_gate_closed"
REPAIR_DISPATCH_BLOCKER_KIND = "repair_dispatch_acceptance_gate_closed"


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

    return result
