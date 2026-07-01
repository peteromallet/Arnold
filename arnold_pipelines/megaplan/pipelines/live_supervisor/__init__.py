"""Megaplan Live Watchdog Supervisor pipeline.

An Arnold pipeline that consumes a Snapshot of likely-live Megaplan/Arnold
runs, classifies each incident into a health category, produces a diagnosis,
 decides whether a repair action is safe via an explicit allowlist, and emits
a recheck request for the outer daemon.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.pipelines.live_supervisor.pipeline import (
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
