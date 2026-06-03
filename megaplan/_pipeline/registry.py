"""Deprecated re-export bridge for megaplan._pipeline.registry.

This module has moved to :mod:`arnold.pipeline.registry`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.

The Megaplan-specific ``_ensure_builtin_pipelines_registered()``
auto-registration of the ``"planning"`` pipeline is preserved here
so existing consumers that depend on implicit registration continue
to work.
"""

from __future__ import annotations

import warnings
from typing import Any, Mapping

warnings.warn(
    "megaplan._pipeline.registry is deprecated; "
    "use arnold.pipeline.registry instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all public symbols from the canonical arnold module
from arnold.pipeline.registry import *  # noqa: F403, E402

# Explicitly import private globals needed for megaplan auto-registration
from arnold.pipeline.registry import (  # noqa: E402
    _GLOBAL_REGISTRY,
    PipelineRegistry,
)

# ── Megaplan-specific auto-registration of the planning pipeline ───────

def _planning_builder():  # type: ignore[no-untyped-def]
    """Lazy builder for the megaplan 'planning' pipeline."""
    from megaplan._pipeline.planning import compile_planning_pipeline
    return compile_planning_pipeline()


def _ensure_builtin_pipelines_registered() -> None:
    """Reassert the built-in ``"planning"`` pipeline in the global registry.

    The chain driver can run for hours in one Python process while
    discovery and test helpers exercise the same global registry.
    The production planning pipeline is not file-discovered, so it
    must be restored idempotently if the registry was reset to
    discovered-only entries.
    """
    if "planning" not in _GLOBAL_REGISTRY.builders:
        _GLOBAL_REGISTRY.register(
            "planning",
            _planning_builder,
            description="Production planning — runnable shape "
                        "(prep→plan→critique→gate→…→review).",
        )


# Idempotent registration at import time
_ensure_builtin_pipelines_registered()
