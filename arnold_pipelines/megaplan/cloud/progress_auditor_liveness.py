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
    if (
        tmux.get("pid_live") is True
        or tmux.get("session_live") is True
        or live_status == "alive"
        or active_step.get("worker_pid_alive") is True
    ):
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
        "tmux_live_status": live_status or "unknown",
        "watchdog_statuses": sorted(statuses),
    }
