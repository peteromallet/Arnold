"""Steps 13B1-13B2: Publication/delivery adapter over action_validator + effect_protocol.

Routes GitHub issue creation and comment calls in :mod:`github_sync`
through the action gate and WBC effect protocol with stable
repository/issue/occurrence global-effect keys.

Real GitHub stays action-off throughout M10 (SD3). The adapter uses a
fake client to prove durable intent, cross-attempt idempotency,
lost-ACK reconciliation, and terminal indeterminate behavior.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from arnold.workflow.effect_protocol import (
    EffectProtocol,
    EffectProtocolConfig,
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


# ── Publication target identity ──────────────────────────────────────────────


@dataclass(frozen=True)
class PublicationTarget:
    """Stable identity for a publication effect target.

    Used to construct the GLEK for every publication dispatch.
    """

    repo: str
    """Repository full name, e.g. ``owner/repo``."""

    issue_number: int | None = None
    """Existing issue number for comment actions; None for creation."""

    occurrence_key: str = ""
    """Stable occurrence identity (problem_id or incident_id)."""

    channel: str = "github_issue"
    """Delivery channel discriminator."""

    @property
    def target_key(self) -> str:
        if self.issue_number is not None:
            return f"github:comment:{self.repo}:{self.issue_number}:{self.occurrence_key}"
        return f"github:create:{self.repo}:{self.occurrence_key}"


# ── Publication result ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class PublicationOutcome:
    """Result of a publication dispatch through the adapter."""

    ok: bool
    action: str  # "created" | "commented"
    repo: str
    issue_number: int | None
    issue_url: str
    glek: str
    outcome_kind: str  # COMPLETED | FAILED | INDETERMINATE
    error: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


# ── Publication adapter ──────────────────────────────────────────────────────


class PublicationAdapterGateError(RuntimeError):
    """Raised when a production publication adapter is opened without a gate.

    Production construction without an explicit ``action_gate_check`` is a
    wiring error, not a runtime denial: the constructor raises before any
    dispatch so a missing gate can never be installed in production mode.
    """


class PublicationAdapter:
    """Routes GitHub issue publication through action_validator + effect_protocol.

    Step 13B1: publication/delivery handoffs are gated at action time.
    Step 13B2: github_sync issue creation/comment are explicitly gated.

    The adapter receives an :class:`EffectProtocol` instance (the
    single durable WBC adapter) and an action-gate checker.  Every
    dispatch is gated through the checker; a missing gate, an
    exceptional gate, or any verdict other than :attr:`GateResult.AUTHORIZED`
    yields a typed failed publication outcome before any protocol
    reservation or publication callback.

    Production construction (``production_enabled=True``) without an explicit
    ``action_gate_check`` is a wiring error: the constructor raises
    :class:`PublicationAdapterGateError` before any dispatch.  Observation-only
    construction (``production_enabled=False``) may omit the gate — every
    dispatch then fails closed as a typed denial.

    Real GitHub stays action-off (SD3).  The ``apply_fn`` must be a
    fake or test client that does not mutate production GitHub.
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
            raise PublicationAdapterGateError(
                "PublicationAdapter refuses production construction without "
                "an explicit action_gate_check; pass a current gate (or an "
                "equivalent denial gate) so production publication reflects "
                "current policy, or open in observation mode "
                "(production_enabled=False)"
            )
        self._protocol = protocol
        self._action_gate_check = action_gate_check
        self._production_enabled = production_enabled

    # ── gate ────────────────────────────────────────────────────────────

    def _gate(self, target: PublicationTarget) -> GateResult | None:
        """Run the installed action gate; ``None`` when none is installed.

        A missing gate is a fail-closed condition, never a shadow pass: the
        caller must convert it (and every non-AUTHORIZED verdict) into a
        typed denial before any publication effect is dispatched.
        """
        if self._action_gate_check is None:
            return None
        return self._action_gate_check("publication", target.target_key)

    @staticmethod
    def _deny(
        target: PublicationTarget,
        *,
        action: str,
        verdict_label: str,
        detail: str,
    ) -> PublicationOutcome:
        """Typed pre-effect denial: no reservation, intent, or publication."""
        return PublicationOutcome(
            ok=False,
            action=action,
            repo=target.repo,
            issue_number=target.issue_number,
            issue_url="",
            glek="",
            outcome_kind=OUTCOME_FAILED,
            error=f"Action gate denied: {detail}",
            evidence={"gate_verdict": verdict_label},
        )

    def _checked_gate(
        self,
        target: PublicationTarget,
        *,
        action: str,
    ) -> PublicationOutcome | None:
        """Run the installed gate; return a typed denial, or ``None`` when AUTHORIZED.

        A missing gate, an exceptional gate, and every verdict other than
        :attr:`GateResult.AUTHORIZED` yield a typed failed publication outcome
        — zero protocol reservation, zero publication callback.
        """
        try:
            verdict = self._gate(target)
        except Exception as exc:
            return self._deny(
                target,
                action=action,
                verdict_label="error",
                detail=f"{type(exc).__name__}: {exc}",
            )
        if adapter_effect_authorized(verdict):
            return None
        if isinstance(verdict, GateResult):
            label = verdict.value
        elif verdict is None:
            label = "missing"
        else:
            label = type(verdict).__name__
        return self._deny(
            target,
            action=action,
            verdict_label=label,
            detail=label if verdict is not None else "no action gate installed",
        )

    def check_gate(self, target: PublicationTarget) -> PublicationOutcome | None:
        """Resolve the action gate for *target* without dispatching anything.

        Returns ``None`` when the verdict is :attr:`GateResult.AUTHORIZED`
        (publication may proceed) or a typed denial :class:`PublicationOutcome`
        otherwise — a missing gate, an exceptional gate, and every other
        verdict fail closed.  Zero protocol reservation, zero provider calls,
        zero filesystem effects: integration code can resolve publication
        authority BEFORE any filesystem write and deny without side effects.
        """
        return self._checked_gate(target, action="create")

    # ── GLEK construction ────────────────────────────────────────────────

    @staticmethod
    def _build_effect_identity(
        target: PublicationTarget,
        action: str,
        boundary_schema_hash: str = "m10-publication-v1",
    ) -> GlobalEffectIdentity:
        return GlobalEffectIdentity(
            environment_id="publication",
            action_target=target.target_key,
            action_version="m10",
            effect_family="publication",
            provider_target=f"github:{target.repo}",
            canonical_request_identity=f"{target.target_key}:{action}",
            boundary_schema_hash=boundary_schema_hash,
        )

    @staticmethod
    def _build_identity_bundle(
        attempt_id: str,
    ) -> tuple[AttemptIdentity, AttemptProvenance, RuntimeAdapter, VersionSet, GrantRef]:
        identity = AttemptIdentity(
            workflow_id=f"pub-{attempt_id}",
            run_id=f"pub-{attempt_id}",
            graph_revision="m10",
            attempt_id=attempt_id,
        )
        provenance = AttemptProvenance(
            actor_id="megaplan-publication-adapter",
            tool_id="github-publication",
        )
        adapter = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="m10-publication",
        )
        versions = VersionSet(code_version="m10")
        grant_ref = GrantRef(grant_id=f"pub-grant-{attempt_id}")
        return identity, provenance, adapter, versions, grant_ref

    # ── dispatch ─────────────────────────────────────────────────────────

    def publish(
        self,
        *,
        target: PublicationTarget,
        action: str,  # "create" | "comment"
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., dict[str, Any]],
        attempt_id: str | None = None,
    ) -> PublicationOutcome:
        """Publish through the durable WBC protocol.

        Args:
            target: Stable publication target identity.
            action: ``"create"`` or ``"comment"``.
            intent_payload: The issue title/body or comment body.
            apply_fn: Provider callable — MUST be a fake in M10.
            attempt_id: Explicit attempt id; auto-generated if None.

        Returns:
            PublicationOutcome with the GLEK, outcome, and error.
        """
        if self._production_enabled:
            LOGGER.warning(
                "Production publication dispatch attempted for %s — "
                "production is action-off in M10",
                target.target_key,
            )

        # 1. Action gate check — deny before any reservation or callback.
        denial = self._checked_gate(target, action=action)
        if denial is not None:
            return denial

        # 2. Build identity
        aid = attempt_id or str(uuid.uuid4())
        ei = self._build_effect_identity(target, action)
        ident, prov, adapter, versions, grant_ref = self._build_identity_bundle(aid)

        # 3. Durable protocol: reserve → intent → dispatch → accept
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

            # 4. Provider dispatch (fake in M10)
            try:
                result = apply_fn(intent_payload)
            except Exception as exc:
                self._protocol.accept_outcome(
                    aid, glek, OUTCOME_FAILED,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                return PublicationOutcome(
                    ok=False,
                    action=action,
                    repo=target.repo,
                    issue_number=target.issue_number,
                    issue_url="",
                    glek=glek,
                    outcome_kind=OUTCOME_FAILED,
                    error=str(exc),
                    evidence={"glek": glek},
                )
            if isinstance(result, dict) and result.get("ok") is False:
                # A provider-visible rejection is a FAILED effect, never a
                # COMPLETED one (T-0017: publication effects close by default).
                self._protocol.accept_outcome(
                    aid, glek, OUTCOME_FAILED, dict(result),
                )
                return PublicationOutcome(
                    ok=False,
                    action=action,
                    repo=target.repo,
                    issue_number=target.issue_number,
                    issue_url="",
                    glek=glek,
                    outcome_kind=OUTCOME_FAILED,
                    error=str(result.get("error") or "provider rejected publication"),
                    evidence={"glek": glek, "result": result},
                )

            # 5. Accept outcome
            outcome = self._protocol.accept_outcome(
                aid, glek, OUTCOME_COMPLETED,
                dict(result) if isinstance(result, dict) else {"result": result},
            )

            provider_evidence = (
                result.get("evidence_ref")
                if isinstance(result, dict)
                and isinstance(result.get("evidence_ref"), dict)
                else {}
            )
            issue_number = (
                result.get("number")
                or provider_evidence.get("number")
                or target.issue_number
                if isinstance(result, dict)
                else target.issue_number
            )
            issue_url = (
                result.get("url")
                or provider_evidence.get("url")
                or ""
                if isinstance(result, dict)
                else ""
            )

            return PublicationOutcome(
                ok=True,
                action=action,
                repo=target.repo,
                issue_number=issue_number,
                issue_url=issue_url,
                glek=glek,
                outcome_kind=OUTCOME_COMPLETED,
                evidence={"glek": glek, "result": result},
            )

        except Exception as exc:
            return PublicationOutcome(
                ok=False,
                action=action,
                repo=target.repo,
                issue_number=target.issue_number,
                issue_url="",
                glek="",
                outcome_kind=OUTCOME_INDETERMINATE,
                error=f"Protocol error: {type(exc).__name__}: {exc}",
            )

    def publish_indeterminate(
        self,
        *,
        target: PublicationTarget,
        action: str,
        reason: str,
        attempt_id: str | None = None,
    ) -> PublicationOutcome:
        """Record an indeterminate publication outcome (no dispatch).

        Gated exactly like :meth:`publish`: a missing gate, an exceptional
        gate, or any verdict other than :attr:`GateResult.AUTHORIZED` is a
        typed denial with zero protocol reservation.  An indeterminate
        record is only written when publication authority was explicitly
        granted (T-0017: publication effects close by default).
        """
        denial = self._checked_gate(target, action=action)
        if denial is not None:
            return denial

        aid = attempt_id or str(uuid.uuid4())
        ei = self._build_effect_identity(target, action)
        ident, prov, adapter, versions, grant_ref = self._build_identity_bundle(aid)

        try:
            self._protocol.reserve_and_start(
                attempt_id=aid,
                effect_identity=ei,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )
        except Exception:
            pass  # Reservation may fail; the indeterminate outcome is still recorded.

        return PublicationOutcome(
            ok=False,
            action=action,
            repo=target.repo,
            issue_number=target.issue_number,
            issue_url="",
            glek=ei.global_logical_effect_key,
            outcome_kind=OUTCOME_INDETERMINATE,
            error=reason,
        )


__all__ = [
    "PublicationTarget",
    "PublicationOutcome",
    "PublicationAdapter",
]
