"""Thin re-export: canonical ``megaplan`` pipeline (legacy planning → megaplan alias).

Registry identity is ``megaplan``; the legacy alias ``planning`` resolves to it.
All canonical metadata lives in :mod:`arnold.pipelines.megaplan`.
"""

from __future__ import annotations

# ── Re-export the canonical implementation ─────────────────────────────────
from arnold.pipelines.megaplan import (  # noqa: F401
    arnold_api_version,
    capabilities,
    default_profile,
    description,
    driver,
    entrypoint,
    name,
    supported_modes,
    build_pipeline as _canonical_build_pipeline,
    compile_planning_pipeline,
)
from arnold.pipelines.megaplan.planning.operations import operation_registry, override_catalog  # noqa: F401


def build_pipeline():
    return _canonical_build_pipeline()


__all__ = [
    "build_pipeline",
    "compile_planning_pipeline",
    "operation_registry",
    "override_catalog",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
