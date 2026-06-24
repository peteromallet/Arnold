"""Package entrypoint for the ``writing-panel-strict`` pipeline."""

from __future__ import annotations

from dataclasses import replace

from arnold.pipelines.megaplan._pipeline.types import Pipeline

from .pipeline import _build_graph_pipeline, _native_bundle, writing_panel_strict_native
from .steps import _make_agent_step, _make_panel_reviewer_step


name: str = "writing-panel-strict"
description: str = (
    "Adversarial review of prose drafts by N reviewers, then revise. "
    "Not for code."
)
default_profile: str = "@writing-panel-strict:standard"
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = (
    "@writing-panel-strict:premium",
    "@writing-panel-strict:standard",
    "@writing-panel-strict:cheap",
)
driver: tuple[str, str] = ("native", "panel")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("writing", "critique", "revise")


def build_pipeline() -> Pipeline:
    """Return the native-backed ``writing-panel-strict`` :class:`Pipeline`.

    The graph shell remains available for explicit legacy execution; the
    canonical runtime dispatches through the attached ``native_program``.
    """

    graph = _build_graph_pipeline(
        name=name,
        description=description,
        default_profile=default_profile,
        supported_modes=supported_modes,
    )
    return replace(
        graph,
        native_program=_native_bundle(),
        resource_bundles=(),
    )


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
    "writing_panel_strict_native",
]
