"""Neutral state-delta primitives for the Arnold pipeline boundary.

This module provides a deliberately *loose* state-patch container
(``StateDelta``) and a companion ``apply_delta`` function.  Arnold owns the
neutral shape; opinionated runtimes (e.g. Megaplan) implement the semantics.

.. note::

    The ``StateDelta`` / ``apply_delta`` names are deliberately shared with
    ``megaplan._pipeline.types``.  The Arnold versions are simpler (ordered
    multi-patch, no CAS, no version stamps) and live under a different
    module path.  M2 will reconcile them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StateDelta:
    """An ordered container of state patches.

    Each element of ``patches`` is a ``dict`` that should be applied
    sequentially via ``dict.update`` when the runtime state is ``dict``-like.
    For non-dict state the entire container replaces the previous value.

    This is intentionally simpler than the Megaplan CAS-based ``StateDelta``
    — no ``op``, no ``key``, no ``version`` stamp.  Arnold defines the
    *neutral* primitive; Megaplan layers opinionated concurrency control on
    top.
    """

    patches: tuple[dict[str, Any], ...]


def apply_delta(state: Any, delta: StateDelta) -> Any:
    """Apply each patch in *delta.patches* in order and return the result.

    * If *state* is a ``dict`` (the common case), each patch is applied via
      ``state.update(patch)``, and the original dict is mutated in place and
      returned.  Callers who need immutability should pass a copy.
    * If *state* is **not** a ``dict``, the *last* patch replaces *state*
      entirely (or *state* is returned unchanged when *patches* is empty).
    """
    for patch in delta.patches:
        if isinstance(state, dict) and isinstance(patch, dict):
            state.update(patch)
        else:
            state = patch
    return state
