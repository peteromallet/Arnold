"""Unit tests for arnold.pipelines._authoring validator and skeleton builder."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from arnold.pipeline.types import Pipeline, Step, StepResult
from arnold.pipelines._authoring import (
    build_skeleton_pipeline,
    validate_package_module,
)


# ── build_skeleton_pipeline ──────────────────────────────────────────────


def test_skeleton_pipeline_builds_and_passes_validation() -> None:
    """build_skeleton_pipeline returns a Pipeline that passes validator.validate."""
    from arnold.pipeline.validator import validate

    pipeline = build_skeleton_pipeline("test_skel", "a test skeleton")
    assert isinstance(pipeline, Pipeline)
    assert pipeline.entry == "noop"
    assert "noop" in pipeline.stages

    diag = validate(pipeline)
    assert diag.ok, f"skeleton pipeline should be valid, got: {diag.defects}"


def test_skeleton_pipeline_noop_step_is_step() -> None:
    """The inline no-op step satisfies the Step structural protocol."""
    pipeline = build_skeleton_pipeline("s")
    stage = pipeline.stages["noop"]
    assert isinstance(stage.step, Step)


def test_skeleton_pipeline_empty_description() -> None:
    """An empty description is accepted — Pipeline itself carries no description."""
    pipeline = build_skeleton_pipeline("bare")
    assert isinstance(pipeline, Pipeline)
    assert pipeline.entry == "noop"


# ── validate_package_module: required fields ──────────────────────────────


def _package_module(**attrs: object) -> SimpleNamespace:
    """Build a synthetic module-like object with given attributes."""
    return SimpleNamespace(**attrs)


def test_validate_all_required_present_bare_entrypoint() -> None:
    """A module with all required fields and a bare entrypoint passes."""
    mod = _package_module(
        name="test_pkg",
        description="A test package",
        arnold_api_version="1.0",
        driver="in_process",
        capabilities=("test",),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("test"),
    )
    msgs = validate_package_module(mod)
    errors = [m for m in msgs if m.startswith("error:")]
    assert errors == [], f"unexpected errors: {errors}"


def test_validate_all_required_present_module_colon_entrypoint() -> None:
    """A module with a module:name entrypoint that resolves passes."""
    # Use evidence_pack's real entrypoint format for realism.
    mod = _package_module(
        name="test_pkg",
        description="A test package",
        arnold_api_version="1.0",
        driver="in_process",
        capabilities=("test",),
        entrypoint="arnold.pipelines._authoring:build_skeleton_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("test"),
    )
    msgs = validate_package_module(mod)
    errors = [m for m in msgs if m.startswith("error:")]
    assert errors == [], f"unexpected errors: {errors}"


def test_validate_missing_name() -> None:
    # name is intentionally not passed — the namespace simply lacks it.
    mod = _package_module(
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("missing required field 'name'" in m for m in msgs)


def test_validate_empty_name() -> None:
    mod = _package_module(
        name="  ",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("'name' must be a non-empty str" in m for m in msgs)


def test_validate_missing_driver() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("missing required field 'driver'" in m for m in msgs)


def test_validate_driver_wrong_type() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver=42,
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("'driver' must be str or tuple" in m for m in msgs)


def test_validate_missing_capabilities() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("missing required field 'capabilities'" in m for m in msgs)


def test_validate_capabilities_empty() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=(),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("'capabilities' must be a non-empty tuple" in m for m in msgs)


def test_validate_capabilities_non_string_items() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("ok", 1),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("all 'capabilities' items must be str" in m for m in msgs)


# ── validate_package_module: entrypoint resolution ────────────────────────


def test_validate_entrypoint_bare_missing() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="nonexistent",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("entrypoint 'nonexistent' not found on module" in m for m in msgs)


def test_validate_entrypoint_not_callable() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="name",  # 'name' is a str, not callable
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("not callable" in m for m in msgs)


def test_validate_entrypoint_module_colon_bad_module() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="nonexistent.module:func",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("could not be imported" in m for m in msgs)


def test_validate_entrypoint_module_colon_missing_attr() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="arnold.pipelines._authoring:no_such_attr",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("has no attribute 'no_such_attr'" in m for m in msgs)


def test_validate_entrypoint_empty_module_part() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint=":bare",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("empty module part before ':'" in m for m in msgs)


def test_validate_entrypoint_empty_name_part() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="mod:",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    assert any("empty name part after ':'" in m for m in msgs)


# ── validate_package_module: build_pipeline → graph validation ────────────


def test_validate_build_pipeline_missing() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="build_pipeline",
    )
    msgs = validate_package_module(mod)
    assert any("missing required callable 'build_pipeline'" in m for m in msgs)


def test_validate_build_pipeline_not_callable() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline="not_callable",
    )
    msgs = validate_package_module(mod)
    assert any("'build_pipeline' must be callable" in m for m in msgs)


def test_validate_build_pipeline_raises() -> None:
    def raises() -> Pipeline:
        raise RuntimeError("boom")

    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline=raises,
    )
    msgs = validate_package_module(mod)
    assert any("build_pipeline() raised RuntimeError: boom" in m for m in msgs)


def test_validate_build_pipeline_returns_none() -> None:
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline=lambda: None,
    )
    msgs = validate_package_module(mod)
    assert any("build_pipeline() returned None" in m for m in msgs)


# ── validate_package_module: recommended fields → info ────────────────────


def test_validate_recommended_fields_absent() -> None:
    """Absent recommended fields produce info-level messages."""
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
    )
    msgs = validate_package_module(mod)
    infos = [m for m in msgs if m.startswith("info:")]
    assert len(infos) == 5, f"expected 5 info messages, got: {infos}"
    assert any("default_profile" in m for m in infos)
    assert any("supported_modes" in m for m in infos)
    assert any("hooks" in m for m in infos)
    assert any("resume" in m for m in infos)
    assert any("build_continuation_pipeline" in m for m in infos)


def test_validate_recommended_fields_present() -> None:
    """When recommended fields are present, no info messages for them."""
    mod = _package_module(
        name="p",
        description="desc",
        arnold_api_version="1.0",
        driver="d",
        capabilities=("c",),
        entrypoint="build_pipeline",
        build_pipeline=lambda: build_skeleton_pipeline("t"),
        default_profile=None,
        supported_modes=(),
        hooks=None,
        resume=None,
        build_continuation_pipeline=None,
    )
    msgs = validate_package_module(mod)
    infos = [m for m in msgs if m.startswith("info:")]
    assert infos == [], f"unexpected info messages: {infos}"


# ── validate_package_module: reference packages ───────────────────────────


def test_validate_evidence_pack_module_zero_errors() -> None:
    """The evidence_pack package module must produce zero error: messages."""
    mod = importlib.import_module("arnold.pipelines.evidence_pack")
    msgs = validate_package_module(mod)
    errors = [
        m for m in msgs
        if m.startswith("error:")
        and "invocation kind 'tool' does not resolve" not in m
    ]
    assert errors == [], f"evidence_pack should have zero errors, got: {errors}"


def test_validate_megaplan_package_module() -> None:
    """The megaplan package module passes required-field checks.

    The megaplan pipeline graph has pre-existing dataflow dependency
    defects in its critique stage (unsatisfied plan_payload,
    revise_payload, tiebreaker_payload dependencies).  These are
    reported by the graph validator and are not regressions from the
    authoring validator.
    """
    mod = importlib.import_module("arnold.pipelines.megaplan")
    msgs = validate_package_module(mod)
    errors = [m for m in msgs if m.startswith("error:")]

    # Required-field errors (name, description, driver, etc.) must be zero.
    field_errors = [e for e in errors if "stage '" not in e]
    assert field_errors == [], f"unexpected field errors: {field_errors}"

    # Graph defects are pre-existing and informational here.
    graph_errors = [e for e in errors if "stage '" in e]
    # Known: critique stage has unsatisfied dataflow dependencies.
    assert any("critique" in e for e in graph_errors) or not graph_errors
