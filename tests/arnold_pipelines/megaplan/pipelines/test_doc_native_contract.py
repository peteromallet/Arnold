"""Native contract tests for the ``doc`` pipeline (restored from archive/m5).

Verifies the native-first package contract: build_pipeline returns a
native-backed projected shell, stage keys are canonical, and no
graph-era builders are exposed publicly.
"""

from __future__ import annotations

from pathlib import Path
import json

import pytest

from arnold.pipeline import Pipeline
from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.native import NativeProgram
from arnold.runtime.envelope import RuntimeEnvelope


# ── Stage-key assertions ─────────────────────────────────────────────────


def test_doc_pipeline_stage_keys_in_canonical_order() -> None:
    from arnold_pipelines.megaplan.pipelines.doc import build_pipeline

    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert tuple(pipeline.stages.keys()) == (
        "outline",
        "section_drafts",
        "critique",
        "revise",
        "assembly",
    )
    # Belt-and-braces: .values() carries Stage objects with .name.
    assert tuple(s.name for s in pipeline.stages.values()) == (
        "outline",
        "section_drafts",
        "critique",
        "revise",
        "assembly",
    )


# ── Native contract assertions ───────────────────────────────────────────


def test_doc_build_pipeline_returns_native_backed_shell() -> None:
    from arnold_pipelines.megaplan.pipelines.doc import build_pipeline

    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "doc"
    assert tuple(pipeline.resource_bundles) == ()


def test_doc_package_metadata_advertises_native() -> None:
    import arnold_pipelines.megaplan.pipelines.doc as pkg

    assert pkg.name == "doc"
    assert pkg.driver[0] == "native"
    assert "native" in pkg.supported_modes
    assert pkg.entrypoint == "build_pipeline"
    assert callable(pkg.build_pipeline)
    # No legacy graph builders leaked.
    assert not hasattr(pkg, "_build_graph_pipeline")


def test_doc_mirror_is_compatibility_shim() -> None:
    import arnold_pipelines.megaplan.pipelines.doc as canonical
    import arnold_pipelines.megaplan.pipelines.doc.pipeline as canonical_pipeline

    assert canonical.build_pipeline is canonical_pipeline.build_pipeline
    # Both expose the same public names (order may differ, pipeline may have extras).
    assert set(canonical.__all__).issubset(set(canonical_pipeline.__all__))


def test_doc_native_program_has_instructions() -> None:
    from arnold_pipelines.megaplan.pipelines.doc import build_pipeline

    pipeline = build_pipeline()
    native = pipeline.native_program
    assert native is not None
    assert native.instructions or native.phases


# ── Runtime smoke (doc pipeline's steps are dual-compatible) ─────────────


def test_doc_pipeline_runs_natively_and_produces_assembly(
    tmp_path: Path,
) -> None:
    """Run the doc pipeline natively with a pre-seeded outline."""
    from arnold_pipelines.megaplan.pipelines.doc import build_pipeline

    plan_dir = tmp_path / "doc-run"
    plan_dir.mkdir(parents=True, exist_ok=True)
    # Pre-seed the outline artifact so OutlineStep doesn't overwrite.
    outline_path = plan_dir / "outline" / "sections.json"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    specs = [
        {"section_id": "intro", "section_title": "Intro"},
        {"section_id": "body", "section_title": "Body"},
        {"section_id": "conclusion", "section_title": "Conclusion"},
    ]
    outline_path.write_text(json.dumps(specs))

    pipeline = build_pipeline()
    envelope = RuntimeEnvelope(artifact_root=str(plan_dir))
    run_pipeline(pipeline, initial_state={}, envelope=envelope)

    # Per-section artifacts landed on disk.
    for sid in ("intro", "body", "conclusion"):
        assert (plan_dir / "section_drafts" / f"{sid}.md").exists()
    # Terminal assembly artifact exists.
    assert (plan_dir / "assembly" / "final.md").exists()
