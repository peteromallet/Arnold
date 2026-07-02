"""Thin compatibility shim — re-exports from ``arnold.pipelines.evidence_pack``.

This package exists only to support legacy import paths. All behavior
lives in the canonical ``arnold.pipelines.evidence_pack`` package.

Do NOT add graph-era imports or behavior forks to this module.
"""

from arnold.pipelines.evidence_pack import (  # noqa: F401
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
