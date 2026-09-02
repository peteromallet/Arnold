"""Focused launcher/fan custody boundaries for NBF-04."""
from __future__ import annotations

import signal
import subprocess
import sys
import asyncio
import os
from pathlib import Path

import pytest


LAUNCHER_DIR = Path(__file__).resolve().parents[3] / "arnold_pipelines/megaplan/skills/subagent-launcher"
if str(LAUNCHER_DIR) not in sys.path:
    sys.path.insert(0, str(LAUNCHER_DIR))
import fan  # noqa: E402
import launch_omp_agent as launcher  # noqa: E402


def test_muse_model_suffix_translates_to_high_thinking() -> None:
    selector, thinking = launcher._translate_model(
        "omp:openrouter/meta/muse-spark-1.3-contributor:high"
    )
    assert selector == "openrouter/meta/muse-spark-1.3-contributor"
    assert thinking == "high"


def test_muse_model_suffix_builds_explicit_high_flag() -> None:
    command = launcher.build_omp_command(
        omp_bin="omp",
        model="openrouter/meta/muse-spark-1.3-contributor",
        thinking="high",
        toolsets="file,web,terminal",
    )
    assert "--model" in command
    assert "openrouter/meta/muse-spark-1.3-contributor" in command
    assert command[command.index("--thinking") + 1] == "high"


class _TimedOutChild:
    pid = 9123
    returncode = None

    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired("child", timeout)

    def poll(self):
        return None


def test_launcher_timeout_with_incomplete_context_is_zero_signal(monkeypatch):
    child = _TimedOutChild()
    calls = []
    monkeypatch.setenv("ARNOLD_WORKER_EXECUTION_CONTEXT", "{}")
    monkeypatch.delenv("ARNOLD_WORKER_IDENTITY", raising=False)
    monkeypatch.delenv("ARNOLD_INCIDENT_LEDGER_ROOT", raising=False)
    monkeypatch.setattr(launcher, "_canonical_group_signal", lambda *args: calls.append(args))

    launcher._terminate_timed_out_child(child, timeout_source="test")

    assert calls == []


def test_standalone_launcher_timeout_is_typed_unresolved_and_zero_signal(monkeypatch):
    child = _TimedOutChild()
    calls = []
    monkeypatch.delenv("ARNOLD_WORKER_EXECUTION_CONTEXT", raising=False)
    monkeypatch.delenv("ARNOLD_WORKER_IDENTITY", raising=False)
    monkeypatch.delenv("ARNOLD_INCIDENT_LEDGER_ROOT", raising=False)
    monkeypatch.setattr(launcher, "_canonical_group_signal", lambda *args: calls.append(args))

    result = launcher._terminate_timed_out_child(child, timeout_source="standalone-test")

    assert result["kind"] == "unresolved_launch"
    assert result["launch_state"] == "ambiguous"
    assert calls == []
    assert child.returncode is None


def test_launcher_popen_owns_a_new_session(monkeypatch):
    captured = {}

    class Child:
        pid = 77
        returncode = 0

        def wait(self, timeout=None):
            return 0

    def fake_popen(*args, **kwargs):
        captured.update(kwargs)
        return Child()

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/bin/true")
    assert launcher.run(query="hello", toolsets="", omp_bin="true") == 0
    assert captured["start_new_session"] is True


def test_launcher_process_start_uses_canonical_unprefixed_identity():
    identity = launcher._process_start_identity(os.getpid())
    assert identity
    assert not identity.startswith("proc-start:")
    assert "proc-start:proc-start:" not in identity


def test_fan_missing_context_does_not_signal(monkeypatch):
    calls = []
    monkeypatch.setattr(fan, "_canonical_group_signal", lambda *args: calls.append(args))
    env = {"ARNOLD_WORKER_EXECUTION_CONTEXT": "{}"}
    assert fan._kill_tree(9123, signal.SIGTERM, environment=env) is False
    assert calls == []


def test_fan_kill_private_adapter_without_ledger_does_not_signal(monkeypatch):
    import fan_kill

    assert fan_kill._signal(9123, signal.SIGTERM, ledger=None) is False


def test_fan_kill_main_requires_explicit_authority_context(monkeypatch, tmp_path):
    import fan_kill

    monkeypatch.setattr(
        sys,
        "argv",
        ["fan_kill.py", "--output-dir", str(tmp_path)],
    )
    assert fan_kill.main() == 78


def test_fan_kill_rejects_noncanonical_ledger_root(monkeypatch, tmp_path):
    import fan_kill

    workspace = tmp_path / "workspace"
    output = workspace / "fan-out"
    marker = workspace / "marker.json"
    output.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fan_kill.py",
            "--output-dir", str(output),
            "--workspace", str(workspace),
            "--ledger-root", str(tmp_path / "wrong-ledger"),
            "--marker", str(marker),
            "--session", "demo",
        ],
    )
    assert fan_kill.main() == 78


def test_fan_kill_target_snapshot_rejects_pid_replacement(monkeypatch, tmp_path):
    import fan_kill

    pidfile = tmp_path / "_fan.pid"
    pidfile.write_text("41\n", encoding="utf-8")
    monkeypatch.setattr(fan_kill, "_read_cmdline", lambda pid: "python fan.py")
    monkeypatch.setattr(fan_kill.os, "getpgid", lambda pid: 401)
    starts = iter(["start-a", "start-b"])
    monkeypatch.setattr(fan_kill, "_process_start_identity", lambda pid: next(starts))
    first = fan_kill._target_snapshot(pidfile)
    with pytest.raises(ValueError, match="incarnation changed"):
        fan_kill._target_snapshot(
            pidfile,
            expected_pid=first[0],
            expected_group=first[1],
            expected_start=first[2],
            expected_cmdline=first[3],
        )


def test_resident_worker_missing_wbc_context_returns_without_waiting(monkeypatch):
    from arnold_pipelines.megaplan.resident import agent_loop

    class Process:
        pid = 9911
        returncode = None

        async def wait(self):
            raise AssertionError("missing WBC context must not wait forever")

    monkeypatch.setattr(agent_loop, "signal_managed_process", lambda *args, **kwargs: False)
    asyncio.run(agent_loop._terminate_process_group(Process()))
