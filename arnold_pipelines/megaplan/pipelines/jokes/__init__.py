"""Native-backed public surface for the first-class ``jokes`` pipeline."""

from __future__ import annotations

name = "jokes"
description = (
    "Joke pipeline: drafts a joke, tightens the beat, and emits the final artifact "
    "via a native projected shell."
)
default_profile = None
supported_modes = ("native", "joke")
recommended_profiles = ()
driver = ("native", "linear")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("creative", "joke")

from arnold_pipelines.megaplan.pipelines.jokes.pipeline import build_pipeline

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
