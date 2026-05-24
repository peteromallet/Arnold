"""Centralised subprocess spawning and process-group reaping for megaplan.

Public surface
--------------
spawn(*args, **kw)               → subprocess.Popen
spawn_async(*args, **kw)         → asyncio.subprocess.Process  (coroutine)
kill_group(proc, *, grace_s, escalate, label) → None
"""

from __future__ import annotations

import asyncio
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
