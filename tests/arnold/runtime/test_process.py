"""Tests for neutral runtime process primitives."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from typing import Any

import pytest

from arnold.runtime.process import kill_group, spawn, spawn_async


def test_spawn_rejects_shell_true() -> None:
    with pytest.raises(ValueError, match="shell=True"):
        spawn("echo hi", shell=True)


def test_spawn_defaults_to_new_session_and_strips_redundant_setsid(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakePopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    spawn(["python", "-V"], preexec_fn=os.setsid)

    assert captured["args"] == (["python", "-V"],)
    assert captured["kwargs"]["start_new_session"] is True
    assert "preexec_fn" not in captured["kwargs"]


def test_spawn_smoke_returns_completed_process() -> None:
    proc = spawn(
        [sys.executable, "-c", "print('ok')"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(timeout=5)

    assert proc.returncode == 0
    assert stdout.strip() == "ok"
    assert stderr == ""


def test_spawn_async_rejects_shell_true() -> None:
    async def run() -> None:
        with pytest.raises(ValueError, match="shell=True"):
            await spawn_async("echo hi", shell=True)

    asyncio.run(run())


def test_kill_group_uses_term_only_when_escalation_disabled(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    class FakeProc:
        pid = 1234
        returncode = None

    monkeypatch.setattr("arnold.runtime.process.os.getpgid", lambda _pid: 4321)
    monkeypatch.setattr(
        "arnold.runtime.process.os.killpg",
        lambda pgid, sig: calls.append((pgid, sig)),
    )

    kill_group(FakeProc(), escalate=False)

    assert calls == [(4321, signal.SIGTERM)]


def test_kill_group_falls_back_when_pgid_lookup_fails() -> None:
    class FakeProc:
        pid = 1234
        returncode = None

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

    proc = FakeProc()

    def fail_getpgid(_pid: int) -> int:
        raise OSError("no pgid")

    original_getpgid = os.getpgid
    try:
        os.getpgid = fail_getpgid  # type: ignore[method-assign]
        kill_group(proc)
    finally:
        os.getpgid = original_getpgid  # type: ignore[method-assign]

    assert proc.terminated is True
    assert proc.killed is True
