"""Compatibility facade for planning operation dispatch.

The canonical home for Megaplan planning operation dispatch is
``arnold_pipelines.megaplan.planning.operations``. This module remains
import-safe so plugin discovery and broad import sweeps do not fail on a
deliberate migration stub.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.planning.operations import (
    PlanningOperationRegistry,
    SUPPORTED_OPERATIONS,
    operation_registry,
    override_catalog,
    preflight_or_raise,
    profile_validate_operation,
    resume_phase_args,
)

__all__ = [
    "PlanningOperationRegistry",
    "SUPPORTED_OPERATIONS",
    "operation_registry",
    "override_catalog",
    "preflight_or_raise",
    "profile_validate_operation",
    "resume_phase_args",
]
