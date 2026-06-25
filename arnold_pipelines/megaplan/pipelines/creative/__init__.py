"""Compatibility mirror for the canonical ``creative`` pipeline package."""

from __future__ import annotations

from arnold.pipelines.megaplan.pipelines.creative import build_pipeline

name: str = "creative"
description: str = (
    "Creative-form pipeline: form-aware prep -> execute -> critique -> "
    "revise -> finalize. Forms registry validates --form; "
    "--primary-criterion threads through as a first-class input."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("creative",)

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
