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

from arnold.runtime.envelope import RunEnvelope


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

    # M4 T3 — per-lease accumulator for fold_shard_spend.
    # Maps lease_id -> highest fencing_token observed; tracks the total
    # capacity_grant folded across all (lease_id, fencing_token) pairs we
    # have not yet de-duplicated.  When a write arrives with a fencing_token
    # strictly less than the highest seen for its lease, the accumulator is
    # poisoned: the very next fold_shard_spend write raises BudgetExceeded.
    _shard_max_token: dict = field(default_factory=dict, repr=False)
    _shard_seen: dict = field(default_factory=dict, repr=False)
    _shard_grants: float = field(default=0.0, repr=False)
    _shard_poisoned: bool = field(default=False, repr=False)

    # ------------------------------------------------------------------
    # Predicate
    # ------------------------------------------------------------------

    def would_exceed(
        self, envelope: RunEnvelope, *, fanout_width: int = 1
    ) -> Optional[ExceedReason]:
        cost = float(getattr(envelope, "cost", 0.0) or 0.0)
        lineage_len = len(getattr(envelope, "lineage", ()) or ())
        # M4 T2: defensively read capacity_grant; legacy envelopes may lack it.
        _ = float(getattr(envelope, "capacity_grant", 0.0) or 0.0)
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
        # M4 T2: defensively read capacity_grant; legacy envelopes may lack it.
        _ = float(getattr(envelope, "capacity_grant", 0.0) or 0.0)
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

    # ------------------------------------------------------------------
    # M4 T3 — Capacity-lease shard fold
    # ------------------------------------------------------------------

    def fold_shard_spend(self, envelope: RunEnvelope) -> None:
        """Fold a per-shard capacity-grant write into the Governor accumulator.

        Reads ``lease_id``, ``fencing_token`` and ``capacity_grant`` via
        :func:`getattr` so legacy envelopes (no shard fields) are accepted as
        no-ops and the single-process, no-shared-ledger path remains
        byte-identical with the pre-M4 behaviour.

        The fold is idempotent per ``(lease_id, fencing_token)`` pair —
        re-folding the same shard is a silent no-op — and rejects stale
        fencing tokens by poisoning the accumulator so the next write raises
        :class:`BudgetExceeded`.  Envelopes without ``lease_id`` or
        ``fencing_token`` are byte-identical no-ops (the executor falls back
        to the existing additive ``envelope.join`` algebra).
        """

        lease_id = getattr(envelope, "lease_id", None)
        fencing_token = getattr(envelope, "fencing_token", None)
        grant = float(getattr(envelope, "capacity_grant", 0.0) or 0.0)

        with self._lock:
            if self._shard_poisoned:
                self._shard_poisoned = False
                raise BudgetExceeded(
                    ExceedReason.DOLLAR_CAP,
                    "stale fencing token poisoned the shard accumulator",
                )
            if lease_id is None or fencing_token is None:
                return
            seen = self._shard_seen.setdefault(lease_id, set())
            if fencing_token in seen:
                return
            cur_max = self._shard_max_token.get(lease_id, -1)
            if fencing_token < cur_max:
                self._shard_poisoned = True
                return
            seen.add(fencing_token)
            self._shard_max_token[lease_id] = fencing_token
            self._shard_grants += grant

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
