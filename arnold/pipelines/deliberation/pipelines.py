"""Private compatibility shim for legacy ``arnold.pipelines.deliberation.pipelines`` imports.

The canonical implementation lives in :mod:`arnold.pipelines.deliberation.pipeline`;
this module re-exports the previous public names so existing tests and downstream
code keep working while the package migrates to a native-first shape.
"""

from arnold.pipelines.deliberation.pipeline import (
    _native_bundle,
    build_initial_pipeline,
    build_pipeline,
)

__all__ = [
    "_native_bundle",
    "build_initial_pipeline",
    "build_pipeline",
]
