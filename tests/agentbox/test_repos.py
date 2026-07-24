from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agentbox.config import AgentBoxConfig
from agentbox.repos import (
    AgentBoxRepoError,
    AgentBoxRepoNotFound,
    get_repo,
    list_repo_statuses,
    list_repos,
    register_repo,
    repo_status,
    repos_registry_path,
)


def test_register_repo_persists_and_loads_canonical_checkout(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    repo = _init_repo(config.repos_root / "app")

    registered = register_repo(config, "app", path=repo, default_ref="main")
    loaded = get_repo(config, "app")
    raw = json.loads(repos_registry_path(config).read_text(encoding="utf-8"))

    assert registered == loaded
    assert loaded.path == repo.resolve()
    assert loaded.default_ref == "main"
    assert list_repos(config) == (registered,)
    assert raw["repos"][0]["name"] == "app"
    assert raw["repos"][0]["path"] == str(repo.resolve())


def test_register_repo_rejects_path_outside_repos_root(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    repo = _init_repo(tmp_path / "elsewhere" / "app")

    with pytest.raises(AgentBoxRepoError, match="under repos_root"):
        register_repo(config, "app", path=repo)


def test_register_repo_rejects_git_worktree_checkout(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    canonical = _init_repo(config.repos_root / "canonical")
    linked = config.repos_root / "linked"
    _git(canonical, "worktree", "add", str(linked))

    with pytest.raises(AgentBoxRepoError, match="normal checkout"):
        register_repo(config, "linked", path=linked)


def test_repo_status_reports_invalid_registered_checkout_without_deleting(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    repo = _init_repo(config.repos_root / "app")
    register_repo(config, "app", path=repo)
    (repo / ".git").rename(repo / ".git-moved")

    status = repo_status(config, "app")

    assert status.valid is False
    assert status.reason is not None
    assert "normal checkout" in status.reason
    assert status.to_dict()["name"] == "app"


def test_list_repo_statuses_are_cli_ready_and_sorted(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    app = _init_repo(config.repos_root / "app")
    infra = _init_repo(config.repos_root / "infra")
    register_repo(config, "infra", path=infra, default_ref="main", remote_url="git@example/infra")
    register_repo(config, "app", path=app)

    statuses = list_repo_statuses(config)

    assert [status.name for status in statuses] == ["app", "infra"]
    assert statuses[0].valid is True
    assert statuses[0].head_sha
    assert statuses[1].to_dict()["remote_url"] == "git@example/infra"


def test_get_repo_raises_for_unknown_name(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")

    with pytest.raises(AgentBoxRepoNotFound):
        get_repo(config, "missing")


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agentbox@example.test")
    _git(path, "config", "user.name", "AgentBox Tests")
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "initial")
    return path


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()
