"""Megaplan planning pipeline — Arnold plugin.

This package is the canonical home for the Megaplan planning pipeline
implementation.  Registry discovery scans ``arnold/pipelines`` before
``megaplan/pipelines``, so this plugin wins deduplication.

Modules:

* ``pipeline.py`` — canonical ``build_pipeline()`` and ``compile_planning_pipeline``.
* ``routing.py`` — planning decision literals and routing helpers.
* ``handlers/`` — handler bridge modules (M5a/M5b deferred).
* ``stages/`` — stage implementation classes.

Operation dispatch lives at ``megaplan.planning.operations``
(canonical) — the old ``operations.py`` adapter has been removed.

**Import note:** Top-level symbols are loaded lazily via ``__getattr__``
to prevent circular imports when orchestration/audit/execute/review
facades import from this package during handler initialization (SD2).
"""


def __getattr__(name: str):
    if name == "build_pipeline":
        from arnold.pipelines.megaplan.pipeline import build_pipeline as _bp
        return _bp
    if name == "compile_planning_pipeline":
        from arnold.pipelines.megaplan.pipeline import compile_planning_pipeline as _cpp
        return _cpp
    if name == "operation_registry":
        from megaplan.planning.operations import operation_registry as _reg
        return _reg
    if name == "override_catalog":
        from megaplan.planning.operations import override_catalog as _cat
        return _cat
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "build_pipeline",
    "compile_planning_pipeline",
    "operation_registry",
    "override_catalog",
]
