"""Canonical public surface for the ``doc`` pipeline package."""

from __future__ import annotations

from .pipeline import build_pipeline

name: str = 'doc'
description: str = 'Linear doc pipeline: outline -> per-section drafts (dynamic fanout) -> critique -> revise -> assembly. Single-pass; no gate.'
default_profile: str | None = None
supported_modes: tuple[str, ...] = ('native',)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ('native', 'dynamic-fanout')
entrypoint: str = 'build_pipeline'
arnold_api_version: str = '1.0'
capabilities: tuple[str, ...] = ('doc',)

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
