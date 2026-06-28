"""Tests for ``arnold_pipelines.discovery``."""

from __future__ import annotations

import pytest

from arnold.pipeline import Pipeline as NativePipeline
from arnold.pipeline.native import NativeProgram
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
        "epic-blitz",
    }
    assert ids == expected, f"missing or extra: {ids ^ expected}"
    for info in results:
        assert info.builder is not None
        pipeline = info.builder()
        if info.builder_contract == "workflow":
            assert info.load_state == "workflow"
            assert isinstance(pipeline, Pipeline)
        elif info.builder_contract == "native":
            if info.load_state == "loadable-native":
                assert isinstance(pipeline, NativePipeline)
                assert isinstance(pipeline.native_program, NativeProgram)
            else:
                assert info.load_state == "not-loadable"
                assert info.diagnostic
        else:
            pytest.fail(f"unexpected loaded contract: {info.builder_contract}")


def test_migrated_subpipeline_rows_use_normalized_package_paths() -> None:
    results = discover_migrated_pipelines()
    by_id = {info.id: info for info in results}

    expected = {
        "creative": "arnold_pipelines/megaplan/pipelines/creative",
        "doc": "arnold_pipelines/megaplan/pipelines/doc",
        "jokes": "arnold_pipelines/megaplan/pipelines/jokes",
        "live-supervisor": "arnold_pipelines/megaplan/pipelines/live_supervisor",
        "writing-panel-strict": "arnold_pipelines/megaplan/pipelines/writing_panel_strict",
        "epic-blitz": "arnold_pipelines/megaplan/pipelines/epic_blitz.py",
        "select-tournament": "arnold_pipelines/megaplan/pipelines/select_tournament",
    }
    for pipeline_id, package_path in expected.items():
        info = by_id[pipeline_id]
        assert info.package_path == package_path
        if package_path.endswith(".py"):
            assert info.docs_path == "arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md"
        else:
            assert info.docs_path == f"{package_path}/SKILL.md"
        if pipeline_id != "epic-blitz":
            assert not info.package_path.endswith(".py")
            assert "-" not in info.package_path
        assert info.builder is not None
        built = info.builder()
        if hasattr(built, "id"):
            assert built.id == pipeline_id
        else:
            assert info.builder_contract == "native"
        assert info.builder_contract == "native"
        assert info.canonical_builder_path == (
            f"{package_path[:-3] if package_path.endswith('.py') else package_path}"
            .replace("/", ".")
            + ":build_pipeline"
        )


def test_discovery_exposes_load_state_contracts_and_deferred_native() -> None:
    results = discover_shipped_pipelines()
    by_id = {info.id: info for info in results}

    workflow_rows = {
        "megaplan",
        "evidence_pack_verifier",
    }
    for pipeline_id in workflow_rows:
        info = by_id[pipeline_id]
        assert info.builder_contract == "workflow"
        assert info.load_state == "workflow"
        assert info.canonical_builder_path is not None

    assert by_id["my-pipeline"].builder_contract == "native"
    assert by_id["my-pipeline"].load_state == "loadable-native"
    assert by_id["my-pipeline"].canonical_builder_path is not None

    assert by_id["creative"].builder_contract == "native"
    assert by_id["creative"].load_state == "loadable-native"


def test_native_discovery_does_not_canonicalize_mirrored_modules() -> None:
    """Megaplan migrated rows use the product package as their canonical source."""

    native_or_deferred = {
        info.id: info
        for info in discover_shipped_pipelines()
        if info.builder_contract in {"native", "deferred-native"}
    }
    expected = {
        "creative": "arnold_pipelines.megaplan.pipelines.creative:build_pipeline",
        "doc": "arnold_pipelines.megaplan.pipelines.doc:build_pipeline",
        "jokes": "arnold_pipelines.megaplan.pipelines.jokes:build_pipeline",
        "live-supervisor": "arnold_pipelines.megaplan.pipelines.live_supervisor:build_pipeline",
        "writing-panel-strict": "arnold_pipelines.megaplan.pipelines.writing_panel_strict:build_pipeline",
        "epic-blitz": "arnold_pipelines.megaplan.pipelines.epic_blitz:build_pipeline",
        "select-tournament": "arnold_pipelines.megaplan.pipelines.select_tournament:build_pipeline",
        "my-pipeline": "arnold_pipelines._template:build_pipeline",
    }

    assert set(native_or_deferred) == set(expected)
    for pipeline_id, target in expected.items():
        info = native_or_deferred[pipeline_id]
        assert info.canonical_builder_path == target

def test_load_builder_works_with_module_target() -> None:
    builder = load_builder("arnold_pipelines.megaplan.pipelines.jokes:build_pipeline")
    pipeline = builder()
    assert isinstance(pipeline, NativePipeline)
    assert pipeline.entry == "draft"


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
    assert "legacy.folder_audit" in archived
    assert "legacy.deliberation" in archived
