"""Post-action repair target custody and liveness revalidation.

Also provides acceptance-aware revalidation so that after a repair result the
prior acceptance candidate is invalidated and the acceptance boundary is forced
to use the full suite (not a focused/scoped selector).

M7 shadow validation is wired into ``revalidate_repair_target`` so that
stale-authority paths are diagnosed before a revalidation verdict is returned.
Production enforcement is always disabled — the validator runs in shadow mode
and does not block callers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

# ── M7 shadow validator import (enforcement always disabled) ────────────────
try:
    from arnold_pipelines.megaplan.custody.action_validator import (
        validate_action_boundary_simple,
    )
    _M7_VALIDATOR_AVAILABLE = True
except ImportError:
    _M7_VALIDATOR_AVAILABLE = False


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

    # ── M7 shadow validation fields (T15) ─────────────────────────────
    m7_shadow_validation: dict[str, Any] | None = None

    def as_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["changed_fields"] = list(self.changed_fields)
        return payload


# ── M7 shadow validator helper (T15) ────────────────────────────────────────


def _shadow_validate_revalidation_boundary(
    *,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    session_health: str,
) -> dict[str, Any]:
    """Run the M7 shadow validator during repair target revalidation (non-blocking).

    Builds a best-effort ``CustodyTargetKey`` from the before/after target
    snapshots, calls ``validate_action_boundary_simple`` with
    ``action_type=\"repair\"``, and returns typed conflict/fence/reconcile
    diagnostics.  Never raises — all errors are captured as diagnostic metadata.

    Production enforcement is always disabled; this is a shadow-only call.
    """
    if not _M7_VALIDATOR_AVAILABLE:
        return {
            "m7_validator_available": False,
            "reason": "action_validator module not importable",
        }

    import hashlib as _hashlib

    try:
        after_map = after if isinstance(after, Mapping) else {}
        before_map = before if isinstance(before, Mapping) else {}

        target_id = str(after_map.get("target_id") or before_map.get("target_id") or "")
        plan_state = (
            after_map.get("plan_state")
            if isinstance(after_map.get("plan_state"), Mapping)
            else before_map.get("plan_state")
            if isinstance(before_map.get("plan_state"), Mapping)
            else {}
        )
        heartbeat = (
            after_map.get("active_step_heartbeat")
            if isinstance(after_map.get("active_step_heartbeat"), Mapping)
            else {}
        )

        target_dict = {
            "environment": "revalidation",
            "session": target_id.split(":")[0] if ":" in target_id else target_id or "unknown",
            "chain": target_id or "unknown",
            "plan_revision": str(plan_state.get("current_state") or ""),
            "phase": str(heartbeat.get("phase") or ""),
            "task": str(heartbeat.get("worker_pid") or "unknown"),
            "attempt": str(heartbeat.get("attempt") or "1"),
            "normalized_failure_kind": "revalidation",
            "blocker_or_phase_result_hash": _hashlib.sha256(
                target_id.encode("utf-8")
            ).hexdigest()[:16],
            "fence": str(plan_state.get("fingerprint") or "0"),
        }

        result = validate_action_boundary_simple(
            action_type="repair",
            target=target_dict,
            run_authority_grant_id="revalidation-grant",
            coordinator_fence_token=0,
            wbc_attempt_reference=target_id,
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
    # ── M7 shadow validation before revalidation verdict (T15) ────────────
    m7_shadow = _shadow_validate_revalidation_boundary(
        before=before,
        after=after,
        session_health=session_health,
    )

    return TargetRevalidation(
        changed_fields=changed,
        superseded=superseded,
        runner_live=runner_live,
        active_worker_live=active_worker_live,
        progress_observed=progress_observed,
        recovery_verified=verified,
        reason=reason,
        m7_shadow_validation=m7_shadow,
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
