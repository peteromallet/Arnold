"""Canonical public surface for the ``live_supervisor`` pipeline package."""

from __future__ import annotations

from .pipeline import build_pipeline

name: str = 'live-supervisor'
description: str = 'Megaplan Live Watchdog Supervisor: classify, diagnose, and decide safe repair actions for likely-live Megaplan/Arnold runs.'
default_profile: str | None = None
supported_modes: tuple[str, ...] = ('supervise', 'native')
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ('native', 'linear')
entrypoint: str = 'build_pipeline'
arnold_api_version: str = '1.0'
capabilities: tuple[str, ...] = ('plan_supervision', 'incident_classification', 'repair_dispatch')

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
