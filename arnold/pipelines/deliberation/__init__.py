"""Deliberation pipeline — layered idea-refinement with critique panels and skeptical synthesis.

This package exposes a native-first deliberation pipeline: question generation,
a human gate, draft planning, three abstraction-layer critique panels with
synthesis, and a final report.  The graph builder remains available internally
for topology hashing, but the public entrypoint advertises native execution.
"""

from arnold.pipelines.deliberation.pipeline import build_pipeline

name = "deliberation"
description = (
    "Layered idea-refinement pipeline with question-gen, human gate, "
    "critique panels, skeptical synthesis, and lineage-aware reporting."
)
default_profile = None
supported_modes = ("native",)
driver = ("native", "dispatch+emit")
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
    "supported_modes",
]
