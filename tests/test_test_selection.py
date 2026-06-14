"""Focused tests for the M1 deterministic blast-radius helper and M2 metadata helpers."""

from __future__ import annotations

import json
from pathlib import Path

from arnold.pipelines.megaplan.orchestration.test_selection import (
    PlanBlastRadius,
    PlanChangedFiles,
    compute_default_blast_radius,
    read_plan_blast_radius,
    resolve_changed_file_provenance,
)


def _write(repo: Path, rel_path: str, content: str = "") -> None:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or f"# {rel_path}\n", encoding="utf-8")


def test_changed_test_file_test_prefix_is_selected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/unit/test_alpha.py")

    radius = compute_default_blast_radius(["tests/unit/test_alpha.py"], repo)

    assert radius["strategy"] == "scoped"
    assert radius["confidence"] == "high"
    assert radius["selectors"] == [
        {
            "kind": "path",
            "value": "tests/unit/test_alpha.py",
            "reason": "changed test file",
        }
    ]
    assert radius["changed_surfaces"] == []


def test_changed_test_file_suffix_pattern_is_selected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/unit/alpha_test.py")

    radius = compute_default_blast_radius(["tests/unit/alpha_test.py"], repo)

    assert radius["strategy"] == "scoped"
    assert radius["confidence"] == "high"
    assert [selector["value"] for selector in radius["selectors"]] == [
        "tests/unit/alpha_test.py"
    ]


