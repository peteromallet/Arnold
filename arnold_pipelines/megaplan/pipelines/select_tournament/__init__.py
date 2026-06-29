"""Package entrypoint for the ``select-tournament`` pipeline."""

from __future__ import annotations

from collections.abc import Sequence

from arnold.pipeline import Pipeline

from .pipeline import (
    DEFAULT_CANDIDATES,
    build_pipeline as _build_pipeline,
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


def build_pipeline(
    candidates: Sequence[str] = DEFAULT_CANDIDATES,
) -> Pipeline:
    """Return the canonical native-projected ``select-tournament`` pipeline."""

    return _build_pipeline(candidates=candidates)


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
