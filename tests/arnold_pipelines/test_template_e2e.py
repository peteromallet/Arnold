"""End-to-end tests for the migrated ``arnold_pipelines/_template`` package.

Covers three concerns from the M5 Phase 3 scaffold plan:

1. **Scanner exclusion** — the legacy megaplan-side pipeline discovery scanner
   must skip ``_template`` because its leading-underscore directory name
   triggers the skip rule.
2. **Workflow compile/dry-run/fake-run** — the skeleton ``build_pipeline()``
   returns an :class:`arnold.workflow.dsl.Pipeline` that compiles, dry-runs,
   and fake-runs to completion.
3. **Determinism** — repeated builds produce the same ``manifest_hash``.
"""

from __future__ import annotations

from pathlib import Path

from arnold.execution import run
from arnold.execution.backend import SkeletalBackend
from arnold.workflow import Pipeline, compile_pipeline, dry_run
from arnold_pipelines._template import build_pipeline
from arnold_pipelines.megaplan._pipeline.registry import _scan_dir_for_pipeline_modules


def test_template_excluded_by_legacy_scanner() -> None:
    """The legacy scanner must NOT return ``_template`` as a discovered pipeline."""

    registry_file = Path(__file__).resolve().parent.parent.parent / (
        "arnold_pipelines/megaplan/_pipeline/registry.py"
    )
    pipelines_dir = registry_file.resolve().parent.parent.parent  # arnold_pipelines/

    results = _scan_dir_for_pipeline_modules(
        pipelines_dir, package_prefix="arnold.pipelines"
    )
    found_names = [cli_name for cli_name, _ in results]
    found_paths = [str(mod_path) for _, mod_path in results]

    assert "_template" not in found_names
    assert not any("_template" in p for p in found_paths)


def test_template_builds_workflow_pipeline() -> None:
    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert pipeline.id == "my-pipeline"


def test_template_compiles() -> None:
    manifest = compile_pipeline(build_pipeline())
    assert manifest.id == "my-pipeline"
    assert manifest.manifest_hash
    assert manifest.topology_hash


def test_template_dry_run() -> None:
    manifest = compile_pipeline(build_pipeline())
    report = dry_run(manifest)
    assert report["id"] == manifest.id
    assert report["manifest_hash"] == manifest.manifest_hash
    assert report["node_count"] == 2
    assert report["edge_count"] == 1


def test_template_fake_runs(tmp_path: Path) -> None:
    manifest = compile_pipeline(build_pipeline())
    result = run(
        manifest,
        artifact_root=tmp_path / "template-run",
        backend=SkeletalBackend(),
    )
    assert result.state.value == "completed"
    assert result.manifest_hash == manifest.manifest_hash


def test_template_manifest_hash_is_deterministic() -> None:
    m1 = compile_pipeline(build_pipeline())
    m2 = compile_pipeline(build_pipeline())
    assert m1.manifest_hash == m2.manifest_hash
