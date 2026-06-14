"""Tests for megaplan.runtime.process — spawn, spawn_async, kill_group."""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import tempfile
import time

import pytest

from arnold.pipelines.megaplan.runtime.process import kill_group, spawn, spawn_async


# ---------------------------------------------------------------------------
# (a) spawn sets start_new_session=True by default
# ---------------------------------------------------------------------------

def test_spawn_sets_start_new_session(monkeypatch):
    captured: dict = {}
    _real_popen = subprocess.Popen

    def fake_popen(*args, **kwargs):
        captured.update(kwargs)
        return _real_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    proc = spawn(["true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
    assert captured.get("start_new_session") is True


# ---------------------------------------------------------------------------
# (b) shell=True raises ValueError on both sync and async paths
# ---------------------------------------------------------------------------

def test_spawn_shell_true_raises():
    with pytest.raises(ValueError, match="shell=True"):
        spawn(["echo", "hi"], shell=True)


def test_spawn_async_shell_true_raises():
    async def _run():
        with pytest.raises(ValueError, match="shell=True"):
            await spawn_async("echo", "hi", shell=True)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# (c) Real grandchild reaping — sync Popen handle
# ---------------------------------------------------------------------------

def test_kill_group_reaps_grandchild_sync():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pid", delete=False) as f:
        pid_file = f.name

    proc = spawn(
        ["/bin/sh", "-c", f"sleep 300 & echo $! > {pid_file}; wait"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait up to 5 s for grandchild PID to appear in the file.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            content = open(pid_file).read().strip()
            if content:
                break
        except OSError:
            pass
        time.sleep(0.05)

    try:
        grandchild_pid = int(open(pid_file).read().strip())
    finally:
        try:
            os.unlink(pid_file)
        except OSError:
            pass

    kill_group(proc, grace_s=3.0)

    # Poll until grandchild is confirmed dead (max 5 s).
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            os.kill(grandchild_pid, 0)
        except ProcessLookupError:
            return  # grandchild dead — test passes
        time.sleep(0.1)

    pytest.fail(f"Grandchild PID {grandchild_pid} still alive after kill_group")


# ---------------------------------------------------------------------------
# (d) Real grandchild reaping — asyncio subprocess handle
# ---------------------------------------------------------------------------

def test_kill_group_reaps_grandchild_async():
    async def _run() -> tuple[bool, int]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pid", delete=False) as f:
            pid_file = f.name

        proc = await spawn_async(
            "/bin/sh",
            "-c",
            f"sleep 300 & echo $! > {pid_file}; wait",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                content = open(pid_file).read().strip()
                if content:
                    break
            except OSError:
                pass
            await asyncio.sleep(0.05)

        try:
            grandchild_pid = int(open(pid_file).read().strip())
        finally:
            try:
                os.unlink(pid_file)
            except OSError:
                pass

        # kill_group is sync — calling it inside asyncio.run blocks the loop for
        # at most grace_s, but OS signal delivery still works.
        kill_group(proc, grace_s=3.0)

        deadline = time.monotonic() + 5.0
        dead = False
        while time.monotonic() < deadline:
            try:
                os.kill(grandchild_pid, 0)
            except ProcessLookupError:
                dead = True
                break
            await asyncio.sleep(0.05)

        return dead, grandchild_pid

    dead, grandchild_pid = asyncio.run(_run())
    assert dead, f"Grandchild PID {grandchild_pid} still alive after kill_group (async handle)"


# ---------------------------------------------------------------------------
# (e) escalate=False: SIGTERM sent, SIGKILL never sent, returns immediately
# ---------------------------------------------------------------------------

def test_kill_group_escalate_false_no_sigkill(monkeypatch):
    sigkill_sent: list[int] = []
    sigterm_sent: list[int] = []

    def fake_killpg(pgid: int, sig: int) -> None:
        if sig == signal.SIGKILL:
            sigkill_sent.append(pgid)
        elif sig == signal.SIGTERM:
            sigterm_sent.append(pgid)
        # Do not actually deliver the signal; process stays alive for cleanup.

    monkeypatch.setattr(os, "killpg", fake_killpg)

    proc = subprocess.Popen(
        ["sleep", "100"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        t0 = time.monotonic()
        kill_group(proc, grace_s=10.0, escalate=False)
        elapsed = time.monotonic() - t0
    finally:
        proc.kill()
        proc.wait()

    assert sigterm_sent, "SIGTERM must be sent when escalate=False"
    assert not sigkill_sent, "SIGKILL must NOT be sent when escalate=False"
    assert elapsed < 1.0, f"escalate=False must return without waiting grace_s; took {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# (f) SD1 setsid-collision: spawn(preexec_fn=os.setsid, start_new_session=True)
#     strips the redundant preexec_fn and must not raise EPERM.
# ---------------------------------------------------------------------------

def test_spawn_strips_setsid_collision():
    proc = spawn(
        ["sleep", "0"],
        preexec_fn=os.setsid,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc.wait()
    assert proc.returncode is not None, "Process should have exited cleanly (no EPERM)"
