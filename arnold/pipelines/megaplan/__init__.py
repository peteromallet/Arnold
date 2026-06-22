"""Megaplan planning pipeline — legacy M4 parity shim.

This package is a temporary M4 parity shim around ``arnold_pipelines.megaplan``.
All implementation has moved; this module re-exports the public surface so
existing imports and plugin discovery continue to work until M6.

Registry discovery scans ``arnold/pipelines`` before ``megaplan/pipelines``,
so this shim wins deduplication during the transition.
"""

from __future__ import annotations

from typing import Any

import arnold_pipelines.megaplan as _new_pkg

# Re-export the public namespace defined by the new package.
__all__ = _new_pkg.__all__

# Plugin metadata (needed by registry discovery before any lazy symbol lookup).
name = _new_pkg.name
description = _new_pkg.description
default_profile = _new_pkg.default_profile
supported_modes = _new_pkg.supported_modes
recommended_profiles = _new_pkg.recommended_profiles
driver = _new_pkg.driver
entrypoint = _new_pkg.entrypoint
arnold_api_version = _new_pkg.arnold_api_version
capabilities = _new_pkg.capabilities

# Eagerly re-export the canonical constructors so direct attribute access works.
build_pipeline = _new_pkg.build_pipeline
compile_planning_pipeline = _new_pkg.compile_planning_pipeline


def __getattr__(name: str) -> Any:
    """Delegate unknown attributes to the new package."""
    return getattr(_new_pkg, name)
