"""Centralised subprocess spawning and process-group reaping for megaplan.

Public surface
--------------
spawn(*args, **kw)               → subprocess.Popen
spawn_async(*args, **kw)         → asyncio.subprocess.Process  (coroutine)
kill_group(proc, *, grace_s, escalate, label) → None
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _already_exited(proc: Any) -> bool:
    """Return True if *proc* has already exited (Popen or asyncio.Process)."""
    if isinstance(proc, subprocess.Popen):
        return proc.poll() is not None
    # asyncio.subprocess.Process: returncode is None while still running
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
    """Remove redundant preexec_fn=os.setsid when start_new_session=True (SD1).

    CPython invokes setsid() in the child for start_new_session=True; a
    redundant preexec_fn=os.setsid then raises EPERM because the child is
    already a session leader.  Four migrated spawn sites pass both; stripping
    the kwarg is the minimal fix that preserves all other caller kwargs.
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
    Strips a redundant preexec_fn=os.setsid when start_new_session=True to
    avoid the EPERM double-setsid error (SD1).
    """
    if kw.get("shell"):
        raise ValueError(
            "spawn() does not permit shell=True — pass an explicit argv list "
            "to prevent shell injection.  If shell syntax is genuinely "
            "unavoidable (e.g. a third-party API that requires a shell string), "
            "call subprocess.Popen directly and add the site to the shell-guard "
            "ledger in megaplan/runtime/process_guard.py."
        )
    kw.setdefault("start_new_session", True)
    _strip_setsid_collision(kw)
    return subprocess.Popen(*args, **kw)


def megaplan_engine_root() -> Path:
    """Return the source root for the currently running megaplan package."""
    import megaplan

    return Path(megaplan.__file__).resolve().parent.parent


def megaplan_engine_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return an env that resolves ``python -m megaplan`` from this engine."""
    root = str(megaplan_engine_root())
    env = dict(os.environ if base_env is None else base_env)
    current = env.get("PYTHONPATH")
    parts = [part for part in (current or "").split(os.pathsep) if part]
    env["PYTHONPATH"] = os.pathsep.join([root, *[part for part in parts if part != root]])
    return env


