"""Runtime-neutral subprocess lifecycle primitives.

Agent tools and other Arnold runtime consumers use this module so importing
them does not pull in a product pipeline.  Product-specific process custody,
engine-root, and tmux policy remains in the owning pipeline package.
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


def _already_exited(proc: Any) -> bool:
    """Return True if *proc* has already exited (Popen or asyncio.Process)."""
    if isinstance(proc, subprocess.Popen):
        return proc.poll() is not None
    return proc.returncode is not None


def _fallback_kill(proc: Any) -> None:
    """Terminate then kill when process-group lookup is unavailable."""
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


def _descendant_pids(root_pid: int) -> list[int]:
    """Return the transitive closure of *root_pid*'s descendant PIDs."""
    descendants: list[int] = []
    seen: set[int] = {root_pid}
    frontier = [root_pid]
    while frontier:
        next_frontier: list[int] = []
        for parent in frontier:
            try:
                result = subprocess.run(
                    ["pgrep", "-P", str(parent)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError:
                return descendants
            if result.returncode not in (0, 1):
                continue
            for line in result.stdout.split():
                try:
                    child = int(line)
                except ValueError:
                    continue
                if child in seen:
                    continue
                seen.add(child)
                descendants.append(child)
                next_frontier.append(child)
        frontier = next_frontier
    return descendants


def _reap_descendants(pids: list[int], tag: str) -> None:
    """SIGKILL descendants that survived process-group signalling."""
    for pid in pids:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, OSError):
            continue
        logger.debug("kill_group: SIGKILL stray descendant pid=%d%s", pid, tag)
        try:
            pgid = os.getpgid(pid)
        except (ProcessLookupError, OSError):
            pgid = None
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass


def _strip_setsid_collision(kw: dict[str, Any]) -> None:
    """Remove redundant ``preexec_fn=os.setsid`` under session isolation."""
    if kw.get("start_new_session") and kw.get("preexec_fn") is os.setsid:
        del kw["preexec_fn"]


def spawn(*args: Any, **kw: Any) -> subprocess.Popen:
    """Spawn an argv command with safe process-group isolation defaults."""
    if kw.get("shell"):
        raise ValueError(
            "spawn() does not permit shell=True — pass an explicit argv list "
            "to prevent shell injection."
        )
    kw.setdefault("start_new_session", True)
    _strip_setsid_collision(kw)
    return subprocess.Popen(*args, **kw)


async def spawn_async(*args: Any, **kw: Any) -> asyncio.subprocess.Process:
    """Async variant of :func:`spawn`."""
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
    """Terminate a process group and reap descendants that changed sessions."""
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
    descendants = _descendant_pids(proc.pid)
    try:
        logger.debug("kill_group: SIGTERM pgid=%d%s", pgid, tag)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        _reap_descendants(descendants, tag)
        return
    if not escalate:
        _reap_descendants(descendants, tag)
        return
    deadline = time.monotonic() + grace_s
    if isinstance(proc, subprocess.Popen):
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                proc.wait(timeout=min(0.1, remaining))
                _reap_descendants(descendants, tag)
                return
            except subprocess.TimeoutExpired:
                pass
            except (ProcessLookupError, OSError):
                _reap_descendants(descendants, tag)
                return
    else:
        while time.monotonic() < deadline:
            if proc.returncode is not None:
                _reap_descendants(descendants, tag)
                return
            time.sleep(0.05)
    try:
        logger.debug(
            "kill_group: SIGKILL pgid=%d%s (grace %.1fs elapsed)",
            pgid,
            tag,
            grace_s,
        )
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass
    if isinstance(proc, subprocess.Popen):
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    _reap_descendants(descendants, tag)