def test_direct_mirror_match_keeps_scoped_high(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/foo.py")
    _write(repo, "tests/pkg/test_foo.py")

    radius = compute_default_blast_radius(["pkg/foo.py"], repo)

    assert radius["strategy"] == "scoped"
    assert radius["confidence"] == "high"
    assert radius["changed_surfaces"] == ["pkg/foo.py"]
    assert [selector["value"] for selector in radius["selectors"]] == [
        "tests/pkg/test_foo.py"
    ]


def test_bounded_basename_match_drops_confidence_to_medium(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/bar.py")
    _write(repo, "tests/integration/test_bar.py")

    radius = compute_default_blast_radius(["pkg/bar.py"], repo)

    assert radius["strategy"] == "scoped"
    assert radius["confidence"] == "medium"
    assert radius["changed_surfaces"] == ["pkg/bar.py"]
    assert [selector["value"] for selector in radius["selectors"]] == [
        "tests/integration/test_bar.py"
    ]
    assert "bounded basename search" in radius["rationale"]


def test_uncovered_python_surface_forces_full_low_with_justification(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/missing.py")

    radius = compute_default_blast_radius(["pkg/missing.py"], repo)

    assert radius["strategy"] == "full"
    assert radius["confidence"] == "low"
    assert radius["selectors"] == []
    assert radius["changed_surfaces"] == ["pkg/missing.py"]
    assert radius["uncovered_changes_justification"] == "pkg/missing.py"


def test_support_file_is_surface_not_direct_selector(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/conftest.py")

    radius = compute_default_blast_radius(["tests/conftest.py"], repo)

    assert radius["strategy"] == "full"
    assert radius["confidence"] == "low"
    assert radius["selectors"] == []
    assert radius["changed_surfaces"] == ["tests/conftest.py"]


def test_non_python_only_changes_produce_none_strategy_and_rationale(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "docs/readme.md")

    radius = compute_default_blast_radius(["docs/readme.md"], repo)

    assert radius["strategy"] == "none"
    assert radius["confidence"] == "medium"
    assert radius["selectors"] == []
    assert radius["changed_surfaces"] == []
    assert "docs/readme.md" in radius["rationale"]


def test_non_python_data_change_forces_full_suite(tmp_path: Path) -> None:
    # A fixture/golden/config change can affect tests the import graph can't see,
    # so it must force the full suite — unlike a prose-doc change.
    repo = tmp_path / "repo"
    _write(repo, "tests/fixtures/data.yaml")

    radius = compute_default_blast_radius(["tests/fixtures/data.yaml"], repo)

    assert radius["strategy"] == "full"
    assert "tests/fixtures/data.yaml" in radius["rationale"]


def test_selectors_are_deduplicated_with_changed_test_reason_winning(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "pkg/foo.py")
    _write(repo, "tests/pkg/test_foo.py")

    radius = compute_default_blast_radius(
        ["pkg/foo.py", "tests/pkg/test_foo.py"],
        repo,
    )

    assert radius["selectors"] == [
        {
            "kind": "path",
            "value": "tests/pkg/test_foo.py",
            "reason": "changed test file",
        }
    ]


# ---------------------------------------------------------------------------
# M2 — Metadata helper tests
# ---------------------------------------------------------------------------


def _make_state(plan_dir: Path, version: int = 1) -> dict:
    """Return a minimal PlanState whose ``plan_versions`` points into *plan_dir*."""
    plan_filename = f"plan_v{version}.md"
    meta_filename = f"plan_v{version}.meta.json"
    return {
        "plan_versions": [
            {"version": version, "file": plan_filename, "hash": "abc", "timestamp": "2026-01-01T00:00:00Z"}
        ],
        "config": {},
        "meta": {},
    }


def _write_plan_meta(plan_dir: Path, version: int, extra: dict | None = None) -> dict:
    """Write a ``plan_v{N}.meta.json`` and return the metadata dict."""
    meta = {
        "version": version,
        "timestamp": "2026-01-01T00:00:00Z",
        "hash": "sha256:abc",
        "questions": [],
        "success_criteria": [],
        "assumptions": [],
        "structure_warnings": [],
    }
    if extra:
        meta.update(extra)
    meta_path = plan_dir / f"plan_v{version}.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    # Also need the plan .md so latest_plan_path doesn't error on read.
    (plan_dir / f"plan_v{version}.md").write_text(f"# Plan v{version}\n", encoding="utf-8")
    return meta


# --- read_plan_blast_radius tests ---


def test_read_blast_radius_returns_value_when_present(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    _write_plan_meta(plan_dir, 2, extra={"test_blast_radius": {"strategy": "scoped", "confidence": "high"}})

    result = read_plan_blast_radius(plan_dir, state)

    assert result.is_present
    assert result.value == {"strategy": "scoped", "confidence": "high"}
    assert result.meta_path == plan_dir / "plan_v2.meta.json"


def test_read_blast_radius_returns_none_when_no_plan_versions(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = {"plan_versions": [], "config": {}, "meta": {}}

    result = read_plan_blast_radius(plan_dir, state)

    assert not result.is_present
    assert result.value is None
    assert result.meta_path is None


def test_read_blast_radius_returns_none_when_meta_file_missing(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=3)
    # Don't write the meta file.

    result = read_plan_blast_radius(plan_dir, state)

    assert not result.is_present
    assert result.value is None


def test_read_blast_radius_returns_none_when_field_absent(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=1)
    _write_plan_meta(plan_dir, 1)  # No test_blast_radius

    result = read_plan_blast_radius(plan_dir, state)

    assert not result.is_present
    assert result.meta_path == plan_dir / "plan_v1.meta.json"


def test_read_blast_radius_returns_none_when_field_is_not_dict(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=1)
    _write_plan_meta(plan_dir, 1, extra={"test_blast_radius": "not a dict"})

    result = read_plan_blast_radius(plan_dir, state)

    assert not result.is_present


# --- resolve_changed_file_provenance tests ---


def test_provenance_uncertain_when_no_blast_radius(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=1)
    _write_plan_meta(plan_dir, 1)  # No test_blast_radius

    result = resolve_changed_file_provenance(plan_dir, state)

    assert result.uncertain is True
    assert result.files == []
    assert "no plan blast radius" in result.source


def test_provenance_uncertain_when_changed_surfaces_missing(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    _write_plan_meta(
        plan_dir, 2,
        extra={"test_blast_radius": {"strategy": "scoped", "confidence": "high"}},
    )

    result = resolve_changed_file_provenance(plan_dir, state)

    assert result.uncertain is True
    assert "changed_surfaces is missing" in result.source


def test_provenance_uncertain_when_changed_surfaces_not_list(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    _write_plan_meta(
        plan_dir, 2,
        extra={"test_blast_radius": {"strategy": "scoped", "changed_surfaces": "not-a-list"}},
    )

    result = resolve_changed_file_provenance(plan_dir, state)

    assert result.uncertain is True


def test_provenance_uncertain_when_entry_invalid(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    _write_plan_meta(
        plan_dir, 2,
        extra={
            "test_blast_radius": {
                "strategy": "scoped",
                "changed_surfaces": ["good.py", 42],
            }
        },
    )

    result = resolve_changed_file_provenance(plan_dir, state)

    assert result.uncertain is True
    assert "non-string" in result.source.lower()


def test_provenance_uncertain_when_empty_string_entry(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    _write_plan_meta(
        plan_dir, 2,
        extra={
            "test_blast_radius": {
                "strategy": "scoped",
                "changed_surfaces": ["good.py", "   "],
            }
        },
    )

    result = resolve_changed_file_provenance(plan_dir, state)

    assert result.uncertain is True


def test_provenance_certain_with_valid_changed_surfaces(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    _write_plan_meta(
        plan_dir, 2,
        extra={
            "test_blast_radius": {
                "strategy": "scoped",
                "changed_surfaces": ["pkg/foo.py", "pkg/bar.py"],
            }
        },
    )

    result = resolve_changed_file_provenance(plan_dir, state)

    assert result.uncertain is False
    assert result.files == ["pkg/foo.py", "pkg/bar.py"]
    assert "plan_v*.meta.json" in result.source


def test_provenance_strips_whitespace_from_entries(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    _write_plan_meta(
        plan_dir, 2,
        extra={
            "test_blast_radius": {
                "strategy": "scoped",
                "changed_surfaces": ["  pkg/foo.py  ", " pkg/bar.py"],
            }
        },
    )

    result = resolve_changed_file_provenance(plan_dir, state)

    assert result.uncertain is False
    assert result.files == ["pkg/foo.py", "pkg/bar.py"]


def test_provenance_certain_with_empty_surfaces_list(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    _write_plan_meta(
        plan_dir, 2,
        extra={
            "test_blast_radius": {
                "strategy": "full",
                "changed_surfaces": [],
            }
        },
    )

    result = resolve_changed_file_provenance(plan_dir, state)

    assert result.uncertain is False
    assert result.files == []


# --- PlanBlastRadius / PlanChangedFiles dataclass behaviour ---


def test_plan_blast_radius_is_present_false_for_none_value() -> None:
    pbr = PlanBlastRadius(value=None)
    assert not pbr.is_present


def test_plan_blast_radius_is_present_true_for_dict_value() -> None:
    pbr = PlanBlastRadius(value={"strategy": "full"})
    assert pbr.is_present


def test_plan_changed_files_defaults() -> None:
    pcf = PlanChangedFiles(files=[])
    assert pcf.files == []
    assert pcf.uncertain is False
    assert pcf.source == ""


# ---------------------------------------------------------------------------
# M2 — resolve_baseline_test_selection tests
# ---------------------------------------------------------------------------


def test_selection_defaults_to_full_when_config_missing(tmp_path: Path) -> None:
    """Default-ON: without test_selection config, scoped selection is attempted for
    every plan, but with no blast radius in metadata the ladder falls back to the
    full suite — so a plan that hasn't earned a scoped run still runs full (safe)."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = {"config": {}, "plan_versions": [], "meta": {}}

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["mode"] == "full"
    assert result["command_override"] is None
    # Default-on reaches full via the no-radius fallback, not the old opt-in gate.
    assert "blast_radius" in result["reason"] or "full suite" in result["reason"]


def test_selection_defaults_to_full_when_config_is_full(tmp_path: Path) -> None:
    """test_selection: 'full' → mode 'full'."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = {"config": {"test_selection": "full"}, "plan_versions": [], "meta": {}}

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["mode"] == "full"
    assert result["command_override"] is None


def test_selection_full_when_scoped_but_no_blast_radius(tmp_path: Path) -> None:
    """test_selection: 'scoped' but no plan meta → full suite fallback."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=1)
    state["config"]["test_selection"] = "scoped"
    # Don't write meta → blast radius unavailable

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["mode"] == "full"
    assert "no test_blast_radius" in result["reason"].lower()


def test_selection_full_when_scoped_but_strategy_full(tmp_path: Path) -> None:
    """test_selection: 'scoped' but blast_radius strategy is 'full' → full."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    state["config"]["test_selection"] = "scoped"
    _write_plan_meta(
        plan_dir, 2,
        extra={"test_blast_radius": {"strategy": "full", "selectors": []}},
    )

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["mode"] == "full"
    assert "not 'scoped'" in result["reason"]


def test_selection_full_when_scoped_but_no_selectors(tmp_path: Path) -> None:
    """test_selection: 'scoped', strategy 'scoped', but selectors empty → full."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    state["config"]["test_selection"] = "scoped"
    _write_plan_meta(
        plan_dir, 2,
        extra={"test_blast_radius": {"strategy": "scoped", "selectors": []}},
    )

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["mode"] == "full"


def test_selection_scoped_with_valid_path_selectors(tmp_path: Path) -> None:
    """Golden path: scoped config + blast radius with path selectors."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    state["config"]["test_selection"] = "scoped"
    _write_plan_meta(
        plan_dir, 2,
        extra={
            "test_blast_radius": {
                "strategy": "scoped",
                "selectors": [
                    {"kind": "path", "value": "tests/test_foo.py", "reason": "changed test file"},
                    {"kind": "path", "value": "tests/test_bar.py", "reason": "mirror for pkg/bar.py"},
                ],
            }
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["mode"] == "scoped"
    assert result["command_override"] is not None
    assert "tests/test_foo.py" in result["command_override"]
    assert "tests/test_bar.py" in result["command_override"]
    assert result["command_override"].startswith("pytest ")
    assert result["selectors_used"] is not None


def test_selection_scoped_deduplicates_path_selectors(tmp_path: Path) -> None:
    """Duplicate path values appear only once in the scoped command."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    state["config"]["test_selection"] = "scoped"
    _write_plan_meta(
        plan_dir, 2,
        extra={
            "test_blast_radius": {
                "strategy": "scoped",
                "selectors": [
                    {"kind": "path", "value": "tests/test_dup.py", "reason": "first"},
                    {"kind": "path", "value": "tests/test_dup.py", "reason": "duplicate"},
                ],
            }
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["mode"] == "scoped"
    # The path should appear only once.
    assert result["command_override"].count("tests/test_dup.py") == 1


def test_selection_full_when_scoped_but_no_path_kind_selectors(tmp_path: Path) -> None:
    """Only 'path'-kind selectors contribute; all others → full fallback."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    state["config"]["test_selection"] = "scoped"
    _write_plan_meta(
        plan_dir, 2,
        extra={
            "test_blast_radius": {
                "strategy": "scoped",
                "selectors": [
                    {"kind": "nodeid", "value": "tests/test_x.py::test_y", "reason": "nodeid"},
                ],
            }
        },
    )

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["mode"] == "full"
    assert "no path selectors" in result["reason"]


def test_selection_records_selectors_used_for_observability(tmp_path: Path) -> None:
    """The returned dict includes selectors_used for payload recording."""
    from arnold.pipelines.megaplan.orchestration.test_selection import resolve_baseline_test_selection

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _make_state(plan_dir, version=2)
    state["config"]["test_selection"] = "scoped"
    selectors = [
        {"kind": "path", "value": "tests/test_a.py", "reason": "changed"},
    ]
    _write_plan_meta(
        plan_dir, 2,
        extra={"test_blast_radius": {"strategy": "scoped", "selectors": selectors}},
    )

    result = resolve_baseline_test_selection(plan_dir, state)
    assert result["selectors_used"] == selectors
