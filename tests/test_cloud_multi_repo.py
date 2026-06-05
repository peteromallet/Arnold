"""Tests for multi-repo and multi-tenant cloud spec extensions."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from arnold.pipelines.megaplan.cloud.cli import _ensure_repo_checkout, _ensure_repo_command
from arnold.pipelines.megaplan.cloud.spec import RepoSpec, load_spec
from arnold.pipelines.megaplan.cloud.template import (
    render_ensure_repo_command,
    render_ensure_repos_block,
    render_entrypoint,
)
from arnold.pipelines.megaplan.types import CliError


def _base_spec(*, mode: str = "idle") -> dict[str, object]:
    spec: dict[str, object] = {
        "provider": "railway",
        "repo": {
            "url": "https://github.com/example/app.git",
            "branch": "main",
            "workspace": "/workspace/app",
        },
        "agents": {"default": "codex"},
        "codex": {"model": "gpt-5.4", "reasoning": "high"},
        "mode": mode,
        "megaplan": {"ref": "main"},
        "resources": {"volume": "agent-volume", "port": 8080},
        "secrets": ["OPENAI_API_KEY"],
    }
    if mode == "chain":
        spec["chain"] = {"spec": "/workspace/app/chain.yaml"}
    return spec


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "cloud.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_extra_repos_default_empty(tmp_path: Path) -> None:
    spec = load_spec(_write(tmp_path, _base_spec()))
    assert spec.extra_repos == ()


def test_extra_repos_parsed_and_preserved_in_order(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {
            "url": "https://github.com/example/worker.git",
            "branch": "main",
            "workspace": "/workspace/worker",
        },
        {
            "url": "https://github.com/example/agent.git",
            "branch": "release/2026",
            "workspace": "/workspace/agent",
        },
    ]
    spec = load_spec(_write(tmp_path, payload))
    assert len(spec.extra_repos) == 2
    assert spec.extra_repos[0].url == "https://github.com/example/worker.git"
    assert spec.extra_repos[0].workspace == "/workspace/worker"
    assert spec.extra_repos[1].branch == "release/2026"


def test_extra_repos_rejects_workspace_collision_with_primary(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {
            "url": "https://github.com/example/dup.git",
            "branch": "main",
            "workspace": "/workspace/app",  # same as primary
        }
    ]
    with pytest.raises(CliError, match="collides"):
        load_spec(_write(tmp_path, payload))


def test_extra_repos_rejects_internal_workspace_collision(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {"url": "https://github.com/a/x.git", "branch": "main", "workspace": "/workspace/x"},
        {"url": "https://github.com/b/x.git", "branch": "main", "workspace": "/workspace/x"},
    ]
    with pytest.raises(CliError, match="collides"):
        load_spec(_write(tmp_path, payload))


def test_extra_repos_rejects_relative_workspace(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {"url": "https://github.com/a/x.git", "branch": "main", "workspace": "relative/path"},
    ]
    with pytest.raises(CliError, match="absolute POSIX"):
        load_spec(_write(tmp_path, payload))


def test_extra_repos_rejects_non_list(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = {"url": "https://github.com/a/x.git"}
    with pytest.raises(CliError, match="must be a list"):
        load_spec(_write(tmp_path, payload))


def test_chain_session_default(tmp_path: Path) -> None:
    spec = load_spec(_write(tmp_path, _base_spec()))
    assert spec.chain_session == "megaplan-chain"


def test_chain_session_override(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["chain_session"] = "slot-first"
    spec = load_spec(_write(tmp_path, payload))
    assert spec.chain_session == "slot-first"


def test_chain_session_rejects_empty(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["chain_session"] = ""
    with pytest.raises(CliError, match="chain_session"):
        load_spec(_write(tmp_path, payload))


def test_render_ensure_repos_block_includes_primary_and_extras(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {"url": "https://github.com/example/worker.git", "branch": "main", "workspace": "/workspace/worker"},
        {"url": "https://github.com/example/agent.git", "branch": "develop", "workspace": "/workspace/agent"},
    ]
    spec = load_spec(_write(tmp_path, payload))
    block = render_ensure_repos_block(spec)
    # Primary first
    assert block.index("/workspace/app") < block.index("/workspace/worker")
    assert block.index("/workspace/worker") < block.index("/workspace/agent")
    # Each repo has its own clone-if-missing guard
    assert block.count("if [ ! -d") == 3
    # Each branch reflected
    assert "--branch main" in block
    assert "--branch develop" in block


def test_render_ensure_repos_block_single_repo_matches_legacy_behavior(tmp_path: Path) -> None:
    spec = load_spec(_write(tmp_path, _base_spec()))
    block = render_ensure_repos_block(spec)
    legacy = render_ensure_repo_command(spec.repo)
    assert block == legacy


def test_entrypoint_renders_multi_repo_block(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {"url": "https://github.com/example/worker.git", "branch": "main", "workspace": "/workspace/worker"},
    ]
    spec = load_spec(_write(tmp_path, payload))
    rendered = render_entrypoint(spec)
    assert "/workspace/app" in rendered
    assert "/workspace/worker" in rendered
    assert "https://github.com/example/worker.git" in rendered


# --- chain-launch path: cli._ensure_repo_checkout must clone every repo ----
#
# The container entrypoint clones primary + extras at boot, but that only runs
# once per `cloud deploy`. A `megaplan cloud chain` launched against a
# container that pre-dates an `extra_repos` edit would otherwise silently
# leave siblings missing on the persistent volume — blocking any milestone
# that depends on them. These tests pin the behavior of the chain-launch
# hook so the regression cannot reappear.


class _RecordingProvider:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.commands: list[str] = []
        self.returncode = returncode
        self.stderr = stderr

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return subprocess.CompletedProcess(
            args=["ssh"], returncode=self.returncode, stdout="", stderr=self.stderr
        )


def test_ensure_repo_command_emits_block_covering_primary_and_each_extra(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {
            "url": "https://github.com/example/worker.git",
            "branch": "release",
            "workspace": "/workspace/worker",
        },
        {
            "url": "https://github.com/example/sibling.git",
            "branch": "trunk",
            "workspace": "/workspace/sibling",
        },
    ]
    spec = load_spec(_write(tmp_path, payload))

    command = _ensure_repo_command(spec)

    assert command == render_ensure_repos_block(spec)
    assert render_ensure_repo_command(spec.repo) in command
    primary_idx = command.index(render_ensure_repo_command(spec.repo))
    last_idx = primary_idx
    for extra in spec.extra_repos:
        snippet = render_ensure_repo_command(extra)
        assert snippet in command
        idx = command.index(snippet)
        assert idx > last_idx, "extras must follow primary in declared order"
        last_idx = idx


def test_ensure_repo_checkout_ssh_execs_single_block_with_every_repo(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {
            "url": "https://github.com/example/worker.git",
            "branch": "release",
            "workspace": "/workspace/worker",
        },
        {
            "url": "https://github.com/example/orchestrator.git",
            "branch": "main",
            "workspace": "/workspace/orchestrator",
        },
    ]
    spec = load_spec(_write(tmp_path, payload))
    provider = _RecordingProvider()

    _ensure_repo_checkout(spec, provider, relay=False)

    assert len(provider.commands) == 1, "ensure_repo_checkout must dispatch exactly one SSH call"
    sent = provider.commands[0]
    for repo in (spec.repo, *spec.extra_repos):
        assert repo.workspace in sent
        assert repo.url in sent
        assert repo.branch in sent


def test_ensure_repo_checkout_failure_message_lists_every_repo(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["extra_repos"] = [
        {
            "url": "https://github.com/example/worker.git",
            "branch": "release",
            "workspace": "/workspace/worker",
        },
    ]
    spec = load_spec(_write(tmp_path, payload))
    provider = _RecordingProvider(returncode=42, stderr="boom\n")

    with pytest.raises(CliError) as exc:
        _ensure_repo_checkout(spec, provider, relay=False)

    message = exc.value.message
    assert "exit 42" in message
    assert spec.repo.url in message
    for extra in spec.extra_repos:
        assert extra.url in message
