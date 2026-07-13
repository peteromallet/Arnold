"""Post-action repair target custody and liveness revalidation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


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
    return TargetRevalidation(
        changed_fields=changed,
        superseded=superseded,
        runner_live=runner_live,
        active_worker_live=active_worker_live,
        progress_observed=progress_observed,
        recovery_verified=verified,
        reason=reason,
    )
