"""Standalone native-first ``deliberation`` pipeline package."""

from arnold.pipelines.deliberation.pipeline import build_pipeline

name = "deliberation"
description = (
    "Layered idea-refinement pipeline with question-gen, human gate, "
    "critique panels, skeptical synthesis, and lineage-aware reporting."
)
default_profile = None
supported_modes = ("native",)
recommended_profiles = ()
driver = ("native", "linear")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("deliberation", "layered-critique")

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
