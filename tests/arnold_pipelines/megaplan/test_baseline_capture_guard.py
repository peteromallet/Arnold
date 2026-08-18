"""Baseline-capture provenance + recapture guard (occurrence a07166d38fbc).

A plan baseline poisoned by a not-yet-existing planned task output
(``baseline_test_failures=null``) broke the no-new-failures contract for the
whole plan.  These tests pin the structural fixes:

- ``_filter_baseline_command_to_existing`` drops selectors that do not exist
  at capture time (truthful evidence: a missing file has no failing tests),
  so a baseline is a real list instead of a poisoned null.
- Every baseline capture records ``baseline_cwd`` + ``baseline_source_revision``
  for provenance.
- ``_recapture_missing_baseline`` refuses to recapture from a post-task tree
  (a dirty git repo root), so the plan's own uncommitted outputs can never be
  folded into a baseline and mask real regressions.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.handlers.finalize import (
    _capture_test_baseline,
    _filter_baseline_command_to_existing,
)
from arnold_pipelines.megaplan.orchestration.full_suite_backstop import (
    _git_tree_has_uncommitted_changes,
    _recapture_missing_baseline,
)


def test_filter_drops_missing_selectors(tmp_path: Path) -> None:
    existing = tmp_path / "tests" / "existing_test.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("def test_x(): pass\n", encoding="utf-8")
    command = (
        "timeout 3600s pytest tests/existing_test.py "
        "tests/planned_output_test.py --tb=short -q"
    )
    filtered, dropped = _filter_baseline_command_to_existing(tmp_path, command)
    assert dropped == ["tests/planned_output_test.py"]
    assert "tests/existing_test.py" in filtered
    assert "tests/planned_output_test.py" not in filtered
    assert filtered.startswith("timeout 3600s pytest ")


def test_filter_unchanged_when_all_exist(tmp_path: Path) -> None:
    existing = tmp_path / "tests" / "existing_test.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("def test_x(): pass\n", encoding="utf-8")
    command = "pytest tests/existing_test.py --tb=short -q"
    filtered, dropped = _filter_baseline_command_to_existing(tmp_path, command)
    assert dropped == []
    assert filtered == command


def test_baseline_capture_all_dropped_is_truthful_empty(
    tmp_path: Path, monkeypatch
) -> None:
    """Every selector missing -> empty baseline with a note, never a null."""
    command = "pytest tests/planned_output_test.py --tb=short -q"
    result = _capture_test_baseline(tmp_path, {"test_command": command})
    assert result["baseline_test_failures"] == []
    assert "did not exist yet" in result["baseline_test_note"]
    assert result["baseline_cwd"] == str(tmp_path)


def test_baseline_capture_records_cwd_and_revision(
    tmp_path: Path, monkeypatch
) -> None:
    from unittest.mock import patch

    from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("def test_x(): pass\n", encoding="utf-8")
    fake = SuiteRunResult(
        run_id="baseline-x",
        phase="baseline",
        command="pytest tests/t.py --tb=no -q --no-header -rA",
        duration=0.1,
        collected=1,
        collected_ids=["tests/t.py::test_x"],
        failures=[],
        passes=["tests/t.py::test_x"],
        status="passed",
        exit_code=0,
        raw_log_path=tmp_path / "raw.log",
        code_hash="sha256:base",
        collections_parse_ok=True,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        result = _capture_test_baseline(
            tmp_path, {"test_command": "pytest tests/t.py --tb=no -q --no-header -rA"}
        )
    assert result["baseline_cwd"] == str(tmp_path)
    assert "baseline_source_revision" in result


def test_git_tree_guard_refuses_dirty_repo_root() -> None:
    # The engine candidate is a git repo root with uncommitted fixer changes.
    assert (
        _git_tree_has_uncommitted_changes(
            Path("/workspace/runtime-candidates/arnold-4a830c6ac9a0")
        )
        is True
    )


def test_git_tree_guard_ignores_scratch_dirs(tmp_path: Path) -> None:
    # A scratch dir inside an unrelated ancestor repo (or no repo at all)
    # must not trip the guard.
    assert _git_tree_has_uncommitted_changes(tmp_path) is False


def test_recapture_refused_on_dirty_repo_root(tmp_path: Path) -> None:
    """A dirty repo-root tree can never recapture a baseline."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "finalize.json").write_text(
        json.dumps({"baseline_test_failures": None, "tasks": []}),
        encoding="utf-8",
    )
    payload, recaptured = _recapture_missing_baseline(
        plan_dir,
        Path("/workspace/runtime-candidates/arnold-4a830c6ac9a0"),
        {"test_command": "pytest tests"},
        None,
        None,
    )
    assert recaptured is False
    assert payload is None
