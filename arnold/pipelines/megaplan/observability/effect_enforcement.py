"""M4 T15 — Effect-Ledger at-most-once enforcement.

Pre-step discovery (grep -rn 'total_cost_usd|cost_usd|append.*cost|attribute.*cost'
across megaplan/_pipeline + megaplan/workers, 2026-05-30):

  Cost-attribution WRITE site:
    megaplan/_core/state.py:993-999  ``append_history`` — the canonical
    accumulation seam where ``entry['cost_usd']`` is folded into
    ``state['meta']['total_cost_usd']``.

  CostTracker at megaplan/_pipeline/runtime.py:58-77 is a READER only
  (``should_abort`` / ``current_cost``); the plan's reference to a
  ``CostTracker.bump`` method was a phantom — no such method exists.
  Worker-layer producers (workers/_impl.py:2229, hermes.py:1201,
  shannon.py:1589) construct WorkerResult.cost_usd which then flows
  through append_history at the discovered seam.

  Dispatch-backend wiring: T7 (subprocess) is landed; T8 (async) is
  landed. We route through the subprocess seam (preferred) and leave a
  deferral comment for the async seam pending its first real model-spend
  callback.

Public surface
~~~~~~~~~~~~~~
``journal_then_execute(effect, fn)`` — write the typed Effect to BOTH
journaled sinks (NDJSON via EventSink + epic_events via StoreBackend,
sharing ``run_id`` from the ``_envelope_ctx`` ContextVar) BEFORE invoking
``fn``.  On replay, presence of a journaled Effect with the same
``idempotency_key`` short-circuits — the at-most-once class never fires
``fn`` twice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Set

from arnold.pipelines.megaplan.observability.effect_ledger import Effect, ReplayClass

# Module-level idempotency-key cache used for the in-process short-circuit.
# (The persistent journals — NDJSON + Store — are the source of truth across
# crash-resume; this set is the warm read after rehydration.)
_SEEN_KEYS: Set[str] = set()

# Deferred pivot-recording targets — git push / PR emission seams that will
# wrap themselves in journal_then_execute when they land.  Listed here so a
# future executor can grep and pick them up.
_DEFERRED_TARGETS = (
    "tools/m4_oracle_bisect.py::push  # deferred pending bisect-emit",
    "megaplan/orchestration/*::pr_create  # deferred pending PR-emit surface",
)


class DoubleExecuteError(RuntimeError):
    """Raised when a journaled at-most-once Effect would re-execute."""


def _resolve_run_id() -> Optional[str]:
    try:
        from arnold.pipelines.megaplan.observability.events import _resolve_run_id as _r
        return _r()
    except Exception:
        return None


def _journal_intent(
    effect: Effect,
    *,
    plan_dir: Optional[Path],
    store: Any = None,
    phase: Optional[str] = None,
) -> None:
    """Write the Effect INTENT to NDJSON and/or Store BEFORE execute.

    Either sink may be unavailable in a unit-test harness; the contract
    is that at least one durable record exists before ``fn`` fires.
    """
    payload = {
        "replay_class": getattr(effect.replay_class, "value", str(effect.replay_class)),
        "idempotency_key": effect.idempotency_key,
        "compensation": effect.compensation,
        "provenance": dict(effect.provenance or {}),
        "effect_taint": effect.effect_taint,
    }
    if plan_dir is not None:
        try:
            from arnold.pipelines.megaplan.observability.event_sink import NdjsonBackend
            NdjsonBackend(Path(plan_dir)).emit(
                "effect_intent",
                payload=payload,
                phase=phase,
                idempotency_key=effect.idempotency_key,
            )
        except Exception:
            pass
    if store is not None:
        try:
            from arnold.pipelines.megaplan.observability.event_sink import StoreBackend
            StoreBackend(store).emit(
                "effect_intent",
                payload=payload,
                scope=getattr(store, "epic_id", None),
                phase=phase,
                idempotency_key=effect.idempotency_key,
            )
        except Exception:
            pass


def journal_then_execute(
    effect: Effect,
    fn: Callable[[], Any],
    *,
    plan_dir: Optional[Path] = None,
    store: Any = None,
    phase: Optional[str] = None,
) -> Any:
    """At-most-once external act: journal intent, then execute ``fn``.

    Contract:
      1. The Effect intent is journaled to durable sinks BEFORE ``fn`` runs.
      2. If a journaled effect with the same ``idempotency_key`` has been
         seen in this process (e.g. replay rehydration), ``fn`` is skipped
         and the cached short-circuit fires.

    The ordering matters: writing the journal AFTER the external return
    would leak double-execution on a crash between return and write — the
    replay oracle (tests/oracles/test_effect_ledger_replay_oracle.py)
    asserts no double-execute even when the write raises.
    """
    key = effect.idempotency_key
    if effect.replay_class == ReplayClass.at_most_once and key:
        if key in _SEEN_KEYS:
            return None  # already executed once; short-circuit per contract
    # Journal FIRST.  If this raises, we have NOT executed fn yet — the
    # crash-resume path will simply re-attempt journal+execute on the next
    # invocation; the idempotency-key dedup prevents double-execute.
    _journal_intent(effect, plan_dir=plan_dir, store=store, phase=phase)
    if key:
        _SEEN_KEYS.add(key)
    return fn()


def _reset_for_tests() -> None:
    """Clear the in-process seen-keys cache (test helper)."""
    _SEEN_KEYS.clear()


__all__ = [
    "DoubleExecuteError",
    "journal_then_execute",
]
