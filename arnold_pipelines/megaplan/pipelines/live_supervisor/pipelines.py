"""Private compatibility imports for the split ``live-supervisor`` mirror."""

from __future__ import annotations

from arnold.pipelines.megaplan.pipelines.live_supervisor.pipeline import (
    _build_graph_pipeline,
    _native_bundle,
    _native_program,
    build_pipeline as _build_pipeline,
    live_supervisor_native,
)

build_pipeline = _build_pipeline

__all__: list[str] = []
