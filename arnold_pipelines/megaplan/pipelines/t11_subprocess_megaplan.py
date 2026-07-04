"""Native-first projected shell for the ``t11-subprocess-megaplan`` pipeline."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from arnold.pipeline.native import (
    compile_pipeline,
    decision,
    phase,
    pipeline,
    project_graph,
)
from arnold.pipeline.types import Pipeline, StepResult


_PIPELINE_DIR: Path = Path(__file__).parent / "t11-subprocess-megaplan"

name: str = "t11-subprocess-megaplan"
description: str = "TODO: add a description"
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "project+validate")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ()


@phase(name="draft")
def _native_draft(ctx: object) -> StepResult:
    del ctx
    return StepResult(outputs={"draft": "TODO"}, next="review")


@phase(name="review")
def _native_review(ctx: object) -> StepResult:
    del ctx
    return StepResult(outputs={"review_notes": "TODO"}, next="ship_or_revise")


@decision(name="ship_or_revise", vocabulary={"ship", "revise"})
def _native_ship_or_revise(ctx: object) -> str:
    del ctx
    return "ship"


@phase(name="publish")
def _native_publish(ctx: object) -> StepResult:
    del ctx
    return StepResult(outputs={"final_artifact": "TODO"}, next="halt")


@pipeline("t11-subprocess-megaplan")
def t11_subprocess_megaplan_native(ctx: object) -> Any:
    state = yield _native_draft(ctx)
    state = yield _native_review(ctx)
    if _native_ship_or_revise(ctx) == "revise":
        state = yield _native_review(ctx)
    state = yield _native_publish(ctx)
    return state


def _native_program() -> Any:
    return compile_pipeline(t11_subprocess_megaplan_native)


def build_pipeline() -> Pipeline:
    """Return the canonical native-backed ``t11-subprocess-megaplan`` :class:`Pipeline`."""

    native_program = _native_program()
    projected = project_graph(native_program, key_mode="phase")
    return replace(
        projected,
        resource_bundles=(),
        native_program=native_program,
    )


__all__ = [
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "recommended_profiles",
    "supported_modes",
]
