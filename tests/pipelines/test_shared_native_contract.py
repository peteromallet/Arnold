"""Native-backed compatibility contract for legacy first-class pipeline packages.

This module covers the packages that remain native-backed during the M2
migration. The active package-authoring contract is workflow-first: new
packages must return ``arnold.workflow.Pipeline`` from ``build_pipeline()``.
See ``tests/arnold_pipelines/test_template_e2e.py`` for the canonical scaffold
contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
from types import ModuleType

import pytest

from arnold.pipeline import Pipeline
from arnold.pipeline.native import NativeProgram


@dataclass(frozen=True)
class NativeTarget:
    module_path: str
    pipeline_name: str


# These are the active first-class packages that remain native-backed.
# Megaplan packages live under ``arnold_pipelines.megaplan.pipelines.*``;
# core Arnold packages live under ``arnold.pipelines.*``.  Archived or
# graph-marked packages (e.g. epic_blitz) are intentionally excluded.
ACTIVE_NATIVE_TARGETS: tuple[NativeTarget, ...] = (
    NativeTarget("arnold_pipelines.megaplan.pipelines.creative", "creative"),
    NativeTarget("arnold_pipelines.megaplan.pipelines.doc", "doc"),
    NativeTarget("arnold_pipelines.megaplan.pipelines.jokes", "jokes"),
    NativeTarget("arnold_pipelines.megaplan.pipelines.live_supervisor", "live-supervisor"),
    NativeTarget(
        "arnold_pipelines.megaplan.pipelines.writing_panel_strict",
        "writing-panel-strict",
    ),
    NativeTarget(
        "arnold_pipelines.megaplan.pipelines.select_tournament",
        "select-tournament",
    ),
)

_FIRST_CLASS_NATIVE_PREFIXES = (
    "arnold.pipelines.",
    "arnold_pipelines.megaplan.pipelines.",
)

DEFERRED_NATIVE_TARGETS: tuple[NativeTarget, ...] = ()

FORBIDDEN_PUBLIC_GRAPH_BUILDERS = {
    "build_graph_pipeline",
    "build_legacy_graph_pipeline",
    "compile_graph_pipeline",
    "compile_legacy_graph_pipeline",
}


def _target_id(target: NativeTarget) -> str:
    return target.pipeline_name


def _import_target(target: NativeTarget) -> ModuleType:
    return importlib.import_module(target.module_path)


def _public_names(module: ModuleType) -> set[str]:
    exported = set(getattr(module, "__all__", ()))
    discovered = {name for name in vars(module) if not name.startswith("_")}
    return exported | discovered


def _graph_builder_like_names(names: set[str]) -> set[str]:
    forbidden = set(names) & FORBIDDEN_PUBLIC_GRAPH_BUILDERS
    forbidden.update(
        name
        for name in names
        if name.startswith("build_") and ("graph" in name or "legacy" in name)
    )
    return forbidden


@pytest.mark.parametrize("target", ACTIVE_NATIVE_TARGETS, ids=_target_id)
def test_active_targets_import_from_first_class_pipeline_paths(
    target: NativeTarget,
) -> None:
    module = _import_target(target)

    assert module.__name__ == target.module_path
    assert any(
        module.__name__.startswith(prefix) for prefix in _FIRST_CLASS_NATIVE_PREFIXES
    )


@pytest.mark.parametrize("target", ACTIVE_NATIVE_TARGETS, ids=_target_id)
def test_active_targets_advertise_native_metadata(target: NativeTarget) -> None:
    module = _import_target(target)

    assert getattr(module, "name") == target.pipeline_name
    assert isinstance(getattr(module, "description"), str)
    assert module.description.strip()
    assert getattr(module, "entrypoint") == "build_pipeline"
    assert getattr(module, module.entrypoint) is getattr(module, "build_pipeline")

    driver = getattr(module, "driver")
    assert isinstance(driver, tuple)
    assert driver
    assert driver[0] == "native"
    assert "native" in tuple(getattr(module, "supported_modes", ()))


@pytest.mark.parametrize("target", ACTIVE_NATIVE_TARGETS, ids=_target_id)
def test_active_targets_build_native_arnold_pipeline(target: NativeTarget) -> None:
    module = _import_target(target)

    built = module.build_pipeline()

    assert isinstance(built, Pipeline)
    assert isinstance(built.native_program, NativeProgram)
    assert built.native_program.name == target.pipeline_name
    assert built.native_program.instructions or built.native_program.phases
    assert tuple(getattr(built, "resource_bundles", ())) == ()


@pytest.mark.parametrize("target", ACTIVE_NATIVE_TARGETS, ids=_target_id)
def test_active_targets_do_not_publish_graph_builders(target: NativeTarget) -> None:
    module = _import_target(target)

    public_graph_builders = _graph_builder_like_names(_public_names(module))

    assert public_graph_builders == set()


def test_deferred_targets_are_not_silently_available() -> None:
    for target in DEFERRED_NATIVE_TARGETS:
        assert importlib.util.find_spec(target.module_path) is None, (
            f"{target.module_path} is now importable; move {target.pipeline_name!r} "
            "into ACTIVE_NATIVE_TARGETS and enforce the same native contract."
        )


def test_contract_target_sets_are_staged_explicitly() -> None:
    active_names = {target.pipeline_name for target in ACTIVE_NATIVE_TARGETS}
    deferred_names = {target.pipeline_name for target in DEFERRED_NATIVE_TARGETS}

    assert active_names == {
        "creative",
        "doc",
        "jokes",
        "live-supervisor",
        "writing-panel-strict",
        "select-tournament",
    }
    assert deferred_names == set()
    assert active_names.isdisjoint(deferred_names)


def test_workflow_first_template_contrasts_with_native_targets() -> None:
    """The canonical scaffold is workflow-first, not native-backed."""
    from arnold_pipelines._template import build_pipeline as template_build

    pipeline = template_build()
    assert type(pipeline).__module__ == "arnold.workflow.dsl"
    assert type(pipeline).__name__ == "Pipeline"
    assert not hasattr(pipeline, "native_program")
