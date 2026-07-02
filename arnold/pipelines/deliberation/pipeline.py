"""Native-first ``deliberation`` package entrypoint and metadata."""

from __future__ import annotations

from dataclasses import replace

from arnold.pipeline import Pipeline
from arnold.pipeline.types import Edge, Stage

from arnold.pipelines.deliberation.steps import (
    DeliberationStep,
    _NATIVE_STAGE_ORDER,
    build_native_program,
)


name: str = "deliberation"
description: str = (
    "Layered idea-refinement pipeline with question-gen, human gate, "
    "critique panels, skeptical synthesis, and lineage-aware reporting."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("deliberation", "layered-critique")


def _stage(stage_name: str, next_label: str) -> Stage:
    output_label = "report" if stage_name == "final_report" else "artifact"
    output_suffix = "md" if stage_name == "final_report" else "json"
    edges = () if next_label == "halt" else (
        Edge(label=next_label, target=next_label),
    )
    return Stage(
        name=stage_name,
        step=DeliberationStep(
            name=stage_name,
            next_label=next_label,
            output_label=output_label,
            output_suffix=output_suffix,
        ),
        edges=edges,
    )


def _build_projected_pipeline(name: str = "deliberation") -> Pipeline:
    if name != "deliberation":
        return Pipeline(
            stages={
                "manifest_introspection": Stage(
                    name="manifest_introspection",
                    step=DeliberationStep(
                        name="manifest_introspection",
                        next_label="halt",
                    ),
                    edges=(),
                )
            },
            entry="manifest_introspection",
        )

    stages = {
        stage_name: _stage(stage_name, next_label)
        for stage_name, next_label in _NATIVE_STAGE_ORDER
    }
    return Pipeline(stages=stages, entry="question_gen")


def build_pipeline(name: str = "deliberation", **_: object) -> Pipeline:
    """Return the canonical native-backed ``deliberation`` pipeline."""
    projected = _build_projected_pipeline(name=name)
    return replace(
        projected,
        native_program=build_native_program(),
        resource_bundles=(),
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
