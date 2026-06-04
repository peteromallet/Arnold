"""Megaplan planning pipeline — Arnold plugin.

This package is the canonical home for the Megaplan planning pipeline
implementation.  Registry discovery scans ``arnold/pipelines`` before
``megaplan/pipelines``, so this plugin wins deduplication.

Modules:

* ``pipeline.py`` — canonical ``build_pipeline()`` and ``compile_planning_pipeline``.
* ``routing.py`` — planning decision literals and routing helpers.
* ``operations.py`` — runtime operation registry adapter.
* ``handlers/`` — handler bridge modules (M5a/M5b deferred).
* ``stages/`` — stage implementation classes.
"""

from arnold.pipelines.megaplan.pipeline import (
    build_pipeline,
    compile_planning_pipeline,
)


def operation_registry():
    """Return the planning operation registry (lazy import)."""
    from arnold.pipelines.megaplan.operations import operation_registry as _reg

    return _reg()


def override_catalog():
    """Return the override catalog (lazy import)."""
    from arnold.pipelines.megaplan.operations import override_catalog as _cat

    return _cat()


__all__ = [
    "build_pipeline",
    "compile_planning_pipeline",
    "operation_registry",
    "override_catalog",
]
