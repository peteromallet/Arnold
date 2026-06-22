"""State-delta primitives with Compare-and-Swap (CAS) concurrency control.

This module owns ``StateDelta``, ``StateDeltaConflict``, and ``apply_delta``
— the Megaplan opinionated CAS-based state mutation contract.  These were
rehomed from ``arnold_pipelines.megaplan._pipeline.types`` during the M3
burn-down (Step 9).

The Arnold boundary provides a simpler neutral ``StateDelta`` /
``apply_delta`` in ``arnold.pipeline.state`` (ordered multi-patch, no CAS,
no version stamps).  Megaplan layers opinionated concurrency control on top
of that primitive via this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


class StateDeltaConflict(Exception):
    """Raised by :func:`apply_delta` when the delta's ``version`` does not
    match the current version recorded in ``state['_state_meta']['versions']``.

    Carries the offending ``key``, the ``expected`` version that the delta
    claimed, and the ``actual`` version observed in state at apply time.
    """

    def __init__(self, key: str, expected: int, actual: int) -> None:
        super().__init__(
            f"state delta for key {key!r} expected version {expected}, "
            f"found {actual}"
        )
        self.key = key
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class StateDelta:
    """Compare-and-swap state mutation.

    ``op`` is one of:

    * ``'replace'`` — last-writer-wins assignment of ``value`` at ``key``.
    * ``'accumulate'`` — append ``value`` to an existing list at ``key``
      (creating ``[]`` if missing); retains all prior entries.
    * ``'deep_merge'`` — recursively merge ``value`` (a mapping) into the
      mapping at ``key``; non-mapping leaves are overwritten.

    ``version`` is the version the writer last observed for ``key``.
    :func:`apply_delta` raises :class:`StateDeltaConflict` when the
    actual version in ``state['_state_meta']['versions']`` differs.
    """

    op: Literal["replace", "accumulate", "deep_merge"]
    key: str
    value: Any
    version: int


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, Mapping):
        out = dict(base)
        for k, v in overlay.items():
            out[k] = _deep_merge(out.get(k), v) if k in out else v
        return out
    return overlay


def apply_delta(
    state: Mapping[str, Any], delta: StateDelta
) -> tuple[dict[str, Any], int]:
    """Apply *delta* to *state* under CAS semantics.

    Returns ``(new_state, new_version)``. Raises
    :class:`StateDeltaConflict` when ``delta.version`` does not match the
    version recorded at ``state['_state_meta']['versions'][delta.key]``
    (absent ⇒ ``0``).
    """
    new_state: dict[str, Any] = dict(state)
    meta = dict(new_state.get("_state_meta", {}))
    versions = dict(meta.get("versions", {}))
    actual = int(versions.get(delta.key, 0))
    if actual != delta.version:
        raise StateDeltaConflict(delta.key, delta.version, actual)

    if delta.op == "replace":
        new_state[delta.key] = delta.value
    elif delta.op == "accumulate":
        existing = list(new_state.get(delta.key, []))
        existing.append(delta.value)
        new_state[delta.key] = existing
    elif delta.op == "deep_merge":
        existing = new_state.get(delta.key, {})
        new_state[delta.key] = _deep_merge(existing, delta.value)
    else:  # pragma: no cover - exhaustive Literal
        raise ValueError(f"unknown StateDelta op: {delta.op!r}")

    new_version = actual + 1
    versions[delta.key] = new_version
    meta["versions"] = versions
    new_state["_state_meta"] = meta
    return new_state, new_version
