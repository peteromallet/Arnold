"""Megaplan Live Watchdog Supervisor pipeline.

An Arnold pipeline that consumes a Snapshot of likely-live Megaplan/Arnold
runs, classifies each incident into a health category, produces a diagnosis,
 decides whether a repair action is safe via an explicit allowlist, and emits
a recheck request for the outer daemon.
"""

from __future__ import annotations

name = "live-supervisor"
description = (
    "Megaplan Live Watchdog Supervisor: classify, diagnose, and decide "
    "repair action for live plan incidents."
)
default_profile = None
supported_modes = ("supervise", "native")
recommended_profiles = ()
driver = ("native", "linear")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = (
    "plan_supervision",
    "incident_classification",
    "repair_decision",
)

from arnold_pipelines.megaplan.pipelines.live_supervisor.pipeline import build_pipeline

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
