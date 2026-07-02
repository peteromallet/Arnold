"""Native-backed public surface for ``writing-panel-strict``."""

from __future__ import annotations

name = "writing-panel-strict"
description = (
    "Adversarial review of prose drafts by N reviewers, then revise. "
    "Not for code."
)
default_profile = "@writing-panel-strict:standard"
supported_modes = ("native",)
recommended_profiles = (
    "@writing-panel-strict:premium",
    "@writing-panel-strict:standard",
)
driver = ("native", "panel")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("writing", "critique", "revise")

from arnold_pipelines.megaplan.pipelines.writing_panel_strict.pipeline import build_pipeline

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
