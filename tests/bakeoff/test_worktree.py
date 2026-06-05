import json
import subprocess
from pathlib import Path

from arnold.pipelines.megaplan.bakeoff.worktree import capture_base_sha, create_worktree, mark_crashed, remove_worktree


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")


def test_worktree_lifecycle_detached_outside_repo_and_crash_marker(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    target = tmp_path / ".megaplan-worktrees" / "exp-1" / "apex"
    branches_before = _git(repo, "branch", "--list").stdout.strip()

    create_worktree(repo, target, capture_base_sha(repo))

    assert target.exists()
    assert not target.resolve().is_relative_to(repo.resolve())
    assert subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=target).returncode != 0
    assert _git(repo, "branch", "--list").stdout.strip() == branches_before

    mark_crashed(target, "boom")
    marker = json.loads((target / "BAKEOFF_CRASHED").read_text(encoding="utf-8"))
    assert marker["reason"] == "boom"
    assert marker["pid"]
    assert marker["ts"]

    remove_worktree(target, force=True)
    assert not target.exists()
    assert not target.parent.exists()
