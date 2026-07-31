import json
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.bakeoff.handlers import handle_merge
from arnold_pipelines.megaplan.bakeoff.state import save_bakeoff_state
from arnold_pipelines.megaplan.bakeoff.worktree import capture_base_sha, create_worktree
from arnold_pipelines.megaplan.types import CliError


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "README.md")
    _git(repo, "commit", "-m", "initial")


def _write_plan(worktree: Path, exp_id: str) -> None:
    plan_dir = worktree / ".megaplan" / "plans" / exp_id
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"config": {"project_dir": str(worktree)}, "history": []}),
        encoding="utf-8",
    )
    (plan_dir / "plan_v1.md").write_text("plan\n", encoding="utf-8")


def _profile(root: Path, worktree: Path, exp_id: str, name: str) -> dict:
    archive = root / ".megaplan" / "bakeoffs" / exp_id / name
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "auto.log").write_text("log\n", encoding="utf-8")
    (archive / "outcome.json").write_text(json.dumps({"status": "done"}), encoding="utf-8")
    return {
        "name": name,
        "worktree": str(worktree),
        "plan_id": exp_id,
        "pid": None,
        "launched_at": None,
        "terminated_at": None,
        "outcome": {"status": "done"},
        "log_path": str(archive / "auto.log"),
        "outcome_path": str(archive / "outcome.json"),
    }


