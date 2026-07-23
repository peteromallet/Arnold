"""Freshness/lag policy per execution, liveness, custody, and integrity dimension.

Stale evidence can deny or diagnose; it cannot become authority.  This module
codifies the freshness policy for every read dimension that projections and
consumers depend on.  Every freshness value is either a concrete SLO (with
typed stale/unknown states for violations) or an explicit ``UNKNOWN`` sentinel
— never an optimistic default.

Design rules
------------
* Every dimension has a configurable ``freshness_window_ms`` and a fallback
  ``stale_after_ms`` that defines when the dimension is considered stale.
* Unresolved or absent values are surfaced as typed ``UNKNOWN``, not silently
  defaulted to "fresh" or "OK".
* Freshness is a blocking/diagnostic dimension, NOT an authorization input.
  A stale projection may deny, block, or diagnose — it may never authorize.
* The policy is consumed by the source-cursor contract (``source_cursor_contract.py``)
  and every projection builder.

Covered dimensions
------------------
- execution          — plan/chain lifecycle state freshness
- runner_liveness    — watchdog runner liveness (process/tmux/heartbeat)
- custody            — custody lease records
- repair             — repair-progress sidecar freshness
- publication        — Discord/notification delivery freshness
- delivery           — artifact delivery freshness
- integrity          — content-hash integrity verification staleness
- wbc                — WBC attempt ledger freshness
- run_authority      — Run Authority grant/fence freshness
- work_ledger        — work-ledger event freshness
- process_correlation — process/tmux/heartbeat correlation freshness
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Literal, Mapping, Optional, Tuple

# ── Freshness status literals ─────────────────────────────────────────────


class FreshnessStatus(Enum):
    """Typed freshness status for a single dimension.

    These map directly onto the source-cursor ``SourceCursorState``:
    * FRESH = "fresh"
    * STALE = "stale"
    * UNKNOWN = "unknown"
    * INCOHERENT = "incoherent"
    """

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    INCOHERENT = "incoherent"


FreshnessState = Literal["fresh", "stale", "unknown", "incoherent"]


# ── Covered freshness dimensions ──────────────────────────────────────────


FreshnessDimension = Literal[
    "execution",
    "runner_liveness",
    "custody",
    "repair",
    "publication",
    "delivery",
    "integrity",
    "wbc",
    "run_authority",
    "work_ledger",
    "process_correlation",
]

ALL_FRESHNESS_DIMENSIONS: FrozenSet[FreshnessDimension] = frozenset(
    {
        "execution",
        "runner_liveness",
        "custody",
        "repair",
        "publication",
        "delivery",
        "integrity",
        "wbc",
        "run_authority",
        "work_ledger",
        "process_correlation",
    }
)

_SORTED_FRESHNESS_DIMENSIONS: Tuple[FreshnessDimension, ...] = (
    "execution",
    "runner_liveness",
    "custody",
    "repair",
    "publication",
    "delivery",
    "integrity",
    "wbc",
    "run_authority",
    "work_ledger",
    "process_correlation",
)


# ── Per-dimension freshness SLO ───────────────────────────────────────────


@dataclass(frozen=True)
class FreshnessSLO:
    """Freshness service-level objective for one dimension.

    Defines the acceptable staleness window for a single dimension.  When
    the window is exceeded or the dimension cannot be read, the status
    degrades to ``stale`` or ``unknown`` — never silently to ``fresh``.
    """

    dimension: FreshnessDimension
    """Which freshness dimension this SLO covers."""

    freshness_window_ms: Optional[int]
    """Maximum age in milliseconds before this entry becomes stale.

    None means no configured window — freshness is always UNKNOWN unless
    explicitly determined by a caller.
    """

    stale_after_ms: Optional[int] = None
    """Hard staleness threshold in milliseconds.

    When the observed age exceeds this value, the dimension is ``stale``
    even if it was read within the freshness window (e.g. the source record
    is known to be outdated).  None means no hard threshold.
    """

    is_blocking: bool = False
    """True when staleness blocks downstream action (deny, not authorize)."""

    is_diagnostic_only: bool = True
    """True when staleness is surfaced for diagnostics only.

    Most freshness dimensions are diagnostic.  Only dimensions whose
    staleness would allow a dangerous action to proceed should set this
    to False.
    """

    detail: str = ""
    """Human-readable detail explaining the SLO rationale."""

    @property
    def status(self) -> FreshnessStatus:
        """The freshness status implied by this SLO (always UNKNOWN until evaluated)."""
        return FreshnessStatus.UNKNOWN

    def evaluate(self, observed_at_epoch_ms: Optional[float], *, now_epoch_ms: Optional[float] = None) -> FreshnessStatus:
        """Evaluate freshness given an observation timestamp.

        Args:
            observed_at_epoch_ms: Epoch milliseconds when the dimension was read.
                None means the dimension could not be read at all.
            now_epoch_ms: Current time for comparison (defaults to time.time()*1000).

        Returns:
            ``FRESH`` when within the window, ``STALE`` when outside,
            ``UNKNOWN`` when the observation is absent.
        """
        if observed_at_epoch_ms is None:
            return FreshnessStatus.UNKNOWN

        now = now_epoch_ms if now_epoch_ms is not None else time.time() * 1000
        age_ms = now - observed_at_epoch_ms

        # Hard staleness threshold wins
        if self.stale_after_ms is not None and age_ms > self.stale_after_ms:
            return FreshnessStatus.STALE

        # Freshness window
        if self.freshness_window_ms is not None and age_ms <= self.freshness_window_ms:
            return FreshnessStatus.FRESH

        # Within stale_after but outside freshness_window → stale
        if self.freshness_window_ms is not None:
            return FreshnessStatus.STALE

        # No window configured → UNKNOWN
        return FreshnessStatus.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "freshness_window_ms": self.freshness_window_ms,
            "stale_after_ms": self.stale_after_ms,
            "is_blocking": self.is_blocking,
            "is_diagnostic_only": self.is_diagnostic_only,
            "detail": self.detail,
        }


# ── Default freshness SLOs (conservative — deny by default) ──────────────


def _slo(
    dimension: FreshnessDimension,
    *,
    freshness_window_ms: Optional[int],
    stale_after_ms: Optional[int] = None,
    is_blocking: bool = False,
    detail: str = "",
) -> FreshnessSLO:
    return FreshnessSLO(
        dimension=dimension,
        freshness_window_ms=freshness_window_ms,
        stale_after_ms=stale_after_ms,
        is_blocking=is_blocking,
        detail=detail,
    )


DEFAULT_FRESHNESS_SLOS: Tuple[FreshnessSLO, ...] = (
    # ── Execution: plan/chain lifecycle state ──
    _slo(
        "execution",
        freshness_window_ms=60_000,  # 60 seconds
        stale_after_ms=300_000,  # 5 minutes hard staleness
        detail="Plan/chain lifecycle state should be read within 60s; "
        "beyond 5 min it is definitively stale.",
    ),
    # ── Runner liveness: watchdog process/tmux/heartbeat ──
    _slo(
        "runner_liveness",
        freshness_window_ms=30_000,  # 30 seconds
        stale_after_ms=120_000,  # 2 minutes hard staleness
        is_blocking=True,  # stale liveness blocks repair dispatch
        detail="Runner liveness must be fresh within 30s to authorize repair. "
        "Stale liveness blocks positive action.",
    ),
    # ── Custody: lease records ──
    _slo(
        "custody",
        freshness_window_ms=30_000,  # 30 seconds
        stale_after_ms=120_000,  # 2 minutes hard staleness
        is_blocking=True,
        detail="Custody leases must be fresh within 30s. Stale custody blocks "
        "all mutation actions.",
    ),
    # ── Repair: repair-progress sidecar ──
    _slo(
        "repair",
        freshness_window_ms=120_000,  # 2 minutes
        stale_after_ms=600_000,  # 10 minutes hard staleness
        detail="Repair progress sidecars are advisory; staleness does not block "
        "but is surfaced diagnostically.",
    ),
    # ── Publication: Discord/notification delivery ──
    _slo(
        "publication",
        freshness_window_ms=300_000,  # 5 minutes
        detail="Publication delivery status is best-effort; staleness is diagnostic only.",
    ),
    # ── Delivery: artifact delivery ──
    _slo(
        "delivery",
        freshness_window_ms=300_000,  # 5 minutes
        detail="Artifact delivery status is best-effort; staleness is diagnostic only.",
    ),
    # ── Integrity: content-hash verification ──
    _slo(
        "integrity",
        freshness_window_ms=None,  # no window — event-driven
        detail="Integrity verification is event-driven; no periodic freshness window. "
        "Absent verification is UNKNOWN, never assumed fresh.",
    ),
    # ── WBC: attempt ledger ──
    _slo(
        "wbc",
        freshness_window_ms=30_000,  # 30 seconds
        stale_after_ms=120_000,  # 2 minutes hard staleness
        is_blocking=True,
        detail="WBC attempt ledger must be fresh within 30s for custody decisions.",
    ),
    # ── Run Authority: grant/fence ──
    _slo(
        "run_authority",
        freshness_window_ms=30_000,  # 30 seconds
        stale_after_ms=120_000,  # 2 minutes hard staleness
        is_blocking=True,
        detail="Run Authority grants/fences must be fresh within 30s. "
        "Stale authority blocks dispatch.",
    ),
    # ── Work ledger: event append ──
    _slo(
        "work_ledger",
        freshness_window_ms=120_000,  # 2 minutes
        stale_after_ms=600_000,  # 10 minutes hard staleness
        detail="Work-ledger event freshness is diagnostic; staleness does not block.",
    ),
    # ── Process correlation: process/tmux/heartbeat ──
    _slo(
        "process_correlation",
        freshness_window_ms=30_000,  # 30 seconds
        stale_after_ms=120_000,  # 2 minutes hard staleness
        is_blocking=True,
        detail="Process correlation identity must be fresh within 30s. "
        "Stale identity produces unknown liveness, blocking repair.",
    ),
)

# ── SLO lookup ────────────────────────────────────────────────────────────

_SLO_BY_DIMENSION: Dict[FreshnessDimension, FreshnessSLO] = {
    slo.dimension: slo for slo in DEFAULT_FRESHNESS_SLOS
}


def get_freshness_slo(dimension: FreshnessDimension) -> FreshnessSLO:
    """Return the default freshness SLO for a dimension.

    Returns a conservative SLO with ``freshness_window_ms=None`` (→ UNKNOWN)
    for unrecognized dimensions.
    """
    return _SLO_BY_DIMENSION.get(
        dimension,
        FreshnessSLO(
            dimension=dimension,
            freshness_window_ms=None,
            detail=f"No SLO configured for {dimension}; defaults to UNKNOWN.",
        ),
    )


# ── Freshness evaluation context ─────────────────────────────────────────


@dataclass(frozen=True)
class FreshnessEvaluation:
    """Result of evaluating freshness for a single dimension at a point in time."""

    dimension: FreshnessDimension
    slo: FreshnessSLO
    status: FreshnessStatus
    observed_at_epoch_ms: Optional[float]
    age_ms: Optional[float]
    detail: str = ""

    @property
    def is_fresh(self) -> bool:
        return self.status == FreshnessStatus.FRESH

    @property
    def is_stale(self) -> bool:
        return self.status == FreshnessStatus.STALE

    @property
    def is_unknown(self) -> bool:
        return self.status == FreshnessStatus.UNKNOWN

    @property
    def is_blocking(self) -> bool:
        """True when staleness blocks action (deny, not authorize)."""
        return self.slo.is_blocking and not self.is_fresh

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "status": self.status.value,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "age_ms": self.age_ms,
            "is_blocking": self.is_blocking,
            "detail": self.detail or self.slo.detail,
        }

    @classmethod
    def evaluate(
        cls,
        dimension: FreshnessDimension,
        *,
        observed_at_epoch_ms: Optional[float] = None,
        now_epoch_ms: Optional[float] = None,
        slo: Optional[FreshnessSLO] = None,
    ) -> "FreshnessEvaluation":
        """Evaluate freshness for a dimension at a point in time."""
        _slo = slo if slo is not None else get_freshness_slo(dimension)
        now = now_epoch_ms if now_epoch_ms is not None else time.time() * 1000
        age_ms = (now - observed_at_epoch_ms) if observed_at_epoch_ms is not None else None
        status = _slo.evaluate(observed_at_epoch_ms, now_epoch_ms=now)

        detail_parts = []
        if status == FreshnessStatus.UNKNOWN:
            detail_parts.append("observation unavailable; dimension defaults to UNKNOWN")
        elif status == FreshnessStatus.STALE:
            if age_ms is not None:
                detail_parts.append(f"age {age_ms:.0f}ms exceeds window")
        elif status == FreshnessStatus.FRESH:
            if age_ms is not None:
                detail_parts.append(f"age {age_ms:.0f}ms within window")

        return cls(
            dimension=dimension,
            slo=_slo,
            status=status,
            observed_at_epoch_ms=observed_at_epoch_ms,
            age_ms=age_ms,
            detail="; ".join(detail_parts) if detail_parts else "",
        )


# ── Aggregate freshness across all dimensions ────────────────────────────


@dataclass(frozen=True)
class AggregateFreshness:
    """Aggregate freshness evaluation across all covered dimensions.

    Consumers use this to decide whether to block, diagnose, or proceed.
    The aggregate is explicitly non-authoritative.
    """

    evaluations: Tuple[FreshnessEvaluation, ...]
    """One evaluation per covered dimension, in deterministic order."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_evals = tuple(
            sorted(self.evaluations, key=lambda e: _SORTED_FRESHNESS_DIMENSIONS.index(e.dimension))
        )
        object.__setattr__(self, "evaluations", sorted_evals)
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def blocking_dimensions(self) -> Tuple[FreshnessDimension, ...]:
        """Dimensions whose staleness blocks action."""
        return tuple(
            e.dimension for e in self.evaluations if e.is_blocking
        )

    @property
    def stale_dimensions(self) -> Tuple[FreshnessDimension, ...]:
        """Dimensions that are stale or worse."""
        return tuple(
            e.dimension for e in self.evaluations if not e.is_fresh
        )

    @property
    def has_blocking_staleness(self) -> bool:
        """True when any blocking dimension is stale/unknown/incoherent."""
        return any(e.is_blocking for e in self.evaluations)

    @property
    def all_fresh(self) -> bool:
        """True when every dimension is fresh."""
        return all(e.is_fresh for e in self.evaluations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluations": [e.to_dict() for e in self.evaluations],
            "blocking_dimensions": list(self.blocking_dimensions),
            "stale_dimensions": list(self.stale_dimensions),
            "has_blocking_staleness": self.has_blocking_staleness,
            "all_fresh": self.all_fresh,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def evaluate_all(
        cls,
        *,
        observed: Optional[Mapping[FreshnessDimension, Optional[float]]] = None,
        now_epoch_ms: Optional[float] = None,
    ) -> "AggregateFreshness":
        """Evaluate freshness for every dimension.

        Args:
            observed: Mapping from dimension to observation epoch ms.
                Dimensions not in the mapping are evaluated as UNKNOWN.
            now_epoch_ms: Current time for comparison.
        """
        obs = observed or {}
        evaluations = tuple(
            FreshnessEvaluation.evaluate(
                dim,
                observed_at_epoch_ms=obs.get(dim),
                now_epoch_ms=now_epoch_ms,
            )
            for dim in _SORTED_FRESHNESS_DIMENSIONS
        )
        return cls(evaluations=evaluations)


# ── Convenience: build evaluation from source-cursor vector ──────────────


def freshness_from_cursor(
    dimension: FreshnessDimension,
    cursor_state: str,
    *,
    observed_at_epoch_ms: Optional[float] = None,
) -> FreshnessEvaluation:
    """Map a source-cursor cursor state to a freshness evaluation.

    This bridges the source-cursor contract with the freshness policy
    by interpreting ``fresh``/``stale``/``unknown``/``incoherent`` states
    as freshness evaluations.
    """
    state_map: Dict[str, FreshnessStatus] = {
        "fresh": FreshnessStatus.FRESH,
        "stale": FreshnessStatus.STALE,
        "unknown": FreshnessStatus.UNKNOWN,
        "incoherent": FreshnessStatus.INCOHERENT,
    }
    status = state_map.get(cursor_state, FreshnessStatus.UNKNOWN)
    slo = get_freshness_slo(dimension)

    now = time.time() * 1000
    age_ms = (now - observed_at_epoch_ms) if observed_at_epoch_ms is not None else None

    return FreshnessEvaluation(
        dimension=dimension,
        slo=slo,
        status=status,
        observed_at_epoch_ms=observed_at_epoch_ms,
        age_ms=age_ms,
        detail=f"cursor state={cursor_state}",
    )


__all__ = [
    # ── Types ──
    "FreshnessStatus",
    "FreshnessState",
    "FreshnessDimension",
    "ALL_FRESHNESS_DIMENSIONS",
    # ── SLO ──
    "FreshnessSLO",
    "DEFAULT_FRESHNESS_SLOS",
    "get_freshness_slo",
    # ── Evaluation ──
    "FreshnessEvaluation",
    "AggregateFreshness",
    # ── Bridge ──
    "freshness_from_cursor",
]
