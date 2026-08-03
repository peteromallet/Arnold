"""Steps 13G1-13G2: Resident delivery effects adapter.

Step 13G1: Create the adapter over the WBC protocol with stable
parent/target/channel global-effect keys and durable
reserve/start/intent/global-reservation contracts.

Step 13G2: Route outbound seams in ``discord_dm.py`` and
``agentbox_adapter.py`` through the delivery effects adapter while
keeping real Discord action-off (SD3).

The adapter introduces no new ledger — it wraps the single durable
:class:`EffectProtocol`.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
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

from arnold_pipelines.megaplan.custody.action_gate import (
    ActionFamily,
    ActionGateVerdict,
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


class DeliveryEffects:
    """Resident delivery adapter over the WBC protocol.

    Step 13G1: thin adapter with stable parent/target/channel GLEKs.
    Step 13G2: routes discord_dm and agentbox_adapter outbound seams.

    Real Discord is action-off in M10 (SD3).  The *apply_fn* must be
    a fake transport that does not call the live Discord API.
    """

    def __init__(
        self,
        protocol: EffectProtocol,
        *,
        action_gate_check: Optional[
            Callable[[ActionFamily, str], ActionGateVerdict]
        ] = None,
        production_enabled: bool = False,
    ) -> None:
        self._protocol = protocol
        self._action_gate_check = action_gate_check
        self._production_enabled = production_enabled

    # ── gate ────────────────────────────────────────────────────────────

    def _gate(self, target: DeliveryTarget) -> ActionGateVerdict:
        if self._action_gate_check is None:
            return ActionGateVerdict.SHADOW_AUTHORIZED
        return self._action_gate_check(ActionFamily.EFFECT, target.target_key)

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
            apply_fn: Transport callable — MUST be fake in M10.
            attempt_id: Explicit attempt id.

        Returns:
            DeliveryOutcome with the GLEK, outcome, and error.
        """
        if self._production_enabled:
            LOGGER.warning(
                "Production delivery dispatch attempted for %s — "
                "production is action-off in M10",
                target.target_key,
            )

        verdict = self._gate(target)
        if verdict not in (
            ActionGateVerdict.AUTHORIZED,
            ActionGateVerdict.SHADOW_AUTHORIZED,
        ):
            return DeliveryOutcome(
                ok=False,
                channel=target.channel.value,
                action=target.action,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error=f"Action gate blocked: {verdict.value}",
                evidence={"gate_verdict": verdict.value},
            )

        aid = attempt_id or str(uuid.uuid4())
        ei = self._build_effect_identity(target)
        ident, prov, adapter, versions, grant_ref = self._build_identity_bundle(aid)

        try:
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
            idempotency_key = str(
                intent_payload.get("idempotency_key")
                or f"resident-delivery:{glek}"
            )
            try:
                result = self._protocol.dispatch(
                    aid,
                    glek,
                    provider_id=provider_key,
                    apply_fn=lambda _key, payload: apply_fn(payload),
                    idempotency_key=idempotency_key,
                    request_payload=dict(intent_payload),
                )
            except Exception as exc:
                self._protocol.accept_outcome(
                    aid, glek, OUTCOME_FAILED,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                return DeliveryOutcome(
                    ok=False,
                    channel=target.channel.value,
                    action=target.action,
                    glek=glek,
                    outcome_kind=OUTCOME_FAILED,
                    error=str(exc),
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


__all__ = [
    "DeliveryChannel",
    "DeliveryTarget",
    "DeliveryOutcome",
    "DeliveryEffects",
]
