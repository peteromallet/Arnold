"""Compatibility mirror for ``arnold.pipelines.megaplan.pipelines.live_supervisor.pipeline``."""

from __future__ import annotations

from arnold.pipelines.megaplan.pipelines.live_supervisor.pipeline import (
    arnold_api_version,
    build_pipeline,
    capabilities,
    default_profile,
    description,
    driver,
    entrypoint,
    name,
    recommended_profiles,
    supported_modes,
)

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
