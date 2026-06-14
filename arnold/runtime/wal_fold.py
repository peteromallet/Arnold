"""Pure fold combinator for event journal replay.

Provides a generalized, parameterized fold over event journals that
is opinion-free — no hard-coded event kinds, no policy vocabulary,
and no I/O.  Callers supply the kind filter and projection function.

Exports
-------
* ``fold_journal`` — generalized fold over events with kind filter and projector.
* ``last_state_snapshot_projector`` — projector that replays the last
  dict-valued ``state`` snapshot from an event's payload.
* ``read_event_journal`` — re-exported from ``arnold.runtime.event_journal``
  for caller convenience (pure file reader).
"""

from __future__ import annotations

from typing import Any, Callable, Union

from arnold.runtime.event_journal import read_event_journal, read_event_journal_paged, stream_event_journal  # noqa: F401


def fold_journal(
    events: list[dict],
    *,
    kind_filter: Union[str, Callable[[str], bool]],
    projector: Callable[[Any, dict], Any],
    initial: Any = None,
) -> Any:
    """Pure, parameterized fold over an event journal.

    Sorts *events* by ``seq`` (ascending), filters to those matching
    *kind_filter*, then folds left-to-right via ``projector(acc, ev)``.

    Parameters
    ----------
    events:
        List of event dicts (must carry a ``"seq"`` field).
    kind_filter:
        Either a ``str`` (exact match on ``event[\"kind\"]``) or a
        callable predicate ``(kind: str) -> bool``.
    projector:
        Callable ``(acc, ev) -> new_acc`` applied to each matching event.
    initial:
        Initial accumulator value (default ``None``).

    Returns
    -------
        *initial* when no events match the filter.
    """
    sorted_events = sorted(events, key=lambda e: e.get("seq", 0))

    if callable(kind_filter):
        filtered = [e for e in sorted_events if kind_filter(e.get("kind"))]
    else:
        filtered = [e for e in sorted_events if e.get("kind") == kind_filter]

    acc = initial
    for ev in filtered:
        acc = projector(acc, ev)
    return acc


def last_state_snapshot_projector(acc: Any, ev: dict) -> Any:
    """Projector that replays the last dict-valued state snapshot.

    Replicates ``fold.py:67-69``: extracts the ``state`` field from
    ``ev[\"payload\"]`` and returns it as the new accumulator when it is
    a ``dict`` instance.  Otherwise returns the previous accumulator
    unchanged — non-dict payloads (e.g. ``None``, missing keys, scalars)
    are silently skipped.

    Parameters
    ----------
    acc:
        Current accumulator (previous snapshot or *initial*).
    ev:
        An event dict carrying ``payload`` with an optional ``state`` field.

    Returns
    -------
        The new accumulator — either *ev*'s state snapshot (when it is a
        ``dict``) or the unchanged *acc*.
    """
    payload = ev.get("payload") or {}
    snapshot = payload.get("state")
    if isinstance(snapshot, dict):
        return snapshot
    return acc


__all__ = [
    "fold_journal",
    "last_state_snapshot_projector",
    "read_event_journal",
    "read_event_journal_paged",
    "stream_event_journal",
]
