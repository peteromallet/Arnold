import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.bakeoff import lifecycle as lifecycle_mod
from arnold_pipelines.megaplan.bakeoff import worktree as worktree_mod
from arnold_pipelines.megaplan.bakeoff.worktree import (
    WorktreeDeleteRefused,
    capture_base_sha,
    create_worktree,
    mark_crashed,
    remove_worktree,
)
from arnold_pipelines.megaplan.types import CliError


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


def _sandbox_census_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point every reference-census store at empty sandbox dirs (hermetic CLEAR)."""
    base = tmp_path / "census-stores"
    for key, name in (
        ("ARNOLD_BASE_DIR", "workspace"),
        ("ARNOLD_RUNTIME_MANIFEST_DIR", "manifests"),
        ("ARNOLD_REFERENCE_CHAIN_STORE", "chains"),
        ("ARNOLD_REFERENCE_MARKER_STORE", "markers"),
        ("ARNOLD_REFERENCE_SCHEDULE_STORES", "schedules"),
        ("ARNOLD_REFERENCE_REPAIR_QUEUE", "repair"),
        ("ARNOLD_REFERENCE_LEASE_STORE", "leases"),
        ("ARNOLD_REFERENCE_PLAN_LEASE_ROOT", "plan-leases"),
        ("ARNOLD_REFERENCE_MANAGED_RUN_STORE", "managed-runs"),
        ("ARNOLD_REFERENCE_STATUS_DIR", "status"),
        ("ARNOLD_REFERENCE_OPS_STORE", "ops"),
    ):
        monkeypatch.setenv(key, str(base / name))


def test_worktree_lifecycle_detached_outside_repo_and_crash_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox_census_env(monkeypatch, tmp_path)
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


@pytest.mark.parametrize("verdict", ["REFERENCED", "DANGLING", "UNKNOWN"])
def test_remove_worktree_refused_when_census_not_clear(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, verdict: str
) -> None:
    """G6 finding 3: non-CLEAR census refuses — zero git worktree remove."""
    target = tmp_path / "wt"
    target.mkdir(parents=True)
    git_calls: list[list[str]] = []
    monkeypatch.setattr(
        worktree_mod,
        "_git",
        lambda repo, args: git_calls.append(args)
        or subprocess.CompletedProcess(args=[], returncode=0),
    )
    monkeypatch.setattr(
        worktree_mod,
        "reference_census_verdict",
        lambda t, v=verdict: (v, [f"test {v}"]),
    )

    with pytest.raises(CliError) as excinfo:
        remove_worktree(target, force=True)

    assert excinfo.value.code == "bakeoff_worktree_delete_refused"
    assert git_calls == []  # not even `git worktree list` — zero worktree remove
    assert target.exists()  # nothing deleted


def test_remove_worktree_proceeds_when_census_clear(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G6 finding 3: CLEAR census proceeds — `git worktree remove` runs."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    target = tmp_path / ".megaplan-worktrees" / "exp-1" / "apex"
    create_worktree(repo, target, capture_base_sha(repo))
    assert target.exists()

    git_calls: list[list[str]] = []
    real_git = worktree_mod._git
    monkeypatch.setattr(
        worktree_mod,
        "_git",
        lambda r, args: (git_calls.append(args), real_git(r, args))[1],
    )
    monkeypatch.setattr(worktree_mod, "reference_census_verdict", lambda t: ("CLEAR", []))

    remove_worktree(target, force=True)

    assert not target.exists()
    assert any(args[0] == "worktree" and "remove" in args for args in git_calls)


def _profile_record(worktree: Path) -> dict:
    return {"name": "p1", "worktree": str(worktree)}


def _git_failure_remove_worktree(target: Path, force: bool = True) -> None:
    raise CliError("bakeoff_worktree_failed", "git boom")


@pytest.mark.parametrize("verdict", ["REFERENCED", "DANGLING", "UNKNOWN"])
def test_abandon_rmtree_fallback_refused_when_census_not_clear(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, verdict: str
) -> None:
    """G6 finding 3: the raw rmtree fallback is censused — non-CLEAR refuses."""
    target = tmp_path / "wt"
    target.mkdir()
    rmtree_calls: list[Path] = []
    monkeypatch.setattr(
        lifecycle_mod.shutil, "rmtree", lambda p, **kw: rmtree_calls.append(Path(p))
    )
    monkeypatch.setattr(lifecycle_mod, "remove_worktree", _git_failure_remove_worktree)
    monkeypatch.setattr(
        lifecycle_mod,
        "reference_census_verdict",
        lambda t, v=verdict: (v, [f"test {v}"]),
    )

    with pytest.raises(WorktreeDeleteRefused) as excinfo:
        lifecycle_mod._abandon_profile_worktree(_profile_record(target))

    assert excinfo.value.code == "bakeoff_worktree_delete_refused"
    assert rmtree_calls == []  # zero rmtree
    assert target.exists()


def test_abandon_rmtree_fallback_proceeds_on_clear(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G6 finding 3: CLEAR census lets the rmtree fallback proceed."""
    target = tmp_path / "wt"
    target.mkdir()
    rmtree_calls: list[Path] = []
    monkeypatch.setattr(
        lifecycle_mod.shutil, "rmtree", lambda p, **kw: rmtree_calls.append(Path(p))
    )
    monkeypatch.setattr(lifecycle_mod, "remove_worktree", _git_failure_remove_worktree)
    monkeypatch.setattr(lifecycle_mod, "reference_census_verdict", lambda t: ("CLEAR", []))

    lifecycle_mod._abandon_profile_worktree(_profile_record(target))

    assert rmtree_calls == [target]


def test_abandon_propagates_remove_worktree_census_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G6 finding 3: a refusal raised inside remove_worktree never falls back to rmtree."""
    target = tmp_path / "wt"
    target.mkdir()
    rmtree_calls: list[Path] = []
    monkeypatch.setattr(
        lifecycle_mod.shutil, "rmtree", lambda p, **kw: rmtree_calls.append(Path(p))
    )

    def _refused(target: Path, force: bool = True) -> None:
        raise WorktreeDeleteRefused(
            "bakeoff_worktree_delete_refused", "census refused"
        )

    monkeypatch.setattr(lifecycle_mod, "remove_worktree", _refused)

    with pytest.raises(WorktreeDeleteRefused):
        lifecycle_mod._abandon_profile_worktree(_profile_record(target))

    assert rmtree_calls == []  # zero rmtree
    assert target.exists()
