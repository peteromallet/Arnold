"""Template package for Arnold pipeline authors.

Copy this directory, rename it (without a leading underscore), fill in the
contract fields, and replace the skeleton pipeline with real logic. The
``build_pipeline()`` entrypoint returns a native-first :class:`arnold.pipeline.Pipeline`
with a compiled :class:`arnold.pipeline.native.NativeProgram` attached.
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline.native import compile_pipeline, phase, pipeline, project_graph
from arnold.pipeline.types import Pipeline


name: str = "my-pipeline"
description: str = (
    "A new Arnold pipeline (replace this description with a meaningful one-liner)."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("skeleton",)


@phase(name="start")
def _start(ctx: Any) -> dict[str, Any]:
    """Skeleton start phase — replace with real logic."""
    return {"intermediate": "TODO"}


@phase(name="finish")
def _finish(ctx: Any) -> dict[str, Any]:
    """Skeleton finish phase — replace with real logic."""
    return {"result": "TODO"}


@pipeline("my-pipeline", description=description)
def _my_pipeline(ctx: Any) -> Any:
    """Skeleton native pipeline — replace phases with real workflow logic."""
    yield _start(ctx)
    yield _finish(ctx)
    return {}


def build_pipeline(name: str = "my-pipeline", description: str = "") -> Pipeline:
    """Build a skeleton native-first pipeline.

    Replace the phases and pipeline body with the real shape of your pipeline.
    The returned :class:`arnold.pipeline.Pipeline` carries the compiled native
    program so the native runtime can execute it directly.
    """

    program = compile_pipeline(_my_pipeline)
    return project_graph(program, key_mode="phase")


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
