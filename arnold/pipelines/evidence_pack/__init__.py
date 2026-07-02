"""Standalone native-first ``evidence_pack`` verification pipeline package.

Model-less verification of persisted evidence-pack JSON artifacts. This is the
M4 canonical home for evidence-pack verification, migrated from the graph-era
``arnold_pipelines.evidence_pack`` package.
"""

from arnold.pipelines.evidence_pack.pipeline import build_pipeline

name = "evidence-pack"
description = "Model-less verification of persisted evidence-pack JSON artifacts."
default_profile = None
supported_modes = ("native",)
recommended_profiles = ()
driver = ("native", "verify")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("artifact-verification", "evidence-pack")

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
