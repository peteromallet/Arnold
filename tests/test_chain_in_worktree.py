"""Tests for `megaplan chain start --in-worktree <name>`."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import arnold.pipelines.megaplan as megaplan


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=check
    )


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _write_chain_spec(path: Path, idea: Path) -> None:
    path.write_text(
        f"""\
base_branch: main
milestones:
  - label: m1
    idea: {idea}
driver:
  robustness: full
""",
        encoding="utf-8",
    )


def test_chain_start_in_worktree_reroots_whole_chain(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    idea = repo / "idea.md"
    idea.write_text("do the thing\n", encoding="utf-8")
    spec = repo / "chain.yaml"
    _write_chain_spec(spec, idea)
    seen: dict[str, Any] = {}

    def fake_run_chain(
        spec_path: Path,
        root: Path,
        *,
        no_git_refresh: bool,
        no_push: bool,
        fresh: bool,
        one: bool,
        mode: str = "start",
    ) -> dict[str, Any]:
        seen["spec_path"] = spec_path
        seen["root"] = root
        seen["no_git_refresh"] = no_git_refresh
        seen["no_push"] = no_push
        seen["fresh"] = fresh
        seen["one"] = one
        return {"status": "done", "chain_state": {}}

    monkeypatch.setattr("arnold.pipelines.megaplan.chain.run_chain", fake_run_chain)
    monkeypatch.chdir(repo)

    code = megaplan.main(
        [
            "chain",
            "start",
            "--spec",
            str(spec),
            "--in-worktree",
            "chain-wt",
            "--clean-worktree",
            "--no-git-refresh",
            "--no-push",
            "--one",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "done"

    expected_wt = fake_home / "Documents" / ".megaplan-worktrees" / "chain-wt"
    assert expected_wt.is_dir()
    assert seen == {
        "spec_path": spec.resolve(),
        "root": expected_wt.resolve(),
        "no_git_refresh": True,
        "no_push": True,
        "fresh": False,
        "one": True,
    }
    assert _git(expected_wt, "rev-parse", "HEAD").stdout.strip() == head
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    assert _git(repo, "status", "--porcelain").stdout.strip() == "?? chain.yaml\n?? idea.md"


def test_chain_start_fresh_in_worktree_recreates_existing_target(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    first_head = _init_repo(repo)
    idea = repo / "idea.md"
    idea.write_text("do the thing\n", encoding="utf-8")
    spec = repo / "chain.yaml"
    _write_chain_spec(spec, idea)
    target = fake_home / "Documents" / ".megaplan-worktrees" / "chain-wt"
    _git(repo, "worktree", "add", "-b", "chain-wt", str(target), first_head)
    (target / "STALE").write_text("old run\n", encoding="utf-8")
    seen: dict[str, Any] = {}

    def fake_run_chain(
        spec_path: Path,
        root: Path,
        *,
        no_git_refresh: bool,
        no_push: bool,
        fresh: bool,
        one: bool,
        mode: str = "start",
    ) -> dict[str, Any]:
        del no_git_refresh, no_push, one, mode
        seen["spec_path"] = spec_path
        seen["root"] = root
        seen["fresh"] = fresh
        return {"status": "done", "chain_state": {}}

    monkeypatch.setattr("megaplan.chain.run_chain", fake_run_chain)
    monkeypatch.chdir(repo)

    code = megaplan.main(
        [
            "chain",
            "start",
            "--spec",
            str(spec),
            "--in-worktree",
            "chain-wt",
            "--fresh",
            "--no-git-refresh",
            "--no-push",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "done"
    assert seen == {
        "spec_path": spec.resolve(),
        "root": target.resolve(),
        "fresh": True,
    }
    assert target.is_dir()
    assert not (target / "STALE").exists()
    assert _git(target, "rev-parse", "HEAD").stdout.strip() == first_head


def test_chain_in_worktree_rejects_project_dir(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    idea = repo / "idea.md"
    idea.write_text("do the thing\n", encoding="utf-8")
    spec = repo / "chain.yaml"
    _write_chain_spec(spec, idea)
    monkeypatch.chdir(repo)

    code = megaplan.main(
        [
            "chain",
            "start",
            "--spec",
            str(spec),
            "--project-dir",
            str(repo),
            "--in-worktree",
            "chain-wt",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["error"] == "invalid_args"
    assert "either --project-dir or --in-worktree" in payload["message"]
    assert not (fake_home / "Documents" / ".megaplan-worktrees" / "chain-wt").exists()
