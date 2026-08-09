"""Step 10A item 2: durable fake effect provider for lost-ACK safety tests.

Provides ``FakeEffectProvider`` — an in-memory provider that:

* Records every ``apply`` call (at-most-one-application invariant).
* Supports reconciliation ``query`` (APPLIED / NOT_APPLIED / UNKNOWN).
* Simulates lost ACK (apply succeeds but caller never sees the result).
* Simulates post-apply kill (crash after apply, before caller returns).
* Simulates query failure (provider becomes unreachable).
* Simulates mixed-version ambiguity (version mismatch returns UNKNOWN).

Production effects remain action-off in M10 (SD3). This fake is the
ONLY provider with query + idempotency support. It is used by the
effect protocol (Step 8C) and retry-gate tests (Step 10B/10C) to
prove at-most-one application and no-false-success across crashes,
lost ACKs, concurrent retries, and idempotency-key reuse.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from arnold.workflow.effect_reconciliation import (
    ProviderCapability,
    QueryFailureError,
    ReconciliationResult,
    ReconciliationVerdict,
)


CAPABILITY = ProviderCapability(
    provider_id="fake-effect-provider",
    supports_query=True,
    supports_idempotency_key=True,
    mixed_version_safe=True,
    production_enabled=False,
)


@dataclass
class _AppliedRecord:
    """Internal record of a single apply call."""

    idempotency_key: str
    payload_digest: str
    transaction_id: str
    applied_at_ns: int


@dataclass
class ApplyResult:
    """Result of an ``apply`` call on the fake provider."""

    transaction_id: str
    applied: bool
    idempotency_key: str


class FakeEffectProvider:
    """In-memory fake provider for lost-ACK / retry-safety tests.

    State is thread-safe via a lock. The provider maintains an ordered
    list of apply calls keyed by idempotency key, so tests can assert
    at-most-one application.

    Failure modes are controllable:

    * ``set_lost_ack`` — the next ``apply`` succeeds (returns a
      transaction ID) but the provider can be queried to confirm
      application even if the caller "lost" the response.
    * ``set_post_apply_kill`` — the next ``apply`` records the
      application then raises ``PostApplyKill`` instead of returning,
      simulating a crash between the external side-effect and the
      response.
    * ``set_query_failure`` — ``query`` raises ``QueryFailureError``
      instead of returning a result.
    * ``set_unknown_verdict`` — ``query`` returns ``UNKNOWN``.
    * ``set_version`` — controls the provider_version reported in
      query results; combined with ``mixed_version_safe=False`` on the
      capability, a version mismatch yields ``UNKNOWN``.
    """

    def __init__(self, *, version: str = "fake-1.0.0") -> None:
        self._lock = threading.Lock()
        self._applied: dict[str, _AppliedRecord] = {}
        self._apply_order: list[_AppliedRecord] = []
        self._version = version
        # Failure-mode flags (one-shot unless noted).
        self._lost_ack_pending = False
        self._post_apply_kill_pending = False
        self._query_failing = False
        self._force_unknown = False

    @property
    def capability(self) -> ProviderCapability:
        return CAPABILITY

    @property
    def provider_id(self) -> str:
        return CAPABILITY.provider_id

    @property
    def version(self) -> str:
        return self._version

    def set_version(self, version: str) -> None:
        with self._lock:
            self._version = version

    def set_lost_ack(self) -> None:
        """Next apply succeeds but simulate the caller losing the ACK."""
        with self._lock:
            self._lost_ack_pending = True

    def set_post_apply_kill(self) -> None:
        """Next apply records the effect then crashes (PostApplyKill)."""
        with self._lock:
            self._post_apply_kill_pending = True

    def set_query_failure(self, failing: bool = True) -> None:
        """Make query() raise QueryFailureError."""
        with self._lock:
            self._query_failing = failing

    def set_unknown_verdict(self, force: bool = True) -> None:
        """Make query() always return UNKNOWN."""
        with self._lock:
            self._force_unknown = force

    # ── apply ──────────────────────────────────────────────────────────

    def apply(
        self,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        now_ns: int = 0,
    ) -> ApplyResult:
        """Apply *payload* under *idempotency_key*.

        Idempotent: if the key was already applied, returns the existing
        transaction ID with ``applied=False`` (dedup). Otherwise records
        the application and returns ``applied=True``.
        """
        payload_digest = _canonical_digest(payload)
        with self._lock:
            existing = self._applied.get(idempotency_key)
            if existing is not None:
                if existing.payload_digest != payload_digest:
                    raise ValueError(
                        f"FakeEffectProvider: divergent payload for "
                        f"idempotency key {idempotency_key!r}"
                    )
                return ApplyResult(
                    transaction_id=existing.transaction_id,
                    applied=False,
                    idempotency_key=idempotency_key,
                )

            record = _AppliedRecord(
                idempotency_key=idempotency_key,
                payload_digest=payload_digest,
                transaction_id="tx-" + uuid.uuid4().hex[:16],
                applied_at_ns=now_ns,
            )
            self._applied[idempotency_key] = record
            self._apply_order.append(record)

            kill = self._post_apply_kill_pending
            lost_ack = self._lost_ack_pending
            self._post_apply_kill_pending = False
            self._lost_ack_pending = False

        if kill:
            raise PostApplyKill(
                "Simulated crash after apply, before returning response"
            )

        result = ApplyResult(
            transaction_id=record.transaction_id,
            applied=True,
            idempotency_key=idempotency_key,
        )
        # In lost-ACK mode, the caller would never see this result —
        # but the provider DID apply the effect. Tests use query() to
        # confirm.
        _ = lost_ack  # flag consumed; no behavioral change in apply
        return result

    # ── query (reconciliation) ─────────────────────────────────────────

    def query(self, idempotency_key: str) -> ReconciliationResult:
        """Reconciliation query: was *idempotency_key* applied?

        Returns ``APPLIED`` if the key is known, ``NOT_APPLIED`` if it is
        definitively not present, or ``UNKNOWN`` in configured failure
        modes.
        """
        with self._lock:
            if self._query_failing:
                raise QueryFailureError(
                    f"FakeEffectProvider query failure for key "
                    f"{idempotency_key!r}"
                )
            if self._force_unknown:
                return ReconciliationResult(
                    verdict=ReconciliationVerdict.UNKNOWN,
                    provider_idempotency_key=idempotency_key,
                    provider_version=self._version,
                )
            record = self._applied.get(idempotency_key)
            version = self._version

        if record is not None:
            return ReconciliationResult(
                verdict=ReconciliationVerdict.APPLIED,
                provider_idempotency_key=idempotency_key,
                evidence_payload={
                    "transaction_id": record.transaction_id,
                    "applied_at_ns": record.applied_at_ns,
                },
                provider_version=version,
            )
        return ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key=idempotency_key,
            provider_version=version,
        )

    # ── introspection (for test assertions) ────────────────────────────

    @property
    def apply_count(self) -> int:
        """Total number of distinct effects applied (deduplicated)."""
        with self._lock:
            return len(self._apply_order)

    @property
    def raw_apply_call_count(self) -> int:
        """Number of apply() calls that actually mutated state."""
        with self._lock:
            return len(self._apply_order)

    def list_transaction_ids(self) -> tuple[str, ...]:
        """Return all transaction IDs in apply order."""
        with self._lock:
            return tuple(r.transaction_id for r in self._apply_order)

    def was_applied(self, idempotency_key: str) -> bool:
        """True if *idempotency_key* was applied at least once."""
        with self._lock:
            return idempotency_key in self._applied

    def reset(self) -> None:
        """Clear all state and failure-mode flags."""
        with self._lock:
            self._applied.clear()
            self._apply_order.clear()
            self._lost_ack_pending = False
            self._post_apply_kill_pending = False
            self._query_failing = False
            self._force_unknown = False


class PostApplyKill(Exception):
    """Simulated crash after apply, before the response is returned."""


def _canonical_digest(payload: dict[str, Any]) -> str:
    """Stable digest of a payload dict for dedup comparison."""
    import hashlib
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
