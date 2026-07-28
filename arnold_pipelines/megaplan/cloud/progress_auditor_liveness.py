"""Shared tri-state runner-liveness semantics for progress auditing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_DEAD_TMUX = frozenset({"dead", "missing", "stopped", "unavailable"})
_DEAD_WATCHDOG = frozenset(
    {
        "stopped",
        "dead",
        "progress_stall",
        "broken_superfixer",
        "canonical_launch_evidence_missing",
        "terminal_repair_failure",
    }
)


def classify_runner_liveness(
    tmux: Mapping[str, Any] | None,
    active_step: Mapping[str, Any] | None,
    watchdog_statuses: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return one consistent ``alive|dead|unknown`` runner classification."""

    tmux = tmux if isinstance(tmux, Mapping) else {}
    active_step = active_step if isinstance(active_step, Mapping) else {}
    live_status = str(tmux.get("live_status") or "").strip().lower()
    statuses = {
        str(item or "").strip().lower()
        for item in (watchdog_statuses or ())
        if str(item or "").strip()
    }
    session_identity = str(tmux.get("session") or "").strip()
    process_identity = tmux.get("pid")
    process_identity_valid = (
        isinstance(process_identity, int)
        and not isinstance(process_identity, bool)
        and process_identity > 0
    )
    active_process_identity = str(active_step.get("worker_pid") or "").strip()
    tmux_process_live = process_identity_valid and tmux.get("pid_live") is True
    tmux_session_live = bool(session_identity) and tmux.get("session_live") is True
    active_process_live = (
        bool(active_process_identity) and active_step.get("worker_pid_alive") is True
    )
    if tmux_process_live or tmux_session_live or active_process_live:
        state = "alive"
        source = "live_process_evidence"
    elif (
        (active_step.get("present") is True and active_step.get("worker_pid_alive") is False)
        or live_status in _DEAD_TMUX
        or bool(statuses & _DEAD_WATCHDOG)
    ):
        state = "dead"
        source = "explicit_absence_evidence"
    else:
        state = "unknown"
        source = "insufficient_liveness_evidence"
    return {
        "state": state,
        "live": state == "alive",
        "dead": state == "dead",
        "known": state != "unknown",
        "source": source,
        "session_identity_present": bool(session_identity),
        "process_identity_present": bool(process_identity_valid or active_process_identity),
        "tmux_live_status": live_status or "unknown",
        "watchdog_statuses": sorted(statuses),
    }
