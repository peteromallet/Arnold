"""Compatibility mirror for the canonical ``jokes`` pipeline package."""

from __future__ import annotations

from arnold.pipelines.megaplan.pipelines.jokes import build_pipeline


name: str = "jokes"
description: str = (
    "Joke pipeline: drafts a joke, tightens the beat, and emits the final artifact "
    "through a direct native program."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native", "joke")
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("creative", "joke")


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
