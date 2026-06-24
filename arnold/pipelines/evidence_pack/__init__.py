"""Evidence-pack pipeline — model-less verification of persisted JSON artifacts.

M4 migration: the package is now native-first.  The canonical entrypoint is
:func:`build_pipeline` in :mod:`arnold.pipelines.evidence_pack.pipeline`.
"""

from arnold.pipelines.evidence_pack.pipeline import build_pipeline

name = "evidence-pack"
description = "Model-less verification of persisted JSON artifacts."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
driver = ("native",)
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("artifact-verification", "evidence-pack")

__all__ = [
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "supported_modes",
]
