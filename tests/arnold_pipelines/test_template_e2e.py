"""End-to-end tests for the workflow-first ``arnold_pipelines/_template`` package.

Covers three concerns from the M2 package-contract phase:

1. **Scanner exclusion** — the legacy megaplan-side pipeline discovery scanner
   must skip ``_template`` because its leading-underscore directory name
   triggers the skip rule.
2. **Workflow-first build** — the skeleton ``build_pipeline()`` returns an
   :class:`arnold.workflow.Pipeline` built from explicit nodes and routes.
3. **Determinism** — repeated builds produce the same pipeline topology and,
   after compilation, the same manifest hashes.
"""

from __future__ import annotations

from pathlib import Path

import arnold.workflow as workflow
from arnold.workflow import Pipeline, compile_pipeline
from arnold_pipelines._template import build_pipeline
from arnold_pipelines.megaplan.runtime.discovery import _scan_dir_for_pipeline_modules


def test_template_excluded_by_legacy_scanner() -> None:
    """The legacy scanner must NOT return ``_template`` as a discovered pipeline."""

    registry_file = Path(__file__).resolve().parent.parent.parent / (
        "arnold_pipelines/megaplan/runtime/discovery.py"
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
    step_ids = {step.id for step in pipeline.steps}
    assert "start" in step_ids
    assert "finish" in step_ids


def test_template_pipeline_has_expected_routes() -> None:
    pipeline = build_pipeline()
    assert len(pipeline.routes) == 1
    assert pipeline.routes[0].id == "start-finish"
    assert pipeline.routes[0].source == "start"
    assert pipeline.routes[0].target == "finish"


def test_template_manifest_identity_is_deterministic() -> None:
    p1 = build_pipeline()
    p2 = build_pipeline()
    m1 = compile_pipeline(p1)
    m2 = compile_pipeline(p2)
    assert m1.manifest_hash == m2.manifest_hash
    assert m1.topology_hash == m2.topology_hash


def test_template_compile_produces_valid_manifest() -> None:
    pipeline = build_pipeline()
    manifest = compile_pipeline(pipeline)
    assert manifest.schema_version == workflow.WorkflowManifest.SCHEMA_VERSION
    assert manifest.manifest_hash
    assert manifest.topology_hash
    assert any(node.id == "start" for node in manifest.nodes)
    assert any(node.id == "finish" for node in manifest.nodes)
