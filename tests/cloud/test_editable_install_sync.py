from __future__ import annotations

import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud.cli import (
    _megaplan_refresh_command,
    _sync_launch_head_to_editable_install_branch,
)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if check:
        assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_cloud_refresh_uses_editible_install_branch() -> None:
    command = _megaplan_refresh_command()

    assert "REF=editible-install" in command
    assert 'git -C "$SRC" fetch origin "$REF"' in command
    assert 'git -C "$SRC" checkout "$REF"' in command
    assert 'git -C "$SRC" pull --ff-only origin "$REF"' in command


def test_cloud_chain_sync_merges_launch_head_into_editible_install(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    verify = tmp_path / "verify"

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(repo))
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "branch", "-M", "main")
    _git(repo, "push", "-u", "origin", "main")

    _git(repo, "checkout", "-b", "editible-install")
    editable_only = _commit(repo, "editable.txt", "keep\n", "editable branch work")
    _git(repo, "push", "-u", "origin", "editible-install")

    _git(repo, "checkout", "-b", "feature", "main")
    launch_head = _commit(repo, "feature.txt", "ship\n", "feature work")

    result = _sync_launch_head_to_editable_install_branch(repo)

    assert result["status"] == "pushed"
    assert result["branch"] == "editible-install"
    assert result["launch_head"] == launch_head
    assert result["editable_head_before"] == editable_only

    _git(tmp_path, "clone", "--branch", "editible-install", str(origin), str(verify))
    assert (verify / "editable.txt").read_text(encoding="utf-8") == "keep\n"
    assert (verify / "feature.txt").read_text(encoding="utf-8") == "ship\n"
    assert (
        _git(verify, "merge-base", "--is-ancestor", launch_head, "HEAD").returncode
        == 0
    )
