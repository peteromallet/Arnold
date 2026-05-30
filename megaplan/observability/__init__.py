"""Observability and introspection layer for megaplan plans.

Exposes:
- ``EventWriter`` / ``emit()`` / ``EventKind``: append-only event journal.
- ``read_events()``: generator for readers (introspect, trace, doctor).
- ``spawned()``: context manager for subprocess lifecycle events.
- ``live_log_tee()``: append to per-phase live log files.
"""
from megaplan.observability.events import (
    EventWriter,
    EventKind,
    emit,
    live_log_tee,
    read_events,
    spawned,
)
from megaplan.observability.event_sink import (
    EventEnvelope,
    EventSink,
    NdjsonBackend,
    StoreBackend,
)
from megaplan.observability.evaluand import EvaluandRecord

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
    "EvaluandRecord",
]
