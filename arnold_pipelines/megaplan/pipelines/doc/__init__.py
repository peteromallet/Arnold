"""Native-backed public surface for the first-class ``doc`` pipeline."""

from __future__ import annotations

name = "doc"
description = (
    "Linear doc pipeline: outline -> per-section drafts (dynamic fanout) "
    "-> critique -> revise -> assembly."
)
default_profile = None
supported_modes = ("native",)
recommended_profiles = ()
driver = ("native", "dynamic-fanout")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("doc",)

from arnold_pipelines.megaplan.pipelines.doc.pipeline import build_pipeline

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
