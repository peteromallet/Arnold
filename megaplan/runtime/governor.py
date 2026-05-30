"""Tree-scoped run Governor — recursion / dollar / concurrency / fan-out caps.

The Governor is attached to a logical execution tree (a top-level plan run and
all of its in-process descendants).  It tracks four budgets and exposes two
operations:

* :meth:`Governor.charge` — record that an envelope has consumed budget (cost,
  one unit of concurrency, one unit of fan-out width).  Called by
  :meth:`megaplan.runtime.key_pool.KeyPool.acquire` so any path that pulls an
  API key is automatically charged.

* :meth:`Governor.would_exceed` — pure predicate returning an
  :class:`ExceedReason` enum when the *next* envelope would push some budget
  past its cap, or ``None`` otherwise.  Called by ``pattern_dynamic`` fan-out
  before spawning child specs; on positive verdict the caller raises
  :class:`BudgetExceeded`.

Ordering invariant
------------------
:func:`megaplan._core.state.restorable_boundary` raises
``RestorableBoundaryViolation`` at ``__enter__`` *before* the protected body
runs.  Any Governor check is performed inside the body, so a boundary refusal
always precedes a :class:`BudgetExceeded` raised by the same operation.
"""

from __future__ import annotations

import enum
import threading
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

from megaplan._pipeline.envelope import RunEnvelope


class ExceedReason(str, enum.Enum):
    RECURSION_DEPTH = "recursion_depth"
    DOLLAR_CAP = "dollar_cap"
    CONCURRENCY_CAP = "concurrency_cap"
    FANOUT_CAP = "fanout_cap"


class BudgetExceeded(RuntimeError):
    """Raised when a Governor cap would be (or has been) exceeded."""

    def __init__(self, reason: ExceedReason, detail: str = "") -> None:
        self.reason = reason
        msg = f"governor budget exceeded: {reason.value}"
        if detail:
            msg = f"{msg} ({detail})"
        super().__init__(msg)


@dataclass
class Governor:
    """Tree-scoped budget tracker.

    All caps default to a sentinel disabling the cap; callers opt in by passing
    a finite value.  Counters are mutated under a lock so concurrent in-process
    consumers (e.g. fan-out replicas) see consistent state.
    """

    recursion_depth_cap: int = 0
    dollar_cap: float = float("inf")
    concurrency_cap: int = 0
    fanout_cap: int = 0

    spent_dollars: float = 0.0
    active_concurrency: int = 0
    active_fanout: int = 0
    current_depth: int = 0

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ------------------------------------------------------------------
    # Predicate
    # ------------------------------------------------------------------

    def would_exceed(
        self, envelope: RunEnvelope, *, fanout_width: int = 1
    ) -> Optional[ExceedReason]:
        cost = float(getattr(envelope, "cost", 0.0) or 0.0)
        lineage_len = len(getattr(envelope, "lineage", ()) or ())
        with self._lock:
            if self.recursion_depth_cap and (
                max(self.current_depth, lineage_len) + 1 > self.recursion_depth_cap
            ):
                return ExceedReason.RECURSION_DEPTH
            if self.spent_dollars + cost > self.dollar_cap:
                return ExceedReason.DOLLAR_CAP
            if self.concurrency_cap and self.active_concurrency + 1 > self.concurrency_cap:
                return ExceedReason.CONCURRENCY_CAP
            if self.fanout_cap and self.active_fanout + fanout_width > self.fanout_cap:
                return ExceedReason.FANOUT_CAP
            return None

    # ------------------------------------------------------------------
    # Mutating charge
    # ------------------------------------------------------------------

    def charge(self, envelope: RunEnvelope) -> None:
        """Account for one consumed envelope.  Raises :class:`BudgetExceeded`
        if the charge would push past a cap (post-hoc verdict — the predicate
        is :meth:`would_exceed`).
        """

        cost = float(getattr(envelope, "cost", 0.0) or 0.0)
        lineage_len = len(getattr(envelope, "lineage", ()) or ())
        with self._lock:
            new_dollars = self.spent_dollars + cost
            if new_dollars > self.dollar_cap:
                raise BudgetExceeded(
                    ExceedReason.DOLLAR_CAP,
                    f"would spend {new_dollars} > cap {self.dollar_cap}",
                )
            new_concurrency = self.active_concurrency + 1
            if self.concurrency_cap and new_concurrency > self.concurrency_cap:
                raise BudgetExceeded(
                    ExceedReason.CONCURRENCY_CAP,
                    f"would hold {new_concurrency} > cap {self.concurrency_cap}",
                )
            depth = max(self.current_depth, lineage_len)
            if self.recursion_depth_cap and depth > self.recursion_depth_cap:
                raise BudgetExceeded(
                    ExceedReason.RECURSION_DEPTH,
                    f"depth {depth} > cap {self.recursion_depth_cap}",
                )
            self.spent_dollars = new_dollars
            self.active_concurrency = new_concurrency
            self.current_depth = depth

    def note_fanout(self, width: int) -> None:
        """Record a fan-out of ``width`` child specs being spawned."""

        with self._lock:
            self.active_fanout += int(width)


# ---------------------------------------------------------------------------
# Tree-scoped attachment
# ---------------------------------------------------------------------------

_governor_ctx: ContextVar[Optional[Governor]] = ContextVar(
    "_governor_ctx", default=None
)


def current_governor() -> Optional[Governor]:
    """Return the Governor attached to the current execution tree, or ``None``."""

    return _governor_ctx.get()


def set_governor(governor: Optional[Governor]):
    """Attach ``governor`` to the current ContextVar scope.  Returns the token
    so the caller can :meth:`ContextVar.reset` it later (test/teardown).
    """

    return _governor_ctx.set(governor)


def reset_governor(token) -> None:
    _governor_ctx.reset(token)
