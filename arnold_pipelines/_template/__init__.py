"""Template package for Arnold workflow pipeline authors.

Copy this directory, rename it (without a leading underscore), fill in the
contract fields, and replace the skeleton pipeline with real logic. The
``build_pipeline()`` entrypoint returns an :class:`arnold.workflow.dsl.Pipeline`
using explicit ``Step`` and ``Route`` nodes.
"""

from __future__ import annotations

from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


name: str = "my-pipeline"
description: str = (
    "A new Arnold workflow pipeline (replace this description with a meaningful one-liner)."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("in_process", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("skeleton",)


def build_pipeline(name: str = "my-pipeline", description: str = "") -> Pipeline:
    """Build a skeleton explicit-node workflow pipeline.

    Replace the steps, routes, inputs, outputs, and capabilities with the real
    shape of your pipeline. Each ``Step`` must have a stable ``id`` and a
    ``kind`` string that your execution backend recognizes.
    """

    resolved_name = name or "my-pipeline"
    resolved_description = description or "Skeleton workflow pipeline — replace with real logic."

    start = Step(
        id="start",
        kind="agent",
        label="Start",
        inputs=(Input(name="input"),),
        outputs=(Output(name="intermediate"),),
        capabilities=(Capability(id="skeleton", route="default"),),
        metadata={"stage": "start"},
    )
    finish = Step(
        id="finish",
        kind="emit",
        label="Finish",
        inputs=(Input(name="intermediate", value_ref="start.intermediate"),),
        outputs=(Output(name="result"),),
        capabilities=(Capability(id="skeleton", route="default"),),
        metadata={"stage": "finish", "terminal": True},
    )

    return Pipeline(
        id=resolved_name,
        version="m5-phase3",
        steps=(start, finish),
        routes=(
            Route(id="start:finish", source="start", target="finish", label="default"),
        ),
        capabilities=(Capability(id="skeleton", route="default"),),
        metadata={
            "name": resolved_name,
            "description": resolved_description,
            "driver": driver,
            "entrypoint": entrypoint,
            "arnold_api_version": arnold_api_version,
            "capabilities": capabilities,
            "default_profile": default_profile,
            "supported_modes": supported_modes,
            "recommended_profiles": recommended_profiles,
        },
    )


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
