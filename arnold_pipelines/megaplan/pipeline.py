"""Canonical Megaplan planning pipeline facade.

This thin module re-exports :func:`build_pipeline` from
:mod:`arnold_pipelines.megaplan.workflows.planning` and provides
:func:`build_and_compile_pipeline` as a convenience wrapper that projects the
authored workflow to a native-backed compatibility shell.

The readable, product-local source of truth for the graph lives in
``arnold_pipelines/megaplan/workflows/workflow.pypeline``.
"""

from __future__ import annotations

from typing import Any

from arnold_pipelines.megaplan._compatibility import build_compatibility_shell
from arnold_pipelines.megaplan.planning.operations import (
    operation_registry as planning_operation_registry,
)
from arnold_pipelines.megaplan.workflows.planning import build_pipeline


def build_and_compile_pipeline(**kwargs: Any) -> Any:
    """Build the DSL pipeline and project it to a native-backed shell."""
    return build_compatibility_shell(build_pipeline(**kwargs))


def operation_registry() -> Any:
    """Expose the canonical planning operation surface for builtin dispatch."""

    return planning_operation_registry()


__all__ = [
    "build_and_compile_pipeline",
    "build_pipeline",
    "operation_registry",
]
