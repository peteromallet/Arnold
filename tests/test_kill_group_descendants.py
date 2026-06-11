"""Tests for kill_group() reaping SESSION-DETACHED descendants.

The base test_runtime_process.py grandchild test uses ``sleep &`` inside the
SAME session, so ``killpg(direct_pgid)`` already reaches it.  These tests cover
the harder case the bug describes: a grandchild that started its OWN session
(start_new_session=True) — reparented out of the direct process group — which
killpg cannot reach.  kill_group must snapshot the descendant tree by parent
links and SIGKILL the survivors.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import time

import pytest

from megaplan.runtime.process import kill_group, spawn

pytestmark = pytest.mark.skipif(
    not hasattr(os, "killpg"), reason="POSIX-only (killpg/start_new_session)"
)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        # EPERM => alive but not ours; treat as alive (shouldn't happen here).
        return True
    return True


def _wait_dead(pid: int, timeout: float = 6.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


def _read_pid(path: str, timeout: float = 6.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            content = open(path).read().strip()
            if content:
                return int(content)
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    raise AssertionError(f"PID never written to {path}")


# Parent: spawn a CHILD in a NEW session, which spawns a GRANDCHILD in YET
# ANOTHER new session.  Each writes its own PID to a file, then sleeps long.
# start_new_session=True at every hop ensures killpg(direct_pgid) misses both
# the child and the grandchild — only parent-link walking finds them.
_TREE_SCRIPT = textwrap.dedent(
    """
    import os, subprocess, sys, time
    child_pid_file, gc_pid_file = sys.argv[1], sys.argv[2]

    grandchild_src = (
        "import os,sys,time\\n"
        "open(sys.argv[1],'w').write(str(os.getpid()))\\n"
        "time.sleep(600)\\n"
    )
    child_src = (
        "import os,subprocess,sys,time\\n"
        "open(sys.argv[1],'w').write(str(os.getpid()))\\n"
        "subprocess.Popen([sys.executable,'-c',sys.argv[3],sys.argv[2]],"
        "start_new_session=True)\\n"
        "time.sleep(600)\\n"
    )
    subprocess.Popen(
        [sys.executable, '-c', child_src, child_pid_file, gc_pid_file, grandchild_src],
        start_new_session=True,
    )
    time.sleep(600)
    """
)


def _spawn_tree():
    tmp = tempfile.mkdtemp(prefix="kg_desc_")
    child_pid_file = os.path.join(tmp, "child.pid")
    gc_pid_file = os.path.join(tmp, "grandchild.pid")
    proc = spawn(
        [sys.executable, "-c", _TREE_SCRIPT, child_pid_file, gc_pid_file],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    child_pid = _read_pid(child_pid_file)
    grandchild_pid = _read_pid(gc_pid_file)
    return proc, child_pid, grandchild_pid


def test_kill_group_reaps_session_detached_descendants():
    proc, child_pid, grandchild_pid = _spawn_tree()
    survivors = [proc.pid, child_pid, grandchild_pid]
    try:
        # Sanity: child and grandchild are in DIFFERENT process groups than the
        # parent — proving killpg(parent_pgid) alone cannot reach them.
        parent_pgid = os.getpgid(proc.pid)
        assert os.getpgid(child_pid) != parent_pgid
        assert os.getpgid(grandchild_pid) != parent_pgid

        kill_group(proc, grace_s=3.0)

        assert _wait_dead(proc.pid), "parent still alive after kill_group"
        assert _wait_dead(child_pid), "session-detached child still alive after kill_group"
        assert _wait_dead(grandchild_pid), (
            "session-detached GRANDCHILD still alive after kill_group "
            "(the orphaned-pytest bug)"
        )
    finally:
        for pid in survivors:
            try:
                os.kill(pid, 9)
            except OSError:
                pass


def test_kill_group_does_not_kill_unrelated_sibling():
    """An unrelated process (NOT a descendant of proc) must survive."""
    sibling = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(600)"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc, child_pid, grandchild_pid = _spawn_tree()
    survivors = [proc.pid, child_pid, grandchild_pid, sibling.pid]
    try:
        kill_group(proc, grace_s=3.0)

        # The whole tree dies...
        assert _wait_dead(grandchild_pid), "grandchild should be reaped"
        # ...but the unrelated sibling is untouched.
        time.sleep(0.5)
        assert _pid_alive(sibling.pid), (
            "unrelated sibling was killed — kill_group over-reached"
        )
    finally:
        for pid in survivors:
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        try:
            sibling.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
