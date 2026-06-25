"""Megaplan Live Watchdog Supervisor pipeline.

An Arnold pipeline that consumes a Snapshot of likely-live Megaplan/Arnold
runs, classifies each incident into a health category, produces a diagnosis,
 decides whether a repair action is safe via an explicit allowlist, and emits
a recheck request for the outer daemon.
"""

from __future__ import annotations

from arnold.pipelines.megaplan.pipelines.live_supervisor.pipeline import (
    build_pipeline,
)


name: str = "live-supervisor"
description: str = (
    "Megaplan Live Watchdog Supervisor: classify, diagnose, and decide "
    "safe repair actions for likely-live Megaplan/Arnold runs."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("supervise", "native")
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "linear")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = (
    "plan_supervision",
    "incident_classification",
    "repair_dispatch",
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
