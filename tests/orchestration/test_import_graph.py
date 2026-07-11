"""Tests for import-graph-aware test blast-radius selection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.import_graph import ImportGraph
from arnold_pipelines.megaplan.orchestration.test_selection import (
    compute_default_blast_radius,
    resolve_baseline_test_selection,
)


def _write(repo: Path, rel_path: str, content: str = "") -> None:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or f"# {rel_path}\n", encoding="utf-8")


def _selector_values(radius: dict) -> list[str]:
    return [selector["value"] for selector in radius["selectors"]]


def _make_state(plan_dir: Path, version: int = 1) -> dict:
    return {
        "plan_versions": [
            {
                "version": version,
                "file": f"plan_v{version}.md",
                "hash": "abc",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "config": {"test_selection": "scoped", "project_dir": str(plan_dir.parent)},
        "meta": {},
    }


def _write_plan_meta(plan_dir: Path, version: int, blast_radius: dict) -> None:
    meta = {
        "version": version,
        "timestamp": "2026-01-01T00:00:00Z",
        "hash": "sha256:abc",
        "questions": [],
        "success_criteria": [],
        "assumptions": [],
        "structure_warnings": [],
        "test_blast_radius": blast_radius,
    }
    (plan_dir / f"plan_v{version}.md").write_text("plan\n", encoding="utf-8")
    (plan_dir / f"plan_v{version}.meta.json").write_text(
        json.dumps(meta),
        encoding="utf-8",
    )


def test_import_graph_adds_non_mirror_dependent_test(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/util.py", "x = 1\n")
    _write(repo, "tests/test_feature.py", "from pkg.util import x\n")
    _write(repo, "tests/test_util.py", "def test_util():\n    assert True\n")
    _write(repo, "tests/test_other.py", "def test_other():\n    assert True\n")

    radius = compute_default_blast_radius(["pkg/util.py"], repo)

    assert radius["strategy"] == "scoped"
    assert _selector_values(radius) == [
        "tests/test_util.py",
        "tests/test_feature.py",
    ]
    assert "tests/test_other.py" not in _selector_values(radius)
    assert radius["import_graph"] == {
        "degraded": False,
        "dependent_tests": 1,
        "unresolved": [],
    }


def test_bounded_basename_match_skips_archived_tests(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/transition_policy.py", "VALUE = 1\n")
    _write(repo, "tests/archive/m5/pipelines/megaplan/orchestration/test_transition_policy.py")
    _write(repo, "tests/orchestration/test_transition_policy.py")

    radius = compute_default_blast_radius(["pkg/transition_policy.py"], repo)

    assert radius["strategy"] == "scoped"
    assert _selector_values(radius) == ["tests/orchestration/test_transition_policy.py"]


def test_import_graph_follows_transitive_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/a.py", "import pkg.b\n")
    _write(repo, "pkg/b.py", "VALUE = 1\n")
    _write(repo, "tests/test_a.py", "import pkg.a\n")

    radius = compute_default_blast_radius(["pkg/b.py"], repo)

    assert radius["strategy"] == "scoped"
    assert _selector_values(radius) == ["tests/test_a.py"]


def test_import_graph_resolves_relative_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/__init__.py")
    _write(repo, "pkg/a.py", "from . import b\n")
    _write(repo, "pkg/b.py", "VALUE = 1\n")
    _write(repo, "tests/test_a.py", "import pkg.a\n")

    radius = compute_default_blast_radius(["pkg/b.py"], repo)

    assert radius["strategy"] == "scoped"
    assert _selector_values(radius) == ["tests/test_a.py"]


def test_import_graph_auto_detects_src_layout_package_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "src/pkg/mod.py", "VALUE = 1\n")
    _write(repo, "tests/test_feature.py", "import pkg.mod\n")

    radius = compute_default_blast_radius(["src/pkg/mod.py"], repo)

    assert radius["strategy"] == "scoped"
    assert _selector_values(radius) == ["tests/test_feature.py"]
    assert radius["import_graph"]["unresolved"] == []


def test_import_graph_keeps_flat_package_layout_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "megaplan/orchestration/import_graph.py", "VALUE = 1\n")
    _write(
        repo,
        "tests/orchestration/test_import_graph.py",
        "import arnold_pipelines.megaplan.orchestration.import_graph\n",
    )

    radius = compute_default_blast_radius(
        ["megaplan/orchestration/import_graph.py"],
        repo,
    )

    assert radius["strategy"] == "scoped"
    assert _selector_values(radius) == ["tests/orchestration/test_import_graph.py"]
    assert radius["import_graph"]["unresolved"] == []


def test_import_graph_syntax_error_degrades_without_losing_other_edges(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/good.py", "VALUE = 1\n")
    _write(repo, "pkg/bad.py", "def broken(:\n")
    _write(repo, "tests/test_good.py", "import pkg.good\n")

    graph = ImportGraph.build(repo)
    resolution = graph.tests_importing(
        ["pkg/good.py"],
        is_test_file=lambda rel_path: rel_path.startswith("tests/test_"),
    )

    assert resolution.degraded is True
    assert resolution.test_files == ["tests/test_good.py"]
    assert resolution.unresolved == []


def test_import_graph_ignores_hidden_and_non_importable_python_paths(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/util.py", "VALUE = 1\n")
    _write(repo, "tests/test_feature.py", "import pkg.util\n")
    _write(repo, "tests/cloud/._test_watchdog_wrappers.py", "import pkg.util\n")
    _write(repo, "tools/subagent-launcher/helper.py", "import pkg.util\n")

    graph = ImportGraph.build(repo)
    resolution = graph.tests_importing(
        ["pkg/util.py"],
        is_test_file=lambda rel_path: rel_path.startswith("tests/test_"),
    )

    assert "tests/cloud/._test_watchdog_wrappers.py" not in graph._file_to_module
    assert "tools/subagent-launcher/helper.py" not in graph._file_to_module
    assert resolution.degraded is False
    assert resolution.test_files == ["tests/test_feature.py"]


def test_degraded_import_graph_caps_scoped_confidence_at_medium(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/good.py", "VALUE = 1\n")
    _write(repo, "pkg/bad.py", "def broken(:\n")
    _write(repo, "tests/test_feature.py", "import pkg.good\n")

    radius = compute_default_blast_radius(["pkg/good.py"], repo)

    assert radius["strategy"] == "scoped"
    assert radius["confidence"] == "medium"
    assert radius["import_graph"]["degraded"] is True
    assert _selector_values(radius) == ["tests/test_feature.py"]


def test_unresolved_surface_without_selector_falls_back_to_full(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/known.py", "VALUE = 1\n")

    radius = compute_default_blast_radius(["pkg/missing.py"], repo)

    assert radius["strategy"] == "full"
    assert radius["confidence"] == "low"
    assert radius["selectors"] == []
    assert radius["import_graph"]["unresolved"] == ["pkg/missing.py"]
    assert radius["uncovered_changes_justification"] == "pkg/missing.py"


def test_non_python_change_preserves_scoped_baseline_with_full_suite_fallback(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/util.py", "VALUE = 1\n")
    _write(repo, "tests/test_feature.py", "import pkg.util\n")
    _write(repo, "tests/fixtures/golden.json", "{}\n")

    radius = compute_default_blast_radius(
        ["pkg/util.py", "tests/fixtures/golden.json"],
        repo,
    )

    assert radius["strategy"] == "scoped"
    assert radius["confidence"] == "low"
    assert radius["full_suite_fallback"] is True
    assert "force the full suite" in radius["rationale"]
    assert _selector_values(radius) == ["tests/test_feature.py"]


def test_missing_declared_pytest_selector_forces_full_suite(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    radius = compute_default_blast_radius(["tests/test_missing.py"], repo)

    assert radius["strategy"] == "full"
    assert radius["selectors"] == []
    assert radius["missing_test_selectors"] == ["tests/test_missing.py"]


def test_resolve_baseline_test_selection_folds_always_run_into_scoped_command(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(tmp_path, "tests/test_feature.py")
    _write(tmp_path, "tests/test_core.py")
    state = _make_state(plan_dir)
    _write_plan_meta(
        plan_dir,
        1,
        {
            "strategy": "scoped",
            "confidence": "high",
            "selectors": [
                {
                    "kind": "path",
                    "value": "tests/test_feature.py",
                    "reason": "import-graph dependent of changed surface",
                }
            ],
            "changed_surfaces": ["pkg/util.py"],
            "always_run": ["tests/test_core.py"],
            "full_suite_fallback": True,
            "rationale": "Scoped.",
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "scoped"
    assert result["command_override"] == (
        "pytest tests/test_feature.py tests/test_core.py"
    )


def test_resolve_baseline_test_selection_rejects_archived_path_selector(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(tmp_path, "tests/archive/m5/pipelines/megaplan/orchestration/test_transition_policy.py")
    state = _make_state(plan_dir)
    _write_plan_meta(
        plan_dir,
        1,
        {
            "strategy": "scoped",
            "confidence": "high",
            "selectors": [
                {
                    "kind": "path",
                    "value": "tests/archive/m5/pipelines/megaplan/orchestration/test_transition_policy.py",
                    "reason": "bad archived selector",
                }
            ],
            "changed_surfaces": ["arnold_pipelines/megaplan/orchestration/transition_policy.py"],
            "always_run": [],
            "full_suite_fallback": True,
            "rationale": "Archived selectors are not valid active baseline inputs.",
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "unresolved"
    assert "do not exist" in result["reason"]


def test_resolve_baseline_test_selection_rejects_missing_path_selector(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir)
    _write_plan_meta(
        plan_dir,
        1,
        {
            "strategy": "scoped",
            "confidence": "high",
            "selectors": [{"kind": "path", "value": "tests/test_missing.py"}],
            "changed_surfaces": ["pkg/util.py"],
            "always_run": [],
            "full_suite_fallback": True,
            "rationale": "Bad selector.",
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "unresolved"
    assert "do not exist" in result["reason"]


def test_resolve_baseline_test_selection_allows_docs_only_no_baseline(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir)
    docs = [
        "docs/extensions/composition-spine/README.md",
        "docs/extensions/composition-spine/m0-decisions.md",
    ]
    _write_plan_meta(
        plan_dir,
        1,
        {
            "strategy": "scoped",
            "confidence": "medium",
            "selectors": [],
            "changed_surfaces": docs,
            "missing_test_selectors": docs,
            "always_run": ["git diff --check -- docs/extensions/composition-spine"],
            "full_suite_fallback": True,
            "rationale": "Documentation-only milestone.",
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "none"
    assert result["command_override"] is None
    assert result["changed_surfaces"] == docs
    assert "documentation surfaces" in result["reason"]


def test_resolve_baseline_test_selection_rejects_missing_always_run_path(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(tmp_path, "tests/test_feature.py")
    state = _make_state(plan_dir)
    _write_plan_meta(
        plan_dir,
        1,
        {
            "strategy": "scoped",
            "confidence": "high",
            "selectors": [{"kind": "path", "value": "tests/test_feature.py"}],
            "changed_surfaces": ["pkg/util.py"],
            "always_run": ["python -m pytest tests/test_missing.py"],
            "full_suite_fallback": True,
            "rationale": "Bad always_run.",
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "unresolved"
    assert "always_run pytest path" in result["reason"]


def test_resolve_baseline_test_selection_missing_metadata_is_unresolved(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir)

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "unresolved"
    assert result["command_override"] is None
    assert "No test_blast_radius" in result["reason"]
    assert "full suite" not in result["reason"]


def test_resolve_baseline_test_selection_explicit_full_allows_full(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir)
    state["config"]["test_selection"] = "full"

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "full"
    assert result["command_override"] is None
    assert "explicit opt-out" in result["reason"]


def test_resolve_baseline_test_selection_ignores_non_path_selector_when_paths_exist(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(tmp_path, "tests/test_feature.py")
    state = _make_state(plan_dir)
    _write_plan_meta(
        plan_dir,
        1,
        {
            "strategy": "scoped",
            "confidence": "high",
            "selectors": [
                {"kind": "path", "value": "tests/test_feature.py"},
                {"kind": "marker", "value": "slow"},
            ],
            "changed_surfaces": ["pkg/util.py"],
            "always_run": [],
            "full_suite_fallback": True,
            "rationale": "Model widened with marker.",
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "scoped"
    assert result["command_override"] == "pytest tests/test_feature.py"
    assert "ignored non-path selector kind(s) marker" in result["reason"]


def test_resolve_baseline_test_selection_rejects_non_path_selector_without_paths(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir)
    _write_plan_meta(
        plan_dir,
        1,
        {
            "strategy": "scoped",
            "confidence": "high",
            "selectors": [{"kind": "marker", "value": "slow"}],
            "changed_surfaces": ["pkg/util.py"],
            "always_run": [],
            "full_suite_fallback": True,
            "rationale": "Model widened with marker only.",
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)

    assert result["mode"] == "unresolved"
    assert result["command_override"] is None
    assert "non-path selector kind(s) marker and no path selectors" in result["reason"]


def test_finalize_baseline_selection_uses_task_files_when_plan_metadata_absent(
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.handlers.finalize import (
        _fallback_baseline_test_selection,
    )

    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    _write(repo, "pkg/util.py", "VALUE = 1\n")
    _write(repo, "tests/test_feature.py", "import pkg.util\n")
    state = _make_state(plan_dir)
    resolved = resolve_baseline_test_selection(plan_dir, state)

    result = _fallback_baseline_test_selection(
        plan_dir,
        state,
        repo,
        resolved,
        planned_files=["pkg/util.py"],
    )

    assert result["mode"] == "scoped"
    assert result["command_override"] == "pytest tests/test_feature.py"
    assert result["fallback_source"] == "finalize_task_files_changed"
    assert "finalize task file" in result["reason"]


def test_finalize_baseline_selection_prefers_task_pytest_commands(
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.handlers.finalize import (
        _fallback_baseline_test_selection,
        _planned_task_pytest_command,
    )

    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    state = _make_state(plan_dir)
    payload = {
        "tasks": [
            {
                "commands_run": [
                    "python scripts/generate_legacy_megaplan_registry.py --check",
                    (
                        "pytest tests/arnold_pipelines/megaplan/test_legacy_surface_ratchets.py "
                        "tests/arnold_pipelines/megaplan/test_import_boundaries.py "
                        "tests/test_gate_grep_ratchet.py -q"
                    ),
                ],
                "files_changed": [
                    "docs/arnold/legacy-megaplan-surface-registry.json"
                ],
            },
            {
                "commands_run": [
                    (
                        "pytest tests/arnold/conformance/test_megaplan_coupling_gate.py "
                        "tests/arnold/conformance/test_conformance_gates.py -q"
                    )
                ],
            },
        ]
    }
    command = _planned_task_pytest_command(payload)
    resolved = resolve_baseline_test_selection(plan_dir, state)

    result = _fallback_baseline_test_selection(
        plan_dir,
        state,
        repo,
        resolved,
        planned_files=["docs/arnold/legacy-megaplan-surface-registry.json"],
        planned_test_command=command,
    )

    assert result["mode"] == "scoped"
    assert result["fallback_source"] == "finalize_task_commands_run"
    assert result["command_override"] == (
        "pytest "
        "tests/arnold_pipelines/megaplan/test_legacy_surface_ratchets.py "
        "tests/arnold_pipelines/megaplan/test_import_boundaries.py "
        "tests/test_gate_grep_ratchet.py "
        "tests/arnold/conformance/test_megaplan_coupling_gate.py "
        "tests/arnold/conformance/test_conformance_gates.py"
    )


def test_finalize_baseline_selection_keeps_full_opt_out_with_task_files(
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.handlers.finalize import (
        _fallback_baseline_test_selection,
    )

    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    state = _make_state(plan_dir)
    state["config"]["test_selection"] = "full"
    resolved = {
        "mode": "full",
        "reason": "explicit full",
        "command_override": None,
    }

    result = _fallback_baseline_test_selection(
        plan_dir,
        state,
        repo,
        resolved,
        planned_files=["pkg/util.py"],
    )

    assert result == resolved


def test_execution_baseline_refreshes_when_finalize_runs_on_new_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.handlers import finalize

    plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    state = _make_state(plan_dir)
    state["meta"]["execution_baseline"] = {
        "captured_at": "2026-01-01T00:00:00Z",
        "head": "old-head",
        "paths": {"tracked.txt": "abc"},
    }

    monkeypatch.setattr(finalize, "_git_head", lambda _project_dir: "new-head")
    monkeypatch.setattr(
        finalize,
        "capture_uncommitted_baseline",
        lambda _project_dir: {
            "captured_at": "2026-01-02T00:00:00Z",
            "head": "new-head",
            "paths": {"tracked.txt": "def"},
        },
    )

    finalize._ensure_execution_baseline(state)

    assert state["meta"]["execution_baseline"] == {
        "captured_at": "2026-01-02T00:00:00Z",
        "head": "new-head",
        "paths": {"tracked.txt": "def"},
    }


def test_graph_build_failure_keeps_name_convention_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/foo.py")
    _write(repo, "tests/pkg/test_foo.py")

    def raise_build(cls: type[ImportGraph], repo_root: Path) -> ImportGraph:
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr(ImportGraph, "build", classmethod(raise_build))

    radius = compute_default_blast_radius(["pkg/foo.py"], repo)

    assert radius["strategy"] == "scoped"
    assert radius["confidence"] == "high"
    assert _selector_values(radius) == ["tests/pkg/test_foo.py"]
