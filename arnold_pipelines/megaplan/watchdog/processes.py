"""Process-signature scanning for Megaplan/Arnold/Shannon/Codex/Claude."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from arnold_pipelines.megaplan._core.state import _pid_is_live


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    cmdline: str
    category: str
    is_live: bool
    cwd: str | None = None
    ppid: int | None = None
    elapsed_seconds: float | None = None
    cpu_seconds: float | None = None
    # M9 — correlated-evidence fields. None of these grant success, repair, or
    # completion authority: they are facts extracted from the process namespace
    # so the watchdog can *correlate* a process to a WBC attempt identity. The
    # correlation verdict is computed in ``watchdog.correlate`` and is always
    # classified as unknown/lost for recycled, hung, dead, or unrelated workers.
    # ``birth_time_seconds`` is the process start time (epoch seconds) used to
    # detect recycled PIDs against an attempt's recorded start time.
    birth_time_seconds: float | None = None
    # Environment/session token extracted best-effort from the cmdline/env.
    session_token: str | None = None
    # Runner lease / epoch reference extracted best-effort from the cmdline/env.
    runner_lease_ref: str | None = None
    # Heartbeat freshness: True when a recent heartbeat file/line was observed.
    heartbeat_fresh: bool | None = None
    # Age in seconds of the most recent heartbeat sample observed for the pid.
    heartbeat_age_seconds: float | None = None
    # tmux session name hosting the process, when discoverable.
    tmux_session: str | None = None
    # Age in seconds of the tmux session / last client activity.
    tmux_age_seconds: float | None = None


_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("megaplan", ("megaplan", "python -m megaplan")),
    ("arnold", ("arnold", "python -m arnold")),
    ("shannon", ("shannon",)),
    ("codex", ("codex",)),
    ("claude", ("claude",)),
)


def _parse_ps_time(value: str) -> float | None:
    """Parse ps ``etime``/``time`` ([[dd-]hh:]mm:ss) to seconds."""
    value = value.strip()
    if not value:
        return None
    try:
        if "-" in value:
            days, rest = value.split("-", 1)
            day_seconds = int(days) * 86400
        else:
            day_seconds = 0
            rest = value
        parts = rest.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return day_seconds + int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return day_seconds + int(minutes) * 60 + int(seconds)
        if len(parts) == 1:
            return day_seconds + int(parts[0])
    except Exception:
        pass
    return None


def _categorize_cmdline(cmdline: str) -> str | None:
    lowered = cmdline.lower()
    # Split on whitespace, path separators, and dots so dotted module paths
    # like "python -m arnold_pipelines.megaplan" are categorized correctly.
    # Path segments like ".megaplan-worktrees" split into "megaplan-worktrees",
    # which does not exactly match the "megaplan" needle, avoiding false positives.
    tokens = re.split(r"[\s/.]", lowered)
    for category, needles in _CATEGORIES:
        for needle in needles:
            if needle in tokens:
                return category
    return None


def _extract_cwd_from_cmdline(cmdline: str) -> str | None:
    """Best-effort cwd extraction from known cmdline patterns."""
    # Claude daemon: --spawned-by {"cwd":"/path",...}
    match = re.search(r'--spawned-by\s+\{[^}]*"cwd"\s*:\s*"([^"]+)"', cmdline)
    if match:
        return match.group(1)
    # tmux new-session -c /path (only when tmux is the executable).
    if cmdline.lstrip().startswith("tmux") or " tmux " in cmdline:
        match = re.search(r'\s-c\s+(\S+)', cmdline)
        if match:
            return match.group(1)
    # Bash wrapper: last `cd '/path' || cd "/path"` in the command.
    matches = re.findall(r"\bcd\s+['\"]([^'\"]+)['\"]", cmdline)
    if matches:
        return matches[-1]
    return None


def _extract_session_token(cmdline: str) -> str | None:
    """Best-effort extraction of an environment/session token from a cmdline.

    Recognizes common shapes such as ``--session <tok>``, ``--session-id <tok>``,
    ``MEGAPLAN_SESSION=<tok>``, ``ARNOLD_SESSION=<tok>``, and
    ``--env MEGAPLAN_SESSION=<tok>``. Returns ``None`` when no token is found.
    The extracted token is correlated *evidence only* — it never authorizes a
    terminal/completion transition.
    """
    for flag in ("--session-id", "--session"):
        match = re.search(rf'{re.escape(flag)}\s+([A-Za-z0-9_.\-:]+)', cmdline)
        if match:
            return match.group(1)
    for env_name in ("MEGAPLAN_SESSION", "ARNOLD_SESSION", "RUN_SESSION"):
        match = re.search(rf'(?:^|\s){env_name}=([A-Za-z0-9_.\-:]+)', cmdline)
        if match:
            return match.group(1)
        match = re.search(rf'--env\s+{env_name}=([A-Za-z0-9_.\-:]+)', cmdline)
        if match:
            return match.group(1)
    return None


def _extract_runner_lease_ref(cmdline: str) -> str | None:
    """Best-effort extraction of a runner lease / epoch reference from a cmdline.

    Recognizes ``--lease <ref>``, ``--runner-lease <ref>``, ``--lease-id <ref>``,
    and ``RUNNER_LEASE=<ref>``. Returns ``None`` when no ref is found. The ref
    is correlated evidence only.
    """
    for flag in ("--runner-lease", "--lease-id", "--lease"):
        match = re.search(rf'{re.escape(flag)}\s+([A-Za-z0-9_.\-:]+)', cmdline)
        if match:
            return match.group(1)
    match = re.search(r'(?:^|\s)RUNNER_LEASE=([A-Za-z0-9_.\-:]+)', cmdline)
    if match:
        return match.group(1)
    return None


def _get_cwd(pid: int) -> str | None:
    """Return the current working directory of *pid* if available."""
    # Linux procfs shortcut (only when procfs is present).
    proc_cwd = Path(f"/proc/{pid}/cwd")
    if proc_cwd.is_symlink():
        try:
            resolved = proc_cwd.resolve()
            if resolved.is_dir():
                return str(resolved)
        except Exception:
            pass
    # macOS / BSD via lsof.
    try:
        result = subprocess.run(
            ["lsof", "-p", str(pid), "-a", "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        for line in result.stdout.splitlines():
            if line.startswith("n"):
                candidate = line[1:]
                if Path(candidate).is_dir():
                    return candidate
    except Exception:
        pass
    return None


def _read_ps() -> list[str]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,ppid,etime,time,args"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.splitlines()
    except Exception:
        return []


def _detect_ps_format(ps_lines: Iterable[str]) -> str:
    """Return ``metadata`` if ps output includes ppid/etime/time, else ``legacy``."""
    for line in ps_lines:
        stripped = line.strip().lower()
        if stripped.startswith("pid args"):
            return "legacy"
        if "ppid" in stripped and "etime" in stripped:
            return "metadata"
        parts = stripped.split()
        if len(parts) >= 2:
            try:
                int(parts[0])
            except ValueError:
                continue
            try:
                int(parts[1])
                return "metadata" if len(parts) >= 5 else "legacy"
            except ValueError:
                return "legacy"
    return "metadata"


def scan_processes(ps_lines: Iterable[str] | None = None) -> tuple[ProcessRecord, ...]:
    """Parse ``ps`` output for Megaplan/Arnold/Shannon/Codex/Claude processes.

    When *ps_lines* is omitted, reads real ``ps -eo pid,ppid,etime,time,args``
    output. Also attempts to resolve each process's cwd so correlation can match
    processes to plans even when the cmdline does not name the plan directly.
    """
    if ps_lines is None:
        ps_lines = _read_ps()

    lines = list(ps_lines)
    fmt = _detect_ps_format(lines)
    records: list[ProcessRecord] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("pid"):
            continue

        ppid: int | None = None
        elapsed_seconds: float | None = None
        cpu_seconds: float | None = None

        if fmt == "metadata":
            parts = stripped.split(None, 4)
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
            except ValueError:
                continue
            elapsed_seconds = _parse_ps_time(parts[2])
            cpu_seconds = _parse_ps_time(parts[3])
            cmdline = parts[4]
        else:
            parts = stripped.split(None, 1)
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            cmdline = parts[1]

        category = _categorize_cmdline(cmdline)
        if category is None:
            continue
        cwd = _extract_cwd_from_cmdline(cmdline) or _get_cwd(pid)
        session_token = _extract_session_token(cmdline)
        runner_lease_ref = _extract_runner_lease_ref(cmdline)
        # Derive birth time from elapsed seconds so the liveness classifier can
        # detect recycled PIDs. None when ``etime`` is unavailable.
        birth_time_seconds: float | None = None
        if elapsed_seconds is not None:
            try:
                birth_time_seconds = time.time() - elapsed_seconds
            except Exception:
                birth_time_seconds = None
        records.append(
            ProcessRecord(
                pid=pid,
                cmdline=cmdline,
                category=category,
                is_live=_pid_is_live(pid),
                cwd=cwd,
                ppid=ppid,
                elapsed_seconds=elapsed_seconds,
                cpu_seconds=cpu_seconds,
                birth_time_seconds=birth_time_seconds,
                session_token=session_token,
                runner_lease_ref=runner_lease_ref,
            )
        )
    return tuple(records)


__all__ = [
    "ProcessRecord",
    "scan_processes",
    "_extract_session_token",
    "_extract_runner_lease_ref",
]
