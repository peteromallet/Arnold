"""Tests for the deterministic blast-radius helper and plan-metadata helpers."""

from __future__ import annotations

import json
from pathlib import Path

from arnold.pipelines.megaplan.orchestration.test_selection import (
    PlanBlastRadius,
    PlanChangedFiles,
    compute_default_blast_radius,
    compute_test_blast_radius,
    read_plan_blast_radius,
    resolve_baseline_test_selection,
    resolve_changed_file_provenance,
)


def _write(repo: Path, rel_path: str, content: str = "") -> None:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or f"# {rel_path}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Scenario 1: explicit test_blast_radius selectors in plan metadata
# ---------------------------------------------------------------------------


def test_resolve_baseline_scoped_uses_selectors_from_metadata(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state: dict = {
        "plan_versions": [{"file": "plan_v1.md", "version": 1}],
        "config": {},
    }
    meta = {
        "test_blast_radius": {
            "strategy": "scoped",
            "confidence": "high",
            "selectors": [
                {"kind": "path", "value": "tests/pkg/test_foo.py", "reason": "mirror"},
            ],
            "changed_surfaces": ["pkg/foo.py"],
            "always_run": [],
        }
    }
    (plan_dir / "plan_v1.meta.json").write_text(json.dumps(meta), encoding="utf-8")

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "scoped"
    assert result["command_override"] == "pytest tests/pkg/test_foo.py"
    assert "selectors_used" in result


# ---------------------------------------------------------------------------
# Scenario 2: strategy "scoped" computes path selectors from changed_surfaces
# ---------------------------------------------------------------------------


def test_compute_default_blast_radius_scoped_for_direct_mirror(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/foo.py")
    _write(repo, "tests/pkg/test_foo.py")

    radius = compute_default_blast_radius(["pkg/foo.py"], repo)

    assert radius["strategy"] == "scoped"
    assert radius["confidence"] == "high"
    assert radius["changed_surfaces"] == ["pkg/foo.py"]
    assert [sel["value"] for sel in radius["selectors"]] == ["tests/pkg/test_foo.py"]


# ---------------------------------------------------------------------------
# Scenario 3: full_suite_fallback + always_run paths included
# ---------------------------------------------------------------------------


def test_resolve_baseline_folds_always_run_into_scoped_command(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state: dict = {
        "plan_versions": [{"file": "plan_v1.md", "version": 1}],
        "config": {},
    }
    meta = {
        "test_blast_radius": {
            "strategy": "scoped",
            "confidence": "high",
            "selectors": [
                {"kind": "path", "value": "tests/unit/test_a.py", "reason": "mirror"},
            ],
            "changed_surfaces": ["src/a.py"],
            "always_run": ["tests/integration/test_smoke.py"],
            "full_suite_fallback": True,
        }
    }
    (plan_dir / "plan_v1.meta.json").write_text(json.dumps(meta), encoding="utf-8")

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "scoped"
    assert "tests/unit/test_a.py" in result["command_override"]
    assert "tests/integration/test_smoke.py" in result["command_override"]


# ---------------------------------------------------------------------------
# Scenario 4: missing blast radius → full suite fallback
# ---------------------------------------------------------------------------


def test_resolve_baseline_full_suite_when_no_blast_radius(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state: dict = {
        "plan_versions": [{"file": "plan_v1.md", "version": 1}],
        "config": {},
    }
    (plan_dir / "plan_v1.meta.json").write_text("{}", encoding="utf-8")

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "full"
    assert result["command_override"] is None


# ---------------------------------------------------------------------------
# Public alias smoke test
# ---------------------------------------------------------------------------


def test_compute_test_blast_radius_is_alias_for_default(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/test_x.py")

    r1 = compute_default_blast_radius(["tests/test_x.py"], repo)
    r2 = compute_test_blast_radius(["tests/test_x.py"], repo)

    assert r1 == r2
