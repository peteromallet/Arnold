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

M9 (T15): Canonical projection rows consumed for liveness/repair routing.
Reads remain observer-pure — no mutation of progress, activity, lifecycle,
delivery, or repair evidence.  Typed drift is emitted for stale markers,
lagged projections, or cursor mismatches via :func:`evaluate_watchdog_liveness`
and :func:`emit_projection_drift`.

M7 shadow validation is wired into both ``check_watchdog_dispatch_acceptance_gate``
and ``assess_watchdog_accepted_progress`` so watchdog subprocess launch and
escalation paths diagnose stale authority before acting.  Production enforcement
is always disabled.
"""

from __future__ import annotations

import hashlib as _hashlib
import time as _time
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
from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorDimension,
    SourceCursorState,
    SourceCursorVector,
)
from arnold_pipelines.megaplan.freshness_policy import (
    FreshnessStatus,
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
    "ProjectionDrift",
    "WatchdogLiveness",
    "WATCHDOG_LIVENESS_LIVE",
    "WATCHDOG_LIVENESS_STALE",
    "WATCHDOG_LIVENESS_DEAD",
    "WATCHDOG_LIVENESS_UNKNOWN",
    "WATCHDOG_LIVENESS_LAGGED",
    "assess_watchdog_accepted_progress",
    "build_audit_input",
    "check_watchdog_dispatch_acceptance_gate",
    "check_wrapper_acceptance_gate",
    "evaluate_watchdog_liveness",
    "emit_projection_drift",
    "_shadow_validate_watchdog_boundary",
]

# ── typed blocker kinds for watchdog dispatch paths ─────────────────────

WATCHDOG_DISPATCH_BLOCKER_KIND = "watchdog_dispatch_acceptance_gate_closed"
REPAIR_DISPATCH_BLOCKER_KIND = "repair_dispatch_acceptance_gate_closed"


# ── M9 liveness and drift types ─────────────────────────────────────────────


class WatchdogLiveness:
    """Typed liveness classification derived from canonical projection rows.

    Reads are observer-pure: this classification is computed from projection
    metadata and never mutates progress, activity, lifecycle, or repair state.
    """

    __slots__ = ("state", "reason", "evidence_id", "source_cursor_dimensions")

    def __init__(
        self,
        state: str,
        reason: str = "",
        evidence_id: str = "",
        source_cursor_dimensions: tuple[str, ...] = (),
    ) -> None:
        self.state = state
        self.reason = reason
        self.evidence_id = evidence_id or self._compute_evidence_id()
        self.source_cursor_dimensions = source_cursor_dimensions

    def _compute_evidence_id(self) -> str:
        raw = f"watchdog_liveness\x00{self.state}\x00{self.reason}"
        return "sha256:" + _hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "evidence_id": self.evidence_id,
            "source_cursor_dimensions": list(self.source_cursor_dimensions),
            "_non_authoritative": True,
        }


# ── M9 liveness state constants ──────────────────────────────────────────

WATCHDOG_LIVENESS_LIVE = "live"
WATCHDOG_LIVENESS_STALE = "stale"
WATCHDOG_LIVENESS_DEAD = "dead"
WATCHDOG_LIVENESS_UNKNOWN = "unknown"
WATCHDOG_LIVENESS_LAGGED = "lagged"

_WATCHDOG_LIVENESS_STATES: frozenset[str] = frozenset(
    (WATCHDOG_LIVENESS_LIVE, WATCHDOG_LIVENESS_STALE, WATCHDOG_LIVENESS_DEAD,
     WATCHDOG_LIVENESS_UNKNOWN, WATCHDOG_LIVENESS_LAGGED)
)


class ProjectionDrift:
    """Typed drift evidence between a projection's cursor and current source.

    Emitted when a projection's source_cursor shows stale dimensions,
    lagged projections, or cursor mismatches relative to fresh reads.
    Never mutates progress — observer-pure diagnostic only.
    """

    __slots__ = ("kind", "dimension", "projection_state", "current_state",
                 "detail", "evidence_id")

    def __init__(
        self,
        kind: str,
        dimension: str = "",
        projection_state: str = "",
        current_state: str = "",
        detail: str = "",
        evidence_id: str = "",
    ) -> None:
        self.kind = kind
        self.dimension = dimension
        self.projection_state = projection_state
        self.current_state = current_state
        self.detail = detail
        self.evidence_id = evidence_id or self._compute_evidence_id()

    def _compute_evidence_id(self) -> str:
        raw = (
            f"projection_drift\x00{self.kind}\x00{self.dimension}\x00"
            f"{self.projection_state}\x00{self.current_state}\x00{self.detail}"
        )
        return "sha256:" + _hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "dimension": self.dimension,
            "projection_state": self.projection_state,
            "current_state": self.current_state,
            "detail": self.detail,
            "evidence_id": self.evidence_id,
            "_non_authoritative": True,
        }


# ── M9: evaluate watchdog liveness from canonical projection rows ──────────


def evaluate_watchdog_liveness(
    snapshot_entry: Mapping[str, Any] | None,
    *,
    observed_at_epoch_ms: float | None = None,
) -> WatchdogLiveness:
    """Evaluate watchdog liveness from canonical projection rows (observer-pure).

    Consumes the source_cursor metadata from the snapshot entry to classify
    liveness.  Reads are strictly observer-pure: this function does NOT
    mutate progress, activity, lifecycle, or repair evidence.  It returns
    typed liveness with evidence IDs for downstream routing.

    Parameters
    ----------
    snapshot_entry:
        A session entry from the cloud-status snapshot carrying source_cursor
        metadata (produced by status_snapshot with M9 enrichment).
    observed_at_epoch_ms:
        Current observation timestamp for freshness evaluation.  Defaults to
        ``time.time() * 1000``.

    Returns
    -------
    WatchdogLiveness
        Typed liveness with state, reason, evidence_id, and the source-cursor
        dimensions that contributed to the classification.
    """
    if observed_at_epoch_ms is None:
        observed_at_epoch_ms = _time.time() * 1000

    if not isinstance(snapshot_entry, Mapping) or not snapshot_entry:
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_UNKNOWN,
            reason="no snapshot entry available",
            source_cursor_dimensions=(),
        )

    source_cursor = snapshot_entry.get("source_cursor")
    if not isinstance(source_cursor, Mapping):
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_UNKNOWN,
            reason="snapshot entry missing source_cursor metadata",
            source_cursor_dimensions=(),
        )

    cursors = source_cursor.get("cursors")
    if not isinstance(cursors, (list, tuple)):
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_UNKNOWN,
            reason="source_cursor has no cursors array",
            source_cursor_dimensions=(),
        )

    # ── Build dimension index ──────────────────────────────────────────
    cursor_map: dict[str, dict[str, Any]] = {}
    observed_dimensions: list[str] = []
    for c in cursors:
        if not isinstance(c, Mapping):
            continue
        dim = c.get("dimension")
        if isinstance(dim, str):
            cursor_map[dim] = dict(c)
            observed_dimensions.append(dim)

    # ── Evaluate freshness per dimension ───────────────────────────────
    stale_dimensions: list[str] = []
    unknown_dimensions: list[str] = []
    fresh_dimensions: list[str] = []

    for dim_name in ("lifecycle", "process_correlation"):
        entry = cursor_map.get(dim_name)
        if entry is None:
            unknown_dimensions.append(dim_name)
            continue
        state = entry.get("state", "")
        if state == "fresh":
            fresh_dimensions.append(dim_name)
        elif state == "stale":
            stale_dimensions.append(dim_name)
        elif state == "unknown":
            unknown_dimensions.append(dim_name)
        else:
            unknown_dimensions.append(dim_name)

    # ── Check for stale banner or degraded snapshot ────────────────────
    stale_banner = snapshot_entry.get("stale_banner")
    if isinstance(stale_banner, str) and stale_banner.strip():
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_STALE,
            reason=f"snapshot carries stale_banner: {stale_banner[:120]}",
            source_cursor_dimensions=tuple(observed_dimensions),
        )

    # ── Check process/tmux liveness signals ────────────────────────────
    process_alive = snapshot_entry.get("process")
    tmux_alive = snapshot_entry.get("tmux")
    repairing = snapshot_entry.get("repairing")
    status = str(snapshot_entry.get("status") or "").casefold()

    if process_alive is True or tmux_alive is True:
        if stale_dimensions and not fresh_dimensions:
            return WatchdogLiveness(
                WATCHDOG_LIVENESS_LAGGED,
                reason="process/tmux alive but all source-cursor dimensions are stale",
                source_cursor_dimensions=tuple(observed_dimensions),
            )
        if stale_dimensions:
            return WatchdogLiveness(
                WATCHDOG_LIVENESS_LIVE,
                reason=f"process/tmux alive with {len(stale_dimensions)} stale dimension(s): {', '.join(stale_dimensions)}",
                source_cursor_dimensions=tuple(observed_dimensions),
            )
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_LIVE,
            reason="process/tmux alive with fresh source-cursor dimensions",
            source_cursor_dimensions=tuple(observed_dimensions),
        )

    if repairing is True or status == "repairing":
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_LIVE,
            reason="repair activity observed",
            source_cursor_dimensions=tuple(observed_dimensions),
        )

    if status in ("complete", "completed", "finished", "success", "succeeded"):
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_DEAD,
            reason=f"chain is terminal: {status}",
            source_cursor_dimensions=tuple(observed_dimensions),
        )

    if unknown_dimensions and not fresh_dimensions and not stale_dimensions:
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_UNKNOWN,
            reason=f"all source-cursor dimensions unknown: {', '.join(unknown_dimensions)}",
            source_cursor_dimensions=tuple(observed_dimensions),
        )

    if stale_dimensions and not fresh_dimensions:
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_STALE,
            reason=f"all source-cursor dimensions stale: {', '.join(stale_dimensions)}",
            source_cursor_dimensions=tuple(observed_dimensions),
        )

    if not fresh_dimensions and not stale_dimensions and not unknown_dimensions:
        return WatchdogLiveness(
            WATCHDOG_LIVENESS_UNKNOWN,
            reason="no source-cursor dimensions with recognizable state",
            source_cursor_dimensions=(),
        )

    return WatchdogLiveness(
        WATCHDOG_LIVENESS_LIVE,
        reason="source-cursor dimensions indicate live projection",
        source_cursor_dimensions=tuple(observed_dimensions),
    )


# ── M9: emit typed projection drift ────────────────────────────────────────


def emit_projection_drift(
    snapshot_entry: Mapping[str, Any] | None,
    *,
    observed_at_epoch_ms: float | None = None,
) -> list[ProjectionDrift]:
    """Emit typed drift for stale markers, lagged projections, or cursor mismatches.

    This is a pure observer read: it diagnoses drift between the projection's
    source_cursor and the current observation without mutating any state.
    Returns a list of ``ProjectionDrift`` entries, one per dimension that
    shows staleness, lag, or mismatch.

    Parameters
    ----------
    snapshot_entry:
        A session entry from the cloud-status snapshot.
    observed_at_epoch_ms:
        Current observation timestamp.

    Returns
    -------
    list[ProjectionDrift]
        Typed drift entries (empty list when no drift is detected).
    """
    if observed_at_epoch_ms is None:
        observed_at_epoch_ms = _time.time() * 1000

    if not isinstance(snapshot_entry, Mapping) or not snapshot_entry:
        return [ProjectionDrift(
            kind="missing_entry",
            detail="no snapshot entry to evaluate drift",
        )]

    source_cursor = snapshot_entry.get("source_cursor")
    if not isinstance(source_cursor, Mapping):
        return [ProjectionDrift(
            kind="missing_source_cursor",
            detail="snapshot entry has no source_cursor metadata",
        )]

    cursors = source_cursor.get("cursors")
    if not isinstance(cursors, (list, tuple)):
        return [ProjectionDrift(
            kind="missing_cursors",
            detail="source_cursor has no cursors array",
        )]

    drift_entries: list[ProjectionDrift] = []

    # ── Check stale banner ─────────────────────────────────────────────
    stale_banner = snapshot_entry.get("stale_banner")
    if isinstance(stale_banner, str) and stale_banner.strip():
        drift_entries.append(ProjectionDrift(
            kind="stale_banner",
            detail=f"snapshot carries stale_banner: {stale_banner[:120]}",
        ))

    # ── Check per-dimension staleness ──────────────────────────────────
    for c in cursors:
        if not isinstance(c, Mapping):
            continue
        dim = c.get("dimension")
        state = c.get("state", "")
        if state == "stale":
            drift_entries.append(ProjectionDrift(
                kind="stale_dimension",
                dimension=str(dim),
                projection_state=state,
                detail=str(c.get("detail", f"dimension {dim} is stale")),
            ))
        elif state == "unknown":
            drift_entries.append(ProjectionDrift(
                kind="unknown_dimension",
                dimension=str(dim),
                projection_state=state,
                detail=str(c.get("detail", f"dimension {dim} is unknown")),
            ))
        elif state == "incoherent":
            drift_entries.append(ProjectionDrift(
                kind="incoherent_dimension",
                dimension=str(dim),
                projection_state=state,
                detail=str(c.get("detail", f"dimension {dim} is incoherent")),
            ))

    # ── Check for lagged projection (no recent observation timestamp) ──
    generated_at = snapshot_entry.get("generated_at") or snapshot_entry.get("watchdog_generated_at")
    if isinstance(generated_at, str):
        try:
            from datetime import datetime
            gen_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            gen_ms = gen_dt.timestamp() * 1000
            age_ms = observed_at_epoch_ms - gen_ms
            if age_ms > 300_000:  # 5 minutes
                drift_entries.append(ProjectionDrift(
                    kind="lagged_projection",
                    detail=f"projection generated {age_ms / 1000:.0f}s ago",
                ))
        except (ValueError, TypeError):
            pass

    return drift_entries


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
        m9_liveness = evaluate_watchdog_liveness(snapshot_entry)
        m9_drift = emit_projection_drift(snapshot_entry)
        return {
            "activity_classification": ACTIVITY_CLASSIFICATION_NOT_APPLICABLE,
            "escalate": False,
            "escalation_reason": "",
            "accepted_progress": None,
            "acceptance_state": "not_applicable",
            "fixer_infrastructure_active": False,
            "automatic_continuation_custody": False,
            "m7_shadow_validation": m7_shadow,
            "m9_liveness": m9_liveness.to_dict(),
            "m9_drift": [d.to_dict() for d in m9_drift],
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

    # ── M9: liveness evaluation from canonical projection rows ─────────────
    m9_liveness = evaluate_watchdog_liveness(snapshot_entry)

    # ── M9: typed projection drift ────────────────────────────────────────
    m9_drift = emit_projection_drift(snapshot_entry)
    m9_drift_dicts = [d.to_dict() for d in m9_drift]

    return {
        "activity_classification": activity_classification,
        "escalate": escalate,
        "escalation_reason": escalation_reason,
        "accepted_progress": dict(accepted_progress),
        "acceptance_state": acceptance_state,
        "fixer_infrastructure_active": fixer_infra_active,
        "automatic_continuation_custody": auto_continuation,
        "m7_shadow_validation": m7_shadow,
        # ── M9: observer-pure liveness + drift from canonical projection rows ──
        "m9_liveness": m9_liveness.to_dict(),
        "m9_drift": m9_drift_dicts,
    }
