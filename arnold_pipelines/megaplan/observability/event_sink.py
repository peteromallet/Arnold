"""M4 T10 — EventSink Protocol + NdjsonBackend + StoreBackend.

The EventSink is the single seam observability callers (effect ledger,
recovery policy, executor, evaluators) emit through.  It carries the
*kind* and *payload* the caller cares about plus the M4 cross-cutting
metadata (``scope``, ``phase``, ``idempotency_key``) that downstream
journals (NDJSON file per plan, Store epic-events table) project
differently.

The two shipping backends route through the SAME ``_envelope_ctx``
ContextVar so the resolved ``run_id`` is consistent across journals
(R5 join key).

* :class:`NdjsonBackend` wraps :class:`EventWriter` — ``phase`` is
  projected onto ``event['phase']``.
* :class:`StoreBackend` wraps the Store's
  ``record_epic_event`` / ``append_progress_event`` — ``scope`` is
  projected onto ``epic_id``.

Both backends defer ``run_id`` resolution to the EventWriter's existing
:func:`_resolve_run_id` so a single seat in ContextVar lights up both
journals simultaneously.

.. note::

   ``EventEnvelope`` and ``EventSink`` are re-exported from
   ``arnold.runtime.event_journal`` (M8 extraction).  ``NdjsonBackend``
   and ``StoreBackend`` remain here because they carry megaplan-specific
   ``_envelope_ctx`` / ``record_epic_event`` wiring.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

# Re-export the runtime-owned pure-data types.
from arnold.runtime.event_journal import EventEnvelope, EventSink  # noqa: F401


class NdjsonBackend:
    """EventSink that routes through the per-plan ``EventWriter`` (NDJSON).

    ``phase`` is projected onto the emitted event's top-level ``phase``
    field.  ``scope`` and ``idempotency_key`` are folded into the payload
    so they survive in the journal without changing the file schema.
    """

    def __init__(self, plan_dir: Path) -> None:
        self._plan_dir = Path(plan_dir)

    def emit(
        self,
        kind: str,
        *,
        payload: Optional[dict] = None,
        scope: Optional[str] = None,
        phase: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        # Local import — events imports envelope lazily, and a top-level
        # import here would re-introduce a cycle with effect_ledger.
        from arnold_pipelines.megaplan.observability.events import emit as _emit
        pl = dict(payload or {})
        if scope is not None:
            pl.setdefault("scope", scope)
        if idempotency_key is not None:
            pl.setdefault("idempotency_key", idempotency_key)
        return _emit(kind, self._plan_dir, phase=phase, payload=pl)


class StoreBackend:
    """EventSink that routes through the multi-tenant Store epic-event API.

    ``scope`` is projected onto ``epic_id``; the Store's existing
    ``append_progress_event`` / ``record_epic_event`` surface is unchanged
    (the record_epic_event ``run_id`` kwarg extension is deferred — see
    M4.1 follow-up).
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    def emit(
        self,
        kind: str,
        *,
        payload: Optional[dict] = None,
        scope: Optional[str] = None,
        phase: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        record_epic_event = getattr(self._store, "record_epic_event", None)
        if record_epic_event is None:
            raise RuntimeError(
                "StoreBackend requires a Store that exposes record_epic_event"
            )
        # Resolve run_id from the SAME ContextVar the NDJSON backend reads
        # so the two journals share the join key (R5).
        from arnold_pipelines.megaplan.observability.events import _resolve_run_id
        run_id = _resolve_run_id()
        fields: dict = {
            "kind": kind,
            "payload": dict(payload or {}),
        }
        if scope is not None:
            fields["epic_id"] = scope
        if phase is not None:
            fields["phase"] = phase
        if idempotency_key is not None:
            fields["idempotency_key"] = idempotency_key
        if run_id is not None:
            fields["run_id"] = run_id
        return record_epic_event(**fields)


__all__ = ["EventSink", "EventEnvelope", "NdjsonBackend", "StoreBackend"]
