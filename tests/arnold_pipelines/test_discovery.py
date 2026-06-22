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
