"""Post-action repair target custody and liveness revalidation.

Also provides acceptance-aware revalidation so that after a repair result the
prior acceptance candidate is invalidated and the acceptance boundary is forced
to use the full suite (not a focused/scoped selector).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud import repair_requests


_AUTHORITY_FIELDS = (
    "target_id",
    "plan_state.current_state",
    "plan_state.fingerprint",
    "chain_state.current_plan_name",
    "chain_state.last_state",
    "chain_state.fingerprint",
    "active_step_heartbeat.phase",
    "active_step_heartbeat.attempt",
    "active_step_heartbeat.worker_pid",
    "event_cursors.line_count",
    "event_cursors.mtime",
)


def _get(record: Mapping[str, Any], dotted: str) -> Any:
    value: Any = record
    for part in dotted.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    return value


@dataclass(frozen=True)
class TargetRevalidation:
    changed_fields: tuple[str, ...]
    superseded: bool
    runner_live: bool
    active_worker_live: bool
    progress_observed: bool
    recovery_verified: bool
    reason: str
    # ── acceptance-aware fields (T14) ────────────────────────────────
    full_boundary_required: bool = False
    acceptance_candidates_invalidated: int = 0
    acceptance_invalidation_reason: str = ""
    expected_repair_identity_key: str = ""
    observed_repair_identity_key: str = ""
    repair_receipt_quarantined: bool = False

    def as_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["changed_fields"] = list(self.changed_fields)
        return payload


def revalidate_repair_target(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    *,
    session_health: str,
) -> TargetRevalidation:
    """Compare dispatch custody with fresh evidence and classify recovery.

    A live tmux session is necessary but not sufficient.  Recovery additionally
    requires either a live active-step PID or durable plan progress since the
    dispatch snapshot.  This keeps stale activity timestamps, dead workers, and
    unrelated workspace processes from projecting a green result.
    """
    old = before if isinstance(before, Mapping) else {}
    new = after if isinstance(after, Mapping) else {}
    changed = tuple(field for field in _AUTHORITY_FIELDS if _get(old, field) != _get(new, field))

    runner = new.get("tmux_process") if isinstance(new.get("tmux_process"), Mapping) else {}
    active = (
        new.get("active_step_heartbeat")
        if isinstance(new.get("active_step_heartbeat"), Mapping)
        else {}
    )
    runner_live = session_health == "alive" and (
        runner.get("session_live") is True or runner.get("live_status") == "alive"
    )
    # Some on-box probes deliberately leave tmux truth unknown.  The watchdog's
    # own session_health result is authoritative for runner presence there.
    if session_health == "alive" and runner.get("session_live") is None:
        runner_live = True
    active_worker_live = bool(active.get("active")) and active.get("pid_live") is True
    progress_observed = any(
        field in changed
        for field in (
            "target_id",
            "plan_state.current_state",
            "plan_state.fingerprint",
            "chain_state.current_plan_name",
            "chain_state.last_state",
            "event_cursors.line_count",
            "event_cursors.mtime",
        )
    )
    verified = runner_live and (active_worker_live or progress_observed)
    superseded = bool(changed)
    if verified:
        reason = "runner live with current active worker" if active_worker_live else "runner live with durable target progress"
    elif not runner_live:
        reason = "runner is not live"
    elif active and not active_worker_live:
        reason = "runner exists but active worker is dead or unverifiable"
    else:
        reason = "runner exists without fresh target progress"
    expected_repair_identity = repair_requests.normalize_repair_identity(
        old.get("repair_identity") if isinstance(old.get("repair_identity"), Mapping) else None
    )
    observed_repair_identity = repair_requests.normalize_repair_identity(
        new.get("repair_identity") if isinstance(new.get("repair_identity"), Mapping) else None
    )
    expected_repair_identity_key = repair_requests.repair_identity_key(expected_repair_identity)
    observed_repair_identity_key = repair_requests.repair_identity_key(observed_repair_identity)
    repair_receipt_quarantined = bool(
        expected_repair_identity_key or observed_repair_identity_key
    ) and expected_repair_identity_key != observed_repair_identity_key
    if repair_receipt_quarantined:
        verified = False
        superseded = True
        reason = "repair receipt identity no longer matches the current target"
    return TargetRevalidation(
        changed_fields=changed,
        superseded=superseded,
        runner_live=runner_live,
        active_worker_live=active_worker_live,
        progress_observed=progress_observed,
        recovery_verified=verified,
        reason=reason,
        expected_repair_identity_key=expected_repair_identity_key,
        observed_repair_identity_key=observed_repair_identity_key,
        repair_receipt_quarantined=repair_receipt_quarantined,
    )


# ──────────────────────────────────────────────────────────────────────
# T14 — acceptance-aware revalidation
# ──────────────────────────────────────────────────────────────────────


def invalidate_acceptance_candidates_after_repair(
    plan_dir: str | Path,
    *,
    milestone_label: str = "",
    repair_reason: str = "",
) -> tuple[int, str]:
    """Invalidate any uncommitted acceptance candidates after a repair.

    After a repair result, every prior uncommitted acceptance candidate is
    stale — the evidence changed, so the old candidate cannot be reused.
    This ensures a newly built snapshot PLUS a full fresh boundary run is
    always required before any acceptance commit.

    Returns ``(count_invalidated, details)`` where *count_invalidated* is
    the number of candidates that were invalidated and *details* is a
    human-readable description.

    When *plan_dir* does not exist or has no acceptance candidates, this
    is a no-op returning ``(0, \"\")``.
    """
    plan = Path(plan_dir)
    if not plan.is_dir():
        return 0, ""

    try:
        from arnold_pipelines.megaplan.orchestration.completion_io import (
            list_uncommitted_acceptance_candidates,
        )
    except ImportError:
        return 0, ""

    candidates = list_uncommitted_acceptance_candidates(plan)
    if not candidates:
        return 0, ""

    reason = repair_reason or "evidence changed due to repair"
    invalidated = 0
    for tx_id in list(candidates.keys()):
        try:
            from arnold_pipelines.megaplan.orchestration.completion_io import (
                discard_acceptance_transaction,
            )
            discard_acceptance_transaction(plan, tx_id)
            invalidated += 1
        except Exception:
            pass

    details = (
        f"invalidated {invalidated} acceptance candidate(s) "
        f"after repair (reason: {reason})"
        if invalidated
        else ""
    )
    return invalidated, details


def require_full_boundary_after_repair(
    plan_dir: str | Path,
    *,
    had_repair: bool = False,
) -> bool:
    """Return ``True`` when the acceptance boundary must use the full suite.

    After a repair, focused/scoped selector success cannot satisfy
    acceptance — the full boundary runner is required.  This function
    returns ``True`` whenever *had_repair* is true **or** there are
    uncommitted candidates still present in *plan_dir* (which indicates
    a repair that hasn't yet invalidated them).
    """
    if had_repair:
        return True

    plan = Path(plan_dir)
    if not plan.is_dir():
        return False

    try:
        from arnold_pipelines.megaplan.orchestration.completion_io import (
            list_uncommitted_acceptance_candidates,
        )
        candidates = list_uncommitted_acceptance_candidates(plan)
        return bool(candidates)
    except ImportError:
        return False


def acceptance_revalidation_after_repair(
    plan_dir: str | Path,
    *,
    had_repair: bool = False,
    repair_reason: str = "",
    milestone_label: str = "",
) -> TargetRevalidation:
    """Run acceptance-aware revalidation after a repair.

    Combines candidate invalidation with the full-boundary requirement
    into a single :class:`TargetRevalidation` record.  This is the
    primary entry point for repair-result handling that must feed back
    into the acceptance boundary.

    Returns a ``TargetRevalidation`` whose *recovery_verified* is always
    ``False`` (the acceptance boundary must rerun) and whose
    *full_boundary_required* reflects whether focused selectors are
    insufficient.
    """
    invalidated_count, invalidation_details = invalidate_acceptance_candidates_after_repair(
        plan_dir,
        milestone_label=milestone_label,
        repair_reason=repair_reason,
    )
    full_required = require_full_boundary_after_repair(
        plan_dir,
        had_repair=had_repair,
    )
    return TargetRevalidation(
        changed_fields=(),
        superseded=True,
        runner_live=False,
        active_worker_live=False,
        progress_observed=False,
        recovery_verified=False,
        reason=(
            f"repair result requires full acceptance boundary rerun"
            + (f"; {invalidation_details}" if invalidation_details else "")
        ),
        full_boundary_required=full_required,
        acceptance_candidates_invalidated=invalidated_count,
        acceptance_invalidation_reason=invalidation_details,
    )


# ──────────────────────────────────────────────────────────────────────
# T18 / Step 11 — canonical dispatch-identity revalidation.
#
# The five mutating repair action kinds (repair / retry / escalation /
# cancellation / adoption) must each pass through a fresh source reread
# before mutating control flow.  ``revalidate_dispatch_identity`` is the
# post-reread check that quarantines the action when the live occurrence
# tuple or fence token has drifted.  It is read-only — it never mutates
# repair state and never grants authority beyond "the tuple is still live".
# ──────────────────────────────────────────────────────────────────────


def revalidate_dispatch_identity(
    action: str,
    *,
    current_identity: repair_requests.RepairDispatchIdentity | None,
    fresh_identity: repair_requests.RepairDispatchIdentity | None,
) -> tuple[bool, str, repair_requests.SourceRereadVerdict]:
    """Revalidate a mutating repair action against a fresh source reread.

    Returns ``(permitted, reason, verdict)`` where *verdict* is the full
    :class:`~arnold_pipelines.megaplan.cloud.repair_requests.SourceRereadVerdict`
    and *permitted* / *reason* are convenience projections of it.  Callers
    that record a quarantine should persist ``verdict.as_dict()``-style
    diagnostics (never authority).
    """
    verdict = repair_requests.require_source_reread_for_action(
        action,
        current_identity=current_identity,
        fresh_identity=fresh_identity,
    )
    return verdict.permitted, verdict.reason, verdict


# ═══════════════════════════════════════════════════════════════════════════
# T23 / Step 36-37 — Recovery latency ledger
# ═══════════════════════════════════════════════════════════════════════════

import hashlib as _hashlib
import json as _json
from datetime import datetime as _datetime, timezone as _timezone
from typing import Sequence as _Sequence


@dataclass(frozen=True)
class LatencyLedgerRow:
    """One row in the recovery latency ledger.

    Records a single durable blocked-occurrence or process-exit event
    and its terminal accepted-repair or typed-escalation receipt, with
    computed occurrence-to-terminal latency in seconds.
    """

    occurrence_fingerprint: str
    """Exact occurrence fingerprint (sha256 over F01 tuple)."""

    durable_event_kind: str
    """``blocked_occurrence`` or ``process_exit``."""

    durable_event_timestamp: str
    """ISO-8601 timestamp when the durable event was recorded."""

    terminal_receipt_kind: str
    """``accepted_repair`` or ``typed_escalation``."""

    terminal_receipt_timestamp: str
    """ISO-8601 timestamp of the terminal receipt."""

    terminal_receipt_id: str
    """Content-addressed receipt identifier."""

    latency_seconds: float
    """Occurrence-to-terminal latency in seconds (may be negative if timestamps are misordered)."""

    cohort_eligible: bool
    """Whether this row is eligible for the M11 SLO cohort."""

    eligibility_reason: str
    """Why the row is eligible or ineligible."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_event_and_receipt(
        cls,
        *,
        occurrence_fingerprint: str,
        durable_event_kind: str,
        durable_event_timestamp: str,
        terminal_receipt_kind: str,
        terminal_receipt_timestamp: str,
        terminal_receipt_id: str,
        has_current_ra_grant: bool = True,
        has_current_custody_lease: bool = True,
        has_verifier_receipts: bool = True,
    ) -> "LatencyLedgerRow":
        """Build a ledger row from a durable event and its terminal receipt.

        Cohort eligibility requires:
        1. Current Run Authority grant/fence
        2. Current Custody lease/epoch
        3. Same-occurrence verifier receipts
        """
        try:
            start = _datetime.fromisoformat(durable_event_timestamp)
            end = _datetime.fromisoformat(terminal_receipt_timestamp)
            latency = (end - start).total_seconds()
        except (ValueError, TypeError):
            latency = -1.0

        eligible = True
        reasons: list[str] = []
        if not has_current_ra_grant:
            eligible = False
            reasons.append("no current Run Authority grant/fence")
        if not has_current_custody_lease:
            eligible = False
            reasons.append("no current Custody lease/epoch")
        if not has_verifier_receipts:
            eligible = False
            reasons.append("missing same-occurrence verifier receipts")
        if latency < 0:
            eligible = False
            reasons.append("negative latency (misordered timestamps)")

        return cls(
            occurrence_fingerprint=occurrence_fingerprint,
            durable_event_kind=durable_event_kind,
            durable_event_timestamp=durable_event_timestamp,
            terminal_receipt_kind=terminal_receipt_kind,
            terminal_receipt_timestamp=terminal_receipt_timestamp,
            terminal_receipt_id=terminal_receipt_id,
            latency_seconds=latency,
            cohort_eligible=eligible,
            eligibility_reason="; ".join(reasons) if reasons else "eligible",
        )


@dataclass(frozen=True)
class RecoveryLatencyLedger:
    """The M11 recovery latency ledger.

    Generated from durable blocked-occurrence / process-exit events and
    their terminal accepted-repair or typed-escalation receipts.

    Provides nearest-rank p95 computation over eligible cohort rows.
    """

    schema_version: int = 1
    milestone: str = "M11"
    rows: tuple[LatencyLedgerRow, ...] = ()

    @property
    def eligible_rows(self) -> tuple[LatencyLedgerRow, ...]:
        return tuple(r for r in self.rows if r.cohort_eligible)

    @property
    def total_rows(self) -> int:
        return len(self.rows)

    @property
    def sample_count(self) -> int:
        return len(self.eligible_rows)

    @property
    def p95_seconds(self) -> float | None:
        """Nearest-rank p95 over eligible cohort latencies.

        Uses ``ceil(0.95 * N)`` over sorted ascending latencies.
        Returns ``None`` when the sample count is zero.
        """
        if self.sample_count == 0:
            return None
        latencies = sorted(r.latency_seconds for r in self.eligible_rows)
        import math
        rank = math.ceil(0.95 * len(latencies))
        # rank is 1-indexed
        return float(latencies[min(rank, len(latencies)) - 1])

    @property
    def slo_met(self) -> bool:
        """Whether the five-minute SLO is met.

        Requires sample_count >= 20 and p95_seconds < 300.0.
        """
        if self.sample_count < 20:
            return False
        p95 = self.p95_seconds
        return p95 is not None and p95 < 300.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "milestone": self.milestone,
            "generated_at": _datetime.now(_timezone.utc).isoformat(),
            "sample_count": self.sample_count,
            "total_rows": len(self.rows),
            "eligible_rows": self.sample_count,
            "p95_seconds": self.p95_seconds,
            "slo_met": self.slo_met,
            "latency_ledger_rows": [r.to_dict() for r in self.rows],
            "cohort_definition": (
                "Eligible durable blocked-occurrence or process-exit events "
                "whose occurrence identity has current Run Authority grant/fence, "
                "current Custody lease/epoch, same-occurrence verifier receipts, "
                "and a terminal accepted-repair or typed-escalation receipt."
            ),
            "p95_method": "nearest-rank ceil(0.95 * N) over sorted ascending latencies",
            "slo_threshold_seconds": 300.0,
            "minimum_cohort_size": 20,
        }

    def write(self, path: str | Path) -> None:
        """Persist the ledger to a JSON file."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def generate_latency_ledger(
    rows: _Sequence[LatencyLedgerRow] | None = None,
    *,
    events: _Sequence[Mapping[str, Any]] | None = None,
    receipts: _Sequence[Mapping[str, Any]] | None = None,
) -> RecoveryLatencyLedger:
    """Generate the recovery latency ledger from durable events and receipts.

    Accepts either pre-built :class:`LatencyLedgerRow` instances or raw
    event/receipt sequences.  When raw sequences are provided, each event
    is paired with its corresponding receipt by ``occurrence_fingerprint``.

    Returns a :class:`RecoveryLatencyLedger` that can compute p95 and
    check the five-minute SLO.
    """
    if rows is not None:
        return RecoveryLatencyLedger(rows=tuple(rows))

    if events is not None and receipts is not None:
        # Pair events with receipts by occurrence_fingerprint
        receipt_by_fp: dict[str, dict[str, Any]] = {}
        for rec in receipts:
            fp = str(rec.get("occurrence_fingerprint", ""))
            if fp:
                receipt_by_fp[fp] = dict(rec)

        built_rows: list[LatencyLedgerRow] = []
        for evt in events:
            fp = str(evt.get("occurrence_fingerprint", ""))
            if not fp:
                continue
            rec = receipt_by_fp.get(fp)
            if rec is None:
                continue
            row = LatencyLedgerRow.from_event_and_receipt(
                occurrence_fingerprint=fp,
                durable_event_kind=str(evt.get("kind", "blocked_occurrence")),
                durable_event_timestamp=str(evt.get("timestamp", "")),
                terminal_receipt_kind=str(rec.get("kind", "accepted_repair")),
                terminal_receipt_timestamp=str(rec.get("emitted_at", "")),
                terminal_receipt_id=str(rec.get("receipt_id", "")),
                has_current_ra_grant=bool(evt.get("has_current_ra_grant", True)),
                has_current_custody_lease=bool(evt.get("has_current_custody_lease", True)),
                has_verifier_receipts=bool(evt.get("has_verifier_receipts", True)),
            )
            built_rows.append(row)
        return RecoveryLatencyLedger(rows=tuple(built_rows))

    # No data — return an empty ledger
    return RecoveryLatencyLedger()


# ═══════════════════════════════════════════════════════════════════════════
# Steps 93-94 — Recovery SLO proof with closed-routes gate
#
# The final M11 acceptance gate combines route-authority closure (Step 92)
# with eligible-cohort nearest-rank p95 (Steps 93-94).  A positive proof
# requires:
#   1. All recovery routes closed (zero unplanned, zero planned_pending).
#   2. At least 20 eligible occurrence-to-terminal cohort rows.
#   3. Nearest-rank p95 under 300 seconds.
#
# When any precondition fails, ``blockers`` carries the typed reason(s)
# instead of a positive ``slo_met``.
# ═══════════════════════════════════════════════════════════════════════════


#: The closed vocabulary of recovery-SLO blocker kinds.
RECOVERY_SLO_BLOCKER_KINDS: frozenset[str] = frozenset({
    "route_closure_pending",
    "insufficient_cohort",
    "p95_exceeds_threshold",
})


@dataclass(frozen=True)
class RecoverySloBlocker:
    """A typed reason why the recovery SLO proof cannot be issued."""

    blocker_kind: str
    detail: str

    def __post_init__(self) -> None:
        if self.blocker_kind not in RECOVERY_SLO_BLOCKER_KINDS:
            raise ValueError(
                f"unknown recovery_slo_blocker_kind: {self.blocker_kind!r}; "
                f"expected one of {sorted(RECOVERY_SLO_BLOCKER_KINDS)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecoverySloProof:
    """The M11 recovery SLO acceptance proof.

    Combines route-authority closure (Step 92) with eligible-cohort
    nearest-rank p95 (Steps 93-94).  A positive proof (``slo_met == True``)
    requires closed routes, ≥ 20 eligible cohort rows, and p95 < 300 s.
    When any precondition fails, ``blockers`` carries the typed reason(s).

    The proof does not create authority from labels, liveness, WBC receipts,
    or rebuildable projections — it only *reads* those as inputs to the
    closure-cohort gate.
    """

    schema_version: int = 1
    milestone: str = "M11"
    routes_closed: bool = False
    sample_count: int = 0
    p95_seconds: float | None = None
    minimum_cohort_size: int = 20
    slo_threshold_seconds: float = 300.0
    slo_met: bool = False
    blockers: tuple[RecoverySloBlocker, ...] = ()
    p95_method: str = "nearest-rank ceil(0.95 * N) over sorted ascending latencies"

    @property
    def has_typed_blocker(self) -> bool:
        """True when at least one typed blocker is present."""
        return len(self.blockers) > 0

    def blocker_kinds(self) -> tuple[str, ...]:
        return tuple(b.blocker_kind for b in self.blockers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "milestone": self.milestone,
            "routes_closed": self.routes_closed,
            "sample_count": self.sample_count,
            "p95_seconds": self.p95_seconds,
            "minimum_cohort_size": self.minimum_cohort_size,
            "slo_threshold_seconds": self.slo_threshold_seconds,
            "slo_met": self.slo_met,
            "blockers": [b.to_dict() for b in self.blockers],
            "p95_method": self.p95_method,
            "cohort_definition": (
                "Eligible durable blocked-occurrence or process-exit events "
                "whose occurrence identity has current Run Authority grant/fence, "
                "current Custody lease/epoch, same-occurrence verifier receipts, "
                "and a terminal accepted-repair or typed-escalation receipt."
            ),
        }


def _evaluate_route_closure(route_closure: Mapping[str, Any]) -> bool:
    """Return ``True`` only if the route-closure summary proves closure.

    Authority is never derived from labels, liveness, WBC receipts, or
    rebuildable projections — this function only *reads* the closure
    summary's explicit counts and completeness flag.
    """
    if route_closure is None:
        return False
    unplanned = int(route_closure.get("unplanned_count", 0))
    planned_pending = int(route_closure.get("planned_pending_count", 0))
    closure_complete = bool(route_closure.get("closure_complete", False))
    return closure_complete and unplanned == 0 and planned_pending == 0


def compute_recovery_slo_proof(
    ledger: RecoveryLatencyLedger,
    *,
    route_closure: Mapping[str, Any] | None = None,
) -> RecoverySloProof:
    """Compute the recovery SLO proof from a latency ledger and route closure.

    Route closure (Step 92) is a precondition: if routes are not closed
    (``unplanned_count > 0`` or ``planned_pending_count > 0``), a typed
    ``route_closure_pending`` blocker is emitted and ``slo_met`` is ``False``
    regardless of cohort size or p95 — the SLO may not be claimed while
    unclosed routes can still materialize unguarded legacy repair authority.

    The cohort (Step 93) requires eligible occurrence-to-terminal rows with
    current Run Authority grant/fence, current Custody lease/epoch, and
    same-occurrence verifier receipts.  Insufficient cohort (< 20) emits
    ``insufficient_cohort``.

    The p95 (Step 94) requires nearest-rank p95 < 300 seconds.  Exceeding the
    threshold emits ``p95_exceeds_threshold``.
    """
    blockers: list[RecoverySloBlocker] = []

    # ── Step 92 gate: route closure ────────────────────────────────────
    routes_closed = _evaluate_route_closure(route_closure) if route_closure is not None else False
    if not routes_closed:
        if route_closure is not None:
            unplanned = int(route_closure.get("unplanned_count", 0))
            planned_pending = int(route_closure.get("planned_pending_count", 0))
            detail = (
                f"route closure incomplete: unplanned={unplanned}, "
                f"planned_pending={planned_pending}"
            )
        else:
            detail = "route closure summary not provided; cannot prove closure"
        blockers.append(RecoverySloBlocker(
            blocker_kind="route_closure_pending",
            detail=detail,
        ))

    # ── Step 93 gate: eligible cohort ──────────────────────────────────
    sample_count = ledger.sample_count if ledger is not None else 0
    minimum_cohort_size = 20
    if sample_count < minimum_cohort_size:
        blockers.append(RecoverySloBlocker(
            blocker_kind="insufficient_cohort",
            detail=(
                f"only {sample_count} eligible occurrence-to-terminal rows; "
                f"require >= {minimum_cohort_size}"
            ),
        ))

    # ── Step 94 gate: p95 threshold ────────────────────────────────────
    p95 = ledger.p95_seconds if ledger is not None else None
    if p95 is not None and p95 >= 300.0:
        blockers.append(RecoverySloBlocker(
            blocker_kind="p95_exceeds_threshold",
            detail=f"nearest-rank p95={p95:.1f}s exceeds 300s threshold",
        ))
    elif sample_count >= 20 and p95 is None:
        blockers.append(RecoverySloBlocker(
            blocker_kind="p95_exceeds_threshold",
            detail="p95 is None despite sufficient cohort",
        ))

    slo_met = (
        routes_closed
        and sample_count >= 20
        and p95 is not None
        and p95 < 300.0
    )

    return RecoverySloProof(
        routes_closed=routes_closed,
        sample_count=sample_count,
        p95_seconds=p95,
        slo_met=slo_met,
        blockers=tuple(blockers),
    )
