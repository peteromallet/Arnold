"""Deliberation pipeline compatibility package."""

from arnold.pipelines.deliberation.pipelines import build_pipeline as _build_pipeline

name = "deliberation"
description = (
    "Layered idea-refinement pipeline with question-gen, human gate, "
    "critique panels, skeptical synthesis, and lineage-aware reporting."
)
default_profile = None
supported_modes = ("default", "native")
driver = ("native", "deliberation")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("deliberation", "layered-critique")

build_pipeline = _build_pipeline

__all__ = [
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "supported_modes",
]
