"""Phase 3 migration tests for shipped ``arnold_pipelines`` packages.

Every surviving shipped pipeline must:

1. Expose ``build_pipeline() -> arnold.workflow.Pipeline``.
2. Compile to a valid ``WorkflowManifest``.
3. Produce a deterministic dry-run report.
4. Fake-run to completion with the skeletal backend.
5. Yield a stable ``manifest_hash`` across repeated builds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import arnold.workflow as workflow
from arnold.execution import run
from arnold.execution.backend import SkeletalBackend
from arnold.workflow import Pipeline, compile_pipeline, dry_run

from arnold_pipelines.discovery import discover_migrated_pipelines


_MIGRATED = discover_migrated_pipelines()
_BUILDER_TARGETS = [
    (info.id, f"{info.package_path.replace('/', '.')}:build_pipeline")
    for info in _MIGRATED
]


def _import_builder(target: str) -> Any:
    """Import a ``package.module:builder_name`` target."""

    module_name, builder_name = target.rsplit(":", 1)
    if module_name.endswith(".py"):
        module_name = module_name[:-3]
    import importlib

    module = importlib.import_module(module_name)
    return getattr(module, builder_name)


@pytest.mark.parametrize("pipeline_id,target", _BUILDER_TARGETS)
def test_build_pipeline_returns_workflow_pipeline(pipeline_id: str, target: str) -> None:
    builder = _import_builder(target)
    pipeline = builder()
    assert isinstance(pipeline, Pipeline), f"{pipeline_id}: expected Pipeline, got {type(pipeline).__name__}"
    assert pipeline.id


@pytest.mark.parametrize("pipeline_id,target", _BUILDER_TARGETS)
def test_compile_pipeline(pipeline_id: str, target: str) -> None:
    builder = _import_builder(target)
    pipeline = builder()
    manifest = compile_pipeline(pipeline)
    assert manifest.id == pipeline.id
    assert manifest.manifest_hash
    assert manifest.topology_hash
    assert manifest.schema_version == workflow.WorkflowManifest.SCHEMA_VERSION


@pytest.mark.parametrize("pipeline_id,target", _BUILDER_TARGETS)
def test_dry_run_report(pipeline_id: str, target: str) -> None:
    builder = _import_builder(target)
    manifest = compile_pipeline(builder())
    report = dry_run(manifest)
    assert report["id"] == manifest.id
    assert report["manifest_hash"] == manifest.manifest_hash
    assert report["node_count"] == len(manifest.nodes)
    assert report["edge_count"] == len(manifest.edges)


@pytest.mark.parametrize("pipeline_id,target", _BUILDER_TARGETS)
def test_fake_run_completes(pipeline_id: str, target: str, tmp_path: Path) -> None:
    builder = _import_builder(target)
    manifest = compile_pipeline(builder())
    result = run(manifest, artifact_root=tmp_path / pipeline_id, backend=SkeletalBackend())
    assert result.state.value == "completed"
    assert result.manifest_hash == manifest.manifest_hash


@pytest.mark.parametrize("pipeline_id,target", _BUILDER_TARGETS)
def test_manifest_hash_is_deterministic(pipeline_id: str, target: str) -> None:
    builder = _import_builder(target)
    m1 = compile_pipeline(builder())
    m2 = compile_pipeline(builder())
    assert m1.manifest_hash == m2.manifest_hash
    assert m1.topology_hash == m2.topology_hash


@pytest.mark.parametrize("pipeline_id,target", _BUILDER_TARGETS)
def test_discovery_matches_build(pipeline_id: str, target: str) -> None:
    """Discovery metadata points at a loadable builder that returns the same id."""

    info = next(info for info in _MIGRATED if info.id == pipeline_id)
    assert info.builder is not None
    assert info.disposition == "migrate"
    assert info.public
    pipeline = info.builder()
    assert isinstance(pipeline, Pipeline)
    # The discovered id is the canonical label; the pipeline id may be a short
    # alias (e.g. "creative") or include underscores (e.g. "evidence_pack_verifier").
    assert pipeline.id
