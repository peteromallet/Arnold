"""Canonical Megaplan planning pipeline facade.

This thin module re-exports :func:`build_pipeline` from
:mod:`arnold_pipelines.megaplan.workflows.planning` and provides
:func:`build_and_compile_pipeline` as a convenience wrapper that compiles the
authored workflow to a :class:`arnold.manifest.WorkflowManifest`.

The readable, product-local source of truth for the graph lives in
``arnold_pipelines/megaplan/workflows/planning.py``.
"""

from __future__ import annotations

from typing import Any

from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline

from arnold_pipelines.megaplan.workflows.planning import build_pipeline


def build_and_compile_pipeline(**kwargs: Any) -> Any:
    """Build the M4 pipeline and compile it to a ``WorkflowManifest``."""
    return compile_pipeline(build_pipeline(**kwargs))


__all__ = [
    "build_and_compile_pipeline",
    "build_pipeline",
]
