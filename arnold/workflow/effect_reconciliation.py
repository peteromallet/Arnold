"""Step 10A: provider reconciliation capabilities.

Defines explicit provider reconciliation query results and capability
declarations that gate cross-attempt retry (Step 10B).

Key concepts:

* ``ReconciliationResult`` — a tri-state outcome of querying a provider
  to determine whether an effect was previously applied:
  ``APPLIED``, ``NOT_APPLIED``, or ``UNKNOWN``. Only ``APPLIED`` and
  ``NOT_APPLIED`` are authoritative; ``UNKNOWN`` keeps the effect
  terminally indeterminate.

* ``ProviderCapability`` — declarative capability set for a provider
  adapter. ``supports_query`` and ``supports_idempotency_key`` must be
  ``True`` for a ``NOT_APPLIED`` result to authorize a re-dispatch.
  ``mixed_version_safe`` indicates whether the provider can
  distinguish a stale-version result from a current one.

Production effects remain **action-off** throughout M10 (SD3). These
types exist so that the effect protocol (Step 8C) and retry gate
(Step 10B) can route reconciliation evidence into typed decisions.
They do NOT enable production dispatch — the durable fakes in
``tests/support/fake_effect_provider.py`` are the only consumers in
M10.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


# ── Reconciliation result tri-state ─────────────────────────────────────────


class ReconciliationVerdict(str, Enum):
    """Authoritative tri-state verdict from a provider query."""

    APPLIED = "applied"
    """The effect was definitively applied by this provider. Safe to
    accept as terminal without re-dispatch."""

    NOT_APPLIED = "not_applied"
    """The effect was definitively NOT applied. With a matching
    idempotency key, this authorizes a fenced re-dispatch."""

    UNKNOWN = "unknown"
    """The provider cannot determine whether the effect was applied.
    Keeps the effect terminally indeterminate — never authorize
    re-dispatch on this."""


# ── Query errors ────────────────────────────────────────────────────────────


class ReconciliationError(Exception):
    """Base error for provider reconciliation failures."""


class QueryCapabilityError(ReconciliationError):
    """Raised when a provider does not support reconciliation queries."""


class QueryFailureError(ReconciliationError):
    """Raised when a provider query fails (network, timeout, etc).

    A query failure is treated identically to ``UNKNOWN`` — the effect
    stays indeterminate. This error exists so callers can distinguish
    a clean ``UNKNOWN`` verdict from a failed query for escalation."""


class ContradictoryEvidenceError(ReconciliationError):
    """Raised when a provider returns contradictory evidence across
    repeated queries (e.g. APPLIED then NOT_APPLIED for the same
    idempotency key). Contradictions are quarantined and escalated."""


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReconciliationResult:
    """Result of a provider reconciliation query (Step 10A item 1).

    Carries the authoritative verdict plus the evidence payload used to
    derive it. The ``is_authoritative`` flag is ``True`` only for
    ``APPLIED`` and ``NOT_APPLIED``; ``UNKNOWN`` is never authoritative.

    ``query_failure`` is ``True`` when the query itself failed (the
    provider was unreachable or returned an error). A query failure is
    NOT authoritative and is routed to indeterminate escalation.
    """

    verdict: ReconciliationVerdict
    provider_idempotency_key: Optional[str] = None
    """The idempotency key the provider used (or would use) for this
    effect. When present and the verdict is ``NOT_APPLIED``, a
    re-dispatch with the same key is safe."""

    evidence_payload: dict[str, Any] = field(default_factory=dict)
    """Provider-specific evidence (e.g., transaction ID, audit record)."""

    query_failure: bool = False
    is_authoritative: bool = True
    provider_version: Optional[str] = None
    """Version of the provider that answered. Used for mixed-version
    ambiguity detection."""

    def __post_init__(self) -> None:
        # UNKNOWN is never authoritative.
        if self.verdict == ReconciliationVerdict.UNKNOWN:
            object.__setattr__(self, "is_authoritative", False)
        # Query failures are never authoritative.
        if self.query_failure:
            object.__setattr__(self, "is_authoritative", False)

    @property
    def is_applied(self) -> bool:
        """True when the provider confirms the effect was applied."""
        return self.verdict == ReconciliationVerdict.APPLIED

    @property
    def is_not_applied(self) -> bool:
        """True when the provider confirms the effect was NOT applied."""
        return self.verdict == ReconciliationVerdict.NOT_APPLIED

    @property
    def is_unknown(self) -> bool:
        """True when the verdict is indeterminate."""
        return self.verdict == ReconciliationVerdict.UNKNOWN


# ── Provider capability declarations ────────────────────────────────────────


@dataclass(frozen=True)
class ProviderCapability:
    """Declarative capability set for a provider adapter (Step 10A item 2).

    The retry gate (Step 10B) inspects these flags:

    * ``supports_query`` — whether the provider can answer reconciliation
      queries. If ``False``, a lost ACK stays indeterminate forever.
    * ``supports_idempotency_key`` — whether the provider deduplicates
      by a client-supplied idempotency key. Required for a safe
      re-dispatch after ``NOT_APPLIED``.
    * ``mixed_version_safe`` — whether the provider can distinguish a
      stale-version query result from a current one. If ``False``, a
      version mismatch must be treated as ``UNKNOWN``.

    ``production_enabled`` is always ``False`` in M10 (SD3). It exists so
    the gate can statically verify that no production path is live.
    """

    provider_id: str
    supports_query: bool = False
    supports_idempotency_key: bool = False
    mixed_version_safe: bool = False
    production_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.provider_id or not self.provider_id.strip():
            raise ValueError("ProviderCapability.provider_id must be non-empty")

    @property
    def can_authorize_redispatch(self) -> bool:
        """True only when the provider supports both query AND idempotency.

        A ``NOT_APPLIED`` verdict from a provider without idempotency key
        support cannot safely authorize a re-dispatch — the second
        dispatch may duplicate the first.
        """
        return self.supports_query and self.supports_idempotency_key

    def assert_query_supported(self) -> None:
        """Raise :class:`QueryCapabilityError` if queries are unsupported."""
        if not self.supports_query:
            raise QueryCapabilityError(
                f"Provider {self.provider_id!r} does not support "
                f"reconciliation queries"
            )


# ── Known provider registry (M10: all action-off) ──────────────────────────

#: Capability registry for known provider adapters.
#: In M10, NO production provider is enabled (SD3). The durable fake
#: provider is the only one with query + idempotency support for
#: testing the retry gate.
KNOWN_PROVIDER_CAPABILITIES: dict[str, ProviderCapability] = {
    "fake-effect-provider": ProviderCapability(
        provider_id="fake-effect-provider",
        supports_query=True,
        supports_idempotency_key=True,
        mixed_version_safe=True,
        production_enabled=False,
    ),
    "unknown-provider": ProviderCapability(
        provider_id="unknown-provider",
        supports_query=False,
        supports_idempotency_key=False,
        mixed_version_safe=False,
        production_enabled=False,
    ),
}


def get_provider_capability(provider_id: str) -> ProviderCapability:
    """Return the capability set for *provider_id*.

    Falls back to a fail-closed ``unknown-provider`` capability for
    providers not in the registry — no query, no idempotency.
    """
    return KNOWN_PROVIDER_CAPABILITIES.get(
        provider_id,
        KNOWN_PROVIDER_CAPABILITIES["unknown-provider"],
    )


def is_production_enabled(provider_id: str) -> bool:
    """Return ``True`` if production dispatch is enabled for *provider_id*.

    Always ``False`` in M10. This function exists so the effect protocol
    can statically assert that no production path is live.
    """
    return get_provider_capability(provider_id).production_enabled
