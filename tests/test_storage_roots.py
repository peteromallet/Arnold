from __future__ import annotations

import json
from pathlib import Path

from arnold.pipelines.megaplan import auto 
from arnold.pipelines.megaplan._core import active_plan_dirs, resolve_plan_dir
from arnold.pipelines.megaplan._core.io import canonical_megaplan_root, find_plan_dir, orphan_plans_root, repo_storage_id


def _write_state(plan_dir: Path, name: str) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": name, "current_state": "initialized"}),
        encoding="utf-8",
    )


def test_repo_storage_id_is_stable_across_git_worktrees(tmp_path: Path) -> None:
    main_repo = tmp_path / "repo-main"
    main_repo.mkdir()
    (main_repo / ".git").mkdir()

    worktree = tmp_path / "repo-worktree"
    worktree.mkdir()
    worktree_gitdir = main_repo / ".git" / "worktrees" / "feature-a"
    worktree_gitdir.mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {worktree_gitdir}\n", encoding="utf-8")

    assert repo_storage_id(main_repo) == repo_storage_id(worktree)


def test_canonical_orphan_plans_are_resolved_from_child_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()

    plan_dir = orphan_plans_root(project) / "canonical-plan"
    _write_state(plan_dir, "canonical-plan")

    child = project / "src" / "nested"
    child.mkdir(parents=True)

    assert find_plan_dir(child, "canonical-plan") == plan_dir
    assert auto._resolve_plan_dir("canonical-plan", child) == plan_dir
    assert resolve_plan_dir(project, "canonical-plan") == plan_dir


def test_legacy_plan_resolution_stays_in_place_without_eager_copy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    project = tmp_path / "legacy-project"
    project.mkdir()
    (project / ".git").mkdir()

    legacy_plan_dir = project / ".megaplan" / "plans" / "legacy-plan"
    _write_state(legacy_plan_dir, "legacy-plan")

    resolved = resolve_plan_dir(project, "legacy-plan")

    assert resolved == legacy_plan_dir
    assert active_plan_dirs(project) == [legacy_plan_dir]
    assert not canonical_megaplan_root(project).exists()
