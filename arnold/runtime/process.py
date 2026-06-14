"""Pure subprocess spawning and process-group reaping primitives.

Public surface
--------------
spawn(*args, **kw)               -> subprocess.Popen
spawn_async(*args, **kw)         -> asyncio.subprocess.Process  (coroutine)
kill_group(proc, *, grace_s, escalate, label) -> None
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import os
import signal
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _already_exited(proc: Any) -> bool:
    """Return True if *proc* has already exited (Popen or asyncio.Process)."""
    if isinstance(proc, subprocess.Popen):
        return proc.poll() is not None
    return proc.returncode is not None


def _fallback_kill(proc: Any) -> None:
    """Terminate then kill — used when pgid lookup fails or POSIX is absent."""
    try:
        proc.terminate()
    except (ProcessLookupError, OSError):
        pass
    if isinstance(proc, subprocess.Popen):
        try:
            proc.wait(timeout=1)
        except (subprocess.TimeoutExpired, OSError):
            pass
    try:
        proc.kill()
    except (ProcessLookupError, OSError):
        pass


def _strip_setsid_collision(kw: dict[str, Any]) -> None:
    """Remove redundant preexec_fn=os.setsid when start_new_session=True.

    CPython invokes setsid() in the child for start_new_session=True; a
    redundant preexec_fn=os.setsid then raises EPERM because the child is
    already a session leader.
    """
    if kw.get("start_new_session") and kw.get("preexec_fn") is os.setsid:
        del kw["preexec_fn"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def spawn(*args: Any, **kw: Any) -> subprocess.Popen:
    """Spawn a subprocess with safe isolation defaults.

    Raises ValueError for shell=True — callers must pass explicit argv lists.
    Defaults start_new_session=True so the child is its own session/pgroup
    leader and kill_group() can reap the whole tree safely.
    """
    if kw.get("shell"):
        raise ValueError(
            "spawn() does not permit shell=True — pass an explicit argv list "
            "to prevent shell injection."
        )
    kw.setdefault("start_new_session", True)
    _strip_setsid_collision(kw)
    return subprocess.Popen(*args, **kw)


async def spawn_async(*args: Any, **kw: Any) -> asyncio.subprocess.Process:
    """Async variant of spawn(); returns an asyncio.subprocess.Process."""
    if kw.get("shell"):
        raise ValueError(
            "spawn_async() does not permit shell=True — pass an explicit argv "
            "list to prevent shell injection."
        )
    kw.setdefault("start_new_session", True)
    _strip_setsid_collision(kw)
    return await asyncio.create_subprocess_exec(*args, **kw)


def kill_group(
    proc: Any,
    *,
    grace_s: float = 3.0,
    escalate: bool = True,
    label: str = "",
) -> None:
    """SIGTERM the process group; optionally escalate to SIGKILL after grace_s.

    Works with both subprocess.Popen and asyncio.subprocess.Process handles.
    """
    if _already_exited(proc):
        return

    tag = f" [{label}]" if label else ""

    if not hasattr(os, "killpg"):
        _fallback_kill(proc)
        return

    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, OSError):
        _fallback_kill(proc)
        return

    try:
        logger.debug("kill_group: SIGTERM pgid=%d%s", pgid, tag)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return

    if not escalate:
        return

    deadline = time.monotonic() + grace_s
    if isinstance(proc, subprocess.Popen):
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                proc.wait(timeout=min(0.1, remaining))
                return
            except subprocess.TimeoutExpired:
                pass
            except (ProcessLookupError, OSError):
                return
    else:
        while time.monotonic() < deadline:
            if proc.returncode is not None:
                return
            time.sleep(0.05)

    try:
        logger.debug(
            "kill_group: SIGKILL pgid=%d%s (grace %.1fs elapsed)", pgid, tag, grace_s
        )
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass
    if isinstance(proc, subprocess.Popen):
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


# ---------------------------------------------------------------------------
# Orphan detection and Tmux session management
# ---------------------------------------------------------------------------


class OrphanDetectedError(Exception):
    """Raised when a tmux session survives teardown and cannot be reaped."""

    def __init__(
        self,
        sessions: list[str],
        pids: list[str],
        remediation: str,
    ) -> None:
        super().__init__(
            f"Orphaned tmux session(s) detected: {sessions}. "
            f"Live PIDs: {pids}. {remediation}"
        )
        self.sessions = sessions
        self.pids = pids
        self.remediation = remediation


class TmuxSession:
    """Handle for a single tmux session, keyed by name."""

    def __init__(self, name: str) -> None:
        self.name = name

    def teardown(self) -> None:
        """Kill the tmux session.  Idempotent — safe to call repeatedly."""
        try:
            result = subprocess.run(
                ["tmux", "kill-session", "-t", self.name],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.debug(
                "TmuxSession.teardown(%r): tmux not found on PATH",
                self.name,
            )
            return

        if result.returncode == 0:
            logger.debug("TmuxSession.teardown(%r): session killed", self.name)
        else:
            logger.debug(
                "TmuxSession.teardown(%r): tmux returned %d (already gone?)",
                self.name,
                result.returncode,
            )

    def exists(self) -> bool:
        """Return True iff the tmux session is currently live."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self.name],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            return False
        return result.returncode == 0


def detect_orphans(session_pattern: str) -> list[str]:
    """Return tmux session names matching *session_pattern* via fnmatch."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []

    if result.returncode != 0:
        return []

    sessions: list[str] = []
    for line in result.stdout.strip().splitlines():
        name = line.strip()
        if name and fnmatch.fnmatch(name, session_pattern):
            sessions.append(name)
    return sessions


def pane_pids(session_name: str) -> list[str]:
    """Return the PIDs of every pane in *session_name*."""
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_pid}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []

    if result.returncode != 0:
        return []

    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


__all__ = [
    "spawn",
    "spawn_async",
    "kill_group",
    "OrphanDetectedError",
    "TmuxSession",
    "detect_orphans",
    "pane_pids",
]
