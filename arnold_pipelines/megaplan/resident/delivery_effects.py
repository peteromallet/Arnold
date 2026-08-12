"""Steps 13G1-13G2: Resident delivery effects adapter.

Step 13G1: Create the adapter over the WBC protocol with stable
parent/target/channel global-effect keys and durable
reserve/start/intent/global-reservation contracts.

Step 13G2: Route outbound seams in ``discord_dm.py`` and
``agentbox_adapter.py`` through the delivery effects adapter.

The adapter introduces no new ledger — it wraps the single durable
:class:`EffectProtocol`.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from arnold.workflow.effect_protocol import (
    EffectProtocol,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_INDETERMINATE,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptIdentity,
    AttemptProvenance,
    GlobalEffectIdentity,
    GrantRef,
    RuntimeAdapter,
    VersionSet,
)

from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryType,
    GateResult,
    adapter_effect_authorized,
)

LOGGER = logging.getLogger(__name__)


# ── Delivery channel ─────────────────────────────────────────────────────────


class DeliveryChannel(str, Enum):
    """Named delivery channels covered by the resident delivery adapter."""

    DISCORD_DM = "discord_dm"
    """Direct message delivery through Discord bot API."""

    AGENTBOX = "agentbox"
    """AgentBox completion notification delivery."""

    RESIDENT = "resident"
    """Generic resident-agent delivery channel."""


# ── Delivery target identity ─────────────────────────────────────────────────


@dataclass(frozen=True)
class DeliveryTarget:
    """Stable identity for a delivery effect target.

    Uses stable parent/target/channel keys for global-effect identity.
    """

    channel: DeliveryChannel
    parent_id: str
    """Stable parent resource id (e.g. user_id, operation_id)."""

    target_id: str
    """Stable target resource id (e.g. channel_id, session_id)."""

    action: str = "send"
    """Delivery action: send, notify, alert, etc."""

    @property
    def target_key(self) -> str:
        return (
            f"delivery:{self.channel.value}:{self.parent_id}:"
            f"{self.target_id}:{self.action}"
        )


# ── Delivery outcome ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeliveryOutcome:
    """Result of a delivery dispatch through the adapter."""

    ok: bool
    channel: str
    action: str
    glek: str
    outcome_kind: str
    error: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    attempt_id: str = ""


# ── Resident delivery effects adapter ────────────────────────────────────────


class ResidentDeliveryGateError(RuntimeError):
    """Raised when a production delivery effects owner is opened without a gate.

    Production construction (``DeliveryEffects(production_enabled=True)`` or
    :func:`open_resident_delivery_effects`) without an explicit
    ``action_gate_check`` is a wiring error, not a runtime denial: the
    constructor raises before any dispatch, and the factory raises before
    creating the state directory, SQLite ledger, or protocol so a missing gate
    can never partially initialize durable state.
    """


class DeliveryEffects:
    """Resident delivery adapter over the WBC protocol.

    Step 13G1: thin adapter with stable parent/target/channel GLEKs.
    Step 13G2: routes discord_dm and agentbox_adapter outbound seams.

    ``apply_fn`` is the single provider callback.  Once this adapter is
    selected, denial or ambiguity fails closed and cannot fall through to a
    competing direct-provider path.
    """

    def __init__(
        self,
        protocol: EffectProtocol,
        *,
        action_gate_check: Optional[
            Callable[[ActionBoundaryType, str], GateResult]
        ] = None,
        production_enabled: bool = False,
    ) -> None:
        if production_enabled and action_gate_check is None:
            raise ResidentDeliveryGateError(
                "DeliveryEffects refuses production construction without an "
                "explicit action_gate_check; pass current_delivery_gate_check "
                "(or an equivalent gate) or construct in observation mode "
                "(production_enabled=False)"
            )
        self._protocol = protocol
        self._action_gate_check = action_gate_check
        self._production_enabled = production_enabled

    @property
    def protocol(self) -> EffectProtocol:
        """Expose the single owned protocol for health checks and shutdown."""

        return self._protocol

    def close(self) -> None:
        """Close the durable ledger owned by this adapter.

        The production resident creates exactly one adapter for the lifetime of
        the process.  Tests and bounded service constructors may close it
        explicitly without reaching through private protocol fields.
        """

        store = getattr(self._protocol, "_store", None)
        close = getattr(store, "close", None)
        if callable(close):
            close()

    # ── gate ────────────────────────────────────────────────────────────

    def _gate(self, target: DeliveryTarget) -> GateResult:
        """Return the current delivery gate verdict, default-deny.

        A missing gate is a typed denial (``BLOCKED_MISSING_GRANT``) and a
        gate that raises is ``ERROR`` — neither may ever admit a delivery.
        """
        if self._action_gate_check is None:
            return GateResult.BLOCKED_MISSING_GRANT
        try:
            return self._action_gate_check("delivery", target.target_key)
        except Exception as exc:
            LOGGER.error(
                "Delivery action gate check raised for %s: %s: %s",
                target.target_key,
                type(exc).__name__,
                exc,
            )
            return GateResult.ERROR

    # ── GLEK ─────────────────────────────────────────────────────────────

    @staticmethod
    def _build_effect_identity(target: DeliveryTarget) -> GlobalEffectIdentity:
        return GlobalEffectIdentity(
            environment_id=f"delivery-{target.channel.value}",
            action_target=target.target_key,
            action_version="m10",
            effect_family="delivery",
            provider_target=f"delivery:{target.channel.value}",
            canonical_request_identity=target.target_key,
            boundary_schema_hash="m10-delivery-v1",
        )

    @staticmethod
    def _build_identity_bundle(
        attempt_id: str,
    ) -> tuple[AttemptIdentity, AttemptProvenance, RuntimeAdapter, VersionSet, GrantRef]:
        identity = AttemptIdentity(
            workflow_id=f"del-{attempt_id}",
            run_id=f"del-{attempt_id}",
            graph_revision="m10",
            attempt_id=attempt_id,
        )
        provenance = AttemptProvenance(
            parent_attempt_id=None,
        )
        adapter = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="m10-delivery",
        )
        versions = VersionSet(code_version="m10")
        grant_ref = GrantRef(grant_id=f"del-grant-{attempt_id}")
        return identity, provenance, adapter, versions, grant_ref

    # ── dispatch ─────────────────────────────────────────────────────────

    def deliver(
        self,
        *,
        target: DeliveryTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
    ) -> DeliveryOutcome:
        """Deliver through the durable WBC protocol.

        Args:
            target: Stable delivery target identity.
            intent_payload: The delivery payload (message, metadata).
            apply_fn: The one transport callable for this logical effect.
            attempt_id: Explicit attempt id.

        Returns:
            DeliveryOutcome with the GLEK, outcome, and error.
        """
        if self._production_enabled:
            LOGGER.info("Production delivery effect selected for %s", target.target_key)

        verdict = self._gate(target)
        if not adapter_effect_authorized(verdict):
            verdict_label = getattr(verdict, "value", None) or str(verdict)
            return DeliveryOutcome(
                ok=False,
                channel=target.channel.value,
                action=target.action,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error=f"Action gate blocked: {verdict_label}",
                evidence={"gate_verdict": verdict_label},
            )

        ei = self._build_effect_identity(target)
        stable_idempotency_key = str(
            intent_payload.get("idempotency_key")
            or f"resident-delivery:{ei.global_logical_effect_key}"
        )
        aid = attempt_id or str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"arnold:resident-delivery:{ei.global_logical_effect_key}:{stable_idempotency_key}",
            )
        )
        ident, prov, adapter, versions, grant_ref = self._build_identity_bundle(aid)

        try:
            accepted = self._protocol.accepted_outcome_for_glek(
                ei.global_logical_effect_key
            )
            if accepted is not None and str(getattr(accepted, "outcome_kind", "")) in {
                OUTCOME_COMPLETED,
                OUTCOME_FAILED,
                OUTCOME_INDETERMINATE,
            }:
                evidence = dict(getattr(accepted, "outcome_payload", {}) or {})
                kind = str(getattr(accepted, "outcome_kind", OUTCOME_INDETERMINATE))
                return DeliveryOutcome(
                    ok=kind == OUTCOME_COMPLETED,
                    channel=target.channel.value,
                    action=target.action,
                    glek=ei.global_logical_effect_key,
                    outcome_kind=kind,
                    error=None if kind == OUTCOME_COMPLETED else "existing effect outcome is not completed",
                    evidence={**evidence, "adopted": True},
                    attempt_id=str(getattr(accepted, "attempt_id", aid)),
                )
            reservation = self._protocol.reserve_and_start(
                attempt_id=aid,
                effect_identity=ei,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )
            glek = reservation.global_logical_effect_key

            accepted = self._protocol.accepted_outcome_for_glek(glek)
            if accepted is not None and str(getattr(accepted, "outcome_kind", "")) in {
                OUTCOME_COMPLETED,
                OUTCOME_FAILED,
                OUTCOME_INDETERMINATE,
            }:
                evidence = dict(getattr(accepted, "outcome_payload", {}) or {})
                kind = str(getattr(accepted, "outcome_kind", OUTCOME_INDETERMINATE))
                return DeliveryOutcome(
                    ok=kind == OUTCOME_COMPLETED,
                    channel=target.channel.value,
                    action=target.action,
                    glek=glek,
                    outcome_kind=kind,
                    error=None if kind == OUTCOME_COMPLETED else "existing effect outcome is not completed",
                    evidence={**evidence, "adopted": True},
                    attempt_id=str(getattr(accepted, "attempt_id", aid)),
                )

            self._protocol.persist_intent(
                attempt_id=aid,
                glek=glek,
                intent_payload=intent_payload,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )

            provider_key = f"resident:{target.channel.value}:{target.action}"
            try:
                result = self._protocol.dispatch(
                    aid,
                    glek,
                    provider_id=provider_key,
                    apply_fn=lambda _key, payload: apply_fn(payload),
                    idempotency_key=stable_idempotency_key,
                    request_payload=dict(intent_payload),
                )
            except Exception as exc:
                reason = f"provider outcome unknown: {type(exc).__name__}: {exc}"
                self._protocol.accept_indeterminate(aid, glek, reason)
                return DeliveryOutcome(
                    ok=False,
                    channel=target.channel.value,
                    action=target.action,
                    glek=glek,
                    outcome_kind=OUTCOME_INDETERMINATE,
                    error=reason,
                    attempt_id=aid,
                )

            evidence = dict(result) if isinstance(result, dict) else {"result": str(result)[:500]}
            self._protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, evidence)
            return DeliveryOutcome(
                ok=True,
                channel=target.channel.value,
                action=target.action,
                glek=glek,
                outcome_kind=OUTCOME_COMPLETED,
                evidence=evidence,
                attempt_id=aid,
            )
        except Exception as exc:
            return DeliveryOutcome(
                ok=False,
                channel=target.channel.value,
                action=target.action,
                glek="",
                outcome_kind=OUTCOME_INDETERMINATE,
                error=f"Protocol error: {type(exc).__name__}: {exc}",
                attempt_id=aid,
            )

    async def deliver_async(
        self,
        *,
        target: DeliveryTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
    ) -> DeliveryOutcome:
        """Async provider variant with the same fail-closed effect protocol.

        The provider callback is awaited exactly once.  Any exception may
        have followed an accepted provider write, so it is durably recorded
        as INDETERMINATE and can never be automatically redriven.
        """
        verdict = self._gate(target)
        if not adapter_effect_authorized(verdict):
            verdict_label = getattr(verdict, "value", None) or str(verdict)
            return DeliveryOutcome(
                ok=False,
                channel=target.channel.value,
                action=target.action,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error=f"Action gate blocked: {verdict_label}",
                evidence={"gate_verdict": verdict_label},
            )

        ei = self._build_effect_identity(target)
        stable_idempotency_key = str(
            intent_payload.get("idempotency_key")
            or f"resident-delivery:{ei.global_logical_effect_key}"
        )
        aid = attempt_id or str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"arnold:resident-delivery:{ei.global_logical_effect_key}:{stable_idempotency_key}",
            )
        )
        ident, prov, adapter, versions, grant_ref = self._build_identity_bundle(aid)
        glek = ""
        try:
            accepted = self._protocol.accepted_outcome_for_glek(
                ei.global_logical_effect_key
            )
            if accepted is not None and str(getattr(accepted, "outcome_kind", "")) in {
                OUTCOME_COMPLETED,
                OUTCOME_FAILED,
                OUTCOME_INDETERMINATE,
            }:
                evidence = dict(getattr(accepted, "outcome_payload", {}) or {})
                kind = str(getattr(accepted, "outcome_kind", OUTCOME_INDETERMINATE))
                return DeliveryOutcome(
                    ok=kind == OUTCOME_COMPLETED,
                    channel=target.channel.value,
                    action=target.action,
                    glek=ei.global_logical_effect_key,
                    outcome_kind=kind,
                    error=None if kind == OUTCOME_COMPLETED else "existing effect outcome is not completed",
                    evidence={**evidence, "adopted": True},
                    attempt_id=str(getattr(accepted, "attempt_id", aid)),
                )
            reservation = self._protocol.reserve_and_start(
                attempt_id=aid,
                effect_identity=ei,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )
            glek = reservation.global_logical_effect_key
            accepted = self._protocol.accepted_outcome_for_glek(glek)
            if accepted is not None and str(getattr(accepted, "outcome_kind", "")) in {
                OUTCOME_COMPLETED,
                OUTCOME_FAILED,
                OUTCOME_INDETERMINATE,
            }:
                evidence = dict(getattr(accepted, "outcome_payload", {}) or {})
                kind = str(getattr(accepted, "outcome_kind", OUTCOME_INDETERMINATE))
                return DeliveryOutcome(
                    ok=kind == OUTCOME_COMPLETED,
                    channel=target.channel.value,
                    action=target.action,
                    glek=glek,
                    outcome_kind=kind,
                    error=None if kind == OUTCOME_COMPLETED else "existing effect outcome is not completed",
                    evidence={**evidence, "adopted": True},
                    attempt_id=str(getattr(accepted, "attempt_id", aid)),
                )
            self._protocol.persist_intent(
                attempt_id=aid,
                glek=glek,
                intent_payload=intent_payload,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )
            provider_key = f"resident:{target.channel.value}:{target.action}"
            self._protocol.verify_dispatch_eligible(aid, glek, provider_key)
            try:
                result = await apply_fn(stable_idempotency_key, dict(intent_payload))
            except Exception as exc:
                reason = f"provider outcome unknown: {type(exc).__name__}: {exc}"
                self._protocol.accept_indeterminate(aid, glek, reason)
                return DeliveryOutcome(
                    ok=False,
                    channel=target.channel.value,
                    action=target.action,
                    glek=glek,
                    outcome_kind=OUTCOME_INDETERMINATE,
                    error=reason,
                    attempt_id=aid,
                )
            evidence = dict(result) if isinstance(result, dict) else {"result": str(result)[:500]}
            self._protocol.accept_outcome(aid, glek, OUTCOME_COMPLETED, evidence)
            return DeliveryOutcome(
                ok=True,
                channel=target.channel.value,
                action=target.action,
                glek=glek,
                outcome_kind=OUTCOME_COMPLETED,
                evidence=evidence,
                attempt_id=aid,
            )
        except Exception as exc:
            return DeliveryOutcome(
                ok=False,
                channel=target.channel.value,
                action=target.action,
                glek=glek,
                outcome_kind=OUTCOME_INDETERMINATE,
                error=f"Protocol error: {type(exc).__name__}: {exc}",
                attempt_id=aid,
            )

    # ── Consumer-specific helpers ────────────────────────────────────────

    def deliver_discord_dm(
        self,
        *,
        user_id: str,
        payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
    ) -> DeliveryOutcome:
        """Step 13G2: route discord_dm.py outbound seam.

        Args:
            user_id: Discord user ID (parent resource).
            payload: The DM payload to render and send.
            apply_fn: Fake transport callable.
            attempt_id: Explicit attempt id.
        """
        target = DeliveryTarget(
            channel=DeliveryChannel.DISCORD_DM,
            parent_id=user_id,
            target_id=user_id,
            action="send_dm",
        )
        return self.deliver(
            target=target,
            intent_payload=payload,
            apply_fn=apply_fn,
            attempt_id=attempt_id,
        )

    def deliver_agentbox(
        self,
        *,
        operation_id: str,
        payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
    ) -> DeliveryOutcome:
        """Step 13G2: route agentbox_adapter.py outbound seam.

        Args:
            operation_id: AgentBox operation ID (parent resource).
            payload: The notification payload.
            apply_fn: Fake transport callable.
            attempt_id: Explicit attempt id.
        """
        target = DeliveryTarget(
            channel=DeliveryChannel.AGENTBOX,
            parent_id=operation_id,
            target_id=operation_id,
            action="notify",
        )
        return self.deliver(
            target=target,
            intent_payload=payload,
            apply_fn=apply_fn,
            attempt_id=attempt_id,
        )


def current_delivery_gate_check(
    allow: Callable[[], bool],
) -> Callable[[ActionBoundaryType, str], GateResult]:
    """Build an explicit delivery gate whose verdict is re-read on every call.

    The predicate *allow* is evaluated at dispatch time, so the verdict tracks
    the current configuration instead of a construction-time snapshot.  Only a
    currently-true predicate yields ``AUTHORIZED``; anything else is the typed
    ``BLOCKED_MISSING_GRANT`` denial, which the adapter honors before any
    protocol reservation or provider contact.
    """

    def gate_check(_family: ActionBoundaryType, _key: str) -> GateResult:
        if allow():
            return GateResult.AUTHORIZED
        return GateResult.BLOCKED_MISSING_GRANT

    return gate_check


def open_resident_delivery_effects(
    state_root: str | Path,
    *,
    production_enabled: bool = True,
    action_gate_check: Optional[
        Callable[[ActionBoundaryType, str], GateResult]
    ] = None,
) -> DeliveryEffects:
    """Open the canonical resident notification effect owner.

    The SQLite ledger and its transactional outbox deliberately share one
    database and one connection.  Reopening this factory after a resident
    restart therefore adopts the accepted GLEK outcome instead of dispatching
    the provider again.

    Production delivery requires an installed current gate.  Missing wiring
    (``action_gate_check=None``) is a construction error: the factory raises
    :class:`ResidentDeliveryGateError` before creating the state directory,
    SQLite ledger, or protocol, so a missing gate can never initialize durable
    state.  Production constructors should pass
    :func:`current_delivery_gate_check` (or an equivalent explicit gate) so an
    ``AUTHORIZED`` verdict reflects current policy.  Observation-only
    constructors (``production_enabled=False``) may omit the gate.
    """
    if production_enabled and action_gate_check is None:
        raise ResidentDeliveryGateError(
            "open_resident_delivery_effects refuses production construction "
            "without an explicit action_gate_check; pass "
            "current_delivery_gate_check (or an equivalent gate) or open in "
            "observation mode (production_enabled=False)"
        )

    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.ledger_outbox import SqliteLedgerOutbox

    root = Path(state_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    store = SqliteAttemptLedgerStore(root / "delivery-effects.sqlite3")
    outbox = SqliteLedgerOutbox(store)
    return DeliveryEffects(
        EffectProtocol(store, outbox),
        action_gate_check=action_gate_check,
        production_enabled=production_enabled,
    )


__all__ = [
    "DeliveryChannel",
    "DeliveryTarget",
    "DeliveryOutcome",
    "DeliveryEffects",
    "ResidentDeliveryGateError",
    "current_delivery_gate_check",
    "open_resident_delivery_effects",
]
