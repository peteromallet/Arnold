"""Tests for ``arnold_pipelines.discovery``."""

from __future__ import annotations

import pytest

from arnold.workflow import Pipeline
from arnold_pipelines.discovery import (
    ShippedPipelineInfo,
    discover_migrated_pipelines,
    discover_shipped_pipelines,
    load_builder,
)


def test_discover_shipped_pipelines_returns_migrated_by_default() -> None:
    results = discover_shipped_pipelines()
    assert results
    for info in results:
        assert info.disposition == "migrate"
        assert isinstance(info, ShippedPipelineInfo)


def test_discover_migrated_pipelines_have_builders() -> None:
    results = discover_migrated_pipelines()
    assert results
    ids = {info.id for info in results}
    expected = {
        "megaplan",
        "doc",
        "creative",
        "jokes",
        "live-supervisor",
        "select-tournament",
        "writing-panel-strict",
        "evidence_pack_verifier",
        "my-pipeline",
    }
    assert ids == expected, f"missing or extra: {ids ^ expected}"
    for info in results:
        assert info.builder is not None
        pipeline = info.builder()
        assert isinstance(pipeline, Pipeline)


def test_migrated_subpipeline_rows_use_normalized_package_paths() -> None:
    results = discover_migrated_pipelines()
    by_id = {info.id: info for info in results}

    expected = {
        "select-tournament": "arnold_pipelines/megaplan/pipelines/select_tournament",
        "writing-panel-strict": "arnold_pipelines/megaplan/pipelines/writing_panel_strict",
    }
    for pipeline_id, package_path in expected.items():
        info = by_id[pipeline_id]
        assert info.package_path == package_path
        assert info.docs_path == f"{package_path}/SKILL.md"
        assert not info.package_path.endswith(".py")
        assert "-" not in info.package_path
        assert info.builder is not None
        assert info.builder().id == pipeline_id


def test_load_builder_works_with_module_target() -> None:
    builder = load_builder("arnold_pipelines.megaplan.pipelines.jokes:build_pipeline")
    pipeline = builder()
    assert isinstance(pipeline, Pipeline)
    assert pipeline.id == "jokes"


def test_load_builder_rejects_malformed_target() -> None:
    with pytest.raises(ValueError):
        load_builder("no_colon_here")


def test_load_builder_rejects_missing_builder() -> None:
    with pytest.raises(ValueError):
        load_builder("arnold_pipelines.megaplan.pipelines.jokes:missing_builder")


def test_archived_pipelines_included_when_requested() -> None:
    results = discover_shipped_pipelines(include_archived=True)
    archived = {info.id for info in results if info.disposition == "archive"}
    assert "megaplan.epic_blitz_py" in archived or "megaplan.epic_blitz" in archived