async def spawn_async(*args: Any, **kw: Any) -> asyncio.subprocess.Process:
    """Async variant of spawn(); returns an asyncio.subprocess.Process.

    Applies the same shell rejection, start_new_session default, and
    setsid-collision strip as spawn().  Use when the caller is already in an
    async context and wants to await output or termination without blocking.
    """
    if kw.get("shell"):
        raise ValueError(
            "spawn_async() does not permit shell=True — pass an explicit argv "
            "list to prevent shell injection.  If shell syntax is unavoidable, "
            "call asyncio.create_subprocess_shell directly and ledger the site "
            "in megaplan/runtime/process_guard.py."
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

    Parameters
    ----------
    proc:
        A subprocess.Popen or asyncio.subprocess.Process instance.
    grace_s:
        Seconds to wait after SIGTERM before SIGKILL (only when escalate=True).
    escalate:
        If True (default), SIGKILL the group after grace_s.  Pass False to
        preserve SIGTERM-only semantics — e.g. local.py timeout path (SD2).
    label:
        Human-readable tag included in log output to identify the call site.
    """
    if _already_exited(proc):
        return

    tag = f" [{label}]" if label else ""

    if not hasattr(os, "killpg"):
        # Non-POSIX platform (Windows): fall back to terminate/kill.
        _fallback_kill(proc)
        return

    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, OSError):
        # Process already gone or platform missing getpgid.
        _fallback_kill(proc)
        return

    try:
        logger.debug("kill_group: SIGTERM pgid=%d%s", pgid, tag)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return

    if not escalate:
        return

    # Wait up to grace_s for the group to exit, then escalate to SIGKILL.
    deadline = time.monotonic() + grace_s
    if isinstance(proc, subprocess.Popen):
        # Blocking wait in a bounded loop — correct in a sync context.
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                proc.wait(timeout=min(0.1, remaining))
                return  # exited cleanly within grace period
            except subprocess.TimeoutExpired:
                pass
            except (ProcessLookupError, OSError):
                return
    else:
        # asyncio.subprocess.Process — poll returncode without awaiting so we
        # never yield the event loop inside this sync function.
        while time.monotonic() < deadline:
            if proc.returncode is not None:
                return
            time.sleep(0.05)

    try:
        logger.debug("kill_group: SIGKILL pgid=%d%s (grace %.1fs elapsed)", pgid, tag, grace_s)
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
    """Raised when a tmux session survives teardown and cannot be reaped.

    This is a hard-fail signal — the orphaned session owns live processes
    that may interfere with subsequent steps.  The structured fields allow
    the caller to log, alert, or attempt a last-resort manual cleanup.
    """

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


def tmux_socket_for(session_name: str) -> str:
    """Private tmux control-socket name for a Shannon session.

    MUST mirror ``megaplanTmuxSocket`` in ``vendor/shannon/index.ts``: every
    Shannon session runs on its OWN tmux server (``tmux -L mp-<session>``) so a
    concurrent chain's last-session teardown — or any ``tmux kill-server`` —
    cannot collapse the shared default server out from under a live Claude pane
    (the "no server running" finalize hang). The Python-side reap/exists/
    pane_pids helpers must therefore address the SAME ``-L`` socket the launcher
    used, or they would query the empty default server and mis-report the
    isolated session as gone. ``SHANNON_TMUX_SOCKET`` overrides (kept in lockstep
    with the launcher's env read) for tests/diagnostics.
    """
    override = os.environ.get("SHANNON_TMUX_SOCKET")
    if override:
        return override
    return f"mp-{session_name}"


class TmuxSession:
    """Handle for a single tmux session, keyed by name.

    Provides idempotent teardown and a lightweight liveness check.  All
    tmux CLI calls degrade gracefully when ``tmux`` is not installed or
    the session has already been torn down by another actor. Every call is
    pinned to this session's PRIVATE tmux server via ``-L`` (see
    :func:`tmux_socket_for`) so it addresses the same isolated server the
    vendored launcher created.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.socket = tmux_socket_for(name)

    def teardown(self) -> None:
        """Kill the tmux session AND its private server.  Idempotent.

        Returns ``None`` unconditionally.  A missing ``tmux`` binary or an
        already-gone session/server is a no-op, logged at debug level.

        The vendored launcher sets ``exit-empty off`` on this session's PRIVATE
        ``-L mp-<name>`` server (defense so a transient last-session kill can't
        strand a live turn). The consequence is that ``kill-session`` alone
        leaves an idle tmux server daemon lingering after every turn — observed
        live as 0-session ``mp-*`` orphans piling up in the socket dir. The
        socket is private to THIS session, so also reaping the whole server is
        safe (no other chain shares it) and complete. This must happen on the
        Python side too, not only in bun's ``killTmux``: when a turn is killed
        for timeout/stall the bun child never runs its own cleanup, so this
        ``finally``-path teardown is the only reaper.
        """
        try:
            result = subprocess.run(
                ["tmux", "-L", self.socket, "kill-session", "-t", self.name],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.debug(
                "TmuxSession.teardown(%r): tmux not found on PATH — nothing to do",
                self.name,
            )
            return

        if result.returncode == 0:
            logger.debug("TmuxSession.teardown(%r): session killed", self.name)
        else:
            # Already-gone sessions produce a non-zero exit; that is
            # expected for an idempotent teardown.
            logger.debug(
                "TmuxSession.teardown(%r): tmux returned %d (already gone?)",
                self.name,
                result.returncode,
            )

        # Reap the private server so no idle daemon lingers (exit-empty off).
        try:
            subprocess.run(
                ["tmux", "-L", self.socket, "kill-server"],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            pass

    def exists(self) -> bool:
        """Return ``True`` iff the tmux session is currently live."""
        try:
            result = subprocess.run(
                ["tmux", "-L", self.socket, "has-session", "-t", self.name],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            return False
        return result.returncode == 0


def detect_orphans(session_pattern: str) -> list[str]:
    """Return tmux session names matching *session_pattern* via fnmatch.

    The pattern is **strictly scoped**: only sessions whose name matches
    ``fnmatch.fnmatch(name, session_pattern)`` are returned.  This prevents
    a broad glob (``*``) from accidentally reaping unrelated sessions.

    Degrades to ``[]`` when ``tmux`` is absent or the server has no sessions.
    """
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
    """Return the PIDs of every pane in *session_name*.

    Degrades to ``[]`` when ``tmux`` is absent or the session does not exist.
    """
    try:
        result = subprocess.run(
            ["tmux", "-L", tmux_socket_for(session_name),
             "list-panes", "-t", session_name, "-F", "#{pane_pid}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []

    if result.returncode != 0:
        return []

    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
