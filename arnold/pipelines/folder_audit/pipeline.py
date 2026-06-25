"""Canonical native declaration and builder for the ``folder-audit`` pipeline."""

from __future__ import annotations

from typing import Any, Callable

from arnold.pipeline import Edge, Pipeline, Stage
from arnold.pipeline.native.compiler import compile_pipeline
from arnold.pipelines.folder_audit.native import folder_audit_native
from arnold.pipelines.folder_audit.steps import (
    AuditStep,
    EmitStep,
    IngestStep,
    _default_worker,
)


def build_pipeline(worker: Callable[..., Any] | None = None) -> Pipeline:
    """Build the native-backed ``folder_audit`` pipeline.

    The returned :class:`~arnold.pipeline.Pipeline` carries a compiled
    :class:`~arnold.pipeline.native.NativeProgram` so the native runtime is
    the canonical execution path. A graph-compatible projected shell is
    retained for callers that still inspect ``pipeline.stages``.
    """
    _w = worker if worker is not None else _default_worker

    ingest_stage = Stage(
        name="ingest",
        step=IngestStep(),
        edges=(Edge(label="audit", target="audit"),),
    )

    audit_stage = Stage(
        name="audit",
        step=AuditStep(
            _worker=_w,
            _pipeline_name="folder-audit",
        ),
        edges=(Edge(label="done", target="emit"),),
    )

    emit_stage = Stage(
        name="emit",
        step=EmitStep(),
        edges=(Edge(label="halt", target="halt"),),
    )

    program = compile_pipeline(folder_audit_native)

    return Pipeline(
        stages={
            "ingest": ingest_stage,
            "audit": audit_stage,
            "emit": emit_stage,
        },
        entry="ingest",
        resource_bundles=(),
        native_program=program,
    )