def _two_profile_bakeoff(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    root = tmp_path / "repo"
    _init_repo(root)
    exp_id = "exp-1"
    base_sha = capture_base_sha(root)
    winner = tmp_path / ".megaplan-worktrees" / exp_id / "winner"
    loser = tmp_path / ".megaplan-worktrees" / exp_id / "loser"
    create_worktree(root, winner, base_sha)
    create_worktree(root, loser, base_sha)
    _write_plan(winner, exp_id)
    _write_plan(loser, exp_id)
    state = {
        "schema_version": 1,
        "experiment_id": exp_id,
        "base_sha": base_sha,
        "idea_hash": "idea",
        "idea_path": str(root / "idea.md"),
        "mode": "code",
        "profiles": [
            _profile(root, winner, exp_id, "winner"),
            _profile(root, loser, exp_id, "loser"),
        ],
        "phase": "picked",
        "chosen_profile": "winner",
        "merged_at": None,
        "judge_model": None,
    }
    save_bakeoff_state(root, state)
    return root, winner, loser, exp_id


def test_merge_applies_winner_patch_archives_all_plans_and_rewrites_project_dirs(tmp_path: Path) -> None:
    root, winner, loser, exp_id = _two_profile_bakeoff(tmp_path)
    (winner / "README.md").write_text("winner edit\n", encoding="utf-8")
    new_file = winner / "src" / "new_feature.py"
    new_file.parent.mkdir()
    new_file.write_text("VALUE = 1\n", encoding="utf-8")

    assert handle_merge(root, Namespace(exp=exp_id)) == 0

    assert (root / "README.md").read_text(encoding="utf-8") == "winner edit\n"
    assert (root / "src" / "new_feature.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert "--- /dev/null" in (root / ".megaplan" / "bakeoffs" / exp_id / "winner.patch").read_text(
        encoding="utf-8"
    )
    archived_loser = json.loads(
        (root / ".megaplan" / "bakeoffs" / exp_id / "loser" / "plan" / "state.json").read_text(
            encoding="utf-8"
        )
    )
    assert archived_loser["config"]["project_dir"] is None
    assert archived_loser["config"]["archived_project_dir"] == str(loser)
    winner_live = json.loads(
        (root / ".megaplan" / "plans" / f"{exp_id}-winner" / "state.json").read_text(encoding="utf-8")
    )
    assert winner_live["config"]["project_dir"] == str(root)
    assert winner_live["config"]["archived_project_dir"] == str(winner)
    merged_state = json.loads(
        (root / ".megaplan" / "bakeoffs" / exp_id / "bakeoff.json").read_text(encoding="utf-8")
    )
    assert merged_state["wbc_transition_evidence"][f"merge:{exp_id}"]["fixture_safety"]["authorized"] is True
    assert not (root / ".megaplan" / "plans" / f"{exp_id}-loser").exists()
    assert not winner.exists()
    assert not loser.exists()


def test_doc_mode_merge_copies_winner_doc_to_main_and_archive(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    exp_id = "exp-doc"
    base_sha = capture_base_sha(root)
    winner = tmp_path / ".megaplan-worktrees" / exp_id / "winner"
    loser = tmp_path / ".megaplan-worktrees" / exp_id / "loser"
    create_worktree(root, winner, base_sha)
    create_worktree(root, loser, base_sha)
    _write_plan(winner, exp_id)
    _write_plan(loser, exp_id)

    # Each profile produces a doc artifact at the configured output path.
    output_path = "docs/design.md"
    winner_doc_dir = winner / "docs"
    winner_doc_dir.mkdir()
    winner_doc = winner_doc_dir / "design.md"
    winner_doc.write_text("# Winner doc\n\nbody\n", encoding="utf-8")
    loser_doc_dir = loser / "docs"
    loser_doc_dir.mkdir()
    (loser_doc_dir / "design.md").write_text("# Loser doc\n\nother\n", encoding="utf-8")

    state = {
        "schema_version": 1,
        "experiment_id": exp_id,
        "base_sha": base_sha,
        "idea_hash": "idea",
        "idea_path": str(root / "idea.md"),
        "mode": "doc",
        "output_path": output_path,
        "profiles": [
            _profile(root, winner, exp_id, "winner"),
            _profile(root, loser, exp_id, "loser"),
        ],
        "phase": "picked",
        "chosen_profile": "winner",
        "merged_at": None,
        "judge_model": None,
    }
    save_bakeoff_state(root, state)

    assert handle_merge(root, Namespace(exp=exp_id)) == 0

    # Main tree should now have the winner's doc content.
    merged_doc = (root / output_path).read_text(encoding="utf-8")
    assert merged_doc == "# Winner doc\n\nbody\n"
    # Archive should mirror the winner doc.
    archived = (root / ".megaplan" / "bakeoffs" / exp_id / "winner.doc").read_text(encoding="utf-8")
    assert archived == merged_doc
    # Doc-mode merge does NOT produce a winner.patch file.
    assert not (root / ".megaplan" / "bakeoffs" / exp_id / "winner.patch").exists()
    # Worktrees still get cleaned up.
    assert not winner.exists()
    assert not loser.exists()


def test_doc_mode_merge_errors_when_winner_doc_missing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    exp_id = "exp-doc-missing"
    base_sha = capture_base_sha(root)
    winner = tmp_path / ".megaplan-worktrees" / exp_id / "winner"
    create_worktree(root, winner, base_sha)
    _write_plan(winner, exp_id)
    # Note: no docs/design.md written into the winner worktree.
    output_path = "docs/design.md"
    state = {
        "schema_version": 1,
        "experiment_id": exp_id,
        "base_sha": base_sha,
        "idea_hash": "idea",
        "idea_path": str(root / "idea.md"),
        "mode": "doc",
        "output_path": output_path,
        "profiles": [_profile(root, winner, exp_id, "winner")],
        "phase": "picked",
        "chosen_profile": "winner",
        "merged_at": None,
        "judge_model": None,
    }
    save_bakeoff_state(root, state)

    with pytest.raises(CliError) as excinfo:
        handle_merge(root, Namespace(exp=exp_id))
    assert excinfo.value.code == "bakeoff_merge_no_changes"
    # Worktree must NOT have been removed on failure (we error before cleanup).
    assert winner.exists()


def test_merge_rejects_dirty_main_tree_before_apply(tmp_path: Path) -> None:
    root, winner, _loser, exp_id = _two_profile_bakeoff(tmp_path)
    (winner / "README.md").write_text("winner edit\n", encoding="utf-8")
    (root / "dirty.txt").write_text("main dirty\n", encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        handle_merge(root, Namespace(exp=exp_id))

    assert excinfo.value.code == "bakeoff_dirty_worktree"
    assert not (root / ".megaplan" / "bakeoffs" / exp_id / "winner.patch").exists()
