"""Manifest-first discovery finds megaplan with correct metadata.

The in-tree planning pipeline package is discovered under the canonical
``megaplan`` identity. These tests assert that discover_python_pipelines()
(flag-ON) returns a ``megaplan`` entry whose
manifest-derived metadata matches the expected contract.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan._pipeline import registry
from arnold.pipeline.discovery.manifest import Manifest


# ── Expected metadata from megaplan/pipelines/planning/__init__.py ──────

EXPECTED_PLANNING_METADATA = {
    "name": "megaplan",
    "description": (
        "Built-in megaplan pipeline: prep → plan → critique/gate/revise loop "
        "→ finalize → execute → review. Gate verdicts: proceed / iterate / "
        "tiebreaker / escalate. Robustness levels: bare / light / full / "
        "thorough / extreme."
    ),
    "arnold_api_version": "1.0",
    "capabilities": ("plan", "execute", "review"),
    "supported_modes": ("plan",),
}


@pytest.fixture
def planning_only_scan_root(tmp_path: Path):
    """Create a temporary pipelines directory containing *only* the planning package.

    This avoids aggregate-RuntimeError from other in-tree pipelines that
    do not yet carry the M6 ``driver`` manifest field.
    """
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    # Copy the real planning package into the temp dir.
    real_planning = (
        Path(__file__).resolve().parents[2]
        / "arnold" / "pipelines" / "megaplan" / "pipelines" / "planning"
    )
    shutil.copytree(real_planning, pipelines_dir / "planning")
    return pipelines_dir


def test_discover_python_pipelines_flag_on_finds_planning_with_correct_metadata(
    planning_only_scan_root: Path,
):
    """Under M6 flag-ON, planning is discovered via manifest."""
    with patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "1"}, clear=False
    ), patch.object(
        registry, "_get_scan_roots",
        lambda: [(planning_only_scan_root, "arnold.pipelines.megaplan.pipelines")],
    ):
        quads = registry.discover_python_pipelines()

    # ── planning must be present ──
    by_name = {q[0]: q for q in quads}
    assert "megaplan" in by_name, (
        f"megaplan not discovered under flag-ON; got names: {sorted(by_name)}"
    )

    cli_name, builder, meta, source_path = by_name["megaplan"]

    # ── builder is deferred ──
    assert getattr(builder, "_m6_deferred", False), (
        "planning builder must be deferred under flag-ON"
    )

    # ── source_path points to a planning __init__.py ──
    source = str(source_path)
    assert "__init__.py" in source, f"unexpected source_path: {source}"

    # ── metadata parity ──
    for key, expected_value in EXPECTED_PLANNING_METADATA.items():
        actual = meta.get(key)
        assert actual == expected_value, (
            f"metadata[{key!r}] mismatch: expected {expected_value!r}, got {actual!r}"
        )

    # ── arnold_api_version is semver-parsable ──
    assert "." in meta["arnold_api_version"], (
        f"arnold_api_version not semver: {meta['arnold_api_version']!r}"
    )


def test_discover_python_pipelines_flag_on_planning_builder_is_callable_and_yields_pipeline(
    planning_only_scan_root: Path,
):
    """The deferred builder for planning actually works — it produces a Pipeline."""
    with patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "1"}, clear=False
    ), patch.object(
        registry, "_get_scan_roots",
        lambda: [(planning_only_scan_root, "arnold.pipelines.megaplan.pipelines")],
    ):
        quads = registry.discover_python_pipelines()

    by_name = {q[0]: q for q in quads}
    assert "megaplan" in by_name

    _cli_name, builder, _meta, _source_path = by_name["megaplan"]

    from arnold.pipeline.types import Pipeline as PipelineCls

    pipeline = builder()
    assert isinstance(pipeline, PipelineCls), (
        f"builder returned {type(pipeline)}, not Pipeline"
    )
    assert pipeline.entry == "prep"
    # canonical 9-stage shape
    assert set(pipeline.stages.keys()) == {
        "prep", "plan", "critique", "gate", "revise",
        "finalize", "execute", "review", "tiebreaker",
    }, f"unexpected stages: {set(pipeline.stages.keys())}"


def test_scan_python_pipelines_flag_on_planning_disposition_has_manifest(
    planning_only_scan_root: Path,
):
    """Under flag-ON, scan_python_pipelines() returns planning's Manifest."""
    with patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "1"}, clear=False
    ), patch.object(
        registry, "_get_scan_roots",
        lambda: [(planning_only_scan_root, "arnold.pipelines.megaplan.pipelines")],
    ):
        dispositions = registry.scan_python_pipelines()

    planning_dispositions = [
        d for d in dispositions if d.cli_name == "megaplan"
    ]
    assert len(planning_dispositions) >= 1, (
        f"no planning disposition; got cli_names: "
        f"{[d.cli_name for d in dispositions]}"
    )

    d = planning_dispositions[0]
    assert d.status == "discovered", f"planning status={d.status!r}, reason={d.reason!r}"
    assert isinstance(d.manifest, Manifest), (
        f"planning manifest is {type(d.manifest)}, not Manifest"
    )
    assert d.manifest.capabilities == ("plan", "execute", "review")
    assert d.manifest.arnold_api_version == "1.0"
    assert d.manifest.name == "megaplan"
