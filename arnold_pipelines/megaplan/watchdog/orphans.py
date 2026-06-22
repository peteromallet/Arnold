"""Orphan-process detection for the live watchdog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


_ORPHAN_AGE_SECONDS = 3600.0


@dataclass(frozen=True)
class OrphanProcess:
    pid: int
    category: str
    elapsed_seconds: float | None
    reason: str


def _is_parent_alive(ppid: int | None, scanned_pids: set[int]) -> bool:
    """A parent is considered alive if it is in our scanned process set.

    ``ppid`` of 0 or 1 means the process is directly owned by the kernel/
    launchd and has no interactive supervisor.
    """
    if ppid is None:
        return False
    if ppid <= 1:
        return False
    return ppid in scanned_pids


def _is_orphaned_tmux_server(proc: Any, min_age_seconds: float) -> bool:
    """True if *proc* looks like an old detached tmux server."""
    cmdline = ""
    if isinstance(proc, dict):
        cmdline = proc.get("cmdline", "")
        ppid = proc.get("ppid")
        elapsed = proc.get("elapsed_seconds")
    else:
        cmdline = getattr(proc, "cmdline", "")
        ppid = getattr(proc, "ppid", None)
        elapsed = getattr(proc, "elapsed_seconds", None)
    lowered = str(cmdline).lower().lstrip()
    if not lowered.startswith("tmux"):
        return False
    try:
        ppid = int(ppid) if ppid is not None else None
    except Exception:
        return False
    if ppid is not None and ppid > 1:
        return False
    try:
        elapsed = float(elapsed) if elapsed is not None else 0.0
    except Exception:
        return False
    return elapsed >= min_age_seconds


def _has_orphaned_tmux_ancestor(
    pid: int,
    proc_by_pid: dict[int, Any],
    min_age_seconds: float,
    visited: set[int] | None = None,
) -> tuple[bool, int | None]:
    """Walk the parent chain looking for an old detached tmux server.

    Returns ``(orphaned, orphan_pid)``.
    """
    if visited is None:
        visited = set()
    if pid in visited or pid <= 1:
        return False, None
    visited.add(pid)
    proc = proc_by_pid.get(pid)
    if proc is None:
        return False, None
    if _is_orphaned_tmux_server(proc, min_age_seconds):
        return True, pid
    if isinstance(proc, dict):
        ppid = proc.get("ppid")
    else:
        ppid = getattr(proc, "ppid", None)
    try:
        ppid = int(ppid) if ppid is not None else 1
    except Exception:
        ppid = 1
    return _has_orphaned_tmux_ancestor(ppid, proc_by_pid, min_age_seconds, visited)


def find_orphan_processes(
    processes: tuple[Any, ...],
    correlations: tuple[Any, ...],
    *,
    min_age_seconds: float = _ORPHAN_AGE_SECONDS,
) -> dict[Path, list[OrphanProcess]]:
    """Return suspected orphan processes grouped by plan directory.

    A process is considered an orphan when it is correlated to a plan, has
    been running longer than ``min_age_seconds``, and its parent is either
    the init process, no longer present, or an old detached tmux server.
    """
    def _get_int(obj: Any, name: str) -> int | None:
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)
        try:
            return int(value) if value is not None else None
        except Exception:
            return None

    def _get_float(obj: Any, name: str) -> float | None:
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)
        try:
            return float(value) if value is not None else None
        except Exception:
            return None

    def _get_str(obj: Any, name: str) -> str | None:
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    scanned_pids: set[int] = {_get_int(p, "pid") for p in processes if _get_int(p, "pid") is not None}
    proc_by_pid: dict[int, Any] = {_get_int(p, "pid"): p for p in processes if _get_int(p, "pid") is not None}

    by_plan: dict[Path, list[OrphanProcess]] = {}
    for corr in correlations:
        plan_dir = Path(corr.plan_dir)
        pid = int(corr.process_pid)
        proc = proc_by_pid.get(pid)
        if proc is None:
            continue

        elapsed = _get_float(proc, "elapsed_seconds")
        if elapsed is None or elapsed < min_age_seconds:
            continue

        ppid = _get_int(proc, "ppid")
        has_orphan_ancestor, orphan_ancestor_pid = _has_orphaned_tmux_ancestor(
            pid, proc_by_pid, min_age_seconds
        )

        if _is_parent_alive(ppid, scanned_pids) and not has_orphan_ancestor:
            continue

        if has_orphan_ancestor:
            reason = f"ancestor tmux server {orphan_ancestor_pid} is detached/orphaned"
        else:
            reason = f"parent {ppid} missing or init"

        by_plan.setdefault(plan_dir, []).append(
            OrphanProcess(
                pid=pid,
                category=_get_str(proc, "category") or "unknown",
                elapsed_seconds=elapsed,
                reason=reason,
            )
        )

    return by_plan


__all__ = [
    "OrphanProcess",
    "find_orphan_processes",
]
