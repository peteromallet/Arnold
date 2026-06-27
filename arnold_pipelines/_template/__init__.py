"""Template package for Arnold pipeline authors.

Copy this directory, rename it (without a leading underscore), fill in the
contract fields, and replace the skeleton pipeline with real logic. The
``build_pipeline()`` entrypoint returns a workflow-first
:class:`arnold.workflow.Pipeline` that the compiler lowers to a neutral
:class:`arnold.workflow.WorkflowManifest`.
"""

from __future__ import annotations

from arnold.workflow import Pipeline, Route, Step


name: str = "my-pipeline"
description: str = (
    "A new Arnold pipeline (replace this description with a meaningful one-liner)."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("graph",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("graph", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("skeleton",)


def build_pipeline() -> Pipeline:
    """Build a skeleton explicit-node workflow pipeline.

    Replace the steps and routes with the real shape of your pipeline. The
    returned :class:`arnold.workflow.Pipeline` is the package source; the
    compiler produces the manifest and hashes at build time.
    """

    return Pipeline(
        id="my-pipeline",
        version="1.0",
        steps=(
            Step(id="start", kind="agent"),
            Step(id="finish", kind="agent"),
        ),
        routes=(
            Route(id="start-finish", source="start", target="finish"),
        ),
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
