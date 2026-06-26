"""Canonical public surface for the ``writing_panel_strict`` pipeline package."""

from __future__ import annotations

from .pipeline import build_pipeline

name: str = 'writing-panel-strict'
description: str = 'Adversarial review of prose drafts by N reviewers, then revise. Not for code.'
default_profile: str | None = '@writing-panel-strict:standard'
supported_modes: tuple[str, ...] = ('native',)
recommended_profiles: tuple[str, ...] = ('@writing-panel-strict:premium', '@writing-panel-strict:standard', '@writing-panel-strict:cheap')
driver: tuple[str, str] = ('native', 'panel')
entrypoint: str = 'build_pipeline'
arnold_api_version: str = '1.0'
capabilities: tuple[str, ...] = ('writing', 'critique', 'revise')

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
