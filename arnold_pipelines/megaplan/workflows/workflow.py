"""Compatibility glue for the Megaplan authored workflow module.

The canonical authored workflow now lives in ``workflow.pypeline``. This
module remains importable for callers that expect a sibling Python module,
but it intentionally carries no independent product skeleton.
"""

from __future__ import annotations

from .planning import AUTHORING_SOURCE_PATH, WORKFLOW_MODULE_PATH, build_pipeline


def canonical_source_path() -> str:
    """Return the canonical authored source path used by planning surfaces."""

    return str(AUTHORING_SOURCE_PATH)


__all__ = ["AUTHORING_SOURCE_PATH", "WORKFLOW_MODULE_PATH", "build_pipeline", "canonical_source_path"]
