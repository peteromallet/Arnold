"""Tests for the base→origin PUSH leg and sync_policy gate (design §6 github_sync.py row)."""

from __future__ import annotations

import subprocess
import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import github_sync
from arnold_pipelines.megaplan.cloud.github_sync import push_base_to_origin, sync_policy_gate

_ORIGIN_URL = "git@github.com:acme/arnold.git"
_BRANCH = "base/editable-install"


def _proc(
    command: list[str],
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)


def _runner_for(repo: Path, *, push_returncode: int = 0, push_stderr: str = "") -> Any:
    """Fake subprocess.run dispatching on the git subcommand."""
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[3] == "push":
            return _proc(command, stderr=push_stderr, returncode=push_returncode)
        if command[3:5] == ["rev-parse", "--is-inside-work-tree"]:
            return _proc(command, stdout="true\n")
        if command[3:5] == ["rev-parse", "--verify"]:
            return _proc(command, stdout="abc123\n")
        raise AssertionError(f"unexpected command: {command}")

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


def test_sync_policy_gate_truth_table() -> None:
    assert sync_policy_gate(None) == (True, "no_policy")
    assert sync_policy_gate({"enabled": False}) == (False, "sync_policy_disabled")
    assert sync_policy_gate("disabled") == (False, "sync_policy_disabled")
    assert sync_policy_gate({"enabled": True}) == (True, "sync_policy_enabled")
    assert sync_policy_gate("enabled") == (True, "sync_policy_enabled")
    # Any other policy value is treated as enabled (re-enable switch).
    assert sync_policy_gate("push-on-promote") == (True, "sync_policy_enabled")


def test_push_base_to_origin_dry_run_returns_command_without_executing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("dry_run must not execute git")

    monkeypatch.setattr(github_sync.subprocess, "run", boom)

    result = push_base_to_origin(
        repo_root=tmp_path,
        origin_url=_ORIGIN_URL,
        branch=_BRANCH,
        commit_message="sync base to origin",
        dry_run=True,
    )

    assert result["status"] == "would_push"
    assert result["dry_run"] is True
    assert result["branch"] == _BRANCH
    assert result["origin_url"] == _ORIGIN_URL
    assert result["command"][:4] == ["git", "-C", str(tmp_path), "push"]
    assert result["command"][-2:] == [_ORIGIN_URL, _BRANCH]
    assert result["command_text"] == " ".join(result["command"])


def test_push_base_to_origin_rejects_non_fast_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    runner = _runner_for(
        repo,
        push_returncode=1,
        push_stderr="! [rejected]  base/editable-install -> base/editable-install (non-fast-forward)\n",
    )
    monkeypatch.setattr(github_sync.subprocess, "run", runner)

    result = push_base_to_origin(
        repo_root=repo,
        origin_url=_ORIGIN_URL,
        branch=_BRANCH,
        commit_message="sync base to origin",
    )

    assert result["status"] == "rejected"
    assert result["reason"] == "non_fast_forward"
    assert "rejected" in result["stderr_tail"]
    assert "non-fast-forward" in result["stderr_tail"]


def test_push_base_to_origin_success_returns_from_to_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    runner = _runner_for(repo)
    monkeypatch.setattr(github_sync.subprocess, "run", runner)

    result = push_base_to_origin(
        repo_root=repo,
        origin_url=_ORIGIN_URL,
        branch=_BRANCH,
        commit_message="sync base to origin",
    )

    assert result["status"] == "pushed"
    assert result["from_sha"] == "abc123"
    assert result["to_sha"] == "abc123"
    assert result["branch"] == _BRANCH
    assert result["origin_url"] == _ORIGIN_URL
    assert result["commit_message"] == "sync base to origin"
    assert result["dry_run"] is False


def test_push_base_to_origin_reports_missing_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[3:5] == ["rev-parse", "--is-inside-work-tree"]:
            return _proc(command, stdout="true\n")
        if command[3:5] == ["rev-parse", "--verify"]:
            return _proc(command, stderr="fatal: Needed a single revision\n", returncode=128)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(github_sync.subprocess, "run", runner)

    result = push_base_to_origin(
        repo_root=repo,
        origin_url=_ORIGIN_URL,
        branch=_BRANCH,
        commit_message="sync base to origin",
    )

    assert result["status"] == "error"
    assert result["reason"] == "branch_missing"
    assert result["branch"] == _BRANCH


def test_push_base_to_origin_reports_non_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "not-a-repo"
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[3:5] == ["rev-parse", "--is-inside-work-tree"]:
            return _proc(command, stderr="fatal: not a git repository\n", returncode=128)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(github_sync.subprocess, "run", runner)

    result = push_base_to_origin(
        repo_root=repo,
        origin_url=_ORIGIN_URL,
        branch=_BRANCH,
        commit_message="sync base to origin",
    )

    assert result["status"] == "error"
    assert result["reason"] == "not_a_git_repo"


def test_push_base_to_origin_redacts_token_bearing_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A credential-bearing origin URL is NEVER returned raw (finding #5)."""
    token_url = "https://git-user:ghp_1234567890abcdef@github.com/acme/arnold.git"
    runner = _runner_for(tmp_path / "repo")
    monkeypatch.setattr(github_sync.subprocess, "run", runner)

    result = push_base_to_origin(
        repo_root=tmp_path / "repo",
        origin_url=token_url,
        branch=_BRANCH,
        commit_message="sync base to origin",
    )

    assert "ghp_1234567890abcdef" not in json.dumps(result)
    assert "git-user:" not in result["origin_url"]
    assert "ghp_1234567890abcdef" not in result["command_text"]
    assert "***@" in result["command_text"]
    # The success path returns no raw command list; command_text is redacted.


def test_push_base_to_origin_redacts_ssh_userinfo_scheme_agnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ssh://user:secret@host URLs are redacted too (finding #5 delta)."""
    ssh_url = "ssh://deploy:supersecret@github.com:2222/acme/arnold.git"
    runner = _runner_for(tmp_path / "repo")
    monkeypatch.setattr(github_sync.subprocess, "run", runner)

    result = push_base_to_origin(
        repo_root=tmp_path / "repo",
        origin_url=ssh_url,
        branch=_BRANCH,
        commit_message="sync base to origin",
    )

    assert "supersecret" not in json.dumps(result)
    assert "deploy:" not in result["origin_url"]
    assert "***@" in result["origin_url"]
    assert "***@" in result["command_text"]


def test_push_base_to_origin_redacts_stderr_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    runner = _runner_for(
        repo,
        push_returncode=1,
        push_stderr=(
            "fatal: could not read Username for 'https://github.com': "
            "terminal prompts disabled\nremote: HTTP Basic: access denied "
            "KEY=sekrit123 Token=abc456Bearer sk-abcdefghijklmnopqrst\n"
        ),
    )
    monkeypatch.setattr(github_sync.subprocess, "run", runner)

    result = push_base_to_origin(
        repo_root=repo,
        origin_url=_ORIGIN_URL,
        branch=_BRANCH,
        commit_message="sync base to origin",
    )

    assert result["status"] == "rejected"
    assert "sekrit123" not in result["stderr_tail"]
    assert "abc456" not in result["stderr_tail"]
    assert "sk-abcdefghijklmnopqrst" not in result["stderr_tail"]
    assert "<redacted>" in result["stderr_tail"]
