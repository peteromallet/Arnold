"""Neutral recovery-classifier seam for Arnold batch execution.

Provides frozen carriers for recovery context and decision, a Protocol that
any recovery policy must satisfy, and a null implementation that reports
``unsupported`` / ``unset`` rather than silently falling back to Megaplan
defaults.

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

__all__ = [
    "RECOVERY_STATUS_VALUES",
    "RecoveryContext",
    "RecoveryDecision",
    "ArnoldRecoveryPolicy",
    "NullRecoveryPolicy",
]

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

RECOVERY_STATUS_VALUES: frozenset[str] = frozenset(
    {"decided", "unsupported", "unset"}
)
"""Prescribed ``status`` values for :class:`RecoveryDecision`.

``"decided"``       — a plugin-owned policy rendered a decision.
``"unsupported"``   — the runtime cannot render a decision (e.g. heartbeat,
                      idle-timeout are unsupported mechanics in M3d).
``"unset"``         — no recovery policy was registered; the caller should
                      treat this as a neutral no-op.
"""


# ---------------------------------------------------------------------------
# Data carriers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecoveryContext:
    """Neutral context passed to :meth:`ArnoldRecoveryPolicy.classify`.

    ``error`` is the exception (or string description) that triggered
    the recovery query.  ``unit`` is the :class:`~arnold.runtime.batch.BatchUnit`
    that was being processed.  ``metadata`` carries opaque,
    plugin-owned annotations (e.g. retry budget, phase label, gate name)
    — Arnold never interprets them.
    """

    error: BaseException | str
    unit: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryDecision:
    """Neutral decision returned by :meth:`ArnoldRecoveryPolicy.classify`.

    ``status`` must be a member of :data:`RECOVERY_STATUS_VALUES`.
    ``action`` is an opaque, plugin-owned action label (retry, abort,
    escalate, …) — Arnold never interprets it.  ``reason`` is a
    human-readable explanation for observability.  ``budget_consumed``
    is informational resource accounting.
    """

    status: str = "unset"
    action: str = ""
    reason: str = ""
    budget_consumed: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Policy Protocol
# ---------------------------------------------------------------------------


class ArnoldRecoveryPolicy(Protocol):
    """Protocol for a recovery-policy plugin.

    Implementations receive an error and the surrounding
    :class:`RecoveryContext` and must return a :class:`RecoveryDecision`.
    The protocol is deliberately minimal — all decision vocabulary
    (retry, abort, escalate, …) is opaque to Arnold.
    """

    def classify(
        self, error: BaseException | str, context: RecoveryContext
    ) -> RecoveryDecision:  # pragma: no cover
        ...


# ---------------------------------------------------------------------------
# Null implementation
# ---------------------------------------------------------------------------


class NullRecoveryPolicy:
    """Recovery policy that always reports ``unset``.

    Used when no plugin recovery policy is registered.  This prevents
    silent fallback to Megaplan defaults — the caller gets an explicit
    signal that no policy is active.
    """

    def classify(
        self, error: BaseException | str, context: RecoveryContext
    ) -> RecoveryDecision:
        """Return ``unset`` for every input — no policy registered."""
        return RecoveryDecision(
            status="unset",
            action="",
            reason="No recovery policy registered (NullRecoveryPolicy)",
            budget_consumed={},
        )
