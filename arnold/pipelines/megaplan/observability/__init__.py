"""Observability and introspection layer for megaplan plans.

Exposes:
- ``EventWriter`` / ``emit()`` / ``EventKind``: append-only event journal.
- ``read_events()``: generator for readers (introspect, trace, doctor).
- ``spawned()``: context manager for subprocess lifecycle events.
- ``live_log_tee()``: append to per-phase live log files.
"""
from arnold.pipelines.megaplan.observability.events import (
    EventWriter,
    EventKind,
    emit,
    live_log_tee,
    read_events,
    spawned,
)
from arnold.pipelines.megaplan.observability.event_sink import (
    EventEnvelope,
    EventSink,
    NdjsonBackend,
    StoreBackend,
)
from arnold.pipelines.megaplan.observability.events_projection import (
    ensure_events_projection,
    project_events,
    project_events_ndjson,
    schema_equivalence_triples,
)
from arnold.pipelines.megaplan.observability.evaluand import (
    BetterResult,
    EvaluandRecord,
    ModelIORef,
    RecordedModelIO,
    RecordedIOScorer,
    RecordedIOUnavailable,
    ReJudgeOutcome,
    better,
    derive_params_hash,
    raw_prompt_sha256,
    read_evaluand,
    read_evaluand_events,
    re_judge,
    stage_receipt,
    write_evaluand,
    write_evaluand_event,
)

__all__ = [
    "EventWriter",
    "EventKind",
    "emit",
    "read_events",
    "spawned",
    "live_log_tee",
    "EventSink",
    "EventEnvelope",
    "NdjsonBackend",
    "StoreBackend",
    "ensure_events_projection",
    "project_events",
    "project_events_ndjson",
    "schema_equivalence_triples",
    "EvaluandRecord",
    "BetterResult",
    "ModelIORef",
    "RecordedModelIO",
    "RecordedIOScorer",
    "RecordedIOUnavailable",
    "ReJudgeOutcome",
    "raw_prompt_sha256",
    "derive_params_hash",
    "better",
    "re_judge",
    "write_evaluand",
    "write_evaluand_event",
    "read_evaluand",
    "read_evaluand_events",
    "stage_receipt",
]
