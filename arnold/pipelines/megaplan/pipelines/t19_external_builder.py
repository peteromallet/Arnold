"""Python composition of the ``t19-external-builder`` pipeline."""

from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._pipeline.types import Pipeline


_PIPELINE_DIR: Path = Path(__file__).parent / "t19-external-builder"


name: str = "t19-external-builder"
description: str = "TODO: add a description"
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
driver: tuple[str, str] = ('graph', "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ()


def build_pipeline() -> Pipeline:
    """Return the canonical ``t19-external-builder`` :class:`Pipeline`."""
    return (
        Pipeline.builder(
            "t19-external-builder",
            description=description,
            pipeline_dir=_PIPELINE_DIR,
        )
        .agent("run", prompt="TODO: add your prompt file path")
        .build()
    )


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
