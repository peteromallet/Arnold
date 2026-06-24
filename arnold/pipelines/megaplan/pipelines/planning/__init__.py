"""Thin re-export: canonical ``megaplan`` pipeline (legacy planning → megaplan alias).

Registry identity is ``megaplan``; the legacy alias ``planning`` resolves to it.
The canonical implementation is imported from :mod:`arnold.pipelines.megaplan`,
but the manifest constants below are declared literally so that the manifest-first
discovery reader can extract them without executing the module.
"""

from __future__ import annotations

name: str = "megaplan"
description: str = (
    "Built-in megaplan pipeline: prep → plan → critique/gate/revise loop "
    "→ finalize → execute → review. Gate verdicts: proceed / iterate / "
    "tiebreaker / escalate. Robustness levels: bare / light / full / "
    "thorough / extreme."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("plan", "native")
driver: tuple[str, str] = ("native", "megaplan")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("plan", "execute", "review")

# ── Re-export the canonical implementation ─────────────────────────────────
from arnold.pipelines.megaplan import (  # noqa: E402, F401
    build_pipeline as _canonical_build_pipeline,
    compile_planning_pipeline,
)
from arnold.pipelines.megaplan.planning.operations import operation_registry, override_catalog  # noqa: E402, F401


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
