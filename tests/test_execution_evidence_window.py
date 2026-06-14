"""Tests for the evidence_window field added to validate_execution_evidence."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.orchestration.execution_evidence import (
    validate_execution_evidence,
)


def _git_init(project_dir: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=str(project_dir),
            check=True,
            capture_output=True,
            text=True,
        )

    git("init", "-q")
    git("config", "user.email", "t@t.test")
    git("config", "user.name", "t")
    (project_dir / "seed.txt").write_text("seed\n")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    git("branch", "-M", "main")


def test_evidence_window_heuristic_when_no_base_ref(tmp_path: Path) -> None:
    """Without base_ref, evidence_window.source is 'heuristic_merge_base'."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _git_init(project_dir)

    finalize_data = {"tasks": [], "sense_checks": []}
    result = validate_execution_evidence(finalize_data, project_dir)

    ew = result["evidence_window"]
    assert ew["source"] == "heuristic_merge_base"
    assert ew["base_sha"] is None
    assert ew["head_sha"] is not None and len(ew["head_sha"]) == 40


def test_evidence_window_declared_when_base_ref_provided(tmp_path: Path) -> None:
    """With base_ref set, evidence_window.source is 'declared' and base_sha resolves."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _git_init(project_dir)

    # HEAD is now at the seed commit; use HEAD itself as base_ref.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(project_dir),
        text=True,
        capture_output=True,
    ).stdout.strip()

    finalize_data = {"tasks": [], "sense_checks": []}
    result = validate_execution_evidence(finalize_data, project_dir, base_ref=head)

    ew = result["evidence_window"]
    assert ew["source"] == "declared"
    assert ew["base_sha"] == head
    assert ew["head_sha"] == head


def test_evidence_window_present_when_no_git_repo(tmp_path: Path) -> None:
    """evidence_window is still returned even when skipped (no .git)."""
    project_dir = tmp_path / "no-git"
    project_dir.mkdir()

    result = validate_execution_evidence({"tasks": [], "sense_checks": []}, project_dir)
    assert result["skipped"] is True
    ew = result["evidence_window"]
    assert "source" in ew
    assert ew["source"] == "heuristic_merge_base"


def test_evidence_window_source_declared_on_no_git_repo(tmp_path: Path) -> None:
    """source is 'declared' when base_ref given even if repo absent (head_sha=None)."""
    project_dir = tmp_path / "no-git"
    project_dir.mkdir()

    result = validate_execution_evidence(
        {"tasks": [], "sense_checks": []}, project_dir, base_ref="main"
    )
    assert result["skipped"] is True
    ew = result["evidence_window"]
    assert ew["source"] == "declared"
    assert ew["head_sha"] is None


def test_validate_execution_evidence_doc_path_unaffected(tmp_path: Path) -> None:
    """_validate_execution_evidence_doc is not touched — no evidence_window key."""
    project_dir = tmp_path / "p"
    project_dir.mkdir()

    result = validate_execution_evidence(
        {"tasks": [], "sense_checks": []},
        project_dir,
        mode="doc",
    )
    # Doc path returns its own shape without evidence_window.
    assert "evidence_window" not in result


# ---------------------------------------------------------------------------
# T8: Committed-range semantics — two-dot vs three-dot divergence
# ---------------------------------------------------------------------------


def test_evidence_window_two_dot_range_excludes_base_side(tmp_path: Path) -> None:
    """Explicit base_ref produces a two-dot (base..HEAD) committed range.

    Create two divergent branches so that two-dot and three-dot differ:
    * base side has ``base_side.py``
    * HEAD side has ``head_side.py``

    ``base..HEAD`` (two-dot) only sees commits reachable from HEAD but NOT
    from base, so ``base_side.py`` is excluded.  ``base...HEAD`` (three-dot)
    would include both, but that's only used for heuristic/no-base paths.
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _git_init(project_dir)

    # Fork a milestone-base branch from seed.
    subprocess.run(
        ["git", "checkout", "-b", "milestone-base"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    (project_dir / "base_side.py").write_text("base\n")
    subprocess.run(
        ["git", "add", "base_side.py"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "base side"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    base_sha = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_dir),
            text=True,
            capture_output=True,
        )
        .stdout.strip()
    )

    # Switch back to main and diverge.
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    (project_dir / "head_side.py").write_text("head\n")
    subprocess.run(
        ["git", "add", "head_side.py"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "head side"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )

    # With explicit base_ref the committed range is base..HEAD (two-dot).
    # head_side.py is reachable from HEAD but not from base → included.
    # base_side.py is reachable from base but not HEAD → excluded.
    finalize_data = {
        "tasks": [
            {
                "id": "t1",
                "status": "done",
                "files_changed": ["head_side.py"],
                "commands_run": ["pytest"],
            }
        ],
        "sense_checks": [],
    }
    result = validate_execution_evidence(finalize_data, project_dir, base_ref=base_sha)

    ew = result["evidence_window"]
    assert ew["source"] == "declared"
    assert ew["base_sha"] == base_sha

    files_in_diff = result["files_in_diff"]
    # Two-dot (base..HEAD) shows the full endpoint diff including deletions.
    # head_side.py is an addition on the HEAD side → always included.
    assert "head_side.py" in files_in_diff
    # base_side.py was committed on the base branch but is absent from HEAD →
    # ``git diff base..HEAD --name-only`` lists it as a deletion.  Three-dot
    # (base...HEAD = merge-base..HEAD) would NOT include it because the
    # merge-base never had it either.  The presence of base_side.py proves
    # the range is two-dot, not three-dot.
    assert "base_side.py" in files_in_diff, (
        "two-dot range must include deletions from base side "
        "(three-dot would exclude them)"
    )


def test_evidence_window_declared_base_unresolvable(tmp_path: Path) -> None:
    """When base_ref is declared but cannot resolve, base_sha is None.

    The evidence_window still records ``source=declared`` because a declared
    intent exists, but ``base_sha=None`` signals the committed range could not
    be anchored.  Downstream code gates authoritative behaviour on
    ``base_sha is not None`` (SD2).
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _git_init(project_dir)

    result = validate_execution_evidence(
        {"tasks": [], "sense_checks": []},
        project_dir,
        base_ref="refs/heads/does-not-exist",
    )

    ew = result["evidence_window"]
    assert ew["source"] == "declared"
    assert ew["base_sha"] is None
    assert ew["head_sha"] is not None  # HEAD still resolves


def test_evidence_window_base_sha_matches_head_when_no_divergence(tmp_path: Path) -> None:
    """When base_ref resolves to HEAD itself, base_sha == head_sha and the
    committed range is empty — only working-tree status contributes."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _git_init(project_dir)

    head = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_dir),
            text=True,
            capture_output=True,
        )
        .stdout.strip()
    )

    result = validate_execution_evidence(
        {"tasks": [], "sense_checks": []}, project_dir, base_ref=head
    )

    ew = result["evidence_window"]
    assert ew["source"] == "declared"
    assert ew["base_sha"] == head
    assert ew["head_sha"] == head
    # No divergence → committed range empty → no files from that source.
    # (Any files_in_diff come from working-tree status only.)
