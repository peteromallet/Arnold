from __future__ import annotations

import json
import subprocess
from pathlib import Path

from arnold.pipelines.megaplan.handlers.finalize import _fallback_baseline_test_selection


def _write(repo: Path, rel_path: str, content: str = "") -> None:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or f"# {rel_path}\n", encoding="utf-8")


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)


def test_finalize_fallback_scopes_baseline_when_plan_metadata_has_no_radius(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    _write(repo, "pkg/foo.py")
    _write(repo, "tests/pkg/test_foo.py")
    _write(repo, ".megaplan/runs/plan/finalize.json", "{}")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan_v1.meta.json").write_text("{}", encoding="utf-8")
    state = {
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "config": {"project_dir": str(repo)},
        "meta": {},
    }
    resolved = {
        "mode": "full",
        "reason": "No test_blast_radius in plan metadata; falling back to full suite",
        "command_override": None,
    }

    result = _fallback_baseline_test_selection(plan_dir, state, repo, resolved)

    assert result["mode"] == "scoped"
    assert result["command_override"] == "pytest tests/pkg/test_foo.py"
    assert result["fallback_attempted"] is True
    assert ".megaplan/runs/plan/finalize.json" not in result["fallback_changed_files"]


def test_finalize_fallback_does_not_override_present_plan_blast_radius(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    _write(repo, "pkg/foo.py")
    _write(repo, "tests/pkg/test_foo.py")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    meta = {
        "test_blast_radius": {
            "strategy": "full",
            "confidence": "low",
            "selectors": [],
            "changed_surfaces": ["pkg/foo.py"],
        }
    }
    (plan_dir / "plan_v1.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    state = {
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "config": {"project_dir": str(repo)},
        "meta": {},
    }
    resolved = {
        "mode": "full",
        "reason": "test_blast_radius strategy is 'full' (not 'scoped')",
        "command_override": None,
    }

    result = _fallback_baseline_test_selection(plan_dir, state, repo, resolved)

    assert result == resolved
