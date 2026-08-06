"""Regression tests: gate baseline-presence must use git plumbing, not `.git` search.

Horizon B (r7 superfixer 20260806): the gate worker escalated on a false
"baseline commit ABSENT" premise because it inferred absence from a naive
`.git/` filesystem content search. Loose objects are zlib-compressed, packed
objects are binary, and objects may live in alternates or a linked-worktree
common directory — none of those are visible to a filesystem text search.
The engine now computes an authoritative `git cat-file -e` /
`git rev-parse --verify` receipt and injects it into gate signals.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.orchestration.gate_signals import (
    _GIT_SHA_RE,
    baseline_presence_signals,
    git_object_presence_receipt,
)
from arnold_pipelines.megaplan.prompts.gate import _gate_prompt


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if check:
        assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc


def _init_repo_with_commit(repo: Path) -> str:
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "file.txt").write_text("baseline content\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "baseline")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_git_object_presence_receipt_loose_object_present(tmp_path: Path) -> None:
    """A commit present as a LOOSE object must be reported present via git plumbing.

    This is the exact regression: a naive `.git/` content search cannot see the
    zlib-compressed loose object, but `git cat-file -e` can.
    """
    repo = tmp_path / "repo"
    sha = _init_repo_with_commit(repo)
    receipt = git_object_presence_receipt(repo, sha)
    assert receipt["present"] is True
    assert receipt["sha"] == sha
    assert receipt["cat_file_exit"] == 0
    assert receipt["rev_parse_exit"] == 0
    assert receipt["method"].startswith("git cat-file -e")
    assert receipt["tree"]  # tree id resolved
    assert receipt["head"] == sha


def test_git_object_presence_receipt_packed_object_still_present(tmp_path: Path) -> None:
    """After `git gc` the object is packed (binary) — plumbing still reports present."""
    repo = tmp_path / "repo"
    sha = _init_repo_with_commit(repo)
    _git(repo, "gc", "--aggressive", "--prune=now")
    # prove the object is no longer a loose object on disk
    loose_dir = repo / ".git" / "objects" / sha[:2]
    assert not loose_dir.exists() or not any(loose_dir.iterdir())
    receipt = git_object_presence_receipt(repo, sha)
    assert receipt["present"] is True
    assert receipt["cat_file_exit"] == 0


def test_git_object_presence_receipt_absent_commit_reported_absent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo_with_commit(repo)
    missing = "c" + "0" * 39
    receipt = git_object_presence_receipt(repo, missing)
    assert receipt["present"] is False
    assert receipt["cat_file_exit"] != 0
    assert receipt["rev_parse_exit"] != 0


def test_git_object_presence_receipt_non_repo_dir_does_not_raise(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    receipt = git_object_presence_receipt(empty, "c" + "0" * 39)
    assert receipt["present"] is False
    assert "cat_file_exit" in receipt


def test_baseline_presence_signals_scans_plan_and_anchor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    sha = _init_repo_with_commit(repo)

    plan_dir = tmp_path / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan_v5.md").write_text(
        f"# Plan\n\nStep 0: baseline is pinned at `{sha}`.\n", encoding="utf-8"
    )
    state = {
        "name": "demo-plan",
        "iteration": 5,
        "plan_versions": [{"file": "plan_v5.md", "iteration": 5}],
        "config": {"project_dir": str(repo)},
        "meta": {},
    }
    block = baseline_presence_signals(plan_dir, state)
    assert block["schema"] == "arnold.megaplan.baseline_presence.v1"
    assert block["project_dir"] == str(repo)
    assert block["count"] >= 1
    by_sha = {r["sha"]: r for r in block["receipts"]}
    assert by_sha[sha]["present"] is True


def test_baseline_presence_signals_empty_without_refs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo_with_commit(repo)
    plan_dir = tmp_path / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan_v5.md").write_text("# Plan\n\nNo pinned commit here.\n", encoding="utf-8")
    state = {
        "name": "demo-plan",
        "iteration": 5,
        "plan_versions": [{"file": "plan_v5.md", "iteration": 5}],
        "config": {"project_dir": str(repo)},
        "meta": {},
    }
    block = baseline_presence_signals(plan_dir, state)
    assert block["count"] == 0


def test_baseline_presence_signals_from_northstar_anchor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    sha = _init_repo_with_commit(repo)
    (repo / "NORTHSTAR.md").write_text(
        f"---\ntype: anchor\n---\n\nbaseline pinned: {sha}\n", encoding="utf-8"
    )
    plan_dir = tmp_path / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan_v5.md").write_text("# Plan\n", encoding="utf-8")
    state = {
        "name": "demo-plan",
        "iteration": 5,
        "plan_versions": [{"file": "plan_v5.md", "iteration": 5}],
        "config": {"project_dir": str(repo)},
        "meta": {},
    }
    block = baseline_presence_signals(plan_dir, state)
    by_sha = {r["sha"]: r for r in block["receipts"]}
    assert by_sha.get(sha, {}).get("present") is True


def test_gate_prompt_instructs_git_plumbing_not_dot_git_search(tmp_path: Path) -> None:
    """The gate prompt must carry the Horizon B instruction verbatim."""
    plan_dir = tmp_path / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan_v5.md").write_text("# Plan\n", encoding="utf-8")
    (plan_dir / "gate_signals_v5.json").write_text(
        '{"robustness": "medium", "signals": {"iteration": 5}, "warnings": []}',
        encoding="utf-8",
    )
    (plan_dir / "plan_v5.meta.json").write_text('{"success_criteria": []}', encoding="utf-8")
    state = {
        "name": "demo-plan",
        "iteration": 5,
        "plan_versions": [{"file": "plan_v5.md", "iteration": 5}],
        "config": {"project_dir": str(tmp_path / "project")},
        "meta": {},
    }
    prompt = _gate_prompt(state, plan_dir)
    assert "baseline_presence" in prompt
    assert "git cat-file -e" in prompt
    assert "never a `.git` text search" in prompt


def test_git_sha_regex_matches_full_sha_only() -> None:
    assert _GIT_SHA_RE.findall("pinned c116f38cc83de11a1a508eff6153205504d1ba5a ok") == [
        "c116f38cc83de11a1a508eff6153205504d1ba5a"
    ]
    assert _GIT_SHA_RE.findall("short c116f38c not matched") == []
