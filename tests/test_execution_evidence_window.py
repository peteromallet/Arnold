"""Tests for the evidence_window field added to validate_execution_evidence."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from megaplan.orchestration.execution_evidence import validate_execution_evidence


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
