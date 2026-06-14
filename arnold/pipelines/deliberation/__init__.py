"""Deliberation pipeline — layered idea-refinement with critique panels and skeptical synthesis.

This pipeline runs a structured deliberation over an input idea through
abstraction layers (high/mid/low), each fanning out a critique panel whose
outputs are skeptically synthesized.  A human gate at the question-generation
stage forces the generic suspend/resume contract.
"""

from arnold.pipelines.deliberation.pipelines import build_pipeline as _build_pipeline

name = "deliberation"
description = (
    "Layered idea-refinement pipeline with question-gen, human gate, "
    "critique panels, skeptical synthesis, and lineage-aware reporting."
)
default_profile = None
supported_modes = ("default",)
driver = "in_process"
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
