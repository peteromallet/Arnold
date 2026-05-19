"""Tests for multi-repo and multi-tenant cloud spec extensions."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from megaplan.cloud.spec import RepoSpec, load_spec
from megaplan.cloud.template import (
    render_ensure_repo_command,
    render_ensure_repos_block,
    render_entrypoint,
)
from megaplan.types import CliError


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
