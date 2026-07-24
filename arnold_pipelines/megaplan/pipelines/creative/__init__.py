"""Native-backed public surface for the first-class ``creative`` pipeline."""

from __future__ import annotations

name = "creative"
description = (
    "Creative-form pipeline: form-aware prep -> execute -> critique -> "
    "revise -> finalize for creative writing artifacts."
)
default_profile = None
supported_modes = ("native",)
recommended_profiles = ()
driver = ("native", "linear")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("creative",)

from arnold_pipelines.megaplan.pipelines.creative.pipeline import build_pipeline

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
