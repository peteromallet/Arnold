"""Compatibility shim — re-exports from ``arnold.pipelines.evidence_pack.pipeline``.

Do NOT add graph-era imports or behavior forks to this module.
"""

from arnold.pipelines.evidence_pack.pipeline import (  # noqa: F401
    EvidencePackStep,
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
    "EvidencePackStep",
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
