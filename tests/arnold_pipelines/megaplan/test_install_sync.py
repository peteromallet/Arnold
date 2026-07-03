from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from arnold_pipelines.megaplan.cloud.install_sync import (
    apply_install_sync,
    capture_runtime_identity,
)


def _proc(
    command: list[str],
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)


def test_capture_runtime_identity_uses_mocked_git_and_probe(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return _proc(command, stdout="abc123\n")
        if command[:3] == ["git", "branch", "--show-current"]:
            return _proc(command, stdout="editible-install\n")
        if command[:2] == [sys.executable, "-c"]:
            return _proc(
                command,
                stdout=json.dumps(
                    {
                        "python_executable": sys.executable,
                        "package_file": "/workspace/arnold/arnold_pipelines/__init__.py",
                        "package_root": "/workspace/arnold",
                    }
                ),
            )
        raise AssertionError(f"unexpected command: {command}")

    identity = capture_runtime_identity(repo, runner=runner)

    assert identity["git_head"] == "abc123"
    assert identity["git_branch"] == "editible-install"
    assert identity["package_root"] == "/workspace/arnold"
    assert calls[0] == ["git", "rev-parse", "HEAD"]
    assert calls[1] == ["git", "branch", "--show-current"]
    assert calls[2][:2] == [sys.executable, "-c"]


def test_apply_install_sync_emits_applied_event_with_runtime_and_verification_evidence(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    call_index = {"probe": 0}

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return _proc(command, stdout="abc123\n")
        if command[:3] == ["git", "branch", "--show-current"]:
            return _proc(command, stdout="editible-install\n")
        if command[:2] == [sys.executable, "-c"]:
            call_index["probe"] += 1
            package_root = "/workspace/arnold-before" if call_index["probe"] == 1 else "/workspace/arnold-after"
            return _proc(
                command,
                stdout=json.dumps(
                    {
                        "python_executable": sys.executable,
                        "package_file": f"{package_root}/arnold_pipelines/__init__.py",
                        "package_root": package_root,
                    }
                ),
            )
        if command[:4] == [sys.executable, "-m", "pip", "install"]:
            return _proc(command, stdout="installed ok\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    result = apply_install_sync(
        source_root=repo,
        incident_id="inc-500",
        session_id="demo-session",
        root=tmp_path,
        runner=runner,
    )

    assert result["status"] == "applied"
    assert result["returncode"] == 0
    assert result["verification"]["success"] is True
    assert result["verification"]["runtime_changed"] is True
    event = result["event"]
    assert event["kind"] == "incident.install_sync_applied"
    payload = event["payload"]
    assert payload["incident_id"] == "inc-500"
    runtime_identity = payload["evidence"][0]
    assert runtime_identity["kind"] == "runtime_identity"
    assert runtime_identity["before"]["package_root"] == "/workspace/arnold-before"
    assert runtime_identity["after"]["package_root"] == "/workspace/arnold-after"
    command_result = payload["evidence"][1]
    assert command_result["command"].endswith(f"pip install -e {repo}")
    assert command_result["returncode"] == 0
    verification = payload["evidence"][2]
    assert verification["kind"] == "install_sync_verification"
    assert verification["success"] is True


def test_apply_install_sync_emits_failed_event_with_redacted_command_tails(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return _proc(command, stdout="deadbeef\n")
        if command[:3] == ["git", "branch", "--show-current"]:
            return _proc(command, stdout="editible-install\n")
        if command[:2] == [sys.executable, "-c"]:
            return _proc(
                command,
                stdout=json.dumps(
                    {
                        "python_executable": sys.executable,
                        "package_file": "/workspace/arnold/arnold_pipelines/__init__.py",
                        "package_root": "/workspace/arnold",
                    }
                ),
            )
        if command[:4] == [sys.executable, "-m", "pip", "install"]:
            return _proc(
                command,
                returncode=2,
                stdout="export API_TOKEN=supersecret\n",
                stderr="Authorization: Bearer very-secret-token-value\n",
            )
        raise AssertionError(f"unexpected command: {command}")

    result = apply_install_sync(
        source_root=repo,
        incident_id="inc-501",
        session_id="demo-session",
        root=tmp_path,
        runner=runner,
    )

    assert result["status"] == "failed"
    assert result["returncode"] == 2
    assert "supersecret" not in result["stdout_tail"]
    assert "very-secret-token-value" not in result["stderr_tail"]
    event = result["event"]
    assert event["kind"] == "incident.install_sync_failed"
    payload = event["payload"]
    command_result = payload["evidence"][1]
    assert command_result["returncode"] == 2
    assert "***REDACTED***" in command_result["stdout_tail"]
    assert "***REDACTED***" in command_result["stderr_tail"]
    verification = payload["evidence"][2]
    assert verification["success"] is False
    assert verification["observed_git_head"] == "deadbeef"
