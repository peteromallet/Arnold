"""Defect 2: the finalize test baseline must be captured ONCE per plan.

The baseline runs the whole pytest suite (minutes of work). A finalize retry —
e.g. after a Shannon readiness-probe stall — has no reason to re-establish it.
The fix persists a SUCCESSFUL baseline to ``<plan_dir>/baseline.json`` and reuses
it verbatim on any subsequent finalize attempt for the same plan. Degraded
(null-failures) outcomes are NOT cached so a retry can re-attempt under better
conditions.

All tests are hermetic: no real pytest suite is spawned. ``_capture_test_baseline``
(the expensive call) is monkeypatched and we assert it is invoked at most once.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import arnold.pipelines.megaplan.handlers.finalize as fin


def _config(project_dir: Path) -> dict:
    return {"project_dir": str(project_dir), "test_command": "pytest -q"}


def test_first_capture_runs_suite_and_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    calls = {"n": 0}

    def _fake_capture(_proj, _cfg):
        calls["n"] += 1
        return {
            "baseline_test_failures": ["tests/test_x.py::test_a"],
            "baseline_test_command": "pytest -q",
        }

    monkeypatch.setattr(fin, "_capture_test_baseline", _fake_capture)

    result = fin._capture_test_baseline_for_plan(plan_dir, project_dir, _config(project_dir))
    assert calls["n"] == 1
    assert result["baseline_test_failures"] == ["tests/test_x.py::test_a"]
    # The cache file was written.
    cache = plan_dir / "baseline.json"
    assert cache.exists()
    cached = json.loads(cache.read_text())
    assert cached["baseline_test_failures"] == ["tests/test_x.py::test_a"]


def test_retry_reuses_cache_without_rerunning_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    calls = {"n": 0}

    def _fake_capture(_proj, _cfg):
        calls["n"] += 1
        return {
            "baseline_test_failures": ["tests/test_x.py::test_a"],
            "baseline_test_command": "pytest -q",
        }

    monkeypatch.setattr(fin, "_capture_test_baseline", _fake_capture)

    # First finalize attempt: runs the suite once.
    first = fin._capture_test_baseline_for_plan(plan_dir, project_dir, _config(project_dir))
    # Second finalize attempt (a retry): MUST NOT re-run the suite.
    second = fin._capture_test_baseline_for_plan(plan_dir, project_dir, _config(project_dir))

    assert calls["n"] == 1, "suite was re-run on a retry — baseline not cached"
    assert second == {
        "baseline_test_failures": ["tests/test_x.py::test_a"],
        "baseline_test_command": "pytest -q",
    }
    assert first["baseline_test_failures"] == second["baseline_test_failures"]


def test_degraded_baseline_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A null-failures (timeout / runner-error) outcome must NOT be cached: a
    retry is free to re-attempt the suite under better conditions."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    calls = {"n": 0}

    def _fake_capture(_proj, _cfg):
        calls["n"] += 1
        return {
            "baseline_test_failures": None,
            "baseline_test_command": "pytest -q",
            "baseline_test_note": "wedged",
        }

    monkeypatch.setattr(fin, "_capture_test_baseline", _fake_capture)

    fin._capture_test_baseline_for_plan(plan_dir, project_dir, _config(project_dir))
    assert not (plan_dir / "baseline.json").exists()
    # A retry re-attempts (degraded result is not cached).
    fin._capture_test_baseline_for_plan(plan_dir, project_dir, _config(project_dir))
    assert calls["n"] == 2


def test_mock_mode_bypasses_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock mode (MEGAPLAN_MOCK_WORKERS=1) takes the real _capture_test_baseline
    mock branch every time and never consults/writes the cache."""
    from arnold.pipelines.megaplan.types import MOCK_ENV_VAR

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.setenv(MOCK_ENV_VAR, "1")

    # Pre-seed a cache that would be returned if mock mode wrongly read it.
    (plan_dir / "baseline.json").write_text(
        json.dumps({"baseline_test_failures": ["SHOULD_NOT_BE_USED"]})
    )

    result = fin._capture_test_baseline_for_plan(plan_dir, project_dir, _config(project_dir))
    # Mock branch returns empty-failures, not the pre-seeded cache.
    assert result["baseline_test_failures"] == []


def test_corrupt_cache_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (plan_dir / "baseline.json").write_text("{ not valid json")

    calls = {"n": 0}

    def _fake_capture(_proj, _cfg):
        calls["n"] += 1
        return {"baseline_test_failures": [], "baseline_test_command": "pytest -q"}

    monkeypatch.setattr(fin, "_capture_test_baseline", _fake_capture)
    result = fin._capture_test_baseline_for_plan(plan_dir, project_dir, _config(project_dir))
    assert calls["n"] == 1  # corrupt cache ignored, real capture ran
    assert result["baseline_test_failures"] == []
