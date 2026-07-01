"""Native contract tests for the ``creative`` pipeline (restored from archive/m5).

Verifies the native-first package contract: build_pipeline returns a
native-backed projected shell with correct form dispatch, primary_criterion
threading, and no leaked graph-era builders.
"""

from __future__ import annotations

import pytest

from arnold.pipeline import Pipeline
from arnold.pipeline.native import NativeProgram


# ── Package metadata / import surface ────────────────────────────────────


def test_creative_package_init_is_thin_metadata_surface() -> None:
    import arnold_pipelines.megaplan.pipelines.creative as package

    assert package.name == "creative"
    assert package.driver[0] == "native"
    assert "native" in package.supported_modes
    assert package.entrypoint == "build_pipeline"
    assert callable(package.build_pipeline)
    # No legacy graph builders leaked.
    assert not hasattr(package, "_build_graph_pipeline")
    assert "build_graph_pipeline" not in (getattr(package, "__all__", ()) or ())


def test_creative_mirror_is_compatibility_shim() -> None:
    import arnold_pipelines.megaplan.pipelines.creative as canonical
    import arnold_pipelines.megaplan.pipelines.creative.pipeline as canonical_pipeline

    assert canonical.build_pipeline is canonical_pipeline.build_pipeline
    assert canonical.__all__ == canonical_pipeline.__all__


# ── Native contract assertions ───────────────────────────────────────────


def test_creative_build_pipeline_returns_native_backed_projected_shell() -> None:
    from arnold_pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="poem", primary_criterion="image pressure")

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "creative"
    assert tuple(pipeline.stages) == (
        "prep",
        "execute_creative",
        "critique_creative",
        "revise_creative",
        "finalize",
    )
    assert tuple(pipeline.resource_bundles) == ()
    # primary_criterion threads through to step dataclass fields.
    assert pipeline.stages["execute_creative"].step.form == "poem"
    assert pipeline.stages["execute_creative"].step.primary_criterion == "image pressure"


def test_creative_native_program_has_instructions() -> None:
    from arnold_pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline()
    native = pipeline.native_program
    assert native is not None
    assert native.instructions or native.phases


# ── Form dispatch: joke vs poem wires the right prompt_key slots ─────────


def test_creative_form_joke_dispatches_joke_prompt_keys() -> None:
    from arnold_pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="joke")
    stage_prompt_keys = {
        name: stage.step.prompt_key for name, stage in pipeline.stages.items()
    }
    assert stage_prompt_keys["prep"] == "prep:joke"
    assert stage_prompt_keys["execute_creative"] == "execute_creative:joke"
    assert stage_prompt_keys["critique_creative"] == "critique_creative:joke"
    assert stage_prompt_keys["revise_creative"] == "revise_creative:joke"
    assert stage_prompt_keys["finalize"] is None


def test_creative_form_poem_dispatches_generic_prompt_keys() -> None:
    from arnold_pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="poem")
    stage_prompt_keys = {
        name: stage.step.prompt_key for name, stage in pipeline.stages.items()
    }
    assert stage_prompt_keys["prep"] == "prep"
    assert stage_prompt_keys["execute_creative"] == "execute_creative"
    assert stage_prompt_keys["critique_creative"] == "critique_creative"
    assert stage_prompt_keys["revise_creative"] == "revise_creative"
    assert stage_prompt_keys["finalize"] is None


# ── primary_criterion threading ──────────────────────────────────────────


def test_creative_pipeline_primary_criterion_threads_through_all_stages() -> None:
    from arnold_pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="joke", primary_criterion="weirdest coherent")
    for name, stage in pipeline.stages.items():
        assert getattr(stage.step, "primary_criterion", None) == "weirdest coherent", (
            f"stage {name!r} did not receive primary_criterion"
        )


def test_creative_pipeline_primary_criterion_default_none() -> None:
    from arnold_pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="joke")
    for name, stage in pipeline.stages.items():
        assert getattr(stage.step, "primary_criterion", None) is None, (
            f"stage {name!r} primary_criterion default should be None"
        )


# ── Unknown form raises error ────────────────────────────────────────────


def test_creative_pipeline_unknown_form_raises_error() -> None:
    from arnold_pipelines.megaplan.pipelines.creative import build_pipeline

    with pytest.raises(Exception) as excinfo:
        build_pipeline(form="not-a-real-form-xyz")
    msg = str(excinfo.value)
    assert "not-a-real-form-xyz" in msg


# ── Provocations / stance validation wiring (import-level) ───────────────


def test_creative_critique_prompt_module_wires_provocations_import() -> None:
    """Provocations selector is importable from the forms package."""
    from arnold_pipelines.megaplan.forms.provocations import select_active_checks

    assert callable(select_active_checks)


def test_creative_pipeline_validate_stance_remains_callable() -> None:
    """``validate_stance`` is still importable from its canonical location."""
    from arnold_pipelines.megaplan.forms.stance import validate_stance

    assert callable(validate_stance)
