"""Compatibility mirror for the canonical ``select-tournament`` package."""

from __future__ import annotations

from arnold.pipelines.megaplan.pipelines.select_tournament import (
    DEFAULT_CANDIDATES,
    build_pipeline,
)


name: str = "select-tournament"
description: str = (
    "Selection tournament pipeline: fan out per-candidate scoring, reduce "
    "scores through a pairwise bracket, then emit a winner artifact."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "fanout+pairwise-reduce")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("review",)


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
