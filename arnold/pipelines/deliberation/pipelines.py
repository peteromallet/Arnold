"""Private compatibility imports for the split ``deliberation`` pipeline."""

from arnold.pipelines.deliberation.pipeline import (
    _native_bundle,
    build_initial_pipeline,
    build_pipeline as _build_pipeline,
)

build_pipeline = _build_pipeline

__all__: list[str] = []
