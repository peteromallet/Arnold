"""Tests for validate_execution_evidence evidence-window primitive (T7)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from arnold.pipelines.megaplan.orchestration.execution_evidence import validate_execution_evidence


def _make_finalize_data(
    tasks: list[dict[str, Any]] | None = None,
    sense_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "tasks": tasks or [],
        "sense_checks": sense_checks or [],
    }


# ---------------------------------------------------------------------------
# Evidence window: base_ref parameter wires into result
# ---------------------------------------------------------------------------


def test_evidence_window_included_when_no_base_ref(tmp_path: Path) -> None:
    """Without base_ref, evidence_window source is 'heuristic_merge_base'."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
             "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(tmp_path)},
    )

    result = validate_execution_evidence(_make_finalize_data(), tmp_path)

    assert "evidence_window" in result
    assert result["evidence_window"]["source"] == "heuristic_merge_base"
    assert result["evidence_window"]["base_sha"] is None
    # head_sha may be None if git commit failed in test env, that's acceptable.


def test_evidence_window_source_declared_when_base_ref_supplied(tmp_path: Path) -> None:
    """With base_ref='HEAD', evidence_window source is 'declared'."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
             "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(tmp_path)},
    )

    result = validate_execution_evidence(
        _make_finalize_data(), tmp_path, base_ref="HEAD"
    )

    assert "evidence_window" in result
    assert result["evidence_window"]["source"] == "declared"


def test_evidence_window_present_when_not_git_repo(tmp_path: Path) -> None:
    """Evidence window is present even when the dir is not a git repo."""
    result = validate_execution_evidence(_make_finalize_data(), tmp_path)

    assert "evidence_window" in result
    assert result["skipped"] is True
    assert result["evidence_window"]["source"] == "heuristic_merge_base"
    assert result["evidence_window"]["base_sha"] is None
    assert result["evidence_window"]["head_sha"] is None


def test_evidence_window_declared_source_when_not_git_repo_and_base_ref(tmp_path: Path) -> None:
    """Declared source is used even in non-git dirs when base_ref is provided."""
    result = validate_execution_evidence(
        _make_finalize_data(), tmp_path, base_ref="abc123"
    )

    assert result["evidence_window"]["source"] == "declared"


# ---------------------------------------------------------------------------
# Backward compatibility: omitting base_ref keeps existing behaviour
# ---------------------------------------------------------------------------


def test_backward_compat_no_base_ref_returns_same_findings_keys(tmp_path: Path) -> None:
    """Calling without base_ref returns all expected keys."""
    result = validate_execution_evidence(_make_finalize_data(), tmp_path)

    for key in ("findings", "files_in_diff", "files_claimed", "skipped", "reason", "evidence_window"):
        assert key in result, f"Missing key: {key}"
