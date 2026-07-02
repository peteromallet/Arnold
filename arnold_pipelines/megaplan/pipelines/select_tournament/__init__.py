"""Package entrypoint for the ``select-tournament`` pipeline."""

from __future__ import annotations

name = "select-tournament"
description = (
    "Selection tournament pipeline: fan out per-candidate scoring, reduce "
    "through pairwise brackets, and emit a winner."
)
default_profile = None
supported_modes = ("native",)
recommended_profiles = ()
driver = ("native", "fanout+pairwise-reduce")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("review",)

from .pipeline import DEFAULT_CANDIDATES, build_pipeline


__all__ = [
    "DEFAULT_CANDIDATES",
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
