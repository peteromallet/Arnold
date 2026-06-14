"""State store backends — pluggable persistence strategies for plan state.

This module is **distinct from arnold.pipelines.megaplan.store** and provides the
storage-axis drivers that the Governor and Conveyance consume. Three
models are defined via ``StateStoreModel``:

* ``forward_only`` — writes are destructive; no snapshot history.
* ``reversible``   — every write snapshots the prior state via
  :func:`megaplan._core.state.snapshot` so the Governor can roll back.
* ``event_sourced`` — (reserved) full WAL-event replay; raises
  :class:`NotImplementedError` in the current implementation.

All backends conform to the :class:`StateStoreBackend` protocol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from arnold.pipelines.megaplan._core.state import (
    read_json,
    restore,
    save_state,
    snapshot,
    write_plan_state,
)

# ---------------------------------------------------------------------------
# Model literal
# ---------------------------------------------------------------------------


StateStoreModel = Literal["forward_only", "reversible", "event_sourced"]


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StateStoreBackend(Protocol):
    """Contract every state-store backend must satisfy.

    Attributes:
        model: The :class:`StateStoreModel` discriminator for this backend.
    """

    model: StateStoreModel

    def write_state(self, plan_dir: Path, state: dict[str, Any]) -> None:
        """Persist *state* as the canonical ``state.json`` for *plan_dir*."""
        ...

    def read_state(self, plan_dir: Path) -> dict[str, Any]:
        """Return the current canonical state dict for *plan_dir*."""
        ...


@runtime_checkable
class ReversibleStoreBackend(Protocol):
    """Extended contract for backends that support snapshot/restore."""

    model: Literal["reversible"]

    def snapshot(self, plan_dir: Path) -> str | None:
        """Capture the current state blob and return its snapshot id."""
        ...

    def restore(self, plan_dir: Path, snapshot_id: str) -> dict[str, Any]:
        """Atomically roll back to *snapshot_id*; return the restored dict."""
        ...


# ---------------------------------------------------------------------------
# Concrete backends
# ---------------------------------------------------------------------------


class ForwardOnlyStateStoreBackend:
    """Destructive-write backend. No snapshot history is kept.

    Delegates to :func:`megaplan._core.state.write_plan_state` with
    ``mode=\"replace\"`` for writes and :func:`read_json` for reads.
    """

    model: StateStoreModel = "forward_only"

    def write_state(self, plan_dir: Path, state: dict[str, Any]) -> None:
        write_plan_state(plan_dir, mode="replace", state=state)

    def read_state(self, plan_dir: Path) -> dict[str, Any]:
        return read_json(plan_dir / "state.json")


class ReversibleStateStoreBackend:
    """Snapshot-preserving backend — every write snapshots the prior state.

    Writes use ``write_plan_state(..., mode=\"reversible\")`` so that
    :func:`megaplan._core.state._snapshot_unlocked` captures a whole-blob
    copy into ``.state-versions/<id>.json`` before overwriting. The
    :meth:`snapshot` / :meth:`restore` pair lets the Governor rewind a
    state mutation that a budget-exhausted step left half-applied.
    """

    model: StateStoreModel = "reversible"

    def write_state(self, plan_dir: Path, state: dict[str, Any]) -> None:
        write_plan_state(plan_dir, mode="reversible", state=state)

    def read_state(self, plan_dir: Path) -> dict[str, Any]:
        return read_json(plan_dir / "state.json")

    def snapshot(self, plan_dir: Path) -> str | None:
        return snapshot(plan_dir)

    def restore(self, plan_dir: Path, snapshot_id: str) -> dict[str, Any]:
        return restore(plan_dir, snapshot_id)


class EventSourcedStateStoreBackend:
    """Reserved event-sourcing backend — **not yet implemented**.

    Raises :class:`NotImplementedError` for every operation so that any
    accidental dispatch to this code path is caught immediately rather
    than silently degrading to a forward-only or reversible fallback.
    """

    model: StateStoreModel = "event_sourced"

    def __init__(self) -> None:
        raise NotImplementedError(
            "EventSourcedStateStoreBackend is not implemented"
        )

    def write_state(self, plan_dir: Path, state: dict[str, Any]) -> None:
        raise NotImplementedError(
            "EventSourcedStateStoreBackend.write_state is not implemented"
        )

    def read_state(self, plan_dir: Path) -> dict[str, Any]:
        raise NotImplementedError(
            "EventSourcedStateStoreBackend.read_state is not implemented"
        )
